"""Generic launcher for all 8 deployable services, selected via the `SERVICE` env var.

Replaces the 7 legacy per-service entrypoints (`services/hub_service.py`,
`services/SIGLIP_v2_service.py`, `services/SIGLIP_v2_B_service.py`,
`services/METACLIP_service.py`, `services/rerank_service.py`,
`services/submission_service.py`, `services/util_service.py`,
`services/result_manager_service.py`). Each service is still a separately
deployable process (`SERVICE=hub uvicorn src.main:app`, `SERVICE=metaclip
uvicorn src.main:app`, ...) -- this file only collapses the boilerplate that
was copy-pasted across all 7.
"""

from __future__ import annotations

import asyncio
import os
import signal
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware

from src.apis.base import create_app
from src.apis.clip_api import build_router as build_clip_router
from src.apis.hub_api import build_router as build_hub_router
from src.apis.rerank_api import build_router as build_rerank_router
from src.apis.result_manager_api import build_router as build_result_manager_router
from src.apis.submission_api import build_router as build_submission_router
from src.apis.util_api import build_router as build_util_router
from src.externals.qdrant_client import QdrantSearchClient
from src.externals.translate_client import TranslateClient
from src.modules.clip_models.metaclip import MetaclipModel
from src.modules.clip_models.siglip2 import Siglip2Model
from src.services.clip_service import ClipSearchService
from src.services.hub_service import HubGatewayService
from src.services.rerank_service import RerankService
from src.services.result_manager_service import ResultManagerService
from src.services.submission_service import SubmissionService
from src.services.util_service import UtilService
from src.utils.logger import get_logger, setup_logger
from src.utils.settings import Settings, get_settings

_KNOWN_SERVICES = (
    "hub",
    "siglip_alpha",
    "siglip_beta",
    "metaclip",
    "rerank",
    "submission",
    "util",
    "result_manager",
)

_UI_DIR = Path(__file__).resolve().parent / "ui"

logger = get_logger()


def _maybe_gzip(app: FastAPI) -> FastAPI:
    """Matches legacy's `ENABLE_GZIP` opt-out, applied uniformly instead of once per entrypoint."""
    if os.getenv("ENABLE_GZIP", "true").lower() == "true":
        app.add_middleware(GZipMiddleware, minimum_size=0)
    return app


def _build_clip_app(
    variant: str,
    model,
    database_name: str,
    qdrant_url: str,
    qdrant_port: int,
    qdrant_grpc_port: int,
) -> FastAPI:
    qdrant = QdrantSearchClient(
        qdrant_url, qdrant_port, qdrant_grpc_port, database_name
    )
    service = ClipSearchService(model, qdrant)
    app = create_app()
    app.include_router(build_clip_router(service, f"/{variant}"))
    return app


def _build_hub_app() -> FastAPI:
    service = HubGatewayService()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        task = asyncio.create_task(service.start_session_refresh_loop())
        yield
        task.cancel()

    app = create_app(
        enable_cors=True,
        templates_dir=_UI_DIR / "templates",
        static_dir=_UI_DIR / "static",
        template_name="hub.html",
        lifespan=lifespan,
    )
    app.include_router(build_hub_router(service))
    return app


def _build_result_manager_app() -> FastAPI:
    service = ResultManagerService()
    app = create_app(
        enable_cors=True,
        templates_dir=_UI_DIR / "templates",
        static_dir=_UI_DIR / "static",
        template_name="result_manager.html",
    )
    app.include_router(build_result_manager_router(service))
    return app


def _build_submission_app() -> FastAPI:
    service = SubmissionService()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            await service.login()
        except (
            Exception
        ) as exc:  # DRES may be unreachable at boot -- don't crash the app for it.
            logger.warning(f"DRES login failed at startup, will retry lazily: {exc}")
        yield

    app = create_app(lifespan=lifespan)
    app.include_router(build_submission_router(service))
    return app


def _build_rerank_app() -> FastAPI:
    service = RerankService()
    app = create_app()
    app.include_router(build_rerank_router(service))
    return app


def _build_util_app() -> FastAPI:
    settings = get_settings()
    # Vector lookups (`UtilService.get_vector`) need *some* CLIP collection to
    # query; legacy hardcoded a "PUMPKING_SIGLIP_V2" client for this, so the
    # siglip_alpha collection is used here as the closest equivalent.
    vector_client = QdrantSearchClient(
        settings.siglip_v2_qdrant_url,
        settings.siglip_v2_qdrant_port,
        settings.siglip_v2_qdrant_grpc_port,
        settings.siglip_v2_database_name,
    )
    service = UtilService(
        translate_client=TranslateClient(), vector_client=vector_client
    )
    app = create_app()
    app.include_router(build_util_router(service))
    return app


def build_app(service_name: str, settings: Settings) -> FastAPI:
    if service_name == "hub":
        app = _build_hub_app()
    elif service_name == "result_manager":
        app = _build_result_manager_app()
    elif service_name == "submission":
        app = _build_submission_app()
    elif service_name == "rerank":
        app = _build_rerank_app()
    elif service_name == "util":
        app = _build_util_app()
    elif service_name == "siglip_alpha":
        model = Siglip2Model(
            settings.siglip_v2_cuda_visible_devices,
            settings.transformers_cache,
            settings.huggingface_hub_token,
        )
        app = _build_clip_app(
            "siglip_alpha",
            model,
            settings.siglip_v2_database_name,
            settings.siglip_v2_qdrant_url,
            settings.siglip_v2_qdrant_port,
            settings.siglip_v2_qdrant_grpc_port,
        )
    elif service_name == "siglip_beta":
        model = Siglip2Model(
            settings.siglip_v2_b_cuda_visible_devices,
            settings.transformers_cache,
            settings.huggingface_hub_token,
        )
        app = _build_clip_app(
            "siglip_beta",
            model,
            settings.siglip_v2_b_database_name,
            settings.siglip_v2_b_qdrant_url,
            settings.siglip_v2_b_qdrant_port,
            settings.siglip_v2_b_qdrant_grpc_port,
        )
    elif service_name == "metaclip":
        model = MetaclipModel(
            settings.metaclip_cuda_visible_devices,
            settings.transformers_cache,
            settings.huggingface_hub_token,
        )
        app = _build_clip_app(
            "metaclip",
            model,
            settings.metaclip_database_name,
            settings.metaclip_qdrant_url,
            settings.metaclip_qdrant_port,
            settings.metaclip_qdrant_grpc_port,
        )
    else:
        raise ValueError(
            f"Unknown SERVICE {service_name!r}, expected one of {_KNOWN_SERVICES}"
        )

    return _maybe_gzip(app)


def _host_port_workers(service_name: str, settings: Settings) -> tuple[str, int, int]:
    return {
        "hub": (settings.hub_host, settings.hub_port, settings.hub_max_workers),
        "result_manager": (
            settings.result_manager_host,
            settings.result_manager_port,
            settings.result_manager_max_workers,
        ),
        "submission": (
            settings.submission_host,
            settings.submission_port,
            settings.submission_max_workers,
        ),
        "util": (settings.util_host, settings.util_port, settings.util_max_workers),
        "rerank": (
            settings.rerank_host,
            settings.rerank_port,
            settings.rerank_max_workers,
        ),
        "siglip_alpha": (
            settings.siglip_v2_host,
            settings.siglip_v2_port,
            settings.siglip_v2_max_workers,
        ),
        "siglip_beta": (
            settings.siglip_v2_b_host,
            settings.siglip_v2_b_port,
            settings.siglip_v2_b_max_workers,
        ),
        "metaclip": (
            settings.metaclip_host,
            settings.metaclip_port,
            settings.metaclip_max_workers,
        ),
    }[service_name]


def _handle_sigterm(*_args) -> None:
    print("Received termination signal. Cleaning up...")
    sys.exit(0)


_SERVICE = os.getenv("SERVICE")
if not _SERVICE or _SERVICE not in _KNOWN_SERVICES:
    raise ValueError(
        f"SERVICE env var must be set to one of {_KNOWN_SERVICES}, got {_SERVICE!r}"
    )

setup_logger(_SERVICE)
app = build_app(_SERVICE, get_settings())

if __name__ == "__main__":
    signal.signal(signal.SIGINT, _handle_sigterm)
    signal.signal(signal.SIGTERM, _handle_sigterm)

    _settings = get_settings()
    _host, _port, _workers = _host_port_workers(_SERVICE, _settings)
    uvicorn.run(
        app,
        host=_host,
        port=_port,
        workers=_workers,
        timeout_keep_alive=_settings.timeout_keep_alive,
    )
