"""Hub-side `/submission/*`: a pass-through to the team's central submission service.

The hub never talks to DRES itself. Every hub (the server's, and any teammate's
local one) forwards to SUBMISSION_HOST_PUBLIC, so the whole team shares one DRES
session, one view of the ACTIVE evaluation and one duplicate guard.
"""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from src.utils.settings import get_settings


def build_router() -> APIRouter:
    settings = get_settings()
    base = f"{settings.submission_host_public.rstrip('/')}/submission"
    router = APIRouter(prefix="/submission", tags=["submission"])

    @router.api_route("/{path:path}", methods=["GET", "POST"])
    async def forward(path: str, request: Request) -> Response:
        headers = {"Content-Type": request.headers.get("content-type", "application/json")}
        try:
            async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
                upstream = await client.request(
                    request.method, f"{base}/{path}",
                    params=request.query_params, content=await request.body(), headers=headers,
                )
        except httpx.HTTPError as exc:
            return JSONResponse(
                status_code=503,
                content={"status": 503, "detail": f"central submission service unreachable at {base}: {type(exc).__name__}",
                         "message": f"central submission service unreachable at {base}", "data": None},
            )
        return Response(content=upstream.content, status_code=upstream.status_code,
                        media_type=upstream.headers.get("content-type"))

    return router
