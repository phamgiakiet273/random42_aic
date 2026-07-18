"""Dominant-color rerank router — prefix `/rerank`. Replaces `routes/rerank_router.py`."""

from __future__ import annotations

from fastapi import APIRouter, Body

from src.common.schemas.api import APIResponse
from src.common.schemas.rerank import VideoMetadata
from src.services.rerank_service import RerankService


def build_router(service: RerankService) -> APIRouter:
    router = APIRouter(prefix="/rerank", tags=["rerank"])

    @router.get("/ping")
    async def ping() -> APIResponse:
        return await service.ping()

    @router.post("/rerank_color")
    async def rerank_color(videos: list[VideoMetadata] = Body(...)) -> APIResponse:
        return await service.color_rerank(videos)

    return router
