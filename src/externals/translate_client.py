"""Thin async HTTP client for the Google Cloud Translation v2 REST API."""

from __future__ import annotations

import httpx

from src.utils.logger import get_logger
from src.utils.settings import get_settings

logger = get_logger()


class TranslateClient:
    """Wraps a single-string call to the Google Translate v2 endpoint."""

    def __init__(
        self,
        api_key: str | None = None,
        endpoint: str | None = None,
        timeout: int | None = None,
    ):
        settings = get_settings()
        self.api_key = api_key or settings.gg_translate_api_key
        self.endpoint = endpoint or settings.gg_translate_endpoint
        self.timeout = timeout or settings.request_timeout

    async def translate(
        self, text: str, target: str = "en", source: str | None = None
    ) -> str:
        """Translate a single string; raises httpx.HTTPStatusError on a non-2xx response."""
        params = {
            "q": text,
            "source": source,
            "target": target,
            "format": "text",
            "key": self.api_key,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(self.endpoint, data=params)
        resp.raise_for_status()
        result = resp.json()
        return result["data"]["translations"][0]["translatedText"]
