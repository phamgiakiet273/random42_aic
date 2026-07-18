"""Thin async HTTP client for the DRES (eventretrieval) submission server."""

from __future__ import annotations

from typing import Any

import httpx

from src.utils.logger import get_logger
from src.utils.settings import get_settings

logger = get_logger()


class DRESClient:
    """Wraps login/session/submit calls to a DRES server. Call `.login()` explicitly before use."""

    def __init__(
        self,
        base_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
        timeout: int | None = None,
    ):
        settings = get_settings()
        self.base_url = (base_url or settings.submit_base_url).rstrip("/")
        self.username = username or settings.submit_username
        self.password = password or settings.submit_password
        self.timeout = timeout or settings.request_timeout
        self.session_id: str | None = None

    async def login(self) -> str:
        """Log in and store the session id; raises on failure instead of swallowing it."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/api/v2/login",
                json={"username": self.username, "password": self.password},
            )
        resp.raise_for_status()
        self.session_id = resp.json()["sessionId"]
        logger.info(f"DRES login successful, session_id: {self.session_id}")
        return self.session_id

    async def get_evaluations(self, session_id: str) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(
                f"{self.base_url}/api/v2/client/evaluation/list",
                params={"session": session_id},
            )
        resp.raise_for_status()
        return resp.json()

    async def submit(
        self, eval_id: str, session_id: str, payload: dict[str, Any]
    ) -> httpx.Response:
        """Generic answer-set submission; caller builds `payload`, this only performs the POST."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            return await client.post(
                f"{self.base_url}/api/v2/submit/{eval_id}",
                json=payload,
                params={"session": session_id},
            )
