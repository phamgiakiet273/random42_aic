"""Hub gateway router — prefix `/hub`.

All retrieval modes share `POST /hub/search`; the form's `model` and
`search_type` fields select the configured backend and operation.
"""

from __future__ import annotations

from typing import Literal

import ujson
from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import FileResponse, RedirectResponse

from src.common.schemas.api import APIResponse
from src.common.schemas.rerank import VideoMetadata
from src.services.hub_service import HubGatewayService

SearchType = Literal["text", "image", "temporal", "scroll"]


def _parse_json_list(value: str, field_name: str) -> list:
    """Decode a form field that represents a JSON list."""
    try:
        parsed = ujson.loads(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=f"{field_name} must be valid JSON"
        ) from exc
    if not isinstance(parsed, list):
        raise HTTPException(status_code=400, detail=f"{field_name} must be a JSON list")
    return parsed


def build_router(service: HubGatewayService) -> APIRouter:
    router = APIRouter(prefix="/hub", tags=["hub"])

    @router.post("/search")
    async def search(
        model: str = Form(...),
        search_type: SearchType = Form(...),
        text: str | None = Form(None),
        image_path: str | None = Form(None),
        k: int = Form(100),
        video_filter: str | None = Form(None),
        s2t_filter: str | None = Form(None),
        time_in: str | None = Form(None),
        time_out: str | None = Form(None),
        return_s2t: bool = Form(True),
        return_object: bool = Form(True),
        frame_class_filter: str = Form("[]"),
        skip_frames: str = Form("[]"),
        sort_to_news: bool = Form(True),
        main_event_index: int = Form(0),
        utility_feature: str = Form("shot"),
    ) -> APIResponse:
        """Dispatch every retrieval operation through one stable hub endpoint."""
        if search_type in {"text", "temporal"} and not text:
            raise HTTPException(
                status_code=400, detail=f"text is required for search_type={search_type}"
            )
        if search_type == "image" and not image_path:
            raise HTTPException(
                status_code=400, detail="image_path is required for search_type=image"
            )
        if search_type == "scroll" and not video_filter:
            raise HTTPException(
                status_code=400, detail="video_filter is required for search_type=scroll"
            )

        return await service.search(
            model=model,
            search_type=search_type,
            text=text,
            image_path=image_path,
            k=k,
            video_filter=video_filter,
            s2t_filter=s2t_filter,
            time_in=time_in,
            time_out=time_out,
            return_s2t=return_s2t,
            return_object=return_object,
            frame_class_filter=_parse_json_list(
                frame_class_filter, "frame_class_filter"
            ),
            skip_frames=_parse_json_list(skip_frames, "skip_frames"),
            sort_to_news=sort_to_news,
            main_event_index=main_event_index,
            utility_feature=utility_feature,
        )

    @router.get("/ping")
    async def ping() -> APIResponse:
        return await service.ping()

    @router.get("/send_file/{file_path:path}")
    async def send_file(file_path: str):
        return FileResponse(service.resolve_send_file_path(file_path))

    @router.get("/send_img/{full_path:path}")
    async def send_img(full_path: str):
        return RedirectResponse(
            url=service.build_image_redirect_target(full_path), status_code=307
        )

    @router.get("/send_img_original/{full_path:path}")
    async def send_img_original(full_path: str):
        return RedirectResponse(
            url=service.build_image_original_redirect_target(full_path), status_code=307
        )

    @router.get("/send_video/{full_path:path}")
    async def send_video(full_path: str):
        return RedirectResponse(
            url=service.build_video_redirect_target(full_path), status_code=307
        )

    @router.post("/rerank_color")
    async def rerank_color(video_metadata_list: str = Form(...)) -> APIResponse:
        items = [VideoMetadata(**item) for item in ujson.loads(video_metadata_list)]
        return await service.rerank_color(items)

    @router.post("/translate")
    async def translate(
        text: str = Form(...),
        source: str | None = Form(""),
        target: str = Form("en"),
    ) -> APIResponse:
        return await service.translate(text, source=source, target=target)

    @router.post("/submit_KIS")
    async def submit_kis(
        mediaItemName: str = Form("K19_V006"),
        start: int = Form(1046169),
        end: int = Form(1046169),
    ) -> APIResponse:
        return await service.submit_kis(mediaItemName, start, end)

    @router.post("/submit_QA")
    async def submit_qa(
        answer: str = Form("?"),
        video_id: str = Form("L11_V018"),
        time: str = Form("359960"),
    ) -> APIResponse:
        return await service.submit_qa(answer, video_id, time)

    @router.post("/submit_TRAKE")
    async def submit_trake(
        video_id: str = Form("L11_V018"),
        frame_ids: str = Form("?"),
    ) -> APIResponse:
        return await service.submit_trake(video_id, frame_ids)

    @router.get("/get_session_and_eval_id")
    async def get_session_and_eval_id() -> APIResponse:
        return await service.get_session_and_eval_id()

    @router.get("/update_session_eval_id")
    async def update_session_eval_id() -> APIResponse:
        return await service.update_session_eval_id()

    @router.post("/get_neighboring_frames")
    async def get_neighboring_frames(
        frame_num: str = Form("12977"),
        video_name: str = Form("L18_V007"),
        k: int = Form(1),
    ) -> APIResponse:
        return await service.get_neighboring_frames(frame_num, video_name, k)

    @router.post("/get_vector_of_frame")
    async def get_vector_of_frame(
        video_name: str = Form("L18_V007"),
        frame_name: str = Form("12977"),
    ) -> APIResponse:
        return await service.get_vector_of_frame(video_name, frame_name)

    @router.post("/get_video_names_of_batch")
    async def get_video_names_of_batch(batch_id: str = Form("[0, 1]")) -> APIResponse:
        return await service.get_video_names_of_batch(ujson.loads(batch_id))

    return router
