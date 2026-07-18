"""Request schemas for the hub gateway's query/scroll endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ImageQuery(BaseModel):
    image_data: str  # base64
    k: int = 100
    video_filter: str | None = None
    s2t_filter: str | None = None
    return_s2t: bool = True
    return_object: bool = True
    frame_class_filter: list[int] | None = None
    skip_frames: list[dict[str, str]] = Field(default_factory=list)
    sort_to_news: bool = True


class ScrollQuery(BaseModel):
    k: int = 100
    video_filter: str | None = None
    s2t_filter: str | None = None
    time_in: str | None = None
    time_out: str | None = None
    return_s2t: bool = True
    return_object: bool = True
    frame_class_filter: list[int] | None = None
    skip_frames: list[dict[str, str]] = Field(default_factory=list)
    sort_to_news: bool = True
    utility_feature: str | None = "shot"
