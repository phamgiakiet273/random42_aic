"""Business logic for submitting KIS/QA/TRAKE answers to the DRES evaluation server.

Login is no longer a constructor side effect (the legacy `SubmissionHandler`
auto-logged in inside `__init__`, so simply instantiating it made a network
call). Call `SubmissionService.login()` explicitly once -- e.g. from the app's
startup hook -- before using the other methods.
"""

from __future__ import annotations

import json
from http import HTTPStatus

from src.common.schemas.api import APIResponse
from src.common.schemas.submission import (
    SubmitKISRequest,
    SubmitQARequest,
    SubmitTRAKERequest,
)
from src.externals.dres_client import DRESClient
from src.utils.logger import get_logger

logger = get_logger()


class DRESSubmitError(RuntimeError):
    """Raised when a DRES `/submit` call returns a non-2xx response."""

    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


class SubmissionService:
    def __init__(self, dres_client: DRESClient | None = None) -> None:
        self.dres_client = dres_client or DRESClient()
        self.eval_id: str | None = None

    async def login(self) -> APIResponse:
        """Explicit login -- call once (e.g. at app startup), not from the constructor."""
        session_id = await self.dres_client.login()
        return APIResponse(
            status=HTTPStatus.OK.value,
            message="Login successful",
            data={"session_id": session_id},
        )

    async def ping(self) -> APIResponse:
        logger.info("ping invoked")
        return APIResponse(
            status=HTTPStatus.OK.value,
            message="Running (Healthy)",
            data="ping",
        )

    async def get_session_id(self) -> APIResponse:
        if not self.dres_client.session_id:
            await self.login()
        logger.info(f"Active SESSION ID: {self.dres_client.session_id}")
        return APIResponse(
            status=HTTPStatus.OK.value,
            message="Session ID fetched",
            data={"session_id": self.dres_client.session_id},
        )

    async def get_eval_id(self, session_id: str) -> APIResponse:
        if not session_id:
            raise ValueError("session_id is required")
        evaluations = await self.dres_client.get_evaluations(session_id)
        active_eval = next((e for e in evaluations if e["status"] == "ACTIVE"), None)
        if not active_eval:
            raise LookupError("No active evaluation found")
        self.eval_id = active_eval["id"]
        logger.info(f"Active EVAL ID: {self.eval_id}")
        return APIResponse(
            status=HTTPStatus.OK.value,
            message="Active evaluation ID fetched",
            data={"eval_id": self.eval_id},
        )

    async def submit_kis(self, request: SubmitKISRequest) -> APIResponse:
        payload = {
            "answerSets": [
                {
                    "answers": [
                        {
                            "mediaItemName": request.mediaItemName,
                            "start": request.start,
                            "end": request.end,
                        }
                    ]
                }
            ]
        }
        logger.info(f"KIS-{request.mediaItemName}-{request.start}-{request.end}")
        return await self._submit(request.eval_id, request.session_id, payload)

    async def submit_qa(self, request: SubmitQARequest) -> APIResponse:
        text = f"QA-{request.answer}-{request.video_id}-{request.time}"
        payload = {"answerSets": [{"answers": [{"text": text}]}]}
        logger.info(text)
        return await self._submit(request.eval_id, request.session_id, payload)

    async def submit_trake(self, request: SubmitTRAKERequest) -> APIResponse:
        elements = [e.strip() for e in request.frame_ids.split(",") if e.strip()]
        text = f"TR-{request.video_id}-{','.join(elements)}"
        payload = {"answerSets": [{"answers": [{"text": text}]}]}
        logger.info(text)
        return await self._submit(request.eval_id, request.session_id, payload)

    async def relogin(self) -> APIResponse:
        session_id = await self.dres_client.login()
        return APIResponse(
            status=HTTPStatus.OK.value,
            message="Re-login successful",
            data={"session_id": session_id},
        )

    async def _submit(
        self, eval_id: str, session_id: str, payload: dict
    ) -> APIResponse:
        """Shared POST + DRES error-detail parsing for the three submit_* methods
        (legacy duplicated this block three times, once per task type)."""
        resp = await self.dres_client.submit(eval_id, session_id, payload)
        if resp.status_code == 200:
            result = resp.json()
            return APIResponse(
                status=HTTPStatus.OK.value,
                message="Submit successful"
                if result.get("status")
                else "Submit failed",
                data=result,
            )

        error_message = resp.text
        try:
            error_data = resp.json()
            detail_str = error_data.get("detail")
            if detail_str and isinstance(detail_str, str):
                inner_data = json.loads(detail_str)
                specific_description = inner_data.get("description")
                if specific_description:
                    error_message = specific_description
        except Exception as e:
            logger.warning(f"Could not parse detailed error from response: {e}")

        logger.error(f"Submit failed ({resp.status_code}): {error_message}")
        raise DRESSubmitError(resp.status_code, error_message)
