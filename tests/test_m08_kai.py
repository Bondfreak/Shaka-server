from __future__ import annotations

from typing import Any, Callable

from fastapi.testclient import TestClient

from shaka_server.app import create_app
from shaka_server.core_client import CoreResult


INSTANCE_ID = "AI-D4-BB-SeaWaterPump"


class FakeCore:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    def asset_instance_detail(self, public_id: str) -> CoreResult:
        self.calls.append(("detail", public_id))
        return CoreResult(
            200,
            {
                "data": {
                    "id": public_id,
                    "type": "asset_instance",
                    "asset": {"id": "ASSET-D4-SEAWATER-PUMP"},
                    "host": {"id": "SYS-0003"},
                    "slot": "PORT",
                    "state": "INSTALLED",
                    "provenance": [{"source": "source://pump"}],
                },
                "meta": {"schemaVersion": "1.0"},
            },
        )

    def graph(self, public_id: str) -> CoreResult:
        self.calls.append(("graph", public_id))
        return CoreResult(
            200,
            {
                "data": {
                    "rootId": public_id,
                    "nodes": [],
                    "edges": [
                        {"from": public_id, "to": "SYS-0003", "type": "PART_OF_SYSTEM"},
                        {"from": public_id, "to": "LOC-0018", "type": "LOCATED_IN"},
                        {"from": "ASSET-D4-SEAWATER-FILTER", "to": public_id, "type": "FLOW_TO"},
                        {"from": public_id, "to": "ASSET-D4-CHARGE-AIR-COOLER", "type": "FLOW_TO"},
                    ],
                },
                "meta": {"schemaVersion": "1.0", "depth": 1},
            },
        )

    def resolve_asset_instance(self, context_public_id: str, asset_public_id: str) -> CoreResult:
        raise AssertionError("M08 minimal tool set must not use resolver")

    def object_detail(self, public_id: str) -> CoreResult:
        self.calls.append(("object", public_id))
        object_type = "location" if public_id.startswith("LOC-") else "system"
        name = "Port machinery zone" if object_type == "location" else "Cooling and Exhaust"
        return CoreResult(
            200,
            {
                "data": {
                    "id": public_id,
                    "type": object_type,
                    "name": name,
                    "vessel": {"id": "VSL-0001"},
                    "parent": None,
                    "provenance": [{"source": f"source://{public_id.lower()}"}],
                },
                "meta": {"schemaVersion": "1.0"},
            },
        )


class GroundedFakeProvider:
    def explain(
        self,
        *,
        context: dict[str, str],
        run_tool: Callable[[str, dict[str, str]], dict[str, Any]],
    ) -> str:
        instance_id = context["contextInstanceId"]
        detail = run_tool("get_asset_instance_detail", {"instance_id": instance_id})
        graph = run_tool("get_direct_relations", {"instance_id": instance_id})
        system = run_tool("get_object_detail", {"object_id": "SYS-0003"})
        location = run_tool("get_object_detail", {"object_id": "LOC-0018"})
        assert detail["data"]["slot"] == "PORT"
        assert graph["data"]["rootId"] == instance_id
        assert system["data"]["name"] == "Cooling and Exhaust"
        assert location["data"]["name"] == "Port machinery zone"
        return (
            "Den valgte installerede søvandspumpe er PORT / INSTALLED i SYS-0003 "
            "og LOC-0018. De direkte Core-relationer viser FLOW_TO ind fra søvandsfilteret "
            "og FLOW_TO ud mod ladeluftkøleren."
        )


class UnsupportedToolProvider:
    def explain(self, *, context, run_tool):
        run_tool("fetch_arbitrary_url", {"url": "https://example.invalid"})
        return "should not be returned"


class InvalidArgumentProvider:
    def explain(self, *, context, run_tool):
        run_tool("get_object_detail", {"object_id": " bad id "})
        return "should not be returned"


class NoToolProvider:
    def explain(self, *, context, run_tool):
        return "ungrounded"


def client_for(fake: FakeCore, provider=None) -> TestClient:
    return TestClient(create_app(core_client=fake, kai_provider=provider))


def request_payload() -> dict[str, str]:
    return {"contextInstanceId": INSTANCE_ID, "intent": "explain_selected_context"}


def test_kai_is_fail_closed_when_provider_is_not_configured() -> None:
    fake = FakeCore()
    response = client_for(fake).post("/api/v1/kai/explain", json=request_payload())
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "kai_unavailable"
    assert fake.calls == []


def test_grounded_provider_can_use_only_three_explicit_read_tools() -> None:
    fake = FakeCore()
    response = client_for(fake, GroundedFakeProvider()).post(
        "/api/v1/kai/explain", json=request_payload()
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"] == {"schemaVersion": "1.0", "toolGrounded": True}
    assert payload["data"]["contextInstanceId"] == INSTANCE_ID
    assert "SYS-0003" in payload["data"]["explanation"]
    assert "LOC-0018" in payload["data"]["explanation"]
    assert [item["name"] for item in payload["data"]["toolTrace"]] == [
        "get_asset_instance_detail",
        "get_direct_relations",
        "get_object_detail",
        "get_object_detail",
    ]
    assert fake.calls == [
        ("detail", INSTANCE_ID),
        ("graph", INSTANCE_ID),
        ("object", "SYS-0003"),
        ("object", "LOC-0018"),
    ]


def test_unsupported_tool_fails_closed_before_core_access() -> None:
    fake = FakeCore()
    response = client_for(fake, UnsupportedToolProvider()).post(
        "/api/v1/kai/explain", json=request_payload()
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "unsupported_tool"
    assert fake.calls == []


def test_invalid_tool_arguments_fail_closed_before_core_access() -> None:
    fake = FakeCore()
    response = client_for(fake, InvalidArgumentProvider()).post(
        "/api/v1/kai/explain", json=request_payload()
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"
    assert fake.calls == []


def test_unapproved_kai_intent_is_rejected_before_provider_or_core() -> None:
    fake = FakeCore()
    response = client_for(fake, GroundedFakeProvider()).post(
        "/api/v1/kai/explain",
        json={"contextInstanceId": INSTANCE_ID, "intent": "run_sql"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "unsupported_request"
    assert fake.calls == []


def test_extra_request_fields_are_rejected() -> None:
    fake = FakeCore()
    response = client_for(fake, GroundedFakeProvider()).post(
        "/api/v1/kai/explain",
        json={**request_payload(), "url": "https://example.invalid"},
    )
    assert response.status_code == 400
    assert fake.calls == []


def test_provider_must_use_at_least_one_approved_tool() -> None:
    fake = FakeCore()
    response = client_for(fake, NoToolProvider()).post(
        "/api/v1/kai/explain", json=request_payload()
    )
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "kai_contract_violation"
    assert fake.calls == []


def test_cors_allows_only_bounded_ui_post_addition() -> None:
    fake = FakeCore()
    response = client_for(fake).options(
        "/api/v1/kai/explain",
        headers={
            "Origin": "https://bondfreak.github.io",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://bondfreak.github.io"
    assert "POST" in response.headers["access-control-allow-methods"]
    assert "Content-Type" in response.headers["access-control-allow-headers"]
