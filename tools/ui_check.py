#!/usr/bin/env python3
"""Drive the real UI (the React app, port 10000) in headless Chromium through every
feature a teammate uses, like a person would. Screenshots per step.

  python3 tools/ui_check.py                                  # http://localhost:10000
  python3 tools/ui_check.py https://hallie-sabulous-nicholle.ngrok-free.dev
  SHOTS=/some/dir python3 tools/ui_check.py                   # where screenshots go

Never sends an answer to DRES: Submit is only clicked while DRES has NO active
evaluation (the central service answers 409 "nothing submitted"); with the confirm
toggle on, the confirm dialog is dismissed. Needs Python Playwright + Chromium.
Exit code = number of FAILs.
"""
import json, os, re, sys, tempfile, urllib.request
from playwright.sync_api import sync_playwright

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:10000").rstrip("/")
SHOTS = os.environ.get("SHOTS", os.path.join(tempfile.gettempdir(), "aic_ui_check"))
SAMPLE_JPG = "/mnt/e/workspace/AIC_2026/batch1/work/keyframes/Keyframes_M05/keyframes/M05_V001/00042.jpg"
os.makedirs(SHOTS, exist_ok=True)
results, console_errors, bad_responses = [], [], []

THUMBS_JS = """() => [...document.images].filter(i => i.src.includes('/media/frames/'))
  .map(i => ({src: i.src, ok: i.complete && i.naturalWidth > 0}))"""
RM_THUMBS_JS = """() => [...document.images].filter(i => i.src.includes('/result_manager/send_img'))
  .map(i => ({src: i.src, ok: i.complete && i.naturalWidth > 0}))"""


def wait_scope(pg):
    """Ticking a batch reloads the video list; searching before it settles uses the old scope."""
    pg.wait_for_function("() => !document.body.innerText.includes('Loading batch scope')", timeout=60000)


def check(name, ok, detail=""):
    results.append(("PASS" if ok else "FAIL") if ok is not None else "SKIP")
    print(f"  {results[-1]:4s}  {name}{'  -- ' + str(detail) if detail else ''}", flush=True)


def shot(pg, name):
    try: pg.screenshot(path=os.path.join(SHOTS, f"{len(results):02d}_{name}.png"))
    except Exception: pass


def videos_of(thumbs):
    # /media/frames/{batch}/frames/{split}/Keyframes_{prefix}/keyframes/{video}/{frame}.avif
    return [t["src"].split("/keyframes/")[-1].split("/")[0] for t in thumbs]


def wait_thumbs(pg, n=10, timeout=30000):
    pg.wait_for_function("(n) => { const a=[...document.images].filter(i=>i.src.includes('/media/frames/'));"
                         " return a.length>0 && a.slice(0,n).every(i=>i.complete) }", arg=n, timeout=timeout)
    return pg.evaluate(THUMBS_JS)


def run_search(pg):
    with pg.expect_response(lambda r: "/hub/search" in r.url, timeout=120000) as ri:
        pg.get_by_role("button", name="Search", exact=True).click()
    return ri.value.status


def step(name, fn, pg):
    try:
        fn()
    except Exception as e:
        check(name, False, f"{type(e).__name__}: {str(e).splitlines()[0][:140]}")
    shot(pg, re.sub(r"\W+", "_", name)[:40])


def main():
    dres = json.load(urllib.request.urlopen(urllib.request.Request(
        BASE + "/submission/get_session_and_eval", headers={"ngrok-skip-browser-warning": "1"}), timeout=30))
    no_active_eval = dres.get("status") == 200 and not (dres.get("data") or {}).get("eval_id")
    print(f"target: {BASE}   screenshots: {SHOTS}")
    with sync_playwright() as p:
        br = p.chromium.launch()
        ctx = br.new_context(viewport={"width": 1600, "height": 1000}, accept_downloads=True,
                             extra_http_headers={"ngrok-skip-browser-warning": "1"})
        pg = ctx.new_page()
        pg.on("console", lambda m: console_errors.append(m.text[:160]) if m.type == "error" else None)
        pg.on("response", lambda r: bad_responses.append(f"{r.status} {r.url[len(BASE):][:90]}")
              if r.status >= 400 and not (r.status == 409 and "/submission/" in r.url) else None)
        dialogs = []
        pg.on("dialog", lambda d: (dialogs.append(d.message), d.dismiss()))

        # 1. page + DRES status
        def s1():
            pg.goto(BASE + "/", wait_until="networkidle", timeout=60000)
            check("page loads", pg.get_by_text("Query", exact=True).count() > 0)
            badge = pg.get_by_text(re.compile(r"^DRES")).first.inner_text()
            check("DRES badge + status toast", "DRES" in badge, f"badge '{badge}'")
        step("page loads", s1, pg)

        q = lambda: pg.get_by_placeholder(re.compile("Describe the frame"))

        # 2. default text search (what a teammate gets without touching filters)
        def s2():
            q().fill("a news anchor in a studio")
            st = run_search(pg); th = wait_thumbs(pg)
            pref = sorted({v[0] for v in videos_of(th)})
            check("text search: results + thumbnails load", st == 200 and all(t["ok"] for t in th[:10]),
                  f"HTTP {st}, {sum(t['ok'] for t in th)}/{len(th)} thumbs, series {pref}")
        step("text search default", s2, pg)

        # 3. search scope. Precedence in the UI: picked videos > ticked content
        # subsets > batch checkboxes (batches only apply when no subset is ticked).
        def s3():
            q().fill("a news anchor in a studio"); run_search(pg); th = wait_thumbs(pg)
            check("default scope includes the 2026 news (M)", "M" in {v[0] for v in videos_of(th)},
                  sorted({v[0] for v in videos_of(th)}))
            pg.get_by_label("Cycling").check(); pg.get_by_label("Traffic CCTV").check()
            q().fill("a bus turning at an intersection"); run_search(pg); th = wait_thumbs(pg)
            check("Traffic CCTV (N) reachable", "N" in {v[0] for v in videos_of(th)}, sorted({v[0] for v in videos_of(th)}))
            q().fill("cyclists racing on a road"); run_search(pg); th = wait_thumbs(pg)
            check("Cycling (S) reachable", "S" in {v[0] for v in videos_of(th)}, sorted({v[0] for v in videos_of(th)}))
            q().fill("a news anchor in a studio")
        step("search scope", s3, pg)

        # 4. pick one video in Included videos
        def s4():
            # the picker lists only the ticked batches -- Batch 1 (M/N/S) is off by default
            pg.get_by_label("Batch 1").check(); wait_scope(pg)
            pg.get_by_placeholder("Search videos...").fill("M05_V001")
            pg.locator("label", has_text=re.compile(r"^\s*M05_V001\s*$")).first.click()
            run_search(pg); th = wait_thumbs(pg)
            vids = set(videos_of(th))
            check("included-videos filter (one video)", vids == {"M05_V001"}, f"{sorted(vids)[:4]}")
        step("video filter", s4, pg)

        # 5. transcript filter (still scoped to M05_V001)
        def s5():
            box = pg.get_by_placeholder(re.compile("Transcript"))
            box.fill("thông tin")
            st = run_search(pg)
            th = pg.evaluate(THUMBS_JS)
            check("transcript (S2T) filter", st == 200, f"{len(th)} results for 'thông tin' in M05_V001")
            box.fill("")
        step("transcript filter", s5, pg)

        # 6. Browse the selected video (Browse tab)
        def s6():
            pg.get_by_role("tab", name="Browse", exact=True).click()
            st = run_search(pg); th = wait_thumbs(pg)
            vids = set(videos_of(th))
            check("Browse a video", st == 200 and vids == {"M05_V001"} and len(th) > 10, f"{len(th)} frames of {sorted(vids)}")
            # un-pick the video again
            pg.locator("label", has_text=re.compile(r"^\s*M05_V001\s*$")).first.click()
            pg.get_by_placeholder("Search videos...").fill("")
            pg.get_by_role("tab", name="Text", exact=True).click()
        step("browse", s6, pg)

        # 7. Image search: a real M keyframe must come back first
        def s7():
            pg.get_by_role("tab", name="Image", exact=True).click()
            pg.locator("input[type=file]").first.set_input_files(SAMPLE_JPG)
            st = run_search(pg); th = wait_thumbs(pg)
            top = videos_of(th)[:3]
            check("image search (upload)", st == 200 and top and top[0] == "M05_V001", f"top {top}")
        step("image search", s7, pg)

        # 8. Temporal + "Use as TRAKE"
        def s8():
            pg.get_by_role("tab", name="Temporal", exact=True).click()
            pg.get_by_placeholder("Event 1").fill("a news anchor in a studio")
            pg.get_by_role("button", name=re.compile("Add event")).click()
            pg.get_by_placeholder("Event 2").fill("a map on the screen")
            st = run_search(pg); wait_thumbs(pg)
            chains = pg.locator('[title="Load this chain as the TRAKE sequence in the submission bar"]')
            n = chains.count()
            check("temporal search (chain rows)", st == 200 and n > 0, f"{n} chains")
            chains.first.click()
            bar = pg.get_by_text(re.compile(r"^[A-Z]\d+_V\d+: \d+")).first.inner_text()
            enabled = pg.get_by_role("button", name="Submit TRAKE").is_enabled()
            check("Use as TRAKE -> submission bar", enabled and ":" in bar, bar)
        step("temporal", s8, pg)

        # 9. back to text; KIS mode
        def s9():
            pg.get_by_role("tab", name="Text", exact=True).click()
            pg.get_by_role("button", name="KIS", exact=True).click()
            q().fill("a bus turning at an intersection")
            run_search(pg); th = wait_thumbs(pg)
            check("text search again (KIS mode)", len(th) > 0, f"{len(th)} results")
        step("text kis", s9, pg)

        # 10. frame viewer: video plays at the frame, neighbouring frames
        def s10():
            pg.locator("img[src*='/media/frames/']").first.click()
            dlg = pg.locator("dialog[open]")
            dlg.wait_for(timeout=10000)
            pg.wait_for_function("() => { const v=document.querySelector('dialog[open] video'); return v && v.readyState>=1 }",
                                 timeout=30000)
            info = pg.evaluate("() => { const v=document.querySelector('dialog[open] video'); "
                               "return {t: v.currentTime, d: v.duration, src: v.currentSrc.slice(-40)} }")
            neigh = dlg.get_by_text("Neighbouring frames").count() > 0
            check("frame viewer: video loads + seeks, neighbours", info["d"] > 0 and neigh,
                  f"t={info['t']:.1f}s of {info['d']:.0f}s {info['src']}")
            dlg.get_by_role("button", name="Close").first.click()
        step("frame viewer", s10, pg)

        # 11. thumbnail actions: exclude shot, browse shot, similar frames
        def s11():
            before = videos_of(pg.evaluate(THUMBS_JS))[:1]
            card = pg.locator("img[src*='/media/frames/']").first
            card.hover()
            pg.locator('[aria-label="Exclude this shot from results"]').first.click(force=True)
            pg.wait_for_timeout(1500)
            ex = pg.locator('[aria-label="Un-exclude"]').count()
            check("exclude shot", ex >= 1, f"excluded list has {ex}")
            if ex: pg.locator('[aria-label="Un-exclude"]').first.click()
            card = pg.locator("img[src*='/media/frames/']").first
            card.hover()
            with pg.expect_response(lambda r: "/hub/search" in r.url, timeout=60000) as ri:
                pg.locator('[title="Browse this whole shot"]').first.click(force=True)
            th = wait_thumbs(pg)
            check("browse this shot", ri.value.status == 200 and len(th) > 0, f"{len(th)} frames of {sorted(set(videos_of(th)))[:2]}")
            card = pg.locator("img[src*='/media/frames/']").first
            card.hover()
            with pg.expect_response(lambda r: "/hub/search" in r.url, timeout=60000) as ri:
                pg.locator('[title="Find similar frames (duplicates of this frame)"]').first.click(force=True)
            check("find similar frames", ri.value.status == 200, f"HTTP {ri.value.status}")
        step("thumbnail actions", s11, pg)

        # 12. DRES submit paths -- only while no evaluation is active. The UI then
        # refuses client-side ("no ACTIVE evaluation") and sends nothing.
        def s12():
            if not no_active_eval:
                check("submit KIS / Q&A / confirm", None, "an evaluation is ACTIVE -- not clicking Submit"); return
            sent = []
            pg.on("request", lambda r: sent.append(r.url) if "/submission/submit" in r.url else None)
            q().fill("a bus turning at an intersection"); run_search(pg); wait_thumbs(pg)
            pg.locator("img[src*='/media/frames/']").first.hover()
            pg.locator('[title="Submit this frame to DRES (KIS)"]').first.click(force=True)
            pg.wait_for_timeout(1500)
            msg = pg.get_by_text(re.compile("no ACTIVE evaluation")).count()
            check("one-click KIS submit (no active eval: refused, nothing sent)", msg > 0 and not sent, f"sent={len(sent)}")
            pg.get_by_role("button", name="Q&A", exact=True).click()
            pg.get_by_placeholder("Q&A answer…").fill("5")
            pg.locator("img[src*='/media/frames/']").first.hover()
            pg.locator('[title="Submit this frame to DRES (QA)"]').first.click(force=True)
            pg.wait_for_timeout(1500)
            check("one-click Q&A submit (no active eval: refused, nothing sent)", not sent, f"sent={len(sent)}")
            pg.get_by_role("button", name="KIS", exact=True).click()
            pg.locator('[title="Confirm each submit before sending to DRES"] input').check()
            pg.locator("img[src*='/media/frames/']").first.hover()
            pg.locator('[title="Submit this frame to DRES (KIS)"]').first.click(force=True)
            pg.wait_for_timeout(1000)
            check("confirm toggle asks first (dismissed -> nothing sent)", dialogs and not sent,
                  f"dialog: {dialogs[-1][:40] if dialogs else None}")
            pg.locator('[title="Confirm each submit before sending to DRES"] input').uncheck()
        step("submission", s12, pg)

        # 13. CSV download + Result Manager import
        def s13():
            with pg.expect_download(timeout=60000) as di:
                pg.get_by_role("button", name=re.compile("Download CSV")).click()
            path = di.value.path()
            rows = [l for l in open(path, encoding="utf-8").read().splitlines() if l.strip()]
            check("Download CSV", len(rows) > 0, f"{len(rows)} rows, e.g. {rows[0][:30] if rows else ''}")
            pg.get_by_role("link", name="Result Manager").click()
            pg.locator('input[type=file][accept=".csv,text/csv"]').set_input_files(path)
            pg.wait_for_function("() => { const a=[...document.images].filter(i=>i.src.includes('/result_manager/send_img'));"
                                 " return a.length>0 && a.slice(0,5).every(i=>i.complete) }", timeout=60000)
            th = pg.evaluate(RM_THUMBS_JS)
            check("Result Manager: load CSV, rows + thumbnails", len(th) > 0 and all(t["ok"] for t in th[:5]),
                  f"{len(th)} rows, {sum(t['ok'] for t in th[:5])}/5 first thumbs")
            pg.get_by_role("link", name="Search Page").click()
        step("csv + result manager", s13, pg)

        # 14. Settings dialog
        def s14():
            pg.get_by_role("button", name=re.compile("Settings")).click()
            ok = pg.locator("dialog[open]").get_by_text("Settings").count() > 0
            check("Settings panel", ok)
            pg.locator("dialog[open]").get_by_role("button", name="Close").first.click()
        step("settings", s14, pg)

        br.close()
    real_errors = [e for e in console_errors if "409" not in e]
    check("no console errors", not real_errors, real_errors[:3])
    check("no failed requests (4xx/5xx other than the expected 409s)", not bad_responses, bad_responses[:4])
    fails = results.count("FAIL")
    print(f"\n{results.count('PASS')} pass, {fails} fail, {results.count('SKIP')} skip   (screenshots: {SHOTS})")
    sys.exit(fails)


if __name__ == "__main__":
    main()
