"""List batch prefixes (LXX/KXX) and video names (LXX_VYYY) for the given batches."""

from __future__ import annotations

import glob
import os

from src.utils.settings import get_settings


def get_video_names(batch_numbers: list[int]) -> list[str]:
    """Sorted batch prefixes, then sorted video names.

    Reads the keyframe tree, not the source-video tree: batch 1 has keyframes
    (and is indexed) but no .mp4 files here, so walking videos/ reported zero
    names for it. Keyframes are what the index is built from.
    """
    settings = get_settings()
    prefixes: set[str] = set()
    video_names: list[str] = []

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
            prefixes.add(prefix)
            video_names.extend(
                sorted(
                    name
                    for name in os.listdir(keyframes_dir)
                    if os.path.isdir(os.path.join(keyframes_dir, name))
                )
            )

    return sorted(prefixes) + sorted(video_names)
