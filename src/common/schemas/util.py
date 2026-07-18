"""Request schemas for the misc util endpoints (translate, neighboring frames, vector lookup)."""

from __future__ import annotations

from pydantic import BaseModel


class TranslateRequest(BaseModel):
    text: str
    target: str | None = "en"
    source: str | None = None


class NeighboringFramesRequest(BaseModel):
    frame_num: str
    video_name: str
    k: int = 1


class GetVectorRequest(BaseModel):
    video_name: str
    frame_name: str


class GetVideoNameRequest(BaseModel):
    batch_id: list[int]
