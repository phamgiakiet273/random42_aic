"""List batch folder names (LXX) and video names (LXX_VYYY) from the original dataset tree."""

from __future__ import annotations

import os

from src.utils.settings import get_settings


def get_video_names(batch_numbers: list[int]) -> list[str]:
    """Return sorted batch-folder names followed by sorted video names, for the given batches."""
    base_path = get_settings().dataset_path_origin
    video_names = []
    lxx_folders = set()

    for batch in sorted(batch_numbers):
        videos_path = os.path.join(base_path, str(batch), "videos")
        if not os.path.exists(videos_path):
            continue

        video_folders = sorted(
            f for f in os.listdir(videos_path) if f.startswith("Videos_")
        )
        for video_folder in video_folders:
            video_subfolder = os.path.join(videos_path, video_folder, "video")
            if not os.path.exists(video_subfolder):
                continue

            lxx_folders.add(video_folder.split("_")[1])
            files = sorted(f for f in os.listdir(video_subfolder) if f.endswith(".mp4"))
            video_names.extend(os.path.splitext(f)[0] for f in files)

    return sorted(lxx_folders) + video_names
