from __future__ import annotations

import copy

import pytest
from fastapi.testclient import TestClient

from shaka_server.app import create_app
from shaka_server.core_client import CoreContractError, CoreResult


DETAIL = {
    "data": {"id": "AI-D4-BB-SeaWaterPump", "type": "asset_instance"},
    "meta": {"schemaVersion": "1.0"},
}
GRAPH = {
    "data": {"rootId": "AI-D4-BB-SeaWaterPump", "nodes": [], "edges": []},
    "meta": {"depth": 1, "schemaVersion": "1.0"},
}
RESOLVED = {
    "data": {"id": "AI-D4-BB-SeaWaterFilter", "type": "asset_instance"},
    "meta": {
        "schemaVersion": "1.0",
        "resolution": {
            "contextId": "AI-D4-BB-SeaWaterPump",
            "assetId": "ASSET-D4-SEAWATER-FILTER",
            "strategy": "same_host_slot_current_installed",
        },
    },
}
SYSTEM = {
    "data": {"id": "SYS-0003", "type": "system"},
    "meta": {"schemaVersion": "1.0"},
}


def error_payload(status: int) -> dict[str, object]:
    return {"error": {"code": f"core_{status}", "message": "bounded Core error"}}


class FakeCore:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.mode = "ok"

    def asset_instance_detail(self, public_id: str) -> CoreResult:
        self.calls.append(("detail", public_id))
        if self.mode in {"400", "404", "409", "503"}:
            status = int(self.mode)
            return CoreResult(status, error_payload(status))
        if self.mode == "malformed":
            return CoreResult(200, {"data": {"type": "asset_instance"}})
        if self.mode == "wrong_detail_id":
            payload = copy.deepcopy(DETAIL)
            payload["data"]["id"] = "AI-WRONG"
            return CoreResult(200, payload)
        if self.mode == "malformed_error":
            return CoreResult(404, {"error": {"code": 404, "message": "bad"}})
        if self.mode == "unexpected_status":
            return CoreResult(418, error_payload(418))
        if self.mode == "timeout":
            raise CoreContractError("core_unavailable")
        return CoreResult(200, DETAIL)

    def graph(self, public_id: str) -> CoreResult:
        self.calls.append(("graph", public_id))
        if self.mode == "wrong_graph_root":
            payload = copy.deepcopy(GRAPH)
            payload["data"]["rootId"] = "AI-WRONG"
            return CoreResult(200, payload)
        return CoreResult(200, GRAPH)

    def resolve_asset_instance(self, context_public_id: str, asset_public_id: str) -> CoreResult:
        self.calls.append(("resolve", context_public_id, asset_public_id))
        if self.mode == "wrong_resolution_context":
            payload = copy.deepcopy(RESOLVED)
            payload["meta"]["resolution"]["contextId"] = "AI-WRONG"
            return CoreResult(200, payload)
        return CoreResult(200, RESOLVED)

    def object_detail(self, public_id: str) -> CoreResult:
        self.calls.append(("object", public_id))
        if self.mode == "unavailable":
            raise CoreContractError("core_unavailable")
        if self.mode == "readiness_503":
            return CoreResult(503, error_payload(503))
        if self.mode == "readiness_malformed":
            return CoreResult(200, {"data": {"id": "SYS-0003", "type": "system"}})
        if self.mode == "wrong_object_id":
            payload = copy.deepcopy(SYSTEM)
            payload["data"]["id"] = "SYS-WRONG"
            return CoreResult(200, payload)
        return CoreResult(200, SYSTEM)


def client_for(fake: FakeCore) -> TestClient:
    return TestClient(create_app(core_client=fake))


def test_liveness_has_no_core_dependency() -> None:
    fake = FakeCore()
    response = client_for(fake).get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"service": "shaka-server", "status": "ok"}
    assert fake.calls == []


def test_readiness_uses_existing_bounded_core_contract() -> None:
    fake = FakeCore()
    response = client_for(fake).get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"service": "shaka-server", "status": "ready"}
    assert fake.calls == [("object", "SYS-0003")]


def test_readiness_maps_core_unavailable_fail_closed() -> None:
    fake = FakeCore()
    fake.mode = "unavailable"
    response = client_for(fake).get("/readyz")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "dependency_unavailable"


def test_readiness_maps_non_200_core_result_to_unavailable() -> None:
    fake = FakeCore()
    fake.mode = "readiness_503"
    response = client_for(fake).get("/readyz")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "dependency_unavailable"


def test_readiness_rejects_malformed_success_payload() -> None:
    fake = FakeCore()
    fake.mode = "readiness_malformed"
    response = client_for(fake).get("/readyz")
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "dependency_contract_violation"


def test_four_bounded_gateway_operations() -> None:
    fake = FakeCore()
    client = client_for(fake)
    assert client.get("/api/v1/asset-instances/AI-D4-BB-SeaWaterPump").status_code == 200
    assert client.get("/api/v1/asset-instances/AI-D4-BB-SeaWaterPump/graph?depth=1").status_code == 200
    assert client.get(
        "/api/v1/asset-instances/AI-D4-BB-SeaWaterPump/resolve-asset/ASSET-D4-SEAWATER-FILTER"
    ).status_code == 200
    assert client.get("/api/v1/objects/SYS-0003").status_code == 200


def test_invalid_id_is_rejected_before_core_call() -> None:
    fake = FakeCore()
    response = client_for(fake).get("/api/v1/asset-instances/%20bad")
    assert response.status_code == 400
    assert fake.calls == []


def test_graph_requires_exact_depth_one() -> None:
    fake = FakeCore()
    client = client_for(fake)
    assert client.get("/api/v1/asset-instances/AI-D4-BB-SeaWaterPump/graph").status_code == 400
    assert client.get("/api/v1/asset-instances/AI-D4-BB-SeaWaterPump/graph?depth=2").status_code == 400
    assert fake.calls == []


@pytest.mark.parametrize("status", [400, 404, 409, 503])
def test_bounded_core_errors_are_mapped_deterministically(status: int) -> None:
    fake = FakeCore()
    fake.mode = str(status)
    response = client_for(fake).get("/api/v1/asset-instances/AI-D4-BB-SeaWaterPump")
    assert response.status_code == status
    assert response.json()["error"]["code"] == f"core_{status}"


@pytest.mark.parametrize(
    ("mode", "path"),
    [
        ("malformed", "/api/v1/asset-instances/AI-D4-BB-SeaWaterPump"),
        ("wrong_detail_id", "/api/v1/asset-instances/AI-D4-BB-SeaWaterPump"),
        ("wrong_graph_root", "/api/v1/asset-instances/AI-D4-BB-SeaWaterPump/graph?depth=1"),
        (
            "wrong_resolution_context",
            "/api/v1/asset-instances/AI-D4-BB-SeaWaterPump/resolve-asset/ASSET-D4-SEAWATER-FILTER",
        ),
        ("wrong_object_id", "/api/v1/objects/SYS-0003"),
        ("malformed_error", "/api/v1/asset-instances/AI-D4-BB-SeaWaterPump"),
        ("unexpected_status", "/api/v1/asset-instances/AI-D4-BB-SeaWaterPump"),
    ],
)
def test_malformed_or_mismatched_core_responses_fail_closed(mode: str, path: str) -> None:
    fake = FakeCore()
    fake.mode = mode
    response = client_for(fake).get(path)
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "dependency_contract_violation"


def test_core_timeout_is_bounded_unavailable() -> None:
    fake = FakeCore()
    fake.mode = "timeout"
    response = client_for(fake).get("/api/v1/asset-instances/AI-D4-BB-SeaWaterPump")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "dependency_unavailable"


def test_unlisted_route_is_not_a_generic_proxy() -> None:
    fake = FakeCore()
    response = client_for(fake).get("/proxy/api/v1/anything")
    assert response.status_code == 404
    assert fake.calls == []
