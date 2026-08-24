from __future__ import annotations

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


def _validate_success(
    payload: dict[str, Any], *, expected_type: str | None = None, expected_id: str | None = None
) -> None:
    data = payload.get("data")
    meta = payload.get("meta")
    if not isinstance(data, dict) or not isinstance(meta, dict):
        raise CoreContractError("malformed_core_response")
    if meta.get("schemaVersion") != "1.0":
        raise CoreContractError("malformed_core_response")
    if expected_type is not None and data.get("type") != expected_type:
        raise CoreContractError("malformed_core_response")
    if expected_id is not None and data.get("id") != expected_id:
        raise CoreContractError("malformed_core_response")


def _validate_graph(payload: dict[str, Any], *, expected_root_id: str) -> None:
    data = payload.get("data")
    meta = payload.get("meta")
    if not isinstance(data, dict) or not isinstance(meta, dict):
        raise CoreContractError("malformed_core_response")
    if meta.get("schemaVersion") != "1.0" or meta.get("depth") != 1:
        raise CoreContractError("malformed_core_response")
    if data.get("rootId") != expected_root_id:
        raise CoreContractError("malformed_core_response")
    if not isinstance(data.get("nodes"), list) or not isinstance(data.get("edges"), list):
        raise CoreContractError("malformed_core_response")


def _validate_cog_graph(payload: dict[str, Any], *, expected_graph_id: str) -> None:
    _validate_success(payload, expected_id=expected_graph_id)
    data = payload["data"]
    if data.get("status") != "canonical":
        raise CoreContractError("malformed_core_response")
    for key in ("objectCount", "relationCount", "deferredCandidateCount"):
        if not isinstance(data.get(key), int) or data[key] < 0:
            raise CoreContractError("malformed_core_response")
    if not isinstance(data.get("sourcePath"), str):
        raise CoreContractError("malformed_core_response")


def _validate_cog_object(payload: dict[str, Any], *, expected_object_id: str) -> None:
    _validate_success(payload, expected_id=expected_object_id)
    data = payload["data"]
    meta = payload["meta"]
    if not isinstance(data.get("type"), str) or not isinstance(data.get("label"), str):
        raise CoreContractError("malformed_core_response")
    if not isinstance(data.get("relations"), list) or not isinstance(meta.get("graphId"), str):
        raise CoreContractError("malformed_core_response")
    for relation in data["relations"]:
        if (
            not isinstance(relation, dict)
            or relation.get("status") != "verified"
            or not all(isinstance(relation.get(key), str) for key in ("from", "type", "to"))
        ):
            raise CoreContractError("malformed_core_response")


def _validate_cog_flow(payload: dict[str, Any], *, expected_circuit_id: str) -> None:
    data = payload.get("data")
    meta = payload.get("meta")
    if not isinstance(data, dict) or not isinstance(meta, dict):
        raise CoreContractError("malformed_core_response")
    if meta.get("schemaVersion") != "1.0" or meta.get("projection") != "verified_directional_flow":
        raise CoreContractError("malformed_core_response")
    if data.get("circuitId") != expected_circuit_id:
        raise CoreContractError("malformed_core_response")
    if data.get("status") not in {"canonical_partial", "canonical_complete"}:
        raise CoreContractError("malformed_core_response")
    if not isinstance(data.get("complete"), bool):
        raise CoreContractError("malformed_core_response")
    if not isinstance(data.get("deferredCandidateCount"), int) or data["deferredCandidateCount"] < 0:
        raise CoreContractError("malformed_core_response")
    if not isinstance(data.get("nodes"), list) or not isinstance(data.get("edges"), list):
        raise CoreContractError("malformed_core_response")
    node_ids = {
        node.get("id")
        for node in data["nodes"]
        if isinstance(node, dict) and isinstance(node.get("id"), str)
    }
    if len(node_ids) != len(data["nodes"]):
        raise CoreContractError("malformed_core_response")
    for edge in data["edges"]:
        if (
            not isinstance(edge, dict)
            or edge.get("status") != "verified"
            or edge.get("type") != "supplies"
            or not all(isinstance(edge.get(key), str) for key in ("from", "to"))
            or edge["from"] not in node_ids
            or edge["to"] not in node_ids
        ):
            raise CoreContractError("malformed_core_response")


def _validate_cog_topology(payload: dict[str, Any], *, expected_system_id: str) -> None:
    data = payload.get("data")
    meta = payload.get("meta")
    if not isinstance(data, dict) or not isinstance(meta, dict):
        raise CoreContractError("malformed_core_response")
    if (
        meta.get("schemaVersion") != "1.0"
        or meta.get("projection")
        != "verified_control_topology_with_explicit_deferred_candidates"
    ):
        raise CoreContractError("malformed_core_response")
    if data.get("systemId") != expected_system_id or data.get("status") not in {"canonical_partial", "canonical_complete"}:
        raise CoreContractError("malformed_core_response")
    if not isinstance(data.get("complete"), bool):
        raise CoreContractError("malformed_core_response")
    nodes = data.get("nodes")
    edges = data.get("edges")
    candidates = data.get("deferredCandidates")
    if not isinstance(nodes, list) or not isinstance(edges, list) or not isinstance(candidates, list):
        raise CoreContractError("malformed_core_response")
    if data.get("deferredCandidateCount") != len(candidates):
        raise CoreContractError("malformed_core_response")
    node_ids = {
        node.get("id")
        for node in nodes
        if isinstance(node, dict)
        and isinstance(node.get("id"), str)
        and isinstance(node.get("type"), str)
        and isinstance(node.get("label"), str)
    }
    if len(node_ids) != len(nodes):
        raise CoreContractError("malformed_core_response")
    for edge in edges:
        if (
            not isinstance(edge, dict)
            or edge.get("status") != "verified"
            or not all(isinstance(edge.get(key), str) for key in ("from", "type", "to"))
            or edge["from"] not in node_ids
            or edge["to"] not in node_ids
        ):
            raise CoreContractError("malformed_core_response")
    for edge in candidates:
        if (
            not isinstance(edge, dict)
            or edge.get("status") != "candidate"
            or not all(isinstance(edge.get(key), str) for key in ("from", "type", "to"))
            or edge["from"] not in node_ids
            or edge["to"] not in node_ids
        ):
            raise CoreContractError("malformed_core_response")
    if meta.get("physicalCableRoutingVerified") is not False:
        raise CoreContractError("malformed_core_response")


def _map_result(result: CoreResult, validator: Callable[[dict[str, Any]], None]) -> JSONResponse:
    if result.status_code == 200:
        validator(result.payload)
        return JSONResponse(result.payload, status_code=200)
    if result.status_code in {400, 404, 409, 503}:
        error = result.payload.get("error")
        if (
            not isinstance(error, dict)
            or not isinstance(error.get("code"), str)
            or not isinstance(error.get("message"), str)
        ):
            raise CoreContractError("malformed_core_response")
        return JSONResponse(result.payload, status_code=result.status_code)
    raise CoreContractError("unexpected_core_status")


def create_app(
    *,
    core_base_url: str | None = None,
    core_client: CoreClient | None = None,
    cors_origins: str | None = None,
    kai_provider: KaiProvider | None = None,
) -> FastAPI:
    if core_client is None:
        resolved_url = core_base_url or os.getenv("SHAKA_CORE_BASE_URL")
        if not resolved_url:
            raise RuntimeError("SHAKA_CORE_BASE_URL is required")
        core_client = CoreClient(resolved_url)

    kai_service = KaiService(
        dispatcher=KaiToolDispatcher(core_client),
        provider=kai_provider if kai_provider is not None else provider_from_env(),
    )

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.state.core_client = core_client
    app.state.kai_service = kai_service
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_resolve_cors_origins(cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Accept", "Content-Type"],
    )

    @app.exception_handler(CoreContractError)
    async def core_contract_error_handler(_, exc: CoreContractError) -> JSONResponse:
        if str(exc) == "core_unavailable":
            return _error("dependency_unavailable", "Shaka Core unavailable", 503)
        return _error("dependency_contract_violation", "Shaka Core contract violation", 502)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"service": "shaka-server", "status": "ok"}

    @app.get("/readyz")
    def readyz() -> JSONResponse:
        result = core_client.object_detail(READINESS_OBJECT_ID)
        if result.status_code != 200:
            return _error("dependency_unavailable", "Shaka Core unavailable", 503)
        _validate_success(result.payload, expected_type="system", expected_id=READINESS_OBJECT_ID)
        return JSONResponse({"service": "shaka-server", "status": "ready"})

    @app.get("/api/v1/asset-instances/{public_id}")
    def asset_instance_detail(public_id: str) -> JSONResponse:
        if not _valid(public_id):
            return _error("invalid_request", "Invalid public ID", 400)
        return _map_result(
            core_client.asset_instance_detail(public_id),
            lambda payload: _validate_success(
                payload, expected_type="asset_instance", expected_id=public_id
            ),
        )

    @app.get("/api/v1/asset-instances/{public_id}/graph")
    def graph(public_id: str, depth: int | None = None) -> JSONResponse:
        if not _valid(public_id) or depth != 1:
            return _error("invalid_request", "public ID and depth=1 are required", 400)
        return _map_result(
            core_client.graph(public_id),
            lambda payload: _validate_graph(payload, expected_root_id=public_id),
        )

    @app.get("/api/v1/asset-instances/{context_public_id}/resolve-asset/{asset_public_id}")
    def resolve_asset(context_public_id: str, asset_public_id: str) -> JSONResponse:
        if not _valid(context_public_id) or not _valid(asset_public_id):
            return _error("invalid_request", "Invalid public ID", 400)

        def validator(payload: dict[str, Any]) -> None:
            _validate_success(payload, expected_type="asset_instance")
            resolution = payload.get("meta", {}).get("resolution")
            if not isinstance(resolution, dict):
                raise CoreContractError("malformed_core_response")
            if (
                resolution.get("contextId") != context_public_id
                or resolution.get("assetId") != asset_public_id
                or resolution.get("strategy") != "same_host_slot_current_installed"
            ):
                raise CoreContractError("malformed_core_response")

        return _map_result(
            core_client.resolve_asset_instance(context_public_id, asset_public_id),
            validator,
        )

    @app.get("/api/v1/objects/{public_id}")
    def object_detail(public_id: str) -> JSONResponse:
        if not _valid(public_id):
            return _error("invalid_request", "Invalid public ID", 400)

        def validator(payload: dict[str, Any]) -> None:
            _validate_success(payload, expected_id=public_id)
            if payload["data"].get("type") not in {"system", "location"}:
                raise CoreContractError("malformed_core_response")

        return _map_result(core_client.object_detail(public_id), validator)

    @app.get("/api/v1/cog/graphs/{graph_id}")
    def cog_graph(graph_id: str) -> JSONResponse:
        if not _valid(graph_id):
            return _error("invalid_request", "Invalid graph ID", 400)
        return _map_result(
            core_client.cog_graph(graph_id),
            lambda payload: _validate_cog_graph(payload, expected_graph_id=graph_id),
        )

    @app.get("/api/v1/cog/objects/{public_id}")
    def cog_object(public_id: str) -> JSONResponse:
        if not _valid(public_id):
            return _error("invalid_request", "Invalid public ID", 400)
        return _map_result(
            core_client.cog_object(public_id),
            lambda payload: _validate_cog_object(payload, expected_object_id=public_id),
        )

    @app.get("/api/v1/cog/flows/{circuit_id}")
    def cog_flow(circuit_id: str) -> JSONResponse:
        if not _valid(circuit_id):
            return _error("invalid_request", "Invalid circuit ID", 400)
        return _map_result(
            core_client.cog_flow(circuit_id),
            lambda payload: _validate_cog_flow(payload, expected_circuit_id=circuit_id),
        )

    @app.get("/api/v1/cog/topologies/{system_id}")
    def cog_topology(system_id: str) -> JSONResponse:
        if not _valid(system_id):
            return _error("invalid_request", "Invalid system ID", 400)
        return _map_result(
            core_client.cog_topology(system_id),
            lambda payload: _validate_cog_topology(payload, expected_system_id=system_id),
        )

    @app.post("/api/v1/kai/explain")
    def kai_explain(payload: dict[str, Any]) -> JSONResponse:
        if set(payload) != {"contextInstanceId", "intent"}:
            return _error("invalid_request", "Bounded KAI request fields are required", 400)
        context_instance_id = payload.get("contextInstanceId")
        if not isinstance(context_instance_id, str) or not _valid(context_instance_id):
            return _error("invalid_request", "Invalid context instance ID", 400)
        if payload.get("intent") != "explain_selected_context":
            return _error("unsupported_request", "Unsupported KAI request", 400)

        try:
            result = kai_service.explain(context_instance_id)
        except KaiProviderUnavailable:
            return _error("kai_unavailable", "KAI model provider unavailable", 503)
        except KaiToolError as exc:
            return _error(exc.code, exc.message, exc.status_code)
        except KaiProviderContractError:
            return _error("kai_contract_violation", "KAI provider contract violation", 502)
        return JSONResponse(result, status_code=200)

    return app


app = create_app(core_base_url=os.getenv("SHAKA_CORE_BASE_URL", "http://127.0.0.1:8001"))