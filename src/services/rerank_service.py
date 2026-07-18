"""Dominant-color reranking of candidate keyframes returned by a search query.

For each candidate frame, reads a precomputed per-frame color JSON, step-sorts
its color entries to pick a "dominant" color, then step-sorts the whole
candidate list by that color and cycles it so the originally top-scored frame
stays first (keeps the best match visible while grouping the rest by color).
"""

from __future__ import annotations

from http import HTTPStatus
from pathlib import Path

import ujson

from src.common.schemas.api import APIResponse
from src.common.schemas.rerank import VideoMetadata
from src.modules.rerank.color_sort import step_sort_key
from src.utils.logger import get_logger
from src.utils.settings import get_settings
from src.utils.video_batch import get_batch

logger = get_logger()


class RerankService:
    """Reranks a list of `VideoMetadata` candidates by dominant color."""

    def __init__(self, color_paths: list[str] | None = None) -> None:
        self.color_paths = (
            color_paths if color_paths is not None else get_settings().rerank_color_path
        )
        logger.info(f"RerankService initialized with color paths: {self.color_paths}")

    async def ping(self) -> APIResponse:
        logger.info("ping invoked")
        return APIResponse(
            status=HTTPStatus.OK.value,
            message="Running (Healthy)",
            data="ping",
        )

    async def color_rerank(self, videos: list[VideoMetadata]) -> APIResponse:
        """Sort `videos` by dominant color, then cycle so the highest-scored video is first."""
        logger.info(f"Starting color_rerank for {len(videos)} videos")
        keyed: list[tuple[VideoMetadata, tuple]] = []

        for vm in videos:
            video_name = vm.video_name.split(".")[0]
            level = video_name.split("_")[0][1:]
            batch = get_batch(video_name)
            # Legacy always read "Keyframes_L{level}", silently producing a wrong
            # (nonexistent) path for batch-1 videos, which are stored under
            # "Keyframes_K{level}". Branch on the resolved batch instead.
            prefix = "L" if batch == 0 else "K"

            base_dir = Path(self.color_paths[int(vm.idx_folder)])
            json_path = (
                base_dir
                / f"Keyframes_{prefix}{level}"
                / "keyframes"
                / video_name
                / f"{int(vm.keyframe_id):05d}.json"
            )
            if not json_path.exists():
                logger.error(f"Color JSON not found at path: {json_path}")
                raise FileNotFoundError(f"Color JSON not found: {json_path}")

            with open(json_path, "r") as f:
                color_data = ujson.load(f)

            # Normalize to a list of color entries (each with an "rgb" field).
            if isinstance(color_data, list):
                colors = color_data
            elif isinstance(color_data, dict) and "rgb" in color_data:
                colors = [color_data]
            else:
                colors = []

            if not colors:
                logger.warning(f"No colors found in color data for {json_path}")

            colors.sort(
                key=lambda c: step_sort_key(*c.get("rgb", (0, 0, 0)), repetitions=8)
            )
            dominant_rgb = (
                tuple(colors[0].get("rgb", (0, 0, 0))) if colors else (0, 0, 0)
            )
            video_key = step_sort_key(*dominant_rgb, repetitions=8)
            keyed.append((vm, video_key))

        keyed.sort(key=lambda pair: pair[1])
        sorted_videos = [pair[0] for pair in keyed]
        logger.info("Videos sorted by dominant color key")

        max_idx = max(
            range(len(sorted_videos)), key=lambda i: float(sorted_videos[i].score)
        )
        cycled = sorted_videos[max_idx:] + sorted_videos[:max_idx]
        logger.info("Cycled videos so that top score video is first")

        for idx, record in enumerate(cycled):
            record.index = idx

        return APIResponse(
            status=HTTPStatus.OK.value,
            message="Videos sorted by dominant color and cycled by top score",
            data=cycled,
        )
