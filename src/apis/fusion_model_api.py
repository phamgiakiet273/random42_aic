"""Expert-fusion router — mounted at `/fusion_model`.

Exposes the same `text_search` surface as the CLIP variants so the hub can
pass through to it like any other variant. Image/temporal/scroll are not
implemented (fusion targets short text queries); the hub frontend maps those
query types back to siglip_alpha for the FUSION_MODEL radio option.
"""

from __future__ import annotations

from fastapi import APIRouter

from src.common.schemas.api import APIResponse
from src.common.schemas.vector import RetrievalRequest
from src.services.fusion_model_service import FusionModelSearchService


def build_router(
    service: FusionModelSearchService, prefix: str = "/fusion_model"
) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=[prefix.lstrip("/")])

    @router.get("/ping")
    async def ping() -> APIResponse:
        return await service.ping()

    @router.post("/text_search")
    async def text_search(req: RetrievalRequest) -> APIResponse:
        return await service.text_search(
            text=req.text or "",
            k=req.k,
            video_filter=req.video_filter,
            s2t_filter=req.s2t_filter,
            return_s2t=req.return_s2t,
            return_object=req.return_object,
            frame_class_filter=req.frame_class_filter,
            skip_frames=req.skip_frames,
            sort_to_news=req.sort_to_news,
        )

    @router.post("/jina_text_search")
    async def jina_text_search(req: RetrievalRequest) -> APIResponse:
        """jina-clip-v2 alone — for A/B testing against SigLIP2 / fusion."""
        return await service.jina_text_search(
            text=req.text or "",
            k=req.k,
            video_filter=req.video_filter,
            s2t_filter=req.s2t_filter,
            return_s2t=req.return_s2t,
            return_object=req.return_object,
            frame_class_filter=req.frame_class_filter,
            skip_frames=req.skip_frames,
            sort_to_news=req.sort_to_news,
        )

    @router.post("/debug")
    async def debug(req: RetrievalRequest) -> APIResponse:
        """Raw per-expert lists + gating weights (diagnostics, k clamped to 100)."""
        return await service.debug_raw(text=req.text or "", k=min(req.k or 100, 100))

    return router
