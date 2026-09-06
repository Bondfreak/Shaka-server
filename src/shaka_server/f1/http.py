"""Read-only FastAPI routes for F1 Canonical Read Core.

Bounded HTTP surface so Navigator/KAI can call F1 without bypassing Shaka Server.
No LLM. No DB writes. Fail-closed.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from shaka_server.f1.assets.api import get_asset, list_assets
from shaka_server.f1.composer.api import answer_query

router = APIRouter(prefix="/api/v1/f1", tags=["f1"])


def _error(code: str, message: str, status_code: int) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status_code)


def _to_jsonable(obj: Any) -> Any:
    """Serialize dataclasses / enums to JSON-safe structures."""
    if isinstance(obj, Enum):
        return obj.value
    if is_dataclass(obj) and not isinstance(obj, type):
        return {key: _to_jsonable(value) for key, value in asdict(obj).items()}
    if isinstance(obj, dict):
        return {key: _to_jsonable(value) for key, value in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(item) for item in obj]
    return obj


def _asset_dict(asset: Any) -> dict[str, Any]:
    return _to_jsonable(asset)


@router.post("/answer")
async def f1_answer(request: Request) -> JSONResponse:
    """Compose a structured Answer from the frozen F1 snapshot (no LLM)."""
    try:
        payload = await request.json()
    except Exception:
        return _error("invalid_request", "JSON body with query is required", 400)

    if not isinstance(payload, dict):
        return _error("invalid_request", "JSON object body is required", 400)
    if set(payload.keys()) - {"query"}:
        return _error("invalid_request", "Only the query field is accepted", 400)

    query = payload.get("query")
    if not isinstance(query, str) or not query.strip():
        return _error("invalid_request", "Non-empty query string is required", 400)

    answer = answer_query(query.strip())
    return JSONResponse(_to_jsonable(answer), status_code=200)


@router.get("/assets")
def f1_list_assets(side: str | None = None) -> JSONResponse:
    """List bootstrapped Asset Instances; optional side= filter (BB/SB/...)."""
    if side is not None and not isinstance(side, str):
        return _error("invalid_request", "Invalid side filter", 400)
    side_filter = side.strip() if isinstance(side, str) and side.strip() else None
    if side is not None and side_filter is None:
        return _error("invalid_request", "Invalid side filter", 400)

    assets = list_assets(side=side_filter)
    return JSONResponse({"assets": [_asset_dict(a) for a in assets]}, status_code=200)


@router.get("/assets/{asset_id}")
def f1_get_asset(asset_id: str) -> JSONResponse:
    """Return one Asset by id, or 404 if missing."""
    if not asset_id or not asset_id.strip():
        return _error("invalid_request", "Invalid asset ID", 400)

    asset = get_asset(asset_id)
    if asset is None:
        return _error("not_found", f"Asset not found: {asset_id}", 404)
    return JSONResponse(_asset_dict(asset), status_code=200)
