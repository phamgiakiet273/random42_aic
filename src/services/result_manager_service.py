"""Business logic for the result-manager service: canonical nginx redirect paths
for frame images/videos, and per-batch video FPS lookup.

Path building here is deliberately NOT delegated to
`src.utils.metadata.get_frame_path`/`get_video_path`: those build filesystem
paths rooted at `dataset_path_team`/`dataset_path_origin` for local file
access, whereas this service builds paths relative to the nginx media root
(starting at the batch number) for HTTP redirects, and also needs to swap
between the normal and low-res split names for images. The two conventions
look similar but serve different consumers, so the logic is kept separate and
documented here instead of silently reusing a helper that doesn't quite fit.
"""

from __future__ import annotations

import os
from http import HTTPStatus

import ujson

from src.common.schemas.api import APIResponse
from src.utils.logger import get_logger
from src.utils.settings import get_settings
from src.utils.video_batch import get_batch

logger = get_logger()


def _level_and_batch(video_name: str) -> tuple[int, int]:
    try:
        level_num = int(video_name.split("_")[0][1:])
    except Exception as e:
        raise ValueError(
            f"video_name must be in format 'Lxx_Vyyy', e.g. 'L27_V011': {e}"
        )
    return level_num, get_batch(video_name)


class ResultManagerService:
    def __init__(self) -> None:
        pass

    async def ping(self) -> APIResponse:
        logger.debug("ping invoked")
        return APIResponse(
            status=HTTPStatus.OK.value,
            message="Running (Healthy)",
            data="ping",
        )

    async def send_file(self, file_path: str) -> str:
        """Validate a local file path exists; the router streams it back (e.g. via FileResponse)."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        return file_path

    async def get_image_redirect_url(self, video_name: str, frame_name: str) -> str:
        """Nginx redirect URL for the low-res (.avif) frame image:
        "<batch>/frames/<SPLIT_NAME_LOW_RES>/Keyframes_{L|K}<level>/keyframes/<video_name>/<frame>.avif"
        """
        settings = get_settings()
        frame_file = (
            frame_name if frame_name.lower().endswith(".avif") else f"{frame_name}.avif"
        )
        level_num, batch = _level_and_batch(video_name)

        # Batch-1 (K-prefixed) keyframe directories are always zero-padded to 2
        # digits (e.g. "Keyframes_K05"), but single-digit levels parsed above are
        # not (e.g. 5) -- undocumented in the legacy code, kept here as-is since
        # it reflects a real directory naming convention on disk.
        level_str = (
            "0" + str(level_num) if batch == 1 and level_num < 10 else str(level_num)
        )

        prefix = "L" if batch == 0 else "K"
        full_path = (
            f"{batch}/frames/{settings.split_name}/Keyframes_{prefix}{level_str}"
            f"/keyframes/{video_name}/{frame_file}"
        )
        full_path = full_path.replace(
            f"/{settings.split_name}/", f"/{settings.split_name_low_res}/"
        )

        target = f"{settings.nginx_image_host}/{full_path}"
        logger.info(f"get_image_redirect_url -> {target}")
        return target

    async def get_image_original_redirect_url(
        self, video_name: str, frame_name: str
    ) -> str:
        """Nginx redirect URL for the original (.jpg) frame image.

        NOTE: legacy `send_img_original_handler` never branched on batch here (it
        always used "Keyframes_L{level}", even for batch-1/K videos) -- unlike the
        low-res path above, which does branch. That looks like the same class of
        oversight fixed elsewhere in this port, but it was not in the requested
        scope for this method, so the original (batch-agnostic, L-only) behavior
        is preserved unchanged below.
        """
        settings = get_settings()
        base = frame_name
        if base.lower().endswith(".avif") or base.lower().endswith(".jpg"):
            base = base.rsplit(".", 1)[0]

        level_num, batch = _level_and_batch(video_name)

        full_path = f"{batch}/frames/{settings.split_name}/Keyframes_L{level_num}/keyframes/{video_name}/{base}.jpg"
        target = f"{settings.nginx_image_host}/{full_path}"
        logger.info(f"get_image_original_redirect_url -> {target}")
        return target

    async def get_video_redirect_url(self, video_name: str) -> str:
        """Nginx redirect URL for the source video:
        "<batch>/videos/Videos_{L|K}<level>/video/<video_name>.mp4"
        """
        settings = get_settings()
        level_num, batch = _level_and_batch(video_name)

        # Same batch-1 zero-pad quirk as get_image_redirect_url (see comment there).
        level_str = (
            "0" + str(level_num) if batch == 1 and level_num < 10 else str(level_num)
        )

        video_file = f"{video_name}.mp4"
        prefix = "L" if batch == 0 else "K"
        full_path = f"{batch}/videos/Videos_{prefix}{level_str}/video/{video_file}"

        target = f"{settings.nginx_video_host}/{full_path}"
        logger.info(f"get_video_redirect_url -> {target}")
        return target

    async def get_video_fps(self, video_name: str) -> APIResponse:
        """`video_name` with or without the .mp4 extension."""
        settings = get_settings()
        batch = get_batch(video_name)
        with open(settings.fps_path[batch], encoding="utf-8-sig") as infile:
            fps = ujson.load(infile)[video_name.replace(".mp4", "")]

        logger.info(f"Got video fps: {video_name}: {fps}")
        return APIResponse(
            status=HTTPStatus.OK.value,
            message="Success",
            data=fps,
        )
