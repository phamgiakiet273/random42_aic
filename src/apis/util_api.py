"""Misc util router — prefix `/util`. Replaces `routes/util_router.py`."""

from __future__ import annotations

from fastapi import APIRouter

from src.common.schemas.api import APIResponse
from src.common.schemas.util import (
    GetVectorRequest,
    GetVideoNameRequest,
    NeighboringFramesRequest,
    TranslateRequest,
)
from src.services.util_service import UtilService


def build_router(service: UtilService) -> APIRouter:
    router = APIRouter(prefix="/util", tags=["util"])

    @router.get("/ping")
    async def ping() -> APIResponse:
        return await service.ping()

    @router.post("/translate")
    async def translate(request: TranslateRequest) -> APIResponse:
        return await service.translate(
            request.text, target=request.target, source=request.source
        )

    @router.post("/get_neighboring_frames")
    async def get_neighboring_frames(request: NeighboringFramesRequest) -> APIResponse:
        return await service.get_neighboring_frames(
            request.frame_num, request.video_name, request.k
        )

    @router.post("/get_vector")
    async def get_vector(request: GetVectorRequest) -> APIResponse:
        return await service.get_vector(request.video_name, request.frame_name)

    @router.post("/get_video_names")
    async def get_video_names(request: GetVideoNameRequest) -> APIResponse:
        return await service.get_video_names(request.batch_id)

    return router
