"""Request schemas for vector-search (Qdrant) queries, shared by all clip model variants."""

from __future__ import annotations

from pydantic import BaseModel, Field


class QdrantRequest(BaseModel):
    k: int
    feat: list[float] | list[list[float]] | None = None
    video_filter: str | list[str] | None = None
    s2t_filter: str | None = None
    time_in: str | None = None
    time_out: str | None = None
    return_s2t: bool = True
    return_object: bool = True
    frame_class_filter: list[int] | None = None
    skip_frames: list[dict[str, str]] = Field(default_factory=list)
    sort_to_news: bool = True
    utility_feature: str | None = "shot"


class RetrievalRequest(BaseModel):
    image_data: str | None = None  # base64
    text: str | None = None
    k: int
    video_filter: str | list[str] | None = None
    s2t_filter: str | None = None
    return_s2t: bool = True
    return_object: bool = True
    frame_class_filter: list[int] | None = None
    skip_frames: list[dict[str, str]] = Field(default_factory=list)
    sort_to_news: bool = True
    main_event_index: int | None = 0
