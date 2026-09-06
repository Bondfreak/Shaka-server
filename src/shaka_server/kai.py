from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from .core_client import CoreClient, CoreContractError, CoreResult
from .f1.composer.api import answer_query
from .f1.http import _to_jsonable

PUBLIC_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
SUPPORTED_TOOLS = {
    "get_asset_instance_detail",
    "get_direct_relations",
    "get_object_detail",
    "get_canonical_graph",
    "get_canonical_object",
    "f1_answer_query",
}


class KaiToolError(RuntimeError):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(code)
        self.code = code
        self.message = message
        self.status_code = status_code


class KaiProviderUnavailable(RuntimeError):
    pass


class KaiProviderContractError(RuntimeError):
    pass


class KaiProvider(Protocol):
    def explain(
        self,
        *,
        context: dict[str, str],
        run_tool: Callable[[str, dict[str, str]], dict[str, Any]],
    ) -> str: ...


class DisabledKaiProvider:
    def explain(
        self,
        *,
        context: dict[str, str],
        run_tool: Callable[[str, dict[str, str]], dict[str, Any]],
    ) -> str:
        raise KaiProviderUnavailable("kai_provider_not_configured")


def _valid(public_id: object) -> bool:
    return isinstance(public_id, str) and bool(PUBLIC_ID.fullmatch(public_id))


def _validate_success(
    result: CoreResult,
    *,
    expected_type: str | None = None,
    expected_id: str | None = None,
) -> dict[str, Any]:
    if result.status_code != 200:
        error = result.payload.get("error")
        if result.status_code not in {400, 404, 409, 503} or not isinstance(error, dict):
            raise CoreContractError("malformed_core_response")
        code = error.get("code")
        message = error.get("message")
        if not isinstance(code, str) or not isinstance(message, str):
            raise CoreContractError("malformed_core_response")
        raise KaiToolError(code, message, result.status_code)

    data = result.payload.get("data")
    meta = result.payload.get("meta")
    if not isinstance(data, dict) or not isinstance(meta, dict) or meta.get("schemaVersion") != "1.0":
        raise CoreContractError("malformed_core_response")
    if expected_type is not None and data.get("type") != expected_type:
        raise CoreContractError("malformed_core_response")
    if expected_id is not None and data.get("id") != expected_id:
        raise CoreContractError("malformed_core_response")
    return result.payload


def _validate_cog_graph(result: CoreResult, graph_id: str) -> dict[str, Any]:
    payload = _validate_success(result, expected_id=graph_id)
    data = payload["data"]
    if data.get("status") != "canonical":
        raise CoreContractError("malformed_core_response")
    for key in ("objectCount", "relationCount", "deferredCandidateCount"):
        if not isinstance(data.get(key), int) or data[key] < 0:
            raise CoreContractError("malformed_core_response")
    if not isinstance(data.get("sourcePath"), str):
        raise CoreContractError("malformed_core_response")
    return payload


def _validate_cog_object(result: CoreResult, object_id: str) -> dict[str, Any]:
    payload = _validate_success(result, expected_id=object_id)
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
    return payload


@dataclass(frozen=True)
class KaiToolDispatcher:
    core_client: CoreClient

    def execute(self, name: str, arguments: dict[str, str]) -> dict[str, Any]:
        if name not in SUPPORTED_TOOLS:
            raise KaiToolError("unsupported_tool", "Unsupported KAI tool", 400)
        if not isinstance(arguments, dict):
            raise KaiToolError("invalid_request", "Tool arguments must be an object", 400)

        if name == "get_asset_instance_detail":
            if set(arguments) != {"instance_id"} or not _valid(arguments.get("instance_id")):
                raise KaiToolError("invalid_request", "Valid instance_id is required", 400)
            instance_id = arguments["instance_id"]
            return _validate_success(
                self.core_client.asset_instance_detail(instance_id),
                expected_type="asset_instance",
                expected_id=instance_id,
            )

        if name == "get_direct_relations":
            if set(arguments) != {"instance_id"} or not _valid(arguments.get("instance_id")):
                raise KaiToolError("invalid_request", "Valid instance_id is required", 400)
            instance_id = arguments["instance_id"]
            result = self.core_client.graph(instance_id)
            if result.status_code != 200:
                return _validate_success(result)
            data = result.payload.get("data")
            meta = result.payload.get("meta")
            if (
                not isinstance(data, dict)
                or not isinstance(meta, dict)
                or meta.get("schemaVersion") != "1.0"
                or meta.get("depth") != 1
                or data.get("rootId") != instance_id
                or not isinstance(data.get("nodes"), list)
                or not isinstance(data.get("edges"), list)
            ):
                raise CoreContractError("malformed_core_response")
            return result.payload

        if name == "get_canonical_graph":
            if set(arguments) != {"graph_id"} or not _valid(arguments.get("graph_id")):
                raise KaiToolError("invalid_request", "Valid graph_id is required", 400)
            graph_id = arguments["graph_id"]
            return _validate_cog_graph(self.core_client.cog_graph(graph_id), graph_id)

        if name == "get_canonical_object":
            if set(arguments) != {"object_id"} or not _valid(arguments.get("object_id")):
                raise KaiToolError("invalid_request", "Valid object_id is required", 400)
            object_id = arguments["object_id"]
            return _validate_cog_object(self.core_client.cog_object(object_id), object_id)

        if name == "f1_answer_query":
            if set(arguments) != {"query"}:
                raise KaiToolError("invalid_request", "Non-empty query string is required", 400)
            query = arguments.get("query")
            if not isinstance(query, str) or not query.strip():
                raise KaiToolError("invalid_request", "Non-empty query string is required", 400)
            # Deterministic F1 composer; no Core client, no writes.
            return _to_jsonable(answer_query(query.strip()))

        if set(arguments) != {"object_id"} or not _valid(arguments.get("object_id")):
            raise KaiToolError("invalid_request", "Valid object_id is required", 400)
        object_id = arguments["object_id"]
        payload = _validate_success(self.core_client.object_detail(object_id), expected_id=object_id)
        if payload["data"].get("type") not in {"system", "location"}:
            raise CoreContractError("malformed_core_response")
        return payload


@dataclass
class KaiService:
    dispatcher: KaiToolDispatcher
    provider: KaiProvider

    def explain(self, context_instance_id: str) -> dict[str, Any]:
        if not _valid(context_instance_id):
            raise KaiToolError("invalid_request", "Invalid context instance ID", 400)

        trace: list[dict[str, Any]] = []

        def run_tool(name: str, arguments: dict[str, str]) -> dict[str, Any]:
            result = self.dispatcher.execute(name, arguments)
            trace.append({"name": name, "arguments": dict(arguments), "result": result})
            return result

        text = self.provider.explain(
            context={
                "contextInstanceId": context_instance_id,
                "intent": "explain_selected_context",
            },
            run_tool=run_tool,
        )
        if not isinstance(text, str) or not text.strip():
            raise KaiProviderContractError("invalid_provider_response")
        if not trace:
            raise KaiProviderContractError("provider_used_no_tools")

        return {
            "data": {
                "contextInstanceId": context_instance_id,
                "explanation": text.strip(),
                "toolTrace": trace,
            },
            "meta": {"schemaVersion": "1.0", "toolGrounded": True},
        }
