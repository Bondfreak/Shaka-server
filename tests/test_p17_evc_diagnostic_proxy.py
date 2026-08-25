from __future__ import annotations

from fastapi.testclient import TestClient

from shaka_server.app import create_app
from shaka_server.core_client import CoreResult

SCENARIO_ID = "EVC-BB-NO-WAKE"


class FakeCore:
    def __init__(self, *, promote_candidate: bool = False, determine_root_cause: bool = False) -> None:
        self.calls: list[tuple[str, str]] = []
        self.promote_candidate = promote_candidate
        self.determine_root_cause = determine_root_cause

    def cog_diagnostic(self, scenario_id: str) -> CoreResult:
        self.calls.append(("cog_diagnostic", scenario_id))
        candidate_status = "verified" if self.promote_candidate else "candidate"
        return CoreResult(
            200,
            {
                "data": {
                    "id": "NAV-DIAG-EVC-BB-NO-WAKE-v0.1",
                    "scenarioId": scenario_id,
                    "graphId": "NAV-COG-EVC-v0.1",
                    "systemId": "SYS-EVC",
                    "status": "diagnostic_bounded_partial",
                    "rootCauseDetermined": self.determine_root_cause,
                    "symptom": {
                        "label": "Bagbord EVC-domæne vågner ikke ved key-on",
                        "affectedDomainId": "SYS-EVC-BB",
                    },
                    "verifiedAnchors": [
                        {
                            "step": 1,
                            "from": "AI-EVC-BB-KeyStart",
                            "type": "wakes",
                            "to": "SYS-EVC-BB",
                            "status": "verified",
                            "meaning": "Canonical wake-forventning.",
                            "check": "Verificér wake før downstream hypoteser.",
                        }
                    ],
                    "deferredInvestigation": [
                        {
                            "priority": 4,
                            "from": "AI-EVC-BB-PCU",
                            "type": "communicates_via",
                            "to": "AI-EVC-Backbone",
                            "status": candidate_status,
                            "meaning": "Relevant først efter wake/power er verificeret.",
                        }
                    ],
                    "notPrimaryForTotalNoWake": [
                        "AI-EVC-BB-PCU commands AI-EVC-BB-SteeringInterface"
                    ],
                },
                "meta": {
                    "schemaVersion": "1.0",
                    "sourceGraph": "NAV-COG-EVC-v0.1",
                    "projection": "verified_diagnostic_anchors_with_explicit_candidate_investigation",
                    "candidateRelationsPromoted": False,
                    "physicalCableRoutingVerified": False,
                    "diagnosticNature": "scenario_template_not_root_cause_determination",
                },
            },
        )

    def object_detail(self, public_id: str) -> CoreResult:
        return CoreResult(200, {"data": {"id": public_id, "type": "system"}, "meta": {"schemaVersion": "1.0"}})

    def asset_instance_detail(self, public_id: str) -> CoreResult: raise AssertionError("not used")
    def graph(self, public_id: str) -> CoreResult: raise AssertionError("not used")
    def resolve_asset_instance(self, context_public_id: str, asset_public_id: str) -> CoreResult: raise AssertionError("not used")
    def cog_graph(self, graph_id: str) -> CoreResult: raise AssertionError("not used")
    def cog_object(self, public_id: str) -> CoreResult: raise AssertionError("not used")
    def cog_flow(self, circuit_id: str) -> CoreResult: raise AssertionError("not used")
    def cog_topology(self, system_id: str) -> CoreResult: raise AssertionError("not used")


def test_server_proxies_bounded_evc_diagnostic_template() -> None:
    fake = FakeCore()
    response = TestClient(create_app(core_client=fake)).get(f"/api/v1/cog/diagnostics/{SCENARIO_ID}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["rootCauseDetermined"] is False
    assert data["verifiedAnchors"][0]["status"] == "verified"
    assert data["deferredInvestigation"][0]["status"] == "candidate"
    assert fake.calls == [("cog_diagnostic", SCENARIO_ID)]


def test_server_rejects_promoted_candidate_in_diagnostic_projection() -> None:
    response = TestClient(create_app(core_client=FakeCore(promote_candidate=True))).get(
        f"/api/v1/cog/diagnostics/{SCENARIO_ID}"
    )
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "dependency_contract_violation"


def test_server_rejects_root_cause_claim() -> None:
    response = TestClient(create_app(core_client=FakeCore(determine_root_cause=True))).get(
        f"/api/v1/cog/diagnostics/{SCENARIO_ID}"
    )
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "dependency_contract_violation"


def test_invalid_diagnostic_id_fails_before_core_access() -> None:
    fake = FakeCore()
    response = TestClient(create_app(core_client=fake)).get("/api/v1/cog/diagnostics/%20bad%20id%20")
    assert response.status_code == 400
    assert fake.calls == []
