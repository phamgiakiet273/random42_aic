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
from src.utils.dataset_layout import frame_relpath, video_prefix, video_relpath
from src.utils.video_batch import get_batch

logger = get_logger()


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
        # dataset_layout owns the naming rule; the old hand-built
        # "Keyframes_{L|K}<level>" could not express N001 or S01.
        full_path = frame_relpath(get_batch(video_name), video_name, frame_name)
        target = f"{settings.nginx_image_host}/{full_path}"
        logger.info(f"get_image_redirect_url -> {target}")
        return target

    async def get_image_original_redirect_url(
        self, video_name: str, frame_name: str
    ) -> str:
        """Nginx redirect URL for the original (.jpg) frame image.

        Legacy always built "Keyframes_L<level>" here, even for batch-1 videos.
        The prefix now comes from the name itself (dataset_layout.video_prefix),
        so N001/S01 resolve too.
        """
        settings = get_settings()
        base = frame_name
        if base.lower().endswith(".avif") or base.lower().endswith(".jpg"):
            base = base.rsplit(".", 1)[0]

        batch = get_batch(video_name)
        full_path = f"{batch}/frames/{settings.split_name}/Keyframes_{video_prefix(video_name)}/keyframes/{video_name}/{base}.jpg"
        target = f"{settings.nginx_image_host}/{full_path}"
        logger.info(f"get_image_original_redirect_url -> {target}")
        return target

    async def get_video_redirect_url(self, video_name: str) -> str:
        """Nginx redirect URL for the source video:
        "<batch>/videos/Videos_{L|K}<level>/video/<video_name>.mp4"
        """
        settings = get_settings()
        full_path = video_relpath(get_batch(video_name), video_name)
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
