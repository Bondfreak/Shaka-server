"""KAI tool binding for F1 Canonical Read Core (dispatcher only, no LLM)."""

from __future__ import annotations

import pytest

from shaka_server.core_client import CoreResult
from shaka_server.kai import KaiToolDispatcher, KaiToolError


class _StubCore:
    """Unused by f1_answer_query; satisfies KaiToolDispatcher construction."""

    def asset_instance_detail(self, public_id: str) -> CoreResult:
        return CoreResult(404, {"error": {"code": "not_found", "message": "unused"}})

    def graph(self, public_id: str) -> CoreResult:
        return CoreResult(404, {"error": {"code": "not_found", "message": "unused"}})

    def resolve_asset_instance(self, context_public_id: str, asset_public_id: str) -> CoreResult:
        return CoreResult(404, {"error": {"code": "not_found", "message": "unused"}})

    def object_detail(self, public_id: str) -> CoreResult:
        return CoreResult(404, {"error": {"code": "not_found", "message": "unused"}})

    def cog_graph(self, graph_id: str) -> CoreResult:
        return CoreResult(404, {"error": {"code": "not_found", "message": "unused"}})

    def cog_object(self, public_id: str) -> CoreResult:
        return CoreResult(404, {"error": {"code": "not_found", "message": "unused"}})


def _dispatcher() -> KaiToolDispatcher:
    return KaiToolDispatcher(core_client=_StubCore())


def test_f1_answer_query_impeller_style_returns_structured_answer() -> None:
    result = _dispatcher().execute(
        "f1_answer_query",
        {"query": "Hvornår blev impellerne sidst skiftet?"},
    )
    for key in (
        "conclusion",
        "basis",
        "uncertainty_conflict",
        "sources",
        "policy_results",
        "epistemic_status",
        "query",
    ):
        assert key in result
    assert isinstance(result["conclusion"], str) and result["conclusion"]
    assert isinstance(result["basis"], list)
    assert isinstance(result["uncertainty_conflict"], list)
    assert isinstance(result["sources"], list)
    assert isinstance(result["policy_results"], list)
    codes = {p["code"] for p in result["policy_results"]}
    assert "INVOICE_NE_INSTALL" in codes or "ACTION_NE_OUTCOME" in codes
    blob = " ".join(
        [
            result["conclusion"],
            *result["basis"],
            *result["uncertainty_conflict"],
        ]
    ).lower()
    assert "not proof" in blob or "invoiced" in blob
    assert "installed on both" not in blob


def test_f1_answer_query_pcu_style_returns_structured_answer() -> None:
    result = _dispatcher().execute(
        "f1_answer_query",
        {"query": "PCU status BB vs SB"},
    )
    assert isinstance(result["conclusion"], str) and result["conclusion"]
    assert "query" in result
    assert result["query"] == "PCU status BB vs SB"


def test_f1_answer_query_empty_query_is_400() -> None:
    with pytest.raises(KaiToolError) as excinfo:
        _dispatcher().execute("f1_answer_query", {"query": "   "})
    assert excinfo.value.status_code == 400
    assert excinfo.value.code == "invalid_request"


def test_f1_answer_query_missing_query_is_400() -> None:
    with pytest.raises(KaiToolError) as excinfo:
        _dispatcher().execute("f1_answer_query", {})
    assert excinfo.value.status_code == 400
    assert excinfo.value.code == "invalid_request"


def test_unsupported_tool_still_400() -> None:
    with pytest.raises(KaiToolError) as excinfo:
        _dispatcher().execute("fetch_arbitrary_url", {"url": "https://example.invalid"})
    assert excinfo.value.status_code == 400
    assert excinfo.value.code == "unsupported_tool"


def test_existing_core_tool_still_works() -> None:
    """Preserve Core tool path alongside the new F1 tool."""

    class CoreOk(_StubCore):
        def asset_instance_detail(self, public_id: str) -> CoreResult:
            return CoreResult(
                200,
                {
                    "data": {
                        "id": public_id,
                        "type": "asset_instance",
                        "asset": {"id": "ASSET-X"},
                        "host": {"id": "SYS-1"},
                        "slot": "PORT",
                        "state": "INSTALLED",
                        "provenance": [],
                    },
                    "meta": {"schemaVersion": "1.0"},
                },
            )

    payload = KaiToolDispatcher(core_client=CoreOk()).execute(
        "get_asset_instance_detail",
        {"instance_id": "AI-D4-BB-SeaWaterPump"},
    )
    assert payload["data"]["id"] == "AI-D4-BB-SeaWaterPump"
    assert payload["data"]["type"] == "asset_instance"
