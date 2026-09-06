"""F1 read-only HTTP routes — answer + assets via FastAPI TestClient."""

from __future__ import annotations

from fastapi.testclient import TestClient

from shaka_server.app import create_app
from shaka_server.core_client import CoreResult
from shaka_server.f1.assets import ASSET_IDS


class _StubCore:
    """Minimal Core stub so create_app can start without a live Core."""

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

    def cog_flow(self, circuit_id: str) -> CoreResult:
        return CoreResult(404, {"error": {"code": "not_found", "message": "unused"}})

    def cog_topology(self, system_id: str) -> CoreResult:
        return CoreResult(404, {"error": {"code": "not_found", "message": "unused"}})

    def cog_diagnostic(self, scenario_id: str) -> CoreResult:
        return CoreResult(404, {"error": {"code": "not_found", "message": "unused"}})


def _client() -> TestClient:
    return TestClient(create_app(core_client=_StubCore()))


def test_answer_ac_style_query_returns_required_fields_and_no_install_promotion() -> None:
    client = _client()
    response = client.post(
        "/api/v1/f1/answer",
        json={"query": "Hvornår blev impellerne sidst skiftet?"},
    )
    assert response.status_code == 200
    body = response.json()
    for key in (
        "conclusion",
        "basis",
        "uncertainty_conflict",
        "sources",
        "policy_results",
        "epistemic_status",
    ):
        assert key in body
    assert isinstance(body["conclusion"], str) and body["conclusion"]
    assert isinstance(body["basis"], list)
    assert isinstance(body["uncertainty_conflict"], list)
    assert isinstance(body["sources"], list)
    assert isinstance(body["policy_results"], list)
    codes = {p["code"] for p in body["policy_results"]}
    assert "INVOICE_NE_INSTALL" in codes or "ACTION_NE_OUTCOME" in codes
    blob = " ".join(
        [
            body["conclusion"],
            *body["basis"],
            *body["uncertainty_conflict"],
        ]
    ).lower()
    assert "not proof" in blob or "invoiced" in blob
    assert "installed on both" not in blob


def test_assets_list_returns_bb_sb_engines() -> None:
    client = _client()
    response = client.get("/api/v1/f1/assets")
    assert response.status_code == 200
    assets = response.json()["assets"]
    by_id = {a["id"]: a for a in assets}
    assert ASSET_IDS["engine_bb"] in by_id
    assert ASSET_IDS["engine_sb"] in by_id
    assert by_id[ASSET_IDS["engine_bb"]]["side"] == "BB"
    assert by_id[ASSET_IDS["engine_sb"]]["side"] == "SB"

    bb_only = client.get("/api/v1/f1/assets", params={"side": "BB"})
    assert bb_only.status_code == 200
    bb_assets = bb_only.json()["assets"]
    assert all(a["side"] == "BB" for a in bb_assets)
    assert ASSET_IDS["engine_bb"] in {a["id"] for a in bb_assets}
    assert ASSET_IDS["engine_sb"] not in {a["id"] for a in bb_assets}


def test_get_known_asset_200_unknown_404() -> None:
    client = _client()
    known = client.get(f"/api/v1/f1/assets/{ASSET_IDS['engine_bb']}")
    assert known.status_code == 200
    body = known.json()
    assert body["id"] == ASSET_IDS["engine_bb"]
    assert body["side"] == "BB"
    assert body["serial"] == "2004030432"

    missing = client.get("/api/v1/f1/assets/AI-DOES-NOT-EXIST")
    assert missing.status_code == 404
    err = missing.json()["error"]
    assert err["code"] == "not_found"
    assert "message" in err


def test_reject_empty_query_400() -> None:
    client = _client()
    for payload in ({"query": ""}, {"query": "   "}, {}):
        response = client.post("/api/v1/f1/answer", json=payload)
        assert response.status_code == 400, payload
        err = response.json()["error"]
        assert err["code"] == "invalid_request"
        assert "message" in err


def test_assets_get_only_answer_is_post() -> None:
    client = _client()
    # Assets: GET only — mutating methods must not succeed
    assert client.post("/api/v1/f1/assets", json={}).status_code in {405, 422}
    assert client.put("/api/v1/f1/assets", json={}).status_code in {405, 422}
    assert client.patch("/api/v1/f1/assets", json={}).status_code in {405, 422}
    assert client.delete("/api/v1/f1/assets").status_code == 405

    # Answer: POST only
    assert client.get("/api/v1/f1/answer").status_code == 405
    assert client.put("/api/v1/f1/answer", json={"query": "x"}).status_code == 405
    assert client.delete("/api/v1/f1/answer").status_code == 405

    # Known asset detail is GET-only
    asset_path = f"/api/v1/f1/assets/{ASSET_IDS['engine_bb']}"
    assert client.post(asset_path, json={}).status_code in {405, 422}
    assert client.put(asset_path, json={}).status_code in {405, 422}
    assert client.patch(asset_path, json={}).status_code in {405, 422}
    assert client.delete(asset_path).status_code == 405
