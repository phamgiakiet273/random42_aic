#!/usr/bin/env python3
"""Measure what a search costs on the wire -- the competition-day internet is slow.

Sends the UI's own requests (POST /hub/search, same form fields and defaults as
src/ui/aic/src/api/search.js: k=100, return_s2t=true, sort_to_news=true) and reports,
per case: gzip bytes on the wire, raw JSON bytes, time, records, and which record
fields take the space. Standard library only.

  python3 tools/payload_size.py                                   # server UI origin (:10000)
  python3 tools/payload_size.py https://hallie-sabulous-nicholle.ngrok-free.dev   # as a teammate sees it
  python3 tools/payload_size.py http://localhost:9080             # through a teammate nginx
"""
import gzip, json, sys, time, urllib.parse, urllib.request
from collections import Counter

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:10000").rstrip("/")
UA = {"User-Agent": "payload-size/1", "Accept-Encoding": "gzip", "ngrok-skip-browser-warning": "1"}

CASES = [  # (label, form fields) -- UI defaults unless the label says otherwise
    ("text k=100 (UI default)", {"search_type": "text", "text": "a red bus turning at an intersection"}),
    ("text k=100, no transcripts", {"search_type": "text", "text": "a red bus turning at an intersection", "return_s2t": "false"}),
    ("text k=100, news query", {"search_type": "text", "text": "a news anchor talking about the economy"}),
    ("text k=500", {"search_type": "text", "text": "a red bus turning at an intersection", "k": "500"}),
    ("temporal 2 events k=100", {"search_type": "temporal", "text": "a man walks into a shop. he pays at the counter"}),
]


def post(fields):
    form = {"model": "siglip_alpha", "k": "100", "return_s2t": "true", "sort_to_news": "true",
            "frame_class_filter": "[]", "skip_frames": "[]", **fields}
    req = urllib.request.Request(f"{BASE}/hub/search", data=urllib.parse.urlencode(form).encode(), headers=UA)
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=300) as r:
        wire = r.read()
        enc = r.headers.get("Content-Encoding", "")
    dt = time.monotonic() - t0
    raw = gzip.decompress(wire) if enc == "gzip" else wire
    return wire, raw, enc, dt


def records_of(data):
    if data and isinstance(data[0], list):  # temporal: list of chains
        return [rec for chain in data for rec in chain], len(data)
    return data, None


def field_share(records):
    c = Counter()
    for rec in records:
        for key, val in rec.items():
            c[key] += len(json.dumps(val, ensure_ascii=False).encode()) + len(key) + 4
    total = sum(c.values()) or 1
    return ", ".join(f"{k} {v * 100 // total}%" for k, v in c.most_common(4))


def fetch(path, headers=None):
    req = urllib.request.Request(BASE + path, headers={**UA, **(headers or {})})
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=300) as r:
        body = r.read()
        return body, r.headers, time.monotonic() - t0


def frame_path(cfg, rec):
    stem = str(rec["video_name"]).split(".")[0]
    return cfg["image_base_url"] + "/" + cfg["frame_template"].format(
        batch=rec.get("idx_folder", 0), split=cfg["split"], prefix=stem.split("_")[0], video=stem,
        keyframe=str(rec["keyframe_id"]).split(".")[0].zfill(cfg.get("keyframe_pad", 5)), ext=cfg["frame_ext"])


def other_traffic():
    """Everything else a search session moves: UI load, thumbnails, video."""
    print("\nother traffic")
    try:  # UI first load (only when BASE serves the UI)
        html, h, _ = fetch("/")
        import re
        assets = re.findall(r'(?:src|href)="(/[^"]+\.(?:js|jsx|css))"', html.decode("utf-8", "replace"))
        total = len(html)
        for a in assets:
            body, _, _ = fetch(a)
            total += len(body)
        print(f"  UI first load (html + {len(assets)} assets, as sent) {total/1024:8.1f} KB"
              + ("   (vite dev server: not what teammates load)" if any(a.startswith("/src/") for a in assets) else ""))
    except Exception as e:
        print(f"  UI first load: n/a ({type(e).__name__})")
    body, h, _ = fetch("/hub/media_config")
    cfg = json.loads(gzip.decompress(body) if h.get("Content-Encoding") == "gzip" else body)["data"]
    _, raw, _, _ = post({"search_type": "text", "text": "a red bus turning at an intersection"})
    recs = json.loads(raw)["data"]
    t0 = time.monotonic(); sizes = []
    for rec in recs:
        body, _, _ = fetch(frame_path(cfg, rec))
        sizes.append(len(body))
    dt = time.monotonic() - t0
    print(f"  100 thumbnails of one results page                {sum(sizes)/1024:8.1f} KB  "
          f"(avg {sum(sizes)/len(sizes)/1024:.1f} KB, {dt:.1f}s fetched one by one)")
    for vid in ("M05_V001", "N001_V001", "L21_V001"):
        _, sraw, _, _ = post({"search_type": "scroll", "video_filter": vid, "k": "5000", "return_s2t": "false"})
        frames = json.loads(sraw)["data"]
        fps = float(frames[0]["fps"]); dur = max(int(r["keyframe_id"]) for r in frames) / fps
        rec = frames[0]; stem = str(rec["video_name"]).split(".")[0]
        vpath = cfg["video_base_url"] + "/" + cfg["video_template"].format(
            batch=rec.get("idx_folder", 0), prefix=stem.split("_")[0], video=stem)
        _, h, _ = fetch(vpath, {"Range": "bytes=0-1"})
        size = int(h["Content-Range"].split("/")[-1])
        body, _, dt = fetch(vpath, {"Range": f"bytes=0-{4 * 1024 * 1024 - 1}"})
        print(f"  video {stem:10s} {size/1e6:7.0f} MB for {dur/60:5.1f} min = {size*8/dur/1e6:4.2f} Mbit/s to play; "
              f"4 MB fetched in {dt:.1f}s ({len(body)*8/dt/1e6:.0f} Mbit/s here)")


print(f"target: {BASE}")
print(f"{'case':30s} {'wire (gzip)':>12s} {'raw JSON':>10s} {'time':>7s} {'records':>8s}  biggest fields")
for label, fields in CASES:
    try:
        wire, raw, enc, dt = post(fields)
        recs, chains = records_of(json.loads(raw).get("data") or [])
        n = f"{len(recs)}" + (f"/{chains}ch" if chains is not None else "")
        print(f"{label:30s} {len(wire)/1024:9.1f} KB {len(raw)/1024:7.1f} KB {dt:6.2f}s {n:>8s}  {field_share(recs)}"
              + ("" if enc == "gzip" else "   !! NOT gzipped"))
    except Exception as e:
        print(f"{label:30s} ERROR {type(e).__name__}: {e}")
other_traffic()
