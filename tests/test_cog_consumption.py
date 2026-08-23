from __future__ import annotations

from typing import Any, Callable

from fastapi.testclient import TestClient

from shaka_server.app import create_app
from shaka_server.core_client import CoreResult

GRAPH_ID = "NAV-COG-D4-BB-COOLING-v0.1"
OBJECT_ID = "AI-D4-BB-SeaWaterPump"


class FakeCore:
    def __init__(self, *, leak_candidate: bool = False) -> None:
        self.calls: list[tuple[str, str]] = []
        self.leak_candidate = leak_candidate

    def object_detail(self, public_id: str) -> CoreResult:
        self.calls.append(("object", public_id))
        return CoreResult(
            200,
            {
                "data": {
                    "id": public_id,
                    "type": "system",
                    "name": "Cooling and Exhaust",
                    "vessel": {"id": "VSL-0001"},
                    "parent": None,
                    "provenance": [],
                },
                "meta": {"schemaVersion": "1.0"},
            },
        )

    def cog_graph(self, graph_id: str) -> CoreResult:
        self.calls.append(("cog_graph", graph_id))
        return CoreResult(
            200,
            {
                "data": {
                    "id": graph_id,
                    "status": "canonical",
                    "objectCount": 28,
                    "relationCount": 42,
                    "deferredCandidateCount": 2,
                    "sourcePath": "cog/canonical/d4-bb-cooling-v0.1.yaml",
                },
                "meta": {"schemaVersion": "1.0"},
            },
        )

    def cog_object(self, object_id: str) -> CoreResult:
        self.calls.append(("cog_object", object_id))
        status = "candidate" if self.leak_candidate else "verified"
        return CoreResult(
            200,
            {
                "data": {
                    "id": object_id,
                    "type": "Pump",
                    "label": "Bagbord Sea Water Pump",
                    "relations": [
                        {
                            "from": "AI-D4-BB-SeaWaterFilter",
                            "type": "supplies",
                            "to": object_id,
                            "status": status,
                        }
                    ],
                },
                "meta": {"graphId": GRAPH_ID, "schemaVersion": "1.0"},
            },
        )

    def asset_instance_detail(self, public_id: str) -> CoreResult:
        raise AssertionError("not used")

    def graph(self, public_id: str) -> CoreResult:
        raise AssertionError("not used")

    def resolve_asset_instance(self, context_public_id: str, asset_public_id: str) -> CoreResult:
        raise AssertionError("not used")


class CogGroundedProvider:
    def explain(
        self,
        *,
        context: dict[str, str],
        run_tool: Callable[[str, dict[str, str]], dict[str, Any]],
    ) -> str:
        graph = run_tool("get_canonical_graph", {"graph_id": GRAPH_ID})
        obj = run_tool("get_canonical_object", {"object_id": context["contextInstanceId"]})
        assert graph["data"]["status"] == "canonical"
        assert obj["data"]["relations"][0]["status"] == "verified"
        return "Canonical graph viser den verificerede relation fra søvandsfilter til søvandspumpe."


def test_server_proxies_canonical_graph_metadata() -> None:
    fake = FakeCore()
    response = TestClient(create_app(core_client=fake)).get(f"/api/v1/cog/graphs/{GRAPH_ID}")
    assert response.status_code == 200
    assert response.json()["data"]["relationCount"] == 42
    assert fake.calls == [("cog_graph", GRAPH_ID)]


def test_server_proxies_verified_canonical_object_relations() -> None:
    fake = FakeCore()
    response = TestClient(create_app(core_client=fake)).get(f"/api/v1/cog/objects/{OBJECT_ID}")
    assert response.status_code == 200
    assert response.json()["data"]["relations"][0]["status"] == "verified"
    assert fake.calls == [("cog_object", OBJECT_ID)]


def test_server_rejects_candidate_relation_leak_from_core() -> None:
    fake = FakeCore(leak_candidate=True)
    response = TestClient(create_app(core_client=fake)).get(f"/api/v1/cog/objects/{OBJECT_ID}")
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "dependency_contract_violation"


def test_kai_can_ground_answer_in_canonical_graph_tools() -> None:
    fake = FakeCore()
    response = TestClient(create_app(core_client=fake, kai_provider=CogGroundedProvider())).post(
        "/api/v1/kai/explain",
        json={"contextInstanceId": OBJECT_ID, "intent": "explain_selected_context"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert [item["name"] for item in payload["data"]["toolTrace"]] == [
        "get_canonical_graph",
        "get_canonical_object",
    ]
    assert fake.calls == [("cog_graph", GRAPH_ID), ("cog_object", OBJECT_ID)]


def test_invalid_cog_id_fails_before_core_access() -> None:
    fake = FakeCore()
    response = TestClient(create_app(core_client=fake)).get("/api/v1/cog/objects/%20bad%20id%20")
    assert response.status_code == 400
    assert fake.calls == []
