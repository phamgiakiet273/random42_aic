"""Frame/video path builders and time<->frame conversion, built from `Settings` paths."""

from __future__ import annotations

import io
import os

import ujson
from PIL import Image

from src.utils.settings import get_settings
from src.utils.video_batch import get_batch


def convert_time_to_frame(video_name: str, input_time: str) -> str:
    """Convert an "mm:ss" timestamp to an absolute frame index using the video's FPS."""
    minutes, seconds = input_time.split(":")
    settings = get_settings()
    fps_path = settings.fps_path[get_batch(video_name)]
    with open(fps_path, encoding="utf-8-sig") as infile:
        fps = ujson.load(infile)[video_name.replace(".mp4", "")]
    return str(int(float(fps) * (60 * int(minutes) + int(seconds))))


def pil_image_to_bytes(image: Image.Image, format: str = "PNG") -> bytes:
    with io.BytesIO() as output:
        image.save(output, format=format)
        return output.getvalue()


def bytes_to_pil_image(image_bytes: bytes) -> Image.Image:
    return Image.open(io.BytesIO(image_bytes))


def get_frame_path(batch: int, video_name: str, frame_name: str) -> str:
    settings = get_settings()
    return os.path.join(
        settings.dataset_path_team,
        str(batch),
        "frames",
        settings.split_name,
        f"Keyframes_{str(video_name).split('_')[0]}",
        "keyframes",
        str(video_name.split(".")[0]),
        str(frame_name.split(".")[0]) + settings.lowres_format,
    )


def get_video_path(batch: int, video_name: str) -> str:
    settings = get_settings()
    video_filename = str(video_name)
    if not video_filename.endswith(".mp4"):
        video_filename += ".mp4"

    return os.path.join(
        settings.dataset_path_origin,
        str(batch),
        "videos",
        f"Videos_{str(video_name).split('_')[0]}",
        "video",
        video_filename,
    )
