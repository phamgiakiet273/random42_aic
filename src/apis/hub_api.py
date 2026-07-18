"""Hub gateway router — prefix `/hub`.

Replaces `routes/hub_router.py` + the hub-facing endpoints of
`handlers/hub_handler.py`. Swagger example defaults on `Form(...)` params are
kept here (this is the right layer for them), matching the legacy router.

Legacy only wired `siglip_alpha_*`/`siglip_beta_*` passthrough routes; the
`/{variant}_*` routes below are generated for `siglip_alpha`, `siglip_beta`,
*and* `metaclip` since `HubGatewayService` generalized its passthrough methods
over a `variant` argument (see src/services/hub_service.py) instead of one
copy-pasted method set per CLIP backend.
"""

from __future__ import annotations

import ujson
from fastapi import APIRouter, Form
from fastapi.responses import FileResponse, RedirectResponse

from src.common.schemas.api import APIResponse
from src.common.schemas.rerank import VideoMetadata
from src.services.hub_service import HubGatewayService

_CLIP_VARIANTS = ("siglip_alpha", "siglip_beta", "metaclip")


def _register_clip_variant_routes(
    router: APIRouter, service: HubGatewayService, variant: str
) -> None:
    """Register the 4 passthrough routes (text/image/temporal/scroll) for one CLIP variant."""

    async def text_search(
        text: str = Form(...),
        k: int = Form(100),
        video_filter: str | None = Form(None),
        s2t_filter: str | None = Form(None),
        return_s2t: bool = Form(True),
        return_object: bool = Form(True),
        frame_class_filter: str = Form("[]"),
        skip_frames: str = Form("[]"),
        sort_to_news: bool = Form(True),
    ) -> APIResponse:
        return await service.clip_text_search(
            variant,
            text,
            k=k,
            video_filter=video_filter,
            s2t_filter=s2t_filter,
            return_s2t=return_s2t,
            return_object=return_object,
            frame_class_filter=ujson.loads(frame_class_filter),
            skip_frames=ujson.loads(skip_frames),
            sort_to_news=sort_to_news,
        )

    async def image_search(
        image_path: str = Form(...),
        k: int = Form(100),
        video_filter: str | None = Form(None),
        s2t_filter: str | None = Form(None),
        return_s2t: bool = Form(True),
        return_object: bool = Form(True),
        frame_class_filter: str = Form("[]"),
        skip_frames: str = Form("[]"),
        sort_to_news: bool = Form(True),
    ) -> APIResponse:
        return await service.clip_image_search_from_path(
            variant,
            image_path,
            k=k,
            video_filter=video_filter,
            s2t_filter=s2t_filter,
            return_s2t=return_s2t,
            return_object=return_object,
            frame_class_filter=ujson.loads(frame_class_filter),
            skip_frames=ujson.loads(skip_frames),
            sort_to_news=sort_to_news,
        )

    async def temporal_search(
        text: str = Form(...),
        k: int = Form(100),
        video_filter: str | None = Form(None),
        s2t_filter: str | None = Form(None),
        return_s2t: bool = Form(True),
        return_object: bool = Form(True),
        frame_class_filter: str = Form("[]"),
        skip_frames: str = Form("[]"),
        sort_to_news: bool = Form(True),
        main_event_index: int = Form(0),
    ) -> APIResponse:
        return await service.clip_temporal_search(
            variant,
            text,
            k=k,
            video_filter=video_filter,
            s2t_filter=s2t_filter,
            return_s2t=return_s2t,
            return_object=return_object,
            frame_class_filter=ujson.loads(frame_class_filter),
            skip_frames=ujson.loads(skip_frames),
            sort_to_news=sort_to_news,
            main_event_index=main_event_index,
        )

    async def scroll(
        k: int = Form(100),
        video_filter: str = Form(...),
        s2t_filter: str | None = Form(None),
        time_in: str | None = Form(None),
        time_out: str | None = Form(None),
        return_s2t: bool = Form(True),
        return_object: bool = Form(True),
        frame_class_filter: str = Form("[]"),
        skip_frames: str = Form("[]"),
        sort_to_news: bool = Form(True),
        utility_feature: str = Form("shot"),
    ) -> APIResponse:
        return await service.clip_scroll(
            variant,
            k=k,
            video_filter=video_filter,
            s2t_filter=s2t_filter,
            time_in=time_in,
            time_out=time_out,
            return_s2t=return_s2t,
            return_object=return_object,
            frame_class_filter=ujson.loads(frame_class_filter),
            skip_frames=ujson.loads(skip_frames),
            sort_to_news=sort_to_news,
            utility_feature=utility_feature,
        )

    router.add_api_route(f"/{variant}_text_search", text_search, methods=["POST"])
    router.add_api_route(f"/{variant}_image_search", image_search, methods=["POST"])
    router.add_api_route(
        f"/{variant}_temporal_search", temporal_search, methods=["POST"]
    )
    router.add_api_route(f"/{variant}_scroll", scroll, methods=["POST"])


def build_router(service: HubGatewayService) -> APIRouter:
    router = APIRouter(prefix="/hub", tags=["hub"])

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

    for variant in _CLIP_VARIANTS:
        _register_clip_variant_routes(router, service, variant)

    return router
