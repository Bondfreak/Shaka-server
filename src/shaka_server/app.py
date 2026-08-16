from __future__ import annotations

import logging
import os
import re
from typing import Any, Callable

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .core_client import CoreClient, CoreContractError, CoreResult
from .kai import (
    KaiProvider,
    KaiProviderContractError,
    KaiProviderUnavailable,
    KaiService,
    KaiToolDispatcher,
    KaiToolError,
)
from .openai_provider import provider_from_env

logger = logging.getLogger(__name__)

PUBLIC_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
READINESS_OBJECT_ID = "SYS-0003"
DEFAULT_UI_ORIGIN = "https://bondfreak.github.io"


def _error(code: str, message: str, status_code: int) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status_code)


def _valid(public_id: str) -> bool:
    return bool(PUBLIC_ID.fullmatch(public_id))


def _resolve_cors_origins(configured: str | None) -> list[str]:
    raw = configured if configured is not None else os.getenv("SHAKA_UI_ORIGINS", DEFAULT_UI_ORIGIN)
    origins = [origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip()]
    if not origins:
        raise RuntimeError("At least one SHAKA_UI_ORIGINS origin is required")
    if "*" in origins:
        raise RuntimeError("Wildcard SHAKA_UI_ORIGINS is not allowed")
    return origins

# Existing validators and routes remain unchanged.

# NOTE: this file is intentionally abbreviated in this patch context.
