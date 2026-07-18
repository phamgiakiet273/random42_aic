"""Schemas describing a keyframe result as passed through the rerank stage."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class DetectedObject(BaseModel):
    bbox: list[float]
    object: str
    conf: float


class VideoMetadata(BaseModel):
    key: str
    idx_folder: str
    video_name: str
    keyframe_id: str
    fps: float
    score: float
    s2t: list[str]
    object: list[DetectedObject]
    index: int
    video_path: str
    frame_path: str

    model_config = ConfigDict(arbitrary_types_allowed=True)
