"""Shared loguru logger setup, used by every service."""

from __future__ import annotations

import logging
import sys
from functools import lru_cache
from pathlib import Path

from loguru import logger

from src.utils.settings import get_settings


def get_logger():
    return logger


@lru_cache
def setup_logger(name: str = "app", log_level: int = logging.INFO):
    """Configure stdout + rotating file sinks for `name`. Cached per name."""
    settings = get_settings()
    logdir = Path(settings.log_dir)
    logdir.mkdir(parents=True, exist_ok=True)
    path = logdir / name

    logger.remove()
    logger.add(
        sys.stdout,
        level=log_level,
        backtrace=settings.log_backtrace,
        diagnose=settings.log_diagnose,
        enqueue=True,
    )
    logger.add(
        path.with_suffix(".log"),
        level=log_level,
        rotation=settings.log_max_bytes,
        retention=settings.log_backup_count,
        backtrace=settings.log_backtrace,
        diagnose=settings.log_diagnose,
        enqueue=True,
        serialize=settings.log_serialize_json,
    )
    return logger
