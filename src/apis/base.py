"""Generic FastAPI app factory shared by all 8 service entrypoints (see src/main.py).

Replaces the legacy `apis/api.py` (plain services) and `apis/hub.py` /
`apis/result_manager.py` (templated services) — those were three near-identical
copies of the same middleware/exception-handler boilerplate, differing only in
whether CORS/Jinja2 templates were wired up. `TimeoutMiddleware` from the
legacy `apis/api.py` is deliberately not ported: it was defined but never
attached to any app (dead code).
"""

from __future__ import annotations

import time
from http import HTTPStatus
from pathlib import Path
from typing import Callable

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from starlette.middleware.base import BaseHTTPMiddleware

from src.common.schemas.api import APIResponse
from src.utils.logger import get_logger
from src.utils.settings import get_settings

logger = get_logger()

_MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB


class _LimitUploadSizeMiddleware(BaseHTTPMiddleware):
    """Rejects requests whose Content-Length exceeds `max_upload_size` with a 413."""

    def __init__(self, app, max_upload_size: int = _MAX_UPLOAD_BYTES) -> None:
        super().__init__(app)
        self.max_upload_size = max_upload_size

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("Content-Length")
        if content_length and int(content_length) > self.max_upload_size:
            return JSONResponse(
                content={"detail": "Request body too large"}, status_code=413
            )
        return await call_next(request)


def create_app(
    *,
    enable_cors: bool = False,
    cors_origins: list[str] | None = None,
    templates_dir: str | Path | None = None,
    static_dir: str | Path | None = None,
    template_name: str = "index.html",
    lifespan: Callable | None = None,
) -> FastAPI:
    """Build a FastAPI app with the middleware/exception-handling baseline shared by every service.

    `templates_dir`/`static_dir` are only needed by the hub and result_manager
    services (their frontends); the other 6 services call this with neither set.
    `lifespan` lets callers (main.py) hook startup/shutdown work — e.g. the hub's
    session-refresh loop or the submission service's DRES login.
    """
    app = FastAPI(docs_url="/docs", redoc_url="/redoc", lifespan=lifespan)

    if enable_cors:
        # NOTE: allow_origins=["*"] (combined with allow_credentials=True) lets
        # any origin read authenticated responses -- insecure for a public
        # deployment. Kept as the default only because it matches current
        # legacy behavior; pass a real `cors_origins` list before shipping.
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins or ["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.add_middleware(_LimitUploadSizeMiddleware, max_upload_size=_MAX_UPLOAD_BYTES)

    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        response.headers["X-Process-Time"] = str(time.time() - start_time)
        return response

    @app.exception_handler(status.HTTP_500_INTERNAL_SERVER_ERROR)
    async def internal_exception_handler(request: Request, exc: Exception):
        logger.exception(exc)
        return JSONResponse(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR.value,
            content=APIResponse(
                status=HTTPStatus.INTERNAL_SERVER_ERROR.value,
                message=HTTPStatus.INTERNAL_SERVER_ERROR.name,
                data=None,
            ).model_dump(),
        )

    @app.exception_handler(ValidationError)
    @app.exception_handler(RequestValidationError)
    async def pydantic_request_validation_error(
        request: Request, err: RequestValidationError | ValidationError
    ):
        logger.exception(err)
        return JSONResponse(
            status_code=HTTPStatus.BAD_REQUEST.value,
            content=APIResponse(
                status=HTTPStatus.BAD_REQUEST.value,
                message=str(HTTPStatus.BAD_REQUEST),
                data=err.errors(),
            ).model_dump(),
        )

    @app.get("/health-check")
    async def health_check() -> APIResponse:
        return APIResponse(status=HTTPStatus.OK.value, message="Running (Healthy)")

    if templates_dir is None:

        @app.get("/")
        async def root() -> APIResponse:
            return APIResponse(status=HTTPStatus.OK.value, message="Running (Healthy)")

    else:
        templates = Jinja2Templates(directory=str(templates_dir))
        app.state.templates = templates

        if static_dir is not None:
            if Path(static_dir).exists():
                app.mount(
                    "/static", StaticFiles(directory=str(static_dir)), name="static"
                )
            else:
                logger.warning(f"Static directory not found at {static_dir}")

        @app.get("/", response_class=HTMLResponse)
        async def render_index(request: Request):
            return templates.TemplateResponse(
                template_name, {"request": request, "base_url": get_settings().base_url}
            )

    return app
