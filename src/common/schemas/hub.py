"""Request schemas for the hub gateway's query/scroll endpoints."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


SearchType = Literal["text", "image", "temporal", "scroll"]


class SearchModelConfig(BaseModel):
    """One retrieval backend exposed by the hub's consolidated search API."""

    base_url: str
    backend_prefix: str
    search_types: set[SearchType] = {"text", "image", "temporal", "scroll"}


class SearchRequest(BaseModel):
    """Validated form of a request to ``POST /hub/search``."""

    model: str
    search_type: SearchType
    text: str | None = None
    image_path: str | None = None
    k: int = 100
    video_filter: str | None = None
    s2t_filter: str | None = None
    time_in: str | None = None
    time_out: str | None = None
    return_s2t: bool = True
    return_object: bool = True
    frame_class_filter: list[int] = Field(default_factory=list)
    skip_frames: list[dict[str, str]] = Field(default_factory=list)
    sort_to_news: bool = True
    main_event_index: int = 0
    utility_feature: str = "shot"

    @model_validator(mode="after")
    def validate_search_input(self) -> "SearchRequest":
        if self.search_type in {"text", "temporal"} and not self.text:
            raise ValueError("text is required for text and temporal searches")
        if self.search_type == "image" and not self.image_path:
            raise ValueError("image_path is required for image searches")
        if self.search_type == "scroll" and not self.video_filter:
            raise ValueError("video_filter is required for scroll searches")
        return self


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
