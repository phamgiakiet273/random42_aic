"""DRES submission router — prefix `/submission`. Replaces `routes/submission_router.py`.

`SubmissionService.login()` is called from main.py's startup hook, not here —
see the module docstring in src/services/submission_service.py.
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

    @router.get("/ping")
    async def ping() -> APIResponse:
        return await service.ping()

    @router.get("/get_session_id")
    async def get_session_id() -> APIResponse:
        return await service.get_session_id()

    @router.get("/get_eval_id")
    async def get_eval_id(session_id: str) -> APIResponse:
        return await service.get_eval_id(session_id)

    @router.post("/submit_kis")
    async def submit_kis(request: SubmitKISRequest) -> APIResponse:
        try:
            return await service.submit_kis(request)
        except DRESSubmitError as exc:
            raise HTTPException(
                status_code=exc.status_code, detail=exc.message
            ) from exc

    @router.post("/submit_qa")
    async def submit_qa(request: SubmitQARequest) -> APIResponse:
        try:
            return await service.submit_qa(request)
        except DRESSubmitError as exc:
            raise HTTPException(
                status_code=exc.status_code, detail=exc.message
            ) from exc

    @router.post("/submit_trake")
    async def submit_trake(request: SubmitTRAKERequest) -> APIResponse:
        try:
            return await service.submit_trake(request)
        except DRESSubmitError as exc:
            raise HTTPException(
                status_code=exc.status_code, detail=exc.message
            ) from exc

    @router.get("/relogin")
    async def relogin() -> APIResponse:
        return await service.relogin()

    return router
