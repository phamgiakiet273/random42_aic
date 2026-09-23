#!/usr/bin/env python3
"""End-to-end check of every UI feature, through one origin -- exactly the requests
the browser makes (src/ui/aic/src/api/*). Standard library only.

  python3 tools/e2e_check.py                                        # server UI (vite :10000)
  python3 tools/e2e_check.py https://hallie-sabulous-nicholle.ngrok-free.dev   # public URL / fallback
  python3 tools/e2e_check.py http://localhost:9080                  # a teammate's nginx

Never submits an answer: the submit path is exercised only while DRES has NO active
evaluation, where the central service refuses (409) before contacting DRES.
Exit code = number of FAILs.
"""
import base64, json, sys, time, urllib.error, urllib.parse, urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:10000").rstrip("/")
UA = {"User-Agent": "aic-e2e/1", "ngrok-skip-browser-warning": "1"}
SAMPLE_JPG = "/mnt/e/workspace/AIC_2026/batch1/work/keyframes/Keyframes_M05/keyframes/M05_V001/00042.jpg"
results = []


def req(path, data=None, headers=None, timeout=120):
    r = urllib.request.Request(BASE + path if path.startswith("/") else path,
                               data=data, headers={**UA, **(headers or {})})
    t0 = time.monotonic()   # WSL's wall clock gets stepped (NTP) -> negative timings
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, resp.headers, resp.read(), time.monotonic() - t0
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read(), time.monotonic() - t0
    except Exception as e:  # dropped connection / timeout: record it, keep checking the rest
        print(f"        (network error on {path[:60]}: {type(e).__name__})", flush=True)
        return 0, {}, b"{}", time.monotonic() - t0


def form(path, fields):
    return req(path, urllib.parse.urlencode(fields).encode())


def check(name, ok, detail=""):
    results.append((("PASS" if ok else "FAIL") if ok is not None else "SKIP", name, detail))
    print(f"  {results[-1][0]:4s}  {name}{'  -- ' + detail if detail else ''}", flush=True)


def search(**fields):
    base = {"model": "siglip_alpha", "k": "100", "return_s2t": "true", "sort_to_news": "true",
            "frame_class_filter": "[]", "skip_frames": "[]"}
    st, _, body, dt = form("/hub/search", {**base, **{k: str(v) for k, v in fields.items()}})
    data = json.loads(body).get("data") if st == 200 else None
    return st, data, dt


def flat(data):
    return [r for c in data for r in c] if data and isinstance(data[0], list) else (data or [])


def stem(v): return str(v).split(".")[0]
def prefix(v): return stem(v).split("_")[0]


def frame_url(cfg, rec):
    path = cfg["frame_template"].format(batch=rec.get("idx_folder", 0), split=cfg["split"], prefix=prefix(rec["video_name"]),
                                        video=stem(rec["video_name"]),
                                        keyframe=str(rec["keyframe_id"]).split(".")[0].zfill(cfg.get("keyframe_pad", 5)),
                                        ext=cfg["frame_ext"])
    return f"{cfg['image_base_url']}/{path}"


def video_url(cfg, rec):
    return f"{cfg['video_base_url']}/" + cfg["video_template"].format(
        batch=rec.get("idx_folder", 0), prefix=prefix(rec["video_name"]), video=stem(rec["video_name"]))


def main():
    print(f"target: {BASE}")
    # --- UI shell ---
    st, h, body, _ = req("/")
    html = body.decode("utf-8", "replace")
    check("UI page loads", st == 200 and "text/html" in (h.get("Content-Type") or ""), f"HTTP {st}")
    import re
    js = re.findall(r'src="([^"]+\.(?:js|jsx))"', html)
    if js:
        st, _, _, _ = req(js[0] if js[0].startswith("/") else "/" + js[0])
        check("UI script loads", st == 200, js[0])

    # --- hub basics ---
    st, _, body, _ = req("/hub/ping"); check("hub ping", st == 200)
    st, _, body, _ = req("/hub/media_config")
    cfg = json.loads(body)["data"] if st == 200 else None
    check("media_config (relative media paths)", bool(cfg) and cfg["image_base_url"].startswith("/"),
          cfg and cfg["image_base_url"])
    st, _, body, _ = req("/hub/subsets")
    check("content subsets", st == 200 and bool(json.loads(body).get("data")), f"HTTP {st}")
    st, _, body, _ = form("/hub/get_video_names_of_batch", {"batch_id": "[0, 1]"})
    names = json.loads(body).get("data") or [] if st == 200 else []
    names = [n for n in (names if isinstance(names, list) else [])]
    by = {}
    for n in names:   # the list also carries series names (M01, N001, S01): count videos only
        if "_V" in n: by[n[0]] = by.get(n[0], 0) + 1
    check("video names (batches 0+1)", by.get("M") == 304 and by.get("N") == 298 and by.get("S") == 12 and by.get("L", 0) > 0,
          f"{by}")
    series = lambda letter: ",".join(sorted({prefix(n) for n in names if n.startswith(letter)}))

    # --- text search per subset, thumbnails resolve ---
    subset_hit = {}
    for letter, q in [("L", "a news anchor in a studio"), ("N", "a bus turning at an intersection"),
                      ("S", "cyclists racing on a road"), ("M", "a news anchor in a studio")]:
        st, data, dt = search(search_type="text", text=q, video_filter=series(letter))
        recs = flat(data)
        ok = st == 200 and len(recs) >= 5 and all(stem(r["video_name"]).startswith(letter) for r in recs)
        thumbs = [req(frame_url(cfg, r))[0] for r in recs[:10]] if ok and cfg else []
        check(f"text search {letter} + 10 thumbnails", ok and thumbs and all(c == 200 for c in thumbs),
              f"{len(recs)} hits {dt:.2f}s, thumbs {thumbs.count(200)}/{len(thumbs)}")
        subset_hit[letter] = recs[0] if recs else None

    # --- transcript (s2t) search on M: word from a real M transcript ---
    m = subset_hit.get("M")
    words = [w for w in (m or {}).get("s2t", []) if isinstance(w, str) and len(w) >= 4] if m else []
    word = words[0] if words else None
    if word:
        st, data, _ = search(search_type="text", text="news", video_filter=series("M"), s2t_filter=word)
        recs = flat(data)
        check("transcript filter on M", st == 200 and recs and all(prefix(r["video_name"]).startswith("M") for r in recs),
              f"'{word}': {len(recs)} hits")
    else:
        check("transcript filter on M", False, "top M result carries no transcript words (M s2t payload missing?)")

    # --- filters ---
    st, data, _ = search(search_type="text", text="a street at night", frame_class_filter="[0]")
    recs = flat(data)
    check("frame-class filter", st == 200 and recs and all(r["frame_class"] == 0 for r in recs), f"{len(recs)} hits")
    st, data, _ = search(search_type="text", text="a street at night")
    recs = flat(data)
    if recs:
        top = recs[0]
        # same shape as the UI's toSkipFrame (searchStore.js): frame numbers as STRINGS
        skip = json.dumps([{"video_name": stem(top["video_name"]), "related_start_frame": str(top["related_start_frame"]),
                            "related_end_frame": str(top["related_end_frame"])}])
        st, data2, _ = search(search_type="text", text="a street at night", skip_frames=skip)
        again = [r for r in flat(data2) if r["video_name"] == top["video_name"] and r["keyframe_id"] == top["keyframe_id"]]
        check("skip-frames filter", st == 200 and not again, f"skipped {stem(top['video_name'])}#{top['keyframe_id']}")
    st, data, _ = search(search_type="text", text="a street at night", sort_to_news="false")
    check("search without news grouping", st == 200 and len(flat(data)) > 0)

    # --- image search: a real M keyframe must find itself ---
    try:
        b64 = base64.b64encode(open(SAMPLE_JPG, "rb").read()).decode()
        st, data, dt = search(search_type="image", image_path=f"data:image/jpeg;base64,{b64}")
        recs = flat(data)[:5]
        hit = any(stem(r["video_name"]) == "M05_V001" and abs(int(r["keyframe_id"]) - 42) <= 200 for r in recs)
        check("image search finds its own frame", st == 200 and hit,
              f"top: {[stem(r['video_name']) + '#' + str(r['keyframe_id']) for r in recs[:3]]}")
    except OSError as e:
        check("image search finds its own frame", None, f"sample frame not readable here ({e.strerror})")

    # --- temporal ---
    st, data, dt = search(search_type="temporal", text="a news anchor in a studio. a map on the screen")
    chains = data if data and isinstance(data[0], list) else []
    good = all(len({r["video_name"] for r in c}) == 1 and
               [int(r["keyframe_id"]) for r in c] == sorted(int(r["keyframe_id"]) for r in c) for c in chains)
    check("temporal search (1 video/chain, ordered)", st == 200 and chains and good, f"{len(chains)} chains {dt:.2f}s")

    # --- scroll (browse one video) ---
    st, data, _ = search(search_type="scroll", video_filter="M05_V001", utility_feature="shot", k="50")
    recs = flat(data)
    check("scroll one video", st == 200 and recs and all(stem(r["video_name"]) == "M05_V001" for r in recs), f"{len(recs)} frames")

    # --- util-backed helpers ---
    st, _, body, _ = form("/hub/translate", {"text": "xe buýt màu đỏ", "source": "", "target": "en"})
    out = json.loads(body).get("data") if st == 200 else None
    check("translate vi->en", bool(out), f"{str(out)[:60]}")
    st, _, body, _ = form("/hub/get_neighboring_frames", {"frame_num": "42", "video_name": "M05_V001", "k": "2"})
    check("neighbouring frames", st == 200 and bool(json.loads(body).get("data")), f"HTTP {st}")
    st, _, body, _ = form("/hub/download", {"model": "siglip_alpha", "search_type": "text", "text": "a bus", "k": "20",
                                            "format": "kis", "return_s2t": "false", "frame_class_filter": "[]", "skip_frames": "[]"})
    lines = [l for l in body.decode("utf-8", "replace").splitlines() if l.strip()]
    check("CSV download (KIS)", st == 200 and lines and "," in lines[0], f"{len(lines)} rows, e.g. {lines[0][:40] if lines else ''}")

    # --- video (range = seeking) per series ---
    for letter, rec in subset_hit.items():
        if not rec: continue
        st, _, _, _ = req(video_url(cfg, rec), headers={"Range": "bytes=0-1023"})
        check(f"video seek {letter} ({stem(rec['video_name'])})", st == 206, f"HTTP {st}")

    # --- result manager ---
    st, _, body, _ = req("/result_manager/get_fps/M05_V001")
    fps = json.loads(body).get("data") if st == 200 else None
    check("result manager fps", bool(fps), f"{fps}")
    st, h, _, _ = req("/result_manager/send_img/M05_V001/42")
    check("result manager thumbnail", st == 200 and "image" in (h.get("Content-Type") or ""), f"HTTP {st}")
    st, _, _, _ = req("/result_manager/send_video/M05_V001", headers={"Range": "bytes=0-1023"})
    check("result manager video", st in (200, 206), f"HTTP {st}")

    # --- DRES submission (never submits while an evaluation is active) ---
    st, _, body, _ = req("/submission/get_session_and_eval")
    j = json.loads(body) if body else {}
    check("DRES session (central service)", j.get("status") == 200, j.get("message", f"HTTP {st}"))
    if j.get("status") == 200 and not (j.get("data") or {}).get("eval_id"):
        st, _, body, _ = req("/submission/submit_kis", json.dumps({"mediaItemName": "N001_V001", "start": 1000, "end": 1000}).encode(),
                             {"Content-Type": "application/json"})
        check("submit path (no active eval -> refused, nothing sent)", st == 409 and b"No ACTIVE evaluation" in body,
              f"HTTP {st} {body[:80]!r}")
    else:
        check("submit path", None, "an evaluation is ACTIVE -- not submitting a test answer")

    fails = sum(r[0] == "FAIL" for r in results)
    print(f"\n{sum(r[0] == 'PASS' for r in results)} pass, {fails} fail, {sum(r[0] == 'SKIP' for r in results)} skip")
    sys.exit(fails)


if __name__ == "__main__":
    main()
