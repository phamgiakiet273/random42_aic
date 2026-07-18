"""CLIP-backed vector search router, mounted 3x (siglip_alpha / siglip_beta / metaclip).

Replaces `routes/SIGLIP_v2_router.py`, `routes/SIGLIP_v2_B_router.py`, and
`routes/METACLIP_router.py` — those were three copy-pasted routers wrapping
three copy-pasted handler classes; `ClipSearchService` already collapsed the
handlers into one class (see src/services/clip_service.py), so this collapses
the routers into one too, parameterized by `prefix`.
"""

from __future__ import annotations

from fastapi import APIRouter

from src.common.schemas.api import APIResponse
from src.common.schemas.vector import QdrantRequest, RetrievalRequest
from src.services.clip_service import ClipSearchService
from src.utils.settings import get_settings

# Per-variant Settings field names used to default `setup_database`'s
# collection-specific arguments. `unique_json_path` is deliberately excluded:
# it has no dedicated Settings field (see ClipSearchService.setup_database),
# so callers must always pass it explicitly.
_VARIANT_SETTINGS_FIELDS = {
    "siglip_alpha": (
        "siglip_v2_database_name",
        "siglip_v2_features_size",
        "siglip_v2_features_path",
        "siglip_v2_dummy_vector_path",
    ),
    "siglip_beta": (
        "siglip_v2_b_database_name",
        "siglip_v2_b_features_size",
        "siglip_v2_b_features_path",
        "siglip_v2_b_dummy_vector_path",
    ),
    "metaclip": (
        "metaclip_database_name",
        "metaclip_features_size",
        "metaclip_features_path",
        "metaclip_dummy_vector_path",
    ),
}


def build_router(service: ClipSearchService, prefix: str) -> APIRouter:
    """`prefix` is also used (stripped of its leading slash) to look up this
    variant's `setup_database` defaults in `_VARIANT_SETTINGS_FIELDS`."""
    router = APIRouter(prefix=prefix, tags=[prefix.lstrip("/")])
    variant = prefix.lstrip("/")

    @router.get("/ping")
    async def ping() -> APIResponse:
        return await service.ping()

    @router.get("/setup_database")
    async def setup_database(
        unique_json_path: str,
        collection_name: str | None = None,
        feature_size: int | None = None,
        dummy_vector_path: str | None = None,
        create_collection: bool = True,
    ) -> APIResponse:
        settings = get_settings()
        field_names = _VARIANT_SETTINGS_FIELDS.get(variant)
        features_path = None
        if field_names:
            db_field, size_field, feats_field, dummy_field = field_names
            collection_name = collection_name or getattr(settings, db_field)
            feature_size = feature_size or getattr(settings, size_field)
            features_path = getattr(settings, feats_field)
            dummy_vector_path = dummy_vector_path or getattr(settings, dummy_field)
        return await service.setup_database(
            collection_name=collection_name,
            feature_size=feature_size,
            features_path=features_path,
            unique_json_path=unique_json_path,
            dummy_vector_path=dummy_vector_path,
            create_collection=create_collection,
        )

    @router.post("/scroll")
    async def scroll(req: QdrantRequest) -> APIResponse:
        return await service.scroll(
            k=req.k,
            video_filter=req.video_filter or "",
            time_in=req.time_in,
            time_out=req.time_out,
            s2t_filter=req.s2t_filter,
            utility_feature=req.utility_feature or "shot",
            frame_class_filter=req.frame_class_filter,
            skip_frames=req.skip_frames,
            return_s2t=req.return_s2t,
            return_object=req.return_object,
        )

    @router.post("/text_search")
    async def text_search(req: RetrievalRequest) -> APIResponse:
        return await service.text_search(
            text=req.text,
            k=req.k,
            video_filter=req.video_filter,
            s2t_filter=req.s2t_filter,
            return_s2t=req.return_s2t,
            return_object=req.return_object,
            frame_class_filter=req.frame_class_filter,
            skip_frames=req.skip_frames,
            sort_to_news=req.sort_to_news,
        )

    @router.post("/image_search")
    async def image_search(req: RetrievalRequest) -> APIResponse:
        return await service.image_search(
            image_data=req.image_data,
            k=req.k,
            video_filter=req.video_filter,
            s2t_filter=req.s2t_filter,
            return_s2t=req.return_s2t,
            return_object=req.return_object,
            frame_class_filter=req.frame_class_filter,
            skip_frames=req.skip_frames,
            sort_to_news=req.sort_to_news,
        )

    @router.post("/temporal_search")
    async def temporal_search(req: RetrievalRequest) -> APIResponse:
        return await service.temporal_search(
            texts=req.text,
            main_event_index=req.main_event_index or 0,
            k=req.k,
            video_filter=req.video_filter,
            s2t_filter=req.s2t_filter,
            return_s2t=req.return_s2t,
            return_object=req.return_object,
            frame_class_filter=req.frame_class_filter,
            skip_frames=req.skip_frames,
        )

    return router
