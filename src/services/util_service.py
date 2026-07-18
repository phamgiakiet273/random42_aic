"""Business logic for the util service: translation, neighboring-frame lookup,
per-batch video name listing, and vector (shot) lookup.
"""

from __future__ import annotations

import re
from http import HTTPStatus

from src.common.schemas.api import APIResponse
from src.externals.qdrant_client import QdrantSearchClient
from src.externals.translate_client import TranslateClient
from src.utils.logger import get_logger
from src.utils.metadata import get_frame_path
from src.utils.settings import get_settings
from src.utils.video_batch import get_neighboring_frames as _get_neighboring_frames
from src.utils.video_names import get_video_names as _get_video_names

logger = get_logger()

# Splits text on '.' while keeping the trailing period attached to each sentence.
_SENTENCE_SPLIT_RE = re.compile(r"[^.]+(?:\.)?")


class UtilService:
    def __init__(
        self,
        translate_client: TranslateClient | None = None,
        vector_client: QdrantSearchClient | None = None,
    ) -> None:
        self.translate_client = translate_client or TranslateClient()
        # Optional: only required by get_vector(). Pass the QdrantSearchClient
        # instance of whichever CLIP-search variant this deployment looks up
        # vectors for (e.g. the SigLIP v2 collection).
        self.vector_client = vector_client

    async def ping(self) -> APIResponse:
        logger.info("ping invoked")
        return APIResponse(
            status=HTTPStatus.OK.value,
            message="Running (Healthy)",
            data="ping",
        )

    async def translate(
        self, text: str, target: str = "en", source: str | None = None
    ) -> APIResponse:
        """Split `text` into sentences and translate each individually via Google
        Translate, re-joining with spaces. Preserves a trailing '.' per sentence
        if the source sentence had one and the translation dropped it."""
        sentences = _SENTENCE_SPLIT_RE.findall(text)
        translated_sentences = []

        for sentence in sentences:
            sentence_strip = sentence.strip()
            if not sentence_strip:
                continue
            translated_text = await self.translate_client.translate(
                sentence_strip, target=target, source=source
            )
            if sentence_strip.endswith(".") and not translated_text.endswith("."):
                translated_text += "."
            translated_sentences.append(translated_text.strip())

        final_text = " ".join(translated_sentences)
        return APIResponse(
            status=HTTPStatus.OK.value,
            message="Translation successful",
            data=final_text,
        )

    async def get_neighboring_frames(
        self, frame_num: str, video_name: str, k: int = 3
    ) -> APIResponse:
        """Thin wrapper over `video_batch.get_neighboring_frames`, returning paths
        relative to `base_path` (as the legacy handler did) instead of absolute ones."""
        prev_frames, next_frames = _get_neighboring_frames(
            frame_num=frame_num, video_name=video_name, k=k
        )

        base_path = get_settings().base_path
        if not base_path.endswith("/"):
            base_path += "/"
        prev_frames = [p.replace(base_path, "") for p in prev_frames]
        next_frames = [p.replace(base_path, "") for p in next_frames]

        return APIResponse(
            status=HTTPStatus.OK.value,
            message="Success",
            data={"prev_frames": prev_frames, "next_frames": next_frames},
        )

    async def get_video_names(self, batch_ids: list[int]) -> APIResponse:
        """Thin wrapper over `video_names.get_video_names`."""
        video_names = _get_video_names(batch_ids)
        return APIResponse(
            status=HTTPStatus.OK.value, message="Success", data=video_names
        )

    async def get_vector(self, video_name: str, frame_name: str) -> APIResponse:
        """Return the frame paths of every frame in the same shot as (video_name, frame_name).

        Replaces the legacy `get_vector_handler`, which bypassed all config via a
        module-level `QdrantClient(url="http://localhost:6333")`, a hardcoded
        "PUMPKING_SIGLIP_V2" collection name, and a stale hardcoded dataset path
        ("/dataset/AIC2024/pumkin_dataset/Vinh"). This version uses the injected
        `QdrantSearchClient` (configured by the caller) and the shared
        `get_frame_path` helper for path construction.
        """
        if self.vector_client is None:
            raise RuntimeError(
                "UtilService.get_vector requires a QdrantSearchClient to be configured"
            )

        anchor_matches = self.vector_client.scroll_video(
            k=1,
            video_filter=video_name,
            time_in=frame_name,
            time_out=frame_name,
            feature="shot",
            return_s2t=False,
            return_object=False,
        )
        if not anchor_matches:
            # Same caveat the legacy comment called out: this only works if the
            # frame is actually indexed in the vector database.
            raise LookupError(
                f"Frame not found in vector database: {video_name}/{frame_name}"
            )

        anchor = anchor_matches[0]
        shot_frames = self.vector_client.scroll_video(
            k=10000,
            video_filter=video_name,
            time_in=anchor["related_start_frame"],
            time_out=anchor["related_end_frame"],
            feature="shot",
            return_s2t=False,
            return_object=False,
        )

        frame_paths = [
            get_frame_path(int(item["idx_folder"]), video_name, item["keyframe_id"])
            for item in shot_frames
        ]
        return APIResponse(
            status=HTTPStatus.OK.value, message="Success", data=frame_paths
        )
