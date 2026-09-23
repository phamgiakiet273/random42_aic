"""DRES submission router -- prefix `/submission`. Replaces `routes/submission_router.py`.

Served ONLY by the central submission service (SERVICE=submission). Hubs do not
mount it; they forward `/submission/*` here (src/apis/submission_proxy.py).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.common.schemas.api import APIResponse
from src.common.schemas.submission import (
    SubmitKISRequest,
    SubmitQARequest,
    SubmitTRAKERequest,
)
from src.services.submission_service import DRESSubmitError, SubmissionService


def build_router(service: SubmissionService) -> APIRouter:
    router = APIRouter(prefix="/submission", tags=["submission"])
    async def _call(fn, request):
        try:
            return await fn(request)
        except DRESSubmitError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    @router.get("/ping")
    async def ping() -> APIResponse:
        return await service.ping()

    @router.get("/get_session_and_eval")
    async def get_session_and_eval() -> APIResponse:
        return await service.get_session_and_eval()

    @router.get("/get_session_id")
    async def get_session_id() -> APIResponse:
        return await service.get_session_id()

    @router.get("/get_eval_id")
    async def get_eval_id(session_id: str | None = None) -> APIResponse:
        return await service.get_eval_id(session_id)

    @router.post("/submit_kis")
    async def submit_kis(request: SubmitKISRequest) -> APIResponse:
        return await _call(service.submit_kis, request)

    @router.post("/submit_qa")
    async def submit_qa(request: SubmitQARequest) -> APIResponse:
        return await _call(service.submit_qa, request)

    @router.post("/submit_trake")
    async def submit_trake(request: SubmitTRAKERequest) -> APIResponse:
        return await _call(service.submit_trake, request)

    @router.get("/relogin")
    async def relogin() -> APIResponse:
        return await service.relogin()

    return router
