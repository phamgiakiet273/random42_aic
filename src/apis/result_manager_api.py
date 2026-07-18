"""Result-manager router — prefix `/result_manager`. Replaces `routes/result_manager_router.py`."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, RedirectResponse

from src.common.schemas.api import APIResponse
from src.services.result_manager_service import ResultManagerService


def build_router(service: ResultManagerService) -> APIRouter:
    router = APIRouter(prefix="/result_manager", tags=["result_manager"])

    @router.get("/ping")
    async def ping() -> APIResponse:
        return await service.ping()

    @router.get("/send_file/{file_path:path}")
    async def send_file(file_path: str):
        try:
            path = await service.send_file(file_path)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return FileResponse(path)

    @router.get("/send_img/{video_name}/{frame_name}")
    async def send_img(video_name: str, frame_name: str):
        target = await service.get_image_redirect_url(video_name, frame_name)
        return RedirectResponse(url=target, status_code=307)

    @router.get("/send_img_original/{video_name}/{frame_name}")
    async def send_img_original(video_name: str, frame_name: str):
        target = await service.get_image_original_redirect_url(video_name, frame_name)
        return RedirectResponse(url=target, status_code=307)

    @router.get("/send_video/{video_name}")
    async def send_video(video_name: str):
        target = await service.get_video_redirect_url(video_name)
        return RedirectResponse(url=target, status_code=307)

    @router.get("/get_fps/{video_name}")
    async def get_fps(video_name: str) -> APIResponse:
        return await service.get_video_fps(video_name)

    return router
