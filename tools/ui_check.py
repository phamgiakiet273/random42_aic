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
SAMPLE_JPG = "/mnt/e/workspace/AIC_2026/batch1/work/keyframes/Keyframes_M05/keyframes/M05_V001/01698.jpg"  # frame_class 3: shown under the default class filter (2, 3)
os.makedirs(SHOTS, exist_ok=True)
results, console_errors, bad_responses = [], [], []

THUMBS_JS = """() => [...document.images].filter(i => i.src.includes('/media/frames/'))
  .map(i => ({src: i.src, ok: i.complete && i.naturalWidth > 0}))"""
RM_THUMBS_JS = """() => [...document.images].filter(i => i.src.includes('/result_manager/send_img'))
  .map(i => ({src: i.src, ok: i.complete && i.naturalWidth > 0}))"""


def wait_scope(pg):
    """Ticking a batch reloads the video list; searching before it settles uses the old scope."""
    pg.wait_for_function("() => !document.querySelector('[aria-busy=true]')", timeout=60000)


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


def open_viewer(pg):
    """The frame viewer dialog, once its <video> has metadata (and the timeline has drawn)."""
    dlg = pg.locator("dialog[open]").filter(has=pg.locator("video"))
    dlg.wait_for(timeout=10000)
    pg.wait_for_function("() => { const v=document.querySelector('dialog[open] video'); return v && v.readyState>=1 }",
                         timeout=30000)
    pg.wait_for_timeout(1000)
    return dlg


def close_viewer(pg):
    pg.locator("dialog[open]").get_by_role("button", name="Close", exact=True).first.click()
    pg.wait_for_function("() => !document.querySelector('dialog[open] video')", timeout=10000)


def active_tab(dlg):
    tab = dlg.locator("[role=tab].tab-active")
    return re.sub(r"\s*\(\d+\)$", "", tab.inner_text().strip()) if tab.count() else None


def markers(pg):
    """TRAKE markers on the wavesurfer timeline (they live in its shadow DOM)."""
    return pg.locator('dialog[open] [part~="marker"]').count()


def _verdict(pg):
    """The last submit message: inside the open viewer (the page behind a modal is
    inert), else the store's toast (the one with a dismiss button)."""
    inside = pg.locator("dialog[open] [role=status]")
    return inside if pg.locator("dialog[open]").count() else pg.locator(".toast .alert:has(button.btn-ghost)")


def last_verdict(pg):
    el = _verdict(pg).locator("span").first
    return el.inner_text() if el.count() else None


def clear_verdict(pg):
    btn = _verdict(pg).locator("button").first
    if btn.count(): btn.click()


def step(name, fn, pg):
    try:
        fn()
    except Exception as e:
        lines = str(e).splitlines()
        why = [l.strip() for l in lines if re.search(r"intercepts|not enabled|not visible|not stable|resolved to", l)][-2:]
        check(name, False, f"{type(e).__name__}: {lines[0][:140]} {' | '.join(why)[:300]}")
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

        # 3b. content buttons: none / all / default (back to the catalog's defaults)
        def s3b():
            ticked = lambda: pg.evaluate("() => [...document.querySelectorAll('div.grid.grid-cols-2 label')]"
                                         ".filter(l => l.querySelector('input').checked).map(l => l.innerText.trim())")
            total = pg.locator("div.grid.grid-cols-2 label").count()
            before = ticked()  # the defaults + Cycling + Traffic CCTV from step 3
            btn = lambda name: pg.get_by_role("button", name=name, exact=True).click()
            btn("none"); none = ticked(); btn("all"); every = ticked(); btn("default"); default = ticked()
            check("content none / all / default", not none and len(every) == total
                  and set(default) == set(before) - {"Cycling", "Traffic CCTV"},
                  f"none {len(none)}, all {len(every)}/{total}, default {default}")
            pg.get_by_label("Cycling").check(); pg.get_by_label("Traffic CCTV").check()  # as later steps expect
        step("content buttons", s3b, pg)

        # 3c. translation (offline VinAI model in the util service): T rewrites the
        # Vietnamese query in English; English leaves T disabled; Auto Translate
        # translates before the search and the box shows what was searched
        def s3c():
            vi = re.compile("[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]", re.I)
            tbtn = pg.locator('button[title^="Translate Vietnamese"]')
            q().fill("Một chiếc xe buýt màu đỏ đang rẽ trái ở ngã tư")
            tbtn.click()
            pg.wait_for_function("() => !document.querySelector('textarea').value.includes('xe buýt')", timeout=30000)
            en = q().input_value()
            check("T translates the query to English in place", "bus" in en.lower() and not vi.search(en), en)
            check("T is disabled for English text", tbtn.is_disabled())
            pg.get_by_role("button", name=re.compile("Settings")).click()
            pg.get_by_label(re.compile("^Auto Translate")).check(); pg.keyboard.press("Escape")
            q().fill("Người bán hàng đang xếp sầu riêng lên sạp trái cây ở chợ")
            with pg.expect_request(lambda r: "/hub/search" in r.url, timeout=60000) as rq:
                pg.get_by_role("button", name="Search", exact=True).click()
            sent, box = rq.value.post_data or "", q().input_value()
            check("Auto Translate: searched in English, box shows it", "durian" in box.lower() and "durian" in sent.lower()
                  and "sầu riêng" not in sent, box)
            pg.get_by_role("button", name=re.compile("Settings")).click()
            pg.get_by_label(re.compile("^Auto Translate")).uncheck(); pg.keyboard.press("Escape")
        step("translate", s3c, pg)

        # 4. pick one video in Included videos
        def s4():
            # the picker lists only the ticked batches (Batch 1 = M/N/S, ticked by default)
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
            chains = pg.locator('[title="Open this chain on the TRAKE timeline (events pre-marked)"]')
            n = chains.count()
            check("temporal search (chain rows)", st == 200 and n > 0, f"{n} chains")
            chains.first.click()
            dlg = open_viewer(pg)
            events = dlg.locator("ol li").count()
            check("Use as TRAKE -> viewer, TRAKE tab, chain pre-marked on the timeline",
                  active_tab(dlg) == "TRAKE" and events >= 1 and markers(pg) == events,
                  f"tab {active_tab(dlg)!r}, {events} events, {markers(pg)} markers")
            close_viewer(pg)
        step("temporal", s8, pg)

        # 9. back to text (there is no submit mode any more)
        def s9():
            pg.get_by_role("tab", name="Text", exact=True).click()
            q().fill("a bus turning at an intersection")
            run_search(pg); th = wait_thumbs(pg)
            check("text search again", len(th) > 0, f"{len(th)} results")
        step("text again", s9, pg)

        # 9b. hover-scrub on a card: right half plays the next keyframes, left half the
        # previous ones; a card button or leaving the card shows the result frame again
        def s9b():
            first = "() => [...document.images].find(i => i.src.includes('/media/frames/')).src"
            num = lambda u: int(u.split("?")[0].split("/")[-1].split(".")[0])
            orig = pg.evaluate(first)
            box = pg.locator("img[src*='/media/frames/']").first.bounding_box()
            at = lambda fx: pg.mouse.move(box["x"] + box["width"] * fx, box["y"] + box["height"] * 0.35)
            at(0.8); pg.wait_for_timeout(1500)
            right = pg.evaluate(first)
            at(0.2); pg.wait_for_timeout(1200); left1 = pg.evaluate(first)
            pg.wait_for_timeout(1000); left2 = pg.evaluate(first)
            check("hover right half plays the next keyframes, left half the previous",
                  num(right) > num(orig) and num(left2) < num(left1),
                  f"result {num(orig)} -> right {num(right)} -> left {num(left1)}, {num(left2)}")
            at(0.8); pg.wait_for_timeout(1000)
            pg.get_by_label("Submit this frame to DRES as KIS").first.hover(); pg.wait_for_timeout(400)
            on_button = pg.evaluate(first)
            at(0.8); pg.wait_for_timeout(1000)
            pg.mouse.move(2, 2); pg.wait_for_timeout(400)
            check("a card button / leaving the card shows the result frame again",
                  on_button == orig and pg.evaluate(first) == orig, f"on K {num(on_button)}, after leaving {num(pg.evaluate(first))}")
        step("hover scrub", s9b, pg)

        # 9c. TRAKE events survive closing the viewer by a click outside: reopening the
        # video (its TR, or a card click) shows them again. Nothing is submitted.
        def s9c():
            pg.get_by_label("TRAKE: mark events on this video").first.click(force=True)
            dlg = open_viewer(pg)
            clear = dlg.locator('button[title="Remove all events"]')
            if clear.is_enabled(): clear.click()
            dlg.locator(".modal-box").click(position={"x": 5, "y": 5})  # keys go to the dialog
            pg.keyboard.press("m"); pg.keyboard.press("ArrowRight"); pg.keyboard.press("ArrowRight")
            pg.wait_for_timeout(400); pg.keyboard.press("m"); pg.wait_for_timeout(600)
            ev = dlg.locator("ol li").all_inner_texts()
            pg.mouse.click(5, 5)  # outside the viewer
            pg.wait_for_function("() => !document.querySelector('dialog[open] video')", timeout=10000)
            pg.get_by_label("TRAKE: mark events on this video").first.click(force=True)
            dlg = open_viewer(pg)
            ev_tr = dlg.locator("ol li").all_inner_texts()
            close_viewer(pg)
            pg.locator("img[src*='/media/frames/']").first.click()
            dlg = open_viewer(pg)
            n_card, tab_label = markers(pg), dlg.get_by_role("tab", name=re.compile("^TRAKE")).inner_text()
            check("TRAKE events kept after a click outside (TR reopen + card click)",
                  len(ev) == 2 and ev_tr == ev and n_card == 2 and "(2)" in tab_label,
                  f"marked {len(ev)}, TR reopen {len(ev_tr)}, card click {n_card} markers, tab {tab_label!r}")
            dlg.get_by_role("tab", name=re.compile("^TRAKE")).click()
            dlg.locator('button[title="Remove all events"]').click()
            close_viewer(pg)
        step("TRAKE kept on close", s9c, pg)

        # 10. frame viewer: opens PAUSED at the frame (no autoplay), KIS panel first,
        # timeline + neighbouring frames
        def s10():
            pg.locator("img[src*='/media/frames/']").first.click()
            dlg = open_viewer(pg)
            info = pg.evaluate("() => { const v=document.querySelector('dialog[open] video'); "
                               "return {t: v.currentTime, d: v.duration, paused: v.paused, src: v.currentSrc.slice(-40)} }")
            neigh = dlg.get_by_text("Neighbouring frames").count() > 0
            check("frame viewer: video loads + seeks, neighbours", info["d"] > 0 and neigh,
                  f"t={info['t']:.1f}s of {info['d']:.0f}s {info['src']}")
            check("frame viewer: no autoplay, KIS panel first", info["paused"] and active_tab(dlg) == "KIS",
                  f"paused={info['paused']}, tab {active_tab(dlg)!r}")
            close_viewer(pg)
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

        # 12. DRES submit paths: a card's K / Q / TR and the viewer's KIS / Q&A / TRAKE
        # panel. Only while no evaluation is active: the UI then refuses client-side
        # ("no ACTIVE evaluation") and sends nothing.
        def s12():
            if not no_active_eval:
                check("submit KIS / Q&A / TRAKE / confirm", None, "an evaluation is ACTIVE -- not clicking Submit"); return
            sent = []
            pg.on("request", lambda r: sent.append(r.url) if "/submission/submit" in r.url else None)
            q().fill("a bus turning at an intersection"); run_search(pg); wait_thumbs(pg)
            card_btn = lambda label: pg.locator(f'button[aria-label="{label}"]').first

            def refused(name, act):
                clear_verdict(pg); act(); pg.wait_for_timeout(1500)
                v = last_verdict(pg) or ""
                check(name, "active evaluation" in v.lower() and not sent, f"sent={len(sent)}, toast {v[:50]!r}")

            # card K: one click
            pg.locator("img[src*='/media/frames/']").first.hover()
            refused("card K = KIS (no active eval: refused, nothing sent)",
                    lambda: card_btn("Submit this frame to DRES as KIS").click(force=True))

            # card Q: a dialog with an EMPTY answer; Enter submits
            def card_q():
                card_btn("Q&A: answer for this frame").click(force=True)
                box = pg.locator("dialog[open]").get_by_placeholder("Answer…")
                box.wait_for(timeout=5000)
                empty = box.input_value() == "" and box.evaluate("e => e === document.activeElement")
                box.fill("5"); box.press("Enter")
                return empty
            empty = [None]
            refused("card Q = Q&A dialog, Enter submits (refused, nothing sent)", lambda: empty.__setitem__(0, card_q()))
            card_btn("Q&A: answer for this frame").click(force=True)
            again = pg.locator("dialog[open]").get_by_placeholder("Answer…").input_value()
            pg.keyboard.press("Escape")
            check("Q&A answer box starts empty + focused, every time", empty[0] and again == "", f"reopened with {again!r}")

            # card TR: the viewer on an EMPTY TRAKE timeline, paused
            card_btn("TRAKE: mark events on this video").click(force=True)
            dlg = open_viewer(pg)
            paused = pg.evaluate("document.querySelector('dialog[open] video').paused")
            check("card TR = viewer on TRAKE, no events, paused", active_tab(dlg) == "TRAKE" and markers(pg) == 0 and paused,
                  f"tab {active_tab(dlg)!r}, {markers(pg)} markers, paused={paused}")
            # mark with the keyboard: M, 2 s later, M
            dlg.locator(".modal-box").click(position={"x": 5, "y": 5})  # keys go to the dialog, not an input
            pg.keyboard.press("m"); pg.keyboard.press("ArrowRight"); pg.keyboard.press("ArrowRight")
            pg.wait_for_timeout(400); pg.keyboard.press("m"); pg.wait_for_timeout(600)
            ev = dlg.locator("ol li").all_inner_texts()
            check("M marks the frame showing now (2 events, 2 markers)", len(ev) == 2 and markers(pg) == 2, [e.split()[1] for e in ev])
            # drag the second marker to the right: its event moves
            box = pg.locator('dialog[open] [part~="marker"]').nth(1).bounding_box()
            pg.mouse.move(box["x"] + 1, box["y"] + box["height"] / 2); pg.mouse.down()
            pg.mouse.move(box["x"] + 40, box["y"] + box["height"] / 2, steps=8); pg.mouse.up(); pg.wait_for_timeout(800)
            ev2 = dlg.locator("ol li").all_inner_texts()
            check("drag a marker on the timeline moves its event", len(ev2) == 2 and ev2[1] != ev[1],
                  f"{ev[1].split()[1]} -> {ev2[1].split()[1] if len(ev2) > 1 else '?'}")
            refused("Submit TRAKE (refused, nothing sent)",
                    lambda: dlg.get_by_role("button", name="Submit TRAKE").click())
            # the viewer's own KIS and Q&A panels
            dlg.get_by_role("tab", name="KIS").click()
            refused("viewer: Submit KIS (refused, nothing sent)", lambda: dlg.get_by_role("button", name="Submit KIS").click())
            dlg.get_by_role("tab", name="Q&A").click()
            qa_empty = dlg.get_by_placeholder("Answer…").input_value() == ""
            dlg.get_by_placeholder("Answer…").fill("7")
            refused("viewer: Submit Q&A (refused, nothing sent)", lambda: dlg.get_by_role("button", name="Submit Q&A").click())
            check("viewer: Q&A answer starts empty", qa_empty)
            close_viewer(pg)

            # confirm toggle: a dialog before anything is sent (dismissed here)
            pg.locator('[title="Confirm each submit before sending to DRES"] input').check()
            n = len(dialogs)
            pg.locator("img[src*='/media/frames/']").first.hover()
            card_btn("Submit this frame to DRES as KIS").click(force=True)
            pg.wait_for_timeout(1000)
            check("confirm toggle asks first (dismissed -> nothing sent)", len(dialogs) > n and not sent,
                  f"dialog: {dialogs[-1][:40] if len(dialogs) > n else None}")
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
            # a row's preview = the same viewer, marks-for-CSV only (no DRES tabs)
            pg.locator("img[src*='/result_manager/send_img']").first.click()
            dlg = open_viewer(pg)
            has_marks = dlg.get_by_role("button", name=re.compile(r"^Mark frame")).count() > 0
            check("Result Manager preview: viewer with the TRAKE timeline, no DRES tabs",
                  has_marks and dlg.locator("[role=tab]").count() == 0 and pg.evaluate(
                      "document.querySelector('dialog[open] video').paused"))
            close_viewer(pg)
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
