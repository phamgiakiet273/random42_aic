"""Generic envelope used for every API response."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class APIResponse(BaseModel):
    status: int
    message: str
    data: Any | None = None
