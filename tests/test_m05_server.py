from __future__ import annotations

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

    def health(self) -> CoreResult:
        self.calls.append(("health",))
        if self.mode == "unavailable":
            raise CoreContractError("core_unavailable")
        return CoreResult(200, {"status": "ok"})

    def asset_instance_detail(self, public_id: str) -> CoreResult:
        self.calls.append(("detail", public_id))
        if self.mode in {"400", "404", "409", "503"}:
            status = int(self.mode)
            return CoreResult(status, error_payload(status))
        if self.mode == "malformed":
            return CoreResult(200, {"data": {"type": "asset_instance"}})
        if self.mode == "timeout":
            raise CoreContractError("core_unavailable")
        return CoreResult(200, DETAIL)

    def graph(self, public_id: str) -> CoreResult:
        self.calls.append(("graph", public_id))
        return CoreResult(200, GRAPH)

    def resolve_asset_instance(self, context_public_id: str, asset_public_id: str) -> CoreResult:
        self.calls.append(("resolve", context_public_id, asset_public_id))
        return CoreResult(200, RESOLVED)

    def object_detail(self, public_id: str) -> CoreResult:
        self.calls.append(("object", public_id))
        return CoreResult(200, SYSTEM)


def client_for(fake: FakeCore) -> TestClient:
    return TestClient(create_app(core_client=fake))


def test_liveness_has_no_core_dependency() -> None:
    fake = FakeCore()
    response = client_for(fake).get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"service": "shaka-server", "status": "ok"}
    assert fake.calls == []


def test_readiness_checks_core_but_not_db() -> None:
    fake = FakeCore()
    response = client_for(fake).get("/readyz")
    assert response.status_code == 200
    assert fake.calls == [("health",)]


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


def test_malformed_core_payload_fails_closed() -> None:
    fake = FakeCore()
    fake.mode = "malformed"
    response = client_for(fake).get("/api/v1/asset-instances/AI-D4-BB-SeaWaterPump")
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "dependency_contract_violation"


def test_core_timeout_is_bounded_unavailable() -> None:
    fake = FakeCore()
    fake.mode = "timeout"
    response = client_for(fake).get("/api/v1/asset-instances/AI-D4-BB-SeaWaterPump")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "dependency_unavailable"


def test_core_unavailability_is_bounded() -> None:
    fake = FakeCore()
    fake.mode = "unavailable"
    response = client_for(fake).get("/readyz")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "dependency_unavailable"


def test_unlisted_route_is_not_a_generic_proxy() -> None:
    fake = FakeCore()
    response = client_for(fake).get("/proxy/api/v1/anything")
    assert response.status_code == 404
    assert fake.calls == []
