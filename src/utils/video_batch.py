"""Batch resolution (video name prefix -> dataset batch) and neighboring-frame lookup."""

from __future__ import annotations

import glob
import os

from src.utils.logger import get_logger
from src.utils.settings import get_settings

logger = get_logger()

# Prefix -> batch index. Extend this if the dataset adds more batches/prefixes.
BATCH_PREFIXES = {"L": 0, "K": 1, "X": 2}


def get_batch(video_name: str) -> int:
    """Resolve a batch index from a video name's leading letter (L->0, K->1, X->2)."""
    for prefix, batch in BATCH_PREFIXES.items():
        if video_name.startswith(prefix):
            return batch
    raise ValueError(f"Could not resolve a batch for video_name: {video_name}")


def get_neighboring_frames(
    frame_num: str, video_name: str, k: int = 3
) -> tuple[list[str], list[str]]:
    """Return the `k` low-res frame paths immediately before/after `frame_num` in `video_name`."""
    settings = get_settings()
    batch = get_batch(video_name)
    prefix = video_name[0]

    frame_dir = os.path.join(
        settings.base_path,
        str(batch),
        "frames",
        settings.split_name_low_res,
        f"Keyframes_{prefix}{video_name[1:3]}",
        "keyframes",
        video_name,
    )

    all_frames = sorted(
        glob.glob(os.path.join(frame_dir, f"*{settings.lowres_format}"))
    )
    if not all_frames:
        logger.warning(
            f"No {settings.lowres_format} frames found for {video_name} in {frame_dir}"
        )
        return [], []

    frame_map = {
        os.path.splitext(os.path.basename(f))[0]: i for i, f in enumerate(all_frames)
    }
    if frame_num not in frame_map:
        logger.warning(f"Frame {frame_num} not found for {video_name}")
        return [], []

    idx = frame_map[frame_num]
    prev_frames = all_frames[max(0, idx - k) : idx]
    next_frames = all_frames[idx + 1 : idx + 1 + k]
    return prev_frames, next_frames
