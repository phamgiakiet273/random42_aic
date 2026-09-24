"""Request schemas for submitting answers to the DRES evaluation server.

`session_id` is IGNORED: the central submission service always uses its own
session. `eval_id` is the evaluation the user chose in the header when DRES runs
several at once; it must be one of the ACTIVE ones (else 409, nothing sent).
Omitted, the only ACTIVE evaluation is used (409 if several are ACTIVE).
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
