"""List batch prefixes (LXX/KXX) and video names (LXX_VYYY) for the given batches.

Served from `video_names.json` next to this file (reloaded when it changes, like
subsets.json): walking the keyframe tree stats ~1,500 folders on the Windows drive
(~2 s) and the UI asks on every page load and batch toggle. The list only changes
when a batch is ingested -- then regenerate it (in a container that sees the data):

    docker exec aic2026-util-1 python -m src.utils.video_names > src/utils/video_names.json
"""

from __future__ import annotations

import glob
import json
import os
import sys

from src.utils.settings import get_settings

_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "video_names.json")
_cache: dict = {"mtime": None, "batches": None}


def _load() -> dict | None:
    """{batch: {prefix: [video, ...]}} from video_names.json, or None if absent."""
    try:
        mtime = os.path.getmtime(_PATH)
    except OSError:
        return None
    if mtime != _cache["mtime"]:
        with open(_PATH, encoding="utf-8") as f:
            _cache["batches"] = json.load(f)["batches"]
        _cache["mtime"] = mtime
    return _cache["batches"]


def _walk(batch_numbers) -> dict[str, dict[str, list[str]]]:
    """Reads the keyframe tree, not the source-video tree: batch 1 has keyframes
    (and is indexed) but no .mp4 files here, so walking videos/ reported zero
    names for it. Keyframes are what the index is built from.
    """
    settings = get_settings()
    out: dict[str, dict[str, list[str]]] = {}
    for batch in sorted(set(batch_numbers)):
        split_glob = os.path.join(
            settings.dataset_path_team,
            str(batch),
            "frames",
            settings.split_name_low_res,
            "Keyframes_*",
        )
        for split_path in sorted(glob.glob(split_glob)):
            prefix = os.path.basename(split_path).split("_", 1)[-1]
            keyframes_dir = os.path.join(split_path, "keyframes")
            if not os.path.isdir(keyframes_dir):
                continue
            out.setdefault(str(batch), {}).setdefault(prefix, []).extend(
                sorted(
                    name
                    for name in os.listdir(keyframes_dir)
                    if os.path.isdir(os.path.join(keyframes_dir, name))
                )
            )
    return out


def get_video_names(batch_numbers: list[int]) -> list[str]:
    """Sorted batch prefixes, then sorted video names."""
    batches = _load()
    if batches is None:  # no list shipped: fall back to walking the tree
        batches = _walk(batch_numbers)
    prefixes: set[str] = set()
    video_names: list[str] = []
    for batch in sorted(set(batch_numbers)):
        for prefix, videos in batches.get(str(batch), {}).items():
            prefixes.add(prefix)
            video_names.extend(videos)
    return sorted(prefixes) + sorted(video_names)


if __name__ == "__main__":
    # Regenerate video_names.json from the keyframe tree (see the module docstring).
    batches = [int(b) for b in sys.argv[1:]] or [0, 1]
    json.dump(
        {
            "_comment": "Videos per batch and prefix, from the keyframe tree. Regenerate after an ingest: "
            "docker exec aic2026-util-1 python -m src.utils.video_names > src/utils/video_names.json",
            "batches": _walk(batches),
        },
        sys.stdout,
        indent=1,
    )
    sys.stdout.write("\n")
