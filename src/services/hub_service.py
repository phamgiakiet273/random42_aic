"""Hub gateway service — proxies frontend/CLI requests to the six backend
services (SIGLIP2 alpha, SIGLIP2 beta, MetaCLIP, rerank, util, submission)
plus nginx media redirects, and tracks the DRES session/eval id used by the
submit_* endpoints.

Replaces `handlers/hub_handler.py`. Framework-specific concerns (FastAPI
`Form(...)` defaults for Swagger docs, `RedirectResponse`/`FileResponse`
wrapping, route registration) live in `src/apis/hub_api.py` — this class only
takes plain typed parameters and returns `APIResponse` (or a plain string for
the redirect-target builders).

Deliberate deviations from the legacy handler (bug fixes, not ports):
  - The unconditional `open("debug_failed_image.bin", "wb")` write in the
    image-search-by-path path is gone — it was dead debug scaffolding that
    silently wrote to the process CWD on every call, image load failure or not.
  - `update_session_and_eval_ids`'s background refresh loop existed in legacy
    but was never scheduled (its `create_task(...)` call was commented out in
    `HubHandler.__init__`). It's implemented here as `start_session_refresh_loop`,
    an explicit opt-in coroutine the caller schedules from main.py's startup
    hook via `asyncio.create_task(...)` — it is not auto-started by `__init__`.
  - All `flask.json` / `ujson` mixing is gone in favor of `ujson` alone (no
    Flask import belongs in a FastAPI service).
  - All `*_HOST_PUBLIC` / `NGINX_*_HOST` / `SPLIT_NAME*` values come from
    `get_settings()` instead of ad hoc `os.getenv()` reads.
  - Response post-processing (video_path/frame_path rewriting) that legacy
    duplicated here once per CLIP variant now lives in `ClipSearchService`
    (see src/services/clip_service.py) — the backend already returns enriched
    records, so `clip_text_search`/`clip_image_search`/`clip_temporal_search`/
    `clip_scroll` below are pure passthroughs.
  - Legacy only wired siglip_alpha/siglip_beta proxying (no metaclip route
    existed in hub_handler.py/hub_router.py, even though `Settings` already
    has `metaclip_host_public`). The proxy methods here are generalized over a
    `variant` argument (`"siglip_alpha" | "siglip_beta" | "metaclip"`) so
    metaclip is a first-class option once a router wires it up, instead of
    requiring a fourth copy-pasted method set.
"""

from __future__ import annotations

import asyncio
import base64
import imghdr
from http import HTTPStatus
from io import BytesIO

import httpx
import ujson
from fastapi import HTTPException
from PIL import Image

from src.common.schemas.api import APIResponse
from src.common.schemas.rerank import VideoMetadata
from src.utils.logger import get_logger
from src.utils.settings import get_settings

logger = get_logger()


class HubGatewayService:
    """Gateway/orchestration layer sitting in front of the other 6 services."""

    _CLIP_VARIANTS = ("siglip_alpha", "siglip_beta", "metaclip")

    def __init__(self, request_timeout: int | None = None) -> None:
        self._settings = get_settings()
        self._timeout = request_timeout or self._settings.request_timeout
        self.session_id: str | None = None
        self.eval_id: str | None = None
        logger.info("Initialized HubGatewayService")

    # ---- health ----

    async def ping(self) -> APIResponse:
        logger.debug("ping invoked")
        return APIResponse(
            status=HTTPStatus.OK.value, message="Running (Healthy)", data="ping"
        )

    # ---- static file / media redirects ----

    def resolve_send_file_path(self, file_path: str) -> str:
        """No-op passthrough (legacy just did `FileResponse(file_path)` directly);
        kept for symmetry with the other send_* helpers below."""
        return file_path

    def build_image_redirect_target(self, full_path: str) -> str:
        """sample input: 0/frames/autoshot/Keyframes_L26/keyframes/L26_V264/06356.avif"""
        settings = self._settings
        full_path = full_path.replace(settings.split_name, settings.split_name_low_res)
        target = f"{settings.nginx_image_host}/{full_path}"
        logger.info(f"send_img redirect target: {target}")
        return target

    def build_image_original_redirect_target(self, full_path: str) -> str:
        settings = self._settings
        full_path = full_path.replace(settings.split_name_low_res, settings.split_name)
        full_path = full_path.replace(".avif", ".jpg")
        target = f"{settings.nginx_image_host}/{full_path}"
        logger.info(f"send_img_original redirect target: {target}")
        return target

    def build_video_redirect_target(self, full_path: str) -> str:
        target = f"{self._settings.nginx_video_host}/{full_path}"
        logger.info(f"send_video redirect target: {target}")
        return target

    # ---- rerank ----

    async def rerank_color(
        self, video_metadata_list: list[VideoMetadata]
    ) -> APIResponse:
        payload = [item.model_dump() for item in video_metadata_list]
        url = f"{self._settings.rerank_host_public}/rerank/rerank_color"
        json_data = await self._post_json(url, payload, "Rerank color")
        return APIResponse(
            status=HTTPStatus.OK.value, message="Running (Healthy)", data=json_data
        )

    # ---- translate ----

    async def translate(
        self, text: str, source: str | None = "", target: str = "en"
    ) -> APIResponse:
        url = f"{self._settings.util_host_public}/util/translate"
        payload = {"text": text, "source": source, "target": target}
        json_data = await self._post_json(url, payload, "Translate")
        return APIResponse(
            status=json_data.get("status", HTTPStatus.OK.value),
            message=json_data.get("message", "Translation result"),
            data=json_data.get("data"),
        )

    # ---- DRES session bookkeeping ----

    async def fetch_session_and_eval_id(self) -> tuple[str, str]:
        """Re-login then fetch the current session_id/eval_id from the submission
        service. Pure — does not mutate `self.session_id`/`self.eval_id`."""
        base_url = f"{self._settings.submission_host_public}/submission"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            relogin_resp = await client.get(f"{base_url}/relogin")
            if relogin_resp.status_code != 200:
                raise HTTPException(
                    status_code=relogin_resp.status_code,
                    detail=f"Re-login failed: {relogin_resp.text}",
                )

            session_resp = await client.get(f"{base_url}/get_session_id")
            if session_resp.status_code != 200:
                raise HTTPException(
                    status_code=session_resp.status_code,
                    detail=f"Error get_session_id: {session_resp.text}",
                )
            session_id = session_resp.json()["data"]["session_id"]

            eval_resp = await client.get(f"{base_url}/get_eval_id")
            if eval_resp.status_code != 200:
                raise HTTPException(
                    status_code=eval_resp.status_code,
                    detail=f"Error get_eval_id: {eval_resp.text}",
                )
            eval_id = eval_resp.json()["data"]["eval_id"]

        return session_id, eval_id

    async def get_session_and_eval_id(self) -> APIResponse:
        session_id, eval_id = await self.fetch_session_and_eval_id()
        return APIResponse(
            status=HTTPStatus.OK.value,
            message="Result",
            data={"session_id": session_id, "eval_id": eval_id},
        )

    async def update_session_eval_id(self) -> APIResponse:
        session_id, eval_id = await self.fetch_session_and_eval_id()
        self.session_id = session_id
        self.eval_id = eval_id
        return APIResponse(
            status=HTTPStatus.OK.value,
            message="Successfully updated",
            data={"session_id": session_id, "eval_id": eval_id},
        )

    async def start_session_refresh_loop(self, interval_seconds: int = 60) -> None:
        """Background loop refreshing `self.session_id`/`self.eval_id` forever.

        Not started automatically — schedule it explicitly from main.py's
        startup hook: `asyncio.create_task(hub_service.start_session_refresh_loop())`.
        """
        while True:
            try:
                self.session_id, self.eval_id = await self.fetch_session_and_eval_id()
                logger.info(
                    f"Updated session_id: {self.session_id}, eval_id: {self.eval_id}"
                )
            except Exception as exc:
                logger.error(f"Failed to update session_id and eval_id: {exc}")
            await asyncio.sleep(interval_seconds)

    # ---- DRES submission ----

    async def _submit(self, path: str, payload: dict, label: str) -> APIResponse:
        url = f"{self._settings.submission_host_public}/submission/{path}"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(url, json=payload)

        if response.status_code != 200:
            error_message = response.text
            try:
                error_data = response.json()
                specific_detail = error_data.get("detail")
                if specific_detail:
                    error_message = specific_detail
                    logger.error(f"{label} error detail: {error_message}")
            except Exception:
                pass
            raise HTTPException(status_code=response.status_code, detail=error_message)

        json_resp = response.json()
        return APIResponse(
            status=json_resp.get("status", HTTPStatus.OK.value),
            message=json_resp.get("message", "Submit result"),
            data=json_resp.get("data"),
        )

    async def submit_kis(
        self, media_item_name: str, start: int, end: int
    ) -> APIResponse:
        logger.info(f"Submit KIS: session_id={self.session_id}, eval_id={self.eval_id}")
        payload = {
            "session_id": self.session_id,
            "eval_id": self.eval_id,
            "mediaItemName": media_item_name,
            "start": start,
            "end": end,
        }
        return await self._submit("submit_kis", payload, "Submit KIS")

    async def submit_qa(self, answer: str, video_id: str, time: str) -> APIResponse:
        logger.info(f"Submit QA: session_id={self.session_id}, eval_id={self.eval_id}")
        payload = {
            "session_id": self.session_id,
            "eval_id": self.eval_id,
            "answer": answer,
            "video_id": video_id,
            "time": time,
        }
        return await self._submit("submit_qa", payload, "Submit QA")

    async def submit_trake(self, video_id: str, frame_ids: str) -> APIResponse:
        logger.info(
            f"Submit TRAKE: session_id={self.session_id}, eval_id={self.eval_id}"
        )
        payload = {
            "session_id": self.session_id,
            "eval_id": self.eval_id,
            "video_id": video_id,
            "frame_ids": frame_ids,
        }
        return await self._submit("submit_trake", payload, "Submit TRAKE")

    # ---- util passthroughs ----

    async def get_neighboring_frames(
        self, frame_num: str, video_name: str, k: int = 1
    ) -> APIResponse:
        if len(frame_num) < 5:
            frame_num = frame_num.zfill(5)
        url = f"{self._settings.util_host_public}/util/get_neighboring_frames"
        payload = {"frame_num": frame_num, "video_name": video_name, "k": k}
        json_data = await self._post_json(url, payload, "Util get_neighboring_frames")
        return APIResponse(
            status=json_data.get("status", HTTPStatus.OK.value),
            message=json_data.get("message", "Result"),
            data=json_data.get("data"),
        )

    async def get_vector_of_frame(
        self, video_name: str, frame_name: str
    ) -> APIResponse:
        url = f"{self._settings.util_host_public}/util/get_vector"
        payload = {"video_name": video_name, "frame_name": frame_name}
        json_data = await self._post_json(url, payload, "Util get_vector")
        return APIResponse(
            status=json_data.get("status", HTTPStatus.OK.value),
            message=json_data.get("message", "Result"),
            data=json_data.get("data"),
        )

    async def get_video_names_of_batch(self, batch_id: list[int]) -> APIResponse:
        url = f"{self._settings.util_host_public}/util/get_video_names"
        payload = {"batch_id": batch_id}
        json_data = await self._post_json(url, payload, "Util get_video_names")
        return APIResponse(
            status=json_data.get("status", HTTPStatus.OK.value),
            message=json_data.get("message", "Result"),
            data=json_data.get("data"),
        )

    # ---- CLIP backend passthrough (siglip_alpha / siglip_beta / metaclip) ----

    def _clip_host(self, variant: str) -> str:
        settings = self._settings
        hosts = {
            "siglip_alpha": settings.siglip_v2_host_public,
            "siglip_beta": settings.siglip_v2_b_host_public,
            "metaclip": settings.metaclip_host_public,
        }
        if variant not in hosts:
            raise ValueError(
                f"Unknown CLIP variant {variant!r}, expected one of {self._CLIP_VARIANTS}"
            )
        return hosts[variant]

    async def clip_text_search(
        self,
        variant: str,
        text: str,
        k: int = 100,
        video_filter: str | None = None,
        s2t_filter: str | None = None,
        return_s2t: bool = True,
        return_object: bool = True,
        frame_class_filter: list[int] | None = None,
        skip_frames: list[dict] | None = None,
        sort_to_news: bool = True,
    ) -> APIResponse:
        url = f"{self._clip_host(variant)}/{variant}/text_search"
        payload = {
            "text": text,
            "k": k,
            "video_filter": video_filter,
            "s2t_filter": s2t_filter,
            "return_s2t": return_s2t,
            "return_object": return_object,
            "frame_class_filter": frame_class_filter or [],
            "skip_frames": skip_frames or [],
            "sort_to_news": sort_to_news,
        }
        json_data = await self._post_json(url, payload, f"{variant} text_search")
        return APIResponse(
            status=HTTPStatus.OK.value,
            message="Running (Healthy)",
            data=json_data.get("data"),
        )

    async def clip_image_search(
        self,
        variant: str,
        image_data: str,
        k: int = 100,
        video_filter: str | None = None,
        s2t_filter: str | None = None,
        return_s2t: bool = True,
        return_object: bool = True,
        frame_class_filter: list[int] | None = None,
        skip_frames: list[dict] | None = None,
        sort_to_news: bool = True,
    ) -> APIResponse:
        """`image_data` is base64-encoded image bytes."""
        url = f"{self._clip_host(variant)}/{variant}/image_search"
        payload = {
            "image_data": image_data,
            "k": k,
            "video_filter": video_filter,
            "s2t_filter": s2t_filter,
            "return_s2t": return_s2t,
            "return_object": return_object,
            "frame_class_filter": frame_class_filter or [],
            "skip_frames": skip_frames or [],
            "sort_to_news": sort_to_news,
        }
        json_data = await self._post_json(url, payload, f"{variant} image_search")
        return APIResponse(
            status=HTTPStatus.OK.value,
            message="Running (Healthy)",
            data=json_data.get("data"),
        )

    async def clip_image_search_from_path(
        self,
        variant: str,
        image_path: str,
        k: int = 100,
        video_filter: str | None = None,
        s2t_filter: str | None = None,
        return_s2t: bool = True,
        return_object: bool = True,
        frame_class_filter: list[int] | None = None,
        skip_frames: list[dict] | None = None,
        sort_to_news: bool = True,
    ) -> APIResponse:
        """Accepts a `data:image/...` URI, an http(s) URL, or a local file path;
        re-encodes to RGB JPEG/base64 and delegates to `clip_image_search`.

        Note: legacy also wrote every loaded image to `debug_failed_image.bin`
        in the process CWD unconditionally (not just on failure) — that dead
        debug write has been removed here.
        """
        try:
            image_bytes = await self._load_image_bytes(image_path)
            logger.info(f"Image bytes length: {len(image_bytes)}")
            logger.info(
                f"Detected format by imghdr: {imghdr.what(None, h=image_bytes)}"
            )

            img = Image.open(BytesIO(image_bytes))
            if img.mode != "RGB":
                img = img.convert("RGB")
            buffered = BytesIO()
            img.save(buffered, format="JPEG")
            image_data = base64.b64encode(buffered.getvalue()).decode("utf-8")
        except Exception as exc:
            logger.exception(f"Image loading failed: {exc}")
            raise HTTPException(
                status_code=400, detail=f"Image loading failed: {exc}"
            ) from exc

        return await self.clip_image_search(
            variant,
            image_data,
            k=k,
            video_filter=video_filter,
            s2t_filter=s2t_filter,
            return_s2t=return_s2t,
            return_object=return_object,
            frame_class_filter=frame_class_filter,
            skip_frames=skip_frames,
            sort_to_news=sort_to_news,
        )

    async def clip_temporal_search(
        self,
        variant: str,
        text: str,
        k: int = 100,
        video_filter: str | None = None,
        s2t_filter: str | None = None,
        return_s2t: bool = True,
        return_object: bool = True,
        frame_class_filter: list[int] | None = None,
        skip_frames: list[dict] | None = None,
        sort_to_news: bool = True,
        main_event_index: int = 0,
    ) -> APIResponse:
        url = f"{self._clip_host(variant)}/{variant}/temporal_search"
        payload = {
            "text": text,
            "k": k,
            "video_filter": video_filter,
            "s2t_filter": s2t_filter,
            "return_s2t": return_s2t,
            "return_object": return_object,
            "frame_class_filter": frame_class_filter or [],
            "skip_frames": skip_frames or [],
            "sort_to_news": sort_to_news,
            "main_event_index": main_event_index,
        }
        json_data = await self._post_json(url, payload, f"{variant} temporal_search")
        return APIResponse(
            status=HTTPStatus.OK.value,
            message="Running (Healthy)",
            data=json_data.get("data"),
        )

    async def clip_scroll(
        self,
        variant: str,
        k: int = 100,
        video_filter: str = "",
        s2t_filter: str | None = None,
        time_in: str | None = None,
        time_out: str | None = None,
        return_s2t: bool = True,
        return_object: bool = True,
        frame_class_filter: list[int] | None = None,
        skip_frames: list[dict] | None = None,
        sort_to_news: bool = True,
        utility_feature: str = "shot",
    ) -> APIResponse:
        url = f"{self._clip_host(variant)}/{variant}/scroll"
        payload = {
            "k": k,
            "video_filter": video_filter,
            "s2t_filter": s2t_filter,
            "time_in": time_in,
            "time_out": time_out,
            "return_s2t": return_s2t,
            "return_object": return_object,
            "frame_class_filter": frame_class_filter or [],
            "skip_frames": skip_frames or [],
            "sort_to_news": sort_to_news,
            "utility_feature": utility_feature,
        }
        json_data = await self._post_json(url, payload, f"{variant} scroll")
        return APIResponse(
            status=HTTPStatus.OK.value,
            message="Running (Healthy)",
            data=json_data.get("data"),
        )

    # ---- shared HTTP helpers ----

    async def _load_image_bytes(self, image_path: str) -> bytes:
        if image_path.startswith("data:image/"):
            _, data = image_path.split(",", 1)
            return base64.b64decode(data)
        if image_path.startswith(("http://", "https://")):
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(image_path)
                response.raise_for_status()
            return response.content
        with open(image_path, "rb") as f:
            return f.read()

    async def _post_json(
        self, url: str, payload: dict | list, error_label: str
    ) -> dict:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(url, json=payload)
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"{error_label} error: {response.text}",
            )
        return ujson.loads(response.text)
