from __future__ import annotations

from fastapi.testclient import TestClient

from shaka_server.app import create_app
from shaka_server.core_client import CoreResult

SYSTEM_ID = "SYS-EVC"
GRAPH_ID = "NAV-COG-EVC-v0.1"


class FakeCore:
    def __init__(self, *, leak_verified_as_candidate: bool = False, leak_candidate_as_verified: bool = False) -> None:
        self.calls: list[tuple[str, str]] = []
        self.leak_verified_as_candidate = leak_verified_as_candidate
        self.leak_candidate_as_verified = leak_candidate_as_verified

    def cog_topology(self, system_id: str) -> CoreResult:
        self.calls.append(("cog_topology", system_id))
        verified_status = "candidate" if self.leak_verified_as_candidate else "verified"
        candidate_status = "verified" if self.leak_candidate_as_verified else "candidate"
        return CoreResult(
            200,
            {
                "data": {
                    "id": "NAV-TOPOLOGY-EVC-v0.1",
                    "systemId": system_id,
                    "graphId": GRAPH_ID,
                    "status": "canonical_partial",
                    "complete": False,
                    "nodes": [
                        {"id": "SYS-EVC", "type": "EVCSystem", "label": "Shaka EVC and Controls"},
                        {"id": "SYS-EVC-BB", "type": "EVCDomain", "label": "Bagbord EVC Domain"},
                        {"id": "AI-EVC-BB-PCU", "type": "ControlUnit", "label": "Bagbord EVC PCU"},
                        {"id": "AI-EVC-Backbone", "type": "NetworkBackbone", "label": "EVC-C Network Backbone"},
                    ],
                    "edges": [
                        {"from": "SYS-EVC-BB", "type": "part_of", "to": "SYS-EVC", "status": verified_status},
                    ],
                    "deferredCandidates": [
                        {"from": "AI-EVC-BB-PCU", "type": "communicates_via", "to": "AI-EVC-Backbone", "status": candidate_status},
                    ],
                    "deferredCandidateCount": 1,
                },
                "meta": {
                    "schemaVersion": "1.0",
                    "sourceGraph": GRAPH_ID,
                    "projection": "verified_topology_with_deferred_candidates",
                    "physicalCableRoutingVerified": False,
                },
            },
        )

    def object_detail(self, public_id: str) -> CoreResult:
        return CoreResult(200, {"data": {"id": public_id, "type": "system"}, "meta": {"schemaVersion": "1.0"}})

    def asset_instance_detail(self, public_id: str) -> CoreResult:
        raise AssertionError("not used")

    def graph(self, public_id: str) -> CoreResult:
        raise AssertionError("not used")

    def resolve_asset_instance(self, context_public_id: str, asset_public_id: str) -> CoreResult:
        raise AssertionError("not used")

    def cog_graph(self, graph_id: str) -> CoreResult:
        raise AssertionError("not used")

    def cog_object(self, public_id: str) -> CoreResult:
        raise AssertionError("not used")

    def cog_flow(self, circuit_id: str) -> CoreResult:
        raise AssertionError("not used")


def test_server_proxies_bounded_evc_topology() -> None:
    fake = FakeCore()
    response = TestClient(create_app(core_client=fake)).get(f"/api/v1/cog/topologies/{SYSTEM_ID}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["status"] == "canonical_partial"
    assert payload["data"]["edges"][0]["status"] == "verified"
    assert payload["data"]["deferredCandidates"][0]["status"] == "candidate"
    assert payload["meta"]["physicalCableRoutingVerified"] is False
    assert fake.calls == [("cog_topology", SYSTEM_ID)]


def test_server_fails_closed_if_verified_topology_edge_is_not_verified() -> None:
    response = TestClient(create_app(core_client=FakeCore(leak_verified_as_candidate=True))).get(
        f"/api/v1/cog/topologies/{SYSTEM_ID}"
    )
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "dependency_contract_violation"


def test_server_fails_closed_if_deferred_candidate_is_promoted() -> None:
    response = TestClient(create_app(core_client=FakeCore(leak_candidate_as_verified=True))).get(
        f"/api/v1/cog/topologies/{SYSTEM_ID}"
    )
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "dependency_contract_violation"


def test_invalid_topology_id_fails_before_core_access() -> None:
    fake = FakeCore()
    response = TestClient(create_app(core_client=fake)).get("/api/v1/cog/topologies/%20bad%20id%20")
    assert response.status_code == 400
    assert fake.calls == []
