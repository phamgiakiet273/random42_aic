#!/usr/bin/env python3
"""Measure what a search costs on the wire -- the competition-day internet is slow.

Sends the UI's own requests (POST /hub/search, same form fields and defaults as
src/ui/aic/src/api/search.js: k=100, return_s2t=true, sort_to_news=true) and reports,
per case: gzip bytes on the wire, raw JSON bytes, time, records, and which record
fields take the space. Standard library only.

  python3 tools/payload_size.py                                   # hub on this machine
  python3 tools/payload_size.py https://hallie-sabulous-nicholle.ngrok-free.dev   # as a teammate sees it
  python3 tools/payload_size.py http://localhost:9080             # through a teammate nginx
"""
import gzip, json, sys, time, urllib.parse, urllib.request
from collections import Counter

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:9021").rstrip("/")
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
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=300) as r:
        wire = r.read()
        enc = r.headers.get("Content-Encoding", "")
    dt = time.time() - t0
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
