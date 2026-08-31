"""Single owner of the dataset's on-disk naming rule (review.md #1).

Also published to the frontend via `GET /hub/media_config` so the browser builds
media URLs from the same source rather than its own copy.
"""

from __future__ import annotations

from src.utils.settings import get_settings

# `{video}` is the video name without extension, `{prefix}` its leading token
# (L21_V001 -> L21), `{batch}` the dataset batch (payload field `idx_folder`).
FRAME_TEMPLATE = (
    "{batch}/frames/{split}/Keyframes_{prefix}/keyframes/{video}/{keyframe}{ext}"
)
VIDEO_TEMPLATE = "{batch}/videos/Videos_{prefix}/video/{video}.mp4"


def video_stem(video_name: str) -> str:
    """`L21_V001.mp4` -> `L21_V001`."""
    return str(video_name).split(".")[0]


def video_prefix(video_name: str) -> str:
    """`L21_V001.mp4` -> `L21`."""
    return video_stem(video_name).split("_")[0]


def frame_relpath(batch: int | str, video_name: str, keyframe_id: str | int) -> str:
    """Dataset-relative path of one keyframe image."""
    settings = get_settings()
    return FRAME_TEMPLATE.format(
        batch=batch,
        split=settings.split_name_low_res,
        prefix=video_prefix(video_name),
        video=video_stem(video_name),
        keyframe=str(keyframe_id).split(".")[0].zfill(5),
        ext=settings.lowres_format,
    )


def video_relpath(batch: int | str, video_name: str) -> str:
    """Dataset-relative path of one source video."""
    return VIDEO_TEMPLATE.format(
        batch=batch,
        prefix=video_prefix(video_name),
        video=video_stem(video_name),
    )


def media_config() -> dict:
    """Layout rule for `GET /hub/media_config`.

    `split` == `split_original` here: the dataset has no full-resolution frame
    tree, so "original" resolves to the same `.avif`.
    """
    settings = get_settings()
    return {
        "image_base_url": settings.nginx_image_host.rstrip("/"),
        "video_base_url": settings.nginx_video_host.rstrip("/"),
        "frame_template": FRAME_TEMPLATE,
        "video_template": VIDEO_TEMPLATE,
        "split": settings.split_name_low_res,
        "split_original": settings.split_name,
        "frame_ext": settings.lowres_format,
        "keyframe_pad": 5,
    }
