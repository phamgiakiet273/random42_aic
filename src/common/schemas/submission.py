"""Request schemas for submitting answers to the DRES evaluation server.

`session_id` / `eval_id` are accepted for compatibility but IGNORED: the central
submission service always submits with its own current session and ACTIVE
evaluation, so a client holding stale ids cannot submit to the wrong one.
"""

from __future__ import annotations

from pydantic import BaseModel


class SubmitKISRequest(BaseModel):
    session_id: str | None = None
    eval_id: str | None = None
    mediaItemName: str
    start: int
    end: int


class SubmitQARequest(BaseModel):
    session_id: str | None = None
    eval_id: str | None = None
    answer: str
    video_id: str
    time: str


class SubmitTRAKERequest(BaseModel):
    session_id: str | None = None
    eval_id: str | None = None
    video_id: str
    frame_ids: str
