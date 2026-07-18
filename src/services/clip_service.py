"""Generic CLIP-backed vector search service.

Legacy had three near-identical handler classes — SIGLIPV2Handler,
SIGLIPV2BetaHandler, METACLIPHandler (handlers/SIGLIP_v2_handler.py,
handlers/SIGLIP_v2_B_handler.py, handlers/METACLIP_handler.py) — that only
differed in which CLIP model + Qdrant collection they wrapped. This single
class replaces all three: construct it with an already-instantiated model
(Siglip2Model or MetaclipModel — both duck-type get_image_features /
get_text_features) and an already-instantiated QdrantSearchClient wired to
that variant's collection, and inject the right pair per deployed process
(SIGLIP2 alpha / SIGLIP2 beta / MetaCLIP).

Design change vs. legacy: response post-processing (rewriting each result's
video_path/frame_path to dataset-relative paths) now lives here instead of
being duplicated in the hub gateway once per CLIP variant. The hub becomes a
pure passthrough proxy for these responses (see src/services/hub_service.py) —
this collapses what used to be 2x-3x copies of the same rewriting loop into
one place.
"""

from __future__ import annotations

import base64
import os
import time
from http import HTTPStatus

import numpy as np

from src.common.schemas.api import APIResponse
from src.externals.qdrant_client import QdrantSearchClient
from src.modules.vector_search.fusion import preprocessing_image, preprocessing_text
from src.utils.logger import get_logger
from src.utils.metadata import bytes_to_pil_image, get_frame_path, get_video_path
from src.utils.settings import get_settings

logger = get_logger()


class ClipSearchService:
    """Text/image/temporal vector search over a single Qdrant collection.

    `model` is duck-typed: anything exposing `get_image_features(PIL.Image) ->
    np.ndarray` and `get_text_features(str) -> np.ndarray` works (Siglip2Model,
    MetaclipModel, ...).
    """

    def __init__(self, model, qdrant: QdrantSearchClient) -> None:
        self.model = model
        self.qdrant = qdrant
        self._settings = get_settings()
        logger.info(
            f"Initialized ClipSearchService (model={type(model).__name__}, "
            f"collection={qdrant.collection_name})"
        )

    async def ping(self) -> APIResponse:
        logger.debug("ping invoked")
        return APIResponse(
            status=HTTPStatus.OK.value, message="Running (Healthy)", data="ping"
        )

    async def setup_database(
        self,
        collection_name: str,
        feature_size: int,
        features_path: list[str],
        unique_json_path: str,
        dummy_vector_path: str,
        keyframe_folder_path: str | None = None,
        split_name: str | None = None,
        s2t_path: list[str] | None = None,
        fps_path: list[str] | None = None,
        shot_path: list[str] | None = None,
        create_collection: bool = True,
    ) -> APIResponse:
        """Build (or rebuild) this variant's Qdrant collection from feature .npy dumps.

        `keyframe_folder_path` / `split_name` / `s2t_path` / `fps_path` /
        `shot_path` are shared across all 3 CLIP variants, so they default to
        `get_settings()`'s values. `collection_name` / `feature_size` /
        `features_path` / `dummy_vector_path` (and `unique_json_path`, which has
        no dedicated settings field) differ per variant, so the caller
        (main.py, reading that variant's own `siglip_v2_*` / `siglip_v2_b_*` /
        `metaclip_*` settings fields) must supply them explicitly.
        """
        settings = self._settings
        keyframe_folder_path = keyframe_folder_path or settings.dataset_path_team
        split_name = split_name or settings.split_name
        s2t_path = s2t_path or settings.s2t_path
        fps_path = fps_path or settings.fps_path
        shot_path = shot_path or settings.shot_path

        logger.info(
            f"Setting up database {collection_name}, expecting up to 60 minutes to finish"
        )
        start = time.time()
        self.qdrant.add_database(
            collection_name=collection_name,
            feature_size=feature_size,
            keyframe_folder_path=keyframe_folder_path,
            features_path=features_path,
            split_name=split_name,
            s2t_path=s2t_path,
            fps_path=fps_path,
            shot_path=shot_path,
            unique_json_path=unique_json_path,
            create_collection=create_collection,
        )

        dummy_query = np.load(dummy_vector_path).reshape(1, -1).astype("float32")[0]
        logger.info("Warming up with dummy query")
        # Legacy called `self.qdrant.search(dummy_query, 3, "", "", "")` positionally,
        # which passed `""` as frame_class_filter (should be a list). Use keywords
        # against the actual signature instead of replicating that bug.
        self.qdrant.search(dummy_query, k=3)
        logger.info("Dummy query finished, ready to use!")

        return APIResponse(
            status=HTTPStatus.OK.value,
            message="Success",
            data={"time_taken_seconds": time.time() - start},
        )

    async def scroll(
        self,
        k: int,
        video_filter: str,
        time_in: str | None = None,
        time_out: str | None = None,
        s2t_filter: str | None = None,
        utility_feature: str = "shot",
        frame_class_filter: list[int] | None = None,
        skip_frames: list[dict] | None = None,
        return_s2t: bool = True,
        return_object: bool = True,
    ) -> APIResponse:
        logger.info(
            f"scroll called with k={k}, video_filter={video_filter}, s2t_filter={s2t_filter}, "
            f"time_in={time_in}, time_out={time_out}, feature={utility_feature}"
        )
        result = self.qdrant.scroll_video(
            k=k,
            video_filter=video_filter,
            time_in=time_in,
            time_out=time_out,
            s2t_filter=s2t_filter,
            feature=utility_feature,
            frame_class_filter=frame_class_filter,
            skip_frames=skip_frames or [],
            return_s2t=return_s2t,
            return_object=return_object,
        )
        logger.info("Scroll video retrieval completed")
        result = self._add_paths(result)
        return APIResponse(status=HTTPStatus.OK.value, message="Success", data=result)

    async def text_search(
        self,
        text: str,
        k: int = 100,
        video_filter: str | list[str] | None = None,
        s2t_filter: str | None = None,
        return_s2t: bool = True,
        return_object: bool = True,
        frame_class_filter: list[int] | None = None,
        skip_frames: list[dict] | None = None,
        sort_to_news: bool = True,
    ) -> APIResponse:
        logger.info(
            f"text_search called with text={text}, k={k}, video_filter={video_filter}"
        )
        if not text:
            raise ValueError("Missing text for search")

        feat = preprocessing_text(self.model, text)
        logger.info("Text feature extracted for search")
        result = self.qdrant.search(
            query=feat,
            k=k,
            video_filter=video_filter or "",
            s2t_filter=s2t_filter,
            frame_class_filter=frame_class_filter,
            skip_frames=skip_frames or [],
            sort_to_news=sort_to_news,
            return_s2t=return_s2t,
            return_object=return_object,
        )
        logger.info(f"Text search completed with query {text!r}")
        result = self._add_paths(result)
        return APIResponse(status=HTTPStatus.OK.value, message="Success", data=result)

    async def image_search(
        self,
        image_data: str | bytes,
        k: int = 100,
        video_filter: str | list[str] | None = None,
        s2t_filter: str | None = None,
        return_s2t: bool = True,
        return_object: bool = True,
        frame_class_filter: list[int] | None = None,
        skip_frames: list[dict] | None = None,
        sort_to_news: bool = True,
    ) -> APIResponse:
        logger.info(f"image_search called with k={k}")
        if not image_data:
            raise ValueError("Missing image_data for search")

        raw_bytes = (
            base64.b64decode(image_data) if isinstance(image_data, str) else image_data
        )
        image = bytes_to_pil_image(raw_bytes)
        feat = preprocessing_image(self.model, image)
        logger.info("Image feature extracted for search")
        result = self.qdrant.search(
            query=feat,
            k=k,
            video_filter=video_filter or "",
            s2t_filter=s2t_filter,
            frame_class_filter=frame_class_filter,
            skip_frames=skip_frames or [],
            sort_to_news=sort_to_news,
            return_s2t=return_s2t,
            return_object=return_object,
        )
        logger.info("Image search completed")
        result = self._add_paths(result)
        return APIResponse(status=HTTPStatus.OK.value, message="Success", data=result)

    async def temporal_search(
        self,
        texts: list[str] | str,
        main_event_index: int = 0,
        k: int = 100,
        video_filter: list[str] | str | None = None,
        s2t_filter: str | None = None,
        return_s2t: bool = True,
        return_object: bool = True,
        frame_class_filter: list[int] | None = None,
        skip_frames: list[dict] | None = None,
    ) -> APIResponse:
        """`texts` may be a pre-split list of per-event segments, or a single
        free-text string using legacy's "one sentence per event, period-separated"
        convention (`"a cat. then a dog."` -> `["a cat", "then a dog"]`).
        """
        logger.info(
            f"temporal_search called with texts={texts}, k={k}, video_filter={video_filter}"
        )
        if not texts:
            raise ValueError("Missing text for temporal search")

        if isinstance(texts, str):
            stripped = texts.rstrip(".")
            segments = [seg.strip() for seg in stripped.split(".") if seg.strip()]
        else:
            segments = [seg.strip() for seg in texts if seg and seg.strip()]

        if not segments:
            raise ValueError("No usable text segments for temporal search")

        feats = [preprocessing_text(self.model, seg) for seg in segments]
        logger.info("Features extracted for all temporal segments")

        result = self.qdrant.search_temporal(
            query_list=feats,
            query_main=main_event_index,
            k=k,
            video_filter=video_filter,
            s2t_filter=s2t_filter,
            frame_class_filter=frame_class_filter,
            skip_frames=skip_frames or [],
            return_s2t=return_s2t,
            return_object=return_object,
        )
        logger.info(f"Temporal search completed with query {segments}")
        result = self._add_paths_nested(result)
        return APIResponse(status=HTTPStatus.OK.value, message="Success", data=result)

    # ---- response post-processing ----

    def _add_paths(self, records: list[dict]) -> list[dict]:
        """Attach a display `index` plus dataset-relative `video_path`/`frame_path`
        to each flat result record (mutates and returns `records`)."""
        settings = self._settings
        for idx, record in enumerate(records):
            record["index"] = idx
            batch = int(record["idx_folder"])

            video_path = get_video_path(batch=batch, video_name=record["video_name"])
            record["video_path"] = os.path.relpath(
                video_path, settings.dataset_path_origin
            )

            frame_path = get_frame_path(
                batch=batch,
                video_name=record["video_name"],
                frame_name=record["keyframe_id"],
            )
            record["frame_path"] = os.path.relpath(
                frame_path, settings.dataset_path_team
            )
        return records

    def _add_paths_nested(self, chains: list[list[dict]]) -> list[list[dict]]:
        """Same as `_add_paths` but for temporal search's list-of-chains shape."""
        for chain in chains:
            self._add_paths(chain)
        return chains
