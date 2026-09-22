"""Content subsets -> DB video_filter (thin wrapper over the video_name prefix match).

A "subset" is a named group of video-code prefixes (see subsets.json). Selecting a
subset scopes a search to those prefixes using the existing `video_filter`, so no
re-ingest or schema change is needed and the new traffic-CCTV data can't pollute a
news/cooking/etc. search. The json is reloaded on edit (mtime-checked)."""
from __future__ import annotations

import json
import os
import threading

_PATH = os.path.join(os.path.dirname(__file__), "subsets.json")
_lock = threading.Lock()
_cache: dict = {"mtime": 0.0, "data": {}}


def _load() -> dict:
    with _lock:
        try:
            mtime = os.path.getmtime(_PATH)
        except OSError:
            return {}
        if mtime != _cache["mtime"]:
            with open(_PATH, encoding="utf-8") as f:
                _cache["data"] = json.load(f).get("subsets", {})
            _cache["mtime"] = mtime
        return _cache["data"]


def catalog() -> dict:
    """{name: {prefixes, desc}} for listing (e.g. a UI dropdown)."""
    return _load()


def resolve(names: str | list[str] | None) -> list[str]:
    """Subset name(s) -> the union of their prefixes. Accepts a comma string or list.
    Unknown names are ignored (returned in no prefixes) so a typo never 500s a search."""
    if not names:
        return []
    if isinstance(names, str):
        names = [n.strip() for n in names.split(",") if n.strip()]
    subs = _load()
    out: list[str] = []
    for n in names:
        for p in subs.get(n, {}).get("prefixes", []):
            if p not in out:
                out.append(p)
    return out


def merge_video_filter(subset: str | list[str] | None, video_filter: str | None) -> str | None:
    """Fold a subset selection into an existing video_filter (both are OR-matched
    prefix lists in the DB). subset prefixes ∪ explicit video_filter prefixes."""
    prefixes = resolve(subset)
    explicit = [p.strip() for p in (video_filter or "").split(",") if p.strip()]
    merged: list[str] = []
    for p in prefixes + explicit:
        if p not in merged:
            merged.append(p)
    return ",".join(merged) if merged else None
