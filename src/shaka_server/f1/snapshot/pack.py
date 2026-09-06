"""Frozen AC-01…06 fixture pack — synthetic but realistic; serials never invented."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from shaka_server.f1.core.types import (
    Asset,
    Claim,
    Event,
    Evidence,
    KnowledgeObject,
    Observation,
    Source,
)
from shaka_server.f1.assets.bootstrap import bootstrap_shaka_assets
from shaka_server.f1.core.validators import (
    validate_claim,
    validate_event,
    validate_evidence,
    validate_knowledge_object,
    validate_observation,
    validate_source,
)

FIXTURE_SERIALS = {
    "BB_ENGINE": "2004030432",
    "SB_ENGINE": "2004030433",
}

FIXTURE_PART_IMPELLER = "3588475"
FIXTURE_PART_ABSENT = "99999999"

# Deterministic fake sha256 hexes for Source.content_hash (not live Drive hashes).
_H = {
    "9631": "a9631a9631a9631a9631a9631a9631a9631a9631a9631a9631a9631a9631a963",
    "9273": "b9273b9273b9273b9273b9273b9273b9273b9273b9273b9273b9273b9273b927",
    "d4lab": "c0d40ab0d40ab0d40ab0d40ab0d40ab0d40ab0d40ab0d40ab0d40ab0d40ab0d4",
    "d6lab": "d0d60ab0d60ab0d60ab0d60ab0d60ab0d60ab0d60ab0d60ab0d60ab0d60ab0d6",
}


@dataclass
class FixtureSnapshot:
    """In-memory frozen snapshot of AC-critical records."""

    snapshot_id: str = "ac-fixture-v1"
    assets: list[Asset] = field(default_factory=list)
    sources: list[Source] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    observations: list[Observation] = field(default_factory=list)
    knowledge_objects: list[KnowledgeObject] = field(default_factory=list)
    # Free-text conflict statements for CF-001 (D4 vs D6 labour on 9631).
    conflict_statements: list[dict[str, str]] = field(default_factory=list)
    # Indexed part numbers present in the pack (exact P/N lookup).
    part_numbers: set[str] = field(default_factory=set)
    # Extra searchable tags keyed by entity id.
    tags: dict[str, list[str]] = field(default_factory=dict)

    def all_entities(self) -> list[Any]:
        return [
            *self.knowledge_objects,
            *self.assets,
            *self.sources,
            *self.evidence,
            *self.claims,
            *self.events,
            *self.observations,
        ]

    def by_id(self) -> dict[str, Any]:
        return {e.id: e for e in self.all_entities()}


def build_ac_fixture_snapshot() -> FixtureSnapshot:
    """Build the frozen AC fixture pack used by retrieval + composer tests."""

    kos = [
        validate_knowledge_object(
            {
                "id": "KO-D4-0007",
                "kind": "KnowledgeObject",
                "title": "Seawater pump impeller",
                "scope": "D4-300 / IPS400",
            }
        ),
        validate_knowledge_object(
            {
                "id": "KO-D4-0036",
                "kind": "KnowledgeObject",
                "title": "Generator belt / auxiliary drive belt",
                "scope": "D4-300",
            }
        ),
        validate_knowledge_object(
            {
                "id": "KO-D4-0190",
                "kind": "KnowledgeObject",
                "title": "PCU / EVC connector service notes",
                "scope": "EVC-C / D4-300",
            }
        ),
        validate_knowledge_object(
            {
                "id": "KO-D4-0062",
                "kind": "KnowledgeObject",
                "title": "Engine identity / ID plate (D4-300D-C)",
                "scope": "D4-300 / IPS400",
            }
        ),
        validate_knowledge_object(
            {
                "id": "KO-D4-0103",
                "kind": "KnowledgeObject",
                "title": "Engine-to-IPS drive interface",
                "scope": "D4-300 / IPS400",
            }
        ),
    ]

    # F1-T05: bootstrap vessel Asset Instances (Unknown-safe; BB/SB never merged).
    assets = bootstrap_shaka_assets()

    sources = [
        validate_source(
            {
                "id": "SRC-FAKTURA-9631",
                "kind": "Source",
                "sourceType": "invoice",
                "issuer": "yard",
                "title": "Faktura 9631 — winter service / impeller kits",
                "contentHash": _H["9631"],
                "mimeType": "application/pdf",
                "storageRef": "fixture://faktura-9631",
                "authorityClass": "service_invoice",
            }
        ),
        validate_source(
            {
                "id": "SRC-FAKTURA-9273",
                "kind": "Source",
                "sourceType": "invoice",
                "issuer": "yard",
                "title": "Faktura 9273 — BB PCU/EVC service",
                "contentHash": _H["9273"],
                "mimeType": "application/pdf",
                "storageRef": "fixture://faktura-9273",
                "authorityClass": "service_invoice",
            }
        ),
        validate_source(
            {
                "id": "SRC-DOC-D4-LABOUR",
                "kind": "Source",
                "sourceType": "extract",
                "issuer": "yard",
                "title": "Labour wording D4 (9631 context)",
                "contentHash": _H["d4lab"],
                "mimeType": "text/plain",
                "storageRef": "fixture://doc-d4-labour",
            }
        ),
        validate_source(
            {
                "id": "SRC-DOC-D6-LABOUR",
                "kind": "Source",
                "sourceType": "extract",
                "issuer": "yard",
                "title": "Labour wording D6 (9631 context)",
                "contentHash": _H["d6lab"],
                "mimeType": "text/plain",
                "storageRef": "fixture://doc-d6-labour",
            }
        ),
    ]

    evidence = [
        validate_evidence(
            {
                "id": "EVD-FAKTURA-9631-IMPELLER",
                "kind": "Evidence",
                "sourceId": "SRC-FAKTURA-9631",
                "locator": "line:3588475",
                "extract": f"IMPELLERSATS {FIXTURE_PART_IMPELLER} × 2 St. (no BB/SB allocation)",
                "context": "Faktura 9631 parts — dual quantity without side",
                "supportsClaimIds": ["CLM-IMPELLER-INVOICED-2024"],
                "provenance": "fixture",
            }
        ),
        validate_evidence(
            {
                "id": "EVD-FAKTURA-9631-DATE",
                "kind": "Evidence",
                "sourceId": "SRC-FAKTURA-9631",
                "locator": "header:date",
                "extract": "Invoice date 2024-11 / winter package 2025/26 context",
                "context": "Service timing for impeller invoice event",
                "supportsClaimIds": ["CLM-IMPELLER-INVOICED-2024"],
                "provenance": "fixture",
            }
        ),
        validate_evidence(
            {
                "id": "EVD-FAKTURA-9273",
                "kind": "Evidence",
                "sourceId": "SRC-FAKTURA-9273",
                "locator": "body:pcu",
                "extract": "BB no-start until SB; oily PCU contact cleaned; VODIA; test run",
                "context": "2025-08 PCU/EVC service",
                "supportsClaimIds": [
                    "CLM-PCU-CLEAN-2025",
                    "CLM-PCU-OIL-HYP",
                    "CLM-EVC-TEST-RUN-2025",
                ],
                "provenance": "fixture",
            }
        ),
        validate_evidence(
            {
                "id": "EVD-D4-LABOUR",
                "kind": "Evidence",
                "sourceId": "SRC-DOC-D4-LABOUR",
                "locator": "labour",
                "extract": "Labour described as D4 impeller service",
                "context": "CF-001 / AC-17 related — D4 wording on 9631 labour",
                "challengesClaimIds": ["CLM-MOTOR-TYPE-D6"],
                "supportsClaimIds": ["CLM-MOTOR-TYPE-D4"],
                "provenance": "fixture",
            }
        ),
        validate_evidence(
            {
                "id": "EVD-D6-LABOUR",
                "kind": "Evidence",
                "sourceId": "SRC-DOC-D6-LABOUR",
                "locator": "labour:line100",
                "extract": "Labour described as D6 related work",
                "context": "CF-001 / AC-17 related — D6 wording on 9631 labour",
                "challengesClaimIds": ["CLM-MOTOR-TYPE-D4"],
                "supportsClaimIds": ["CLM-MOTOR-TYPE-D6"],
                "provenance": "fixture",
            }
        ),
    ]

    claims = [
        validate_claim(
            {
                "id": "CLM-IMPELLER-INVOICED-2024",
                "kind": "Claim",
                "statement": (
                    f"Impeller kits {FIXTURE_PART_IMPELLER} ×2 invoiced on Faktura 9631; "
                    "side allocation unknown; install not proven by invoice alone"
                ),
                "subjectId": "AI-D4-IMPELLER-KIT",
                "predicate": "invoiced_quantity",
                "value": "2",
                "timeValidity": "2024",
                "status": "invoiced_without_action",
                "evidenceIds": ["EVD-FAKTURA-9631-IMPELLER", "EVD-FAKTURA-9631-DATE"],
                "role": "action",
            }
        ),
        validate_claim(
            {
                "id": "CLM-IMPELLER-SIDE-UNKNOWN",
                "kind": "Claim",
                "statement": (
                    "Quantity ×2 without side evidence does not allocate BB vs SB; "
                    "cannot conclude both motors' impellers were changed"
                ),
                "subjectId": "AI-D4-IMPELLER-KIT",
                "predicate": "side_allocation",
                "value": "unknown",
                "status": "unknown",
                "evidenceIds": ["EVD-FAKTURA-9631-IMPELLER"],
                "role": "other",
            }
        ),
        validate_claim(
            {
                "id": "CLM-PCU-CLEAN-2025",
                "kind": "Claim",
                "statement": "PCU connector cleaned (not replaced)",
                "subjectId": "AI-D4-BB-PCU",
                "predicate": "service_action",
                "value": "cleaned",
                "timeValidity": "2025-08",
                "status": "documented",
                "evidenceIds": ["EVD-FAKTURA-9273"],
                "role": "action",
            }
        ),
        validate_claim(
            {
                "id": "CLM-EVC-TEST-RUN-2025",
                "kind": "Claim",
                "statement": "Test run / provkørsel after PCU cleaning documented; lasting fix unknown",
                "subjectId": "AI-D4-BB-PCU",
                "predicate": "validation",
                "value": "test_run_ok_short_term",
                "timeValidity": "2025-08",
                "status": "unknown",
                "evidenceIds": ["EVD-FAKTURA-9273"],
                "role": "result",
            }
        ),
        validate_claim(
            {
                "id": "CLM-PCU-OIL-HYP",
                "kind": "Claim",
                "statement": "Oiled / oily PCU contact may explain BB no-start (possible cause only)",
                "subjectId": "AI-D4-BB-PCU",
                "predicate": "possible_cause",
                "value": "oily_pcu_contact",
                "timeValidity": "2025-08",
                "status": "inferred",
                "evidenceIds": ["EVD-FAKTURA-9273"],
                "role": "hypothesis",
            }
        ),
        validate_claim(
            {
                "id": "CLM-MOTOR-TYPE-D4",
                "kind": "Claim",
                "statement": "Labour described as D4 impeller service (9631 context)",
                "subjectId": "AI-D4-BB-ENGINE",
                "predicate": "motor_type_wording",
                "value": "D4",
                "status": "conflicted",
                "evidenceIds": ["EVD-D4-LABOUR"],
                "role": "other",
            }
        ),
        validate_claim(
            {
                "id": "CLM-MOTOR-TYPE-D6",
                "kind": "Claim",
                "statement": "Labour described as D6 related work (9631 context)",
                "subjectId": "AI-D4-BB-ENGINE",
                "predicate": "motor_type_wording",
                "value": "D6",
                "status": "conflicted",
                "evidenceIds": ["EVD-D6-LABOUR"],
                "role": "other",
            }
        ),
    ]

    events = [
        validate_event(
            {
                "id": "EVT-FAKTURA-9631-IMPELLER",
                "kind": "Event",
                "eventType": "service_invoice",
                "timeOrPeriod": "2024-11",
                "subjectIds": ["AI-D4-IMPELLER-KIT"],
                "sourceIds": ["SRC-FAKTURA-9631"],
                "evidenceIds": ["EVD-FAKTURA-9631-IMPELLER", "EVD-FAKTURA-9631-DATE"],
                "role": "invoiced",
                "outcome": None,
                "location": "yard",
            }
        ),
        validate_event(
            {
                "id": "EVT-FAKTURA-9273-PCU",
                "kind": "Event",
                "eventType": "service_action",
                "timeOrPeriod": "2025-08-26",
                "subjectIds": ["AI-D4-BB-PCU", "AI-D4-BB-ENGINE"],
                "sourceIds": ["SRC-FAKTURA-9273"],
                "evidenceIds": ["EVD-FAKTURA-9273"],
                "role": "action",
                "outcome": "cleaned; lasting outcome unknown",
                "location": "yard",
            }
        ),
        validate_event(
            {
                "id": "EVT-FAKTURA-9273-VALIDATION",
                "kind": "Event",
                "eventType": "validation",
                "timeOrPeriod": "2025-08-26",
                "subjectIds": ["AI-D4-BB-PCU"],
                "sourceIds": ["SRC-FAKTURA-9273"],
                "evidenceIds": ["EVD-FAKTURA-9273"],
                "role": "validation",
                "outcome": "test_run_documented; lasting_fix_unknown",
            }
        ),
    ]

    observations = [
        validate_observation(
            {
                "id": "OBS-BB-NO-START-2025",
                "kind": "Observation",
                "subjectId": "AI-D4-BB-ENGINE",
                "side": "BB",
                "observedAt": "2025-08-26",
                "context": "BB would not start until SB started; oily PCU contact noted",
                "value": "no_start_until_sb",
                "observer": "yard",
                "evidenceIds": ["EVD-FAKTURA-9273"],
                "status": "recorded",
            }
        ),
    ]

    conflict_statements = [
        {"id": "DOC-D4-LABOUR", "text": "Labour described as D4 impeller service"},
        {"id": "DOC-D6-LABOUR", "text": "Labour described as D6 related work"},
    ]

    tags: dict[str, list[str]] = {
        "EVT-FAKTURA-9631-IMPELLER": [
            "impeller",
            "impellerne",
            "skiftet",
            "faktura",
            "9631",
            FIXTURE_PART_IMPELLER,
            "invoice",
            "side",
            "bb",
            "sb",
            "both",
            "begge",
            "motor",
        ],
        "CLM-IMPELLER-INVOICED-2024": [
            "impeller",
            "impellerne",
            "skiftet",
            "9631",
            FIXTURE_PART_IMPELLER,
            "invoice",
            "invoiced",
        ],
        "CLM-IMPELLER-SIDE-UNKNOWN": [
            "impeller",
            "begge",
            "both",
            "side",
            "bb",
            "sb",
            "allocation",
            "quantity",
            "×2",
            "x2",
        ],
        "EVT-FAKTURA-9273-PCU": [
            "pcu",
            "evc",
            "cleaned",
            "renset",
            "stik",
            "connector",
            "9273",
            "bb",
            "replaced",
            "udskiftet",
        ],
        "CLM-PCU-CLEAN-2025": [
            "pcu",
            "cleaned",
            "renset",
            "stik",
            "connector",
            "9273",
            "action",
        ],
        "CLM-EVC-TEST-RUN-2025": [
            "evc",
            "fejl",
            "løst",
            "lasting",
            "outcome",
            "provkørsel",
            "test",
            "9273",
        ],
        "EVT-FAKTURA-9273-VALIDATION": [
            "evc",
            "validation",
            "provkørsel",
            "test",
            "lasting",
            "9273",
        ],
        "CLM-PCU-OIL-HYP": [
            "årsag",
            "cause",
            "root",
            "oily",
            "olie",
            "pcu",
            "bb",
            "død",
            "no-start",
            "hypothesis",
        ],
        "OBS-BB-NO-START-2025": ["bb", "død", "no-start", "pcu", "årsag"],
        "CLM-MOTOR-TYPE-D4": [
            "motor",
            "type",
            "d4",
            "d6",
            "labour",
            "9631",
            "conflict",
            "wording",
        ],
        "CLM-MOTOR-TYPE-D6": [
            "motor",
            "type",
            "d4",
            "d6",
            "labour",
            "9631",
            "conflict",
            "wording",
        ],
        "AI-D4-BB-ENGINE": ["serial", FIXTURE_SERIALS["BB_ENGINE"], "bb", "engine"],
        "AI-D4-SB-ENGINE": ["serial", FIXTURE_SERIALS["SB_ENGINE"], "sb", "engine"],
        "AI-D4-IMPELLER-KIT": ["impeller", FIXTURE_PART_IMPELLER, "unknown", "side"],
        "AI-D4-IMPELLER-CANDIDATE-A": ["impeller", "candidate", "unknown", "side"],
        "AI-D4-IMPELLER-CANDIDATE-B": ["impeller", "candidate", "unknown", "side"],
        "AI-D4-BB-IPS": ["ips", "bb", "drive"],
        "AI-D4-SB-IPS": ["ips", "sb", "drive"],
        "AI-D4-BB-PCU": ["pcu", "bb", "evc", "cf-003"],
        "AI-D4-SB-PCU": ["pcu", "sb", "evc", "placeholder"],
        "AI-SHAKA-VESSEL": ["vessel", "shaka", "nw370", "fly"],
        "SRC-FAKTURA-9631": ["9631", "faktura", "impeller", "source", FIXTURE_PART_IMPELLER],
        "SRC-FAKTURA-9273": ["9273", "faktura", "pcu", "evc", "source"],
        "KO-D4-0036": ["generatorrem", "belt", "generator", "21407028"],
        "KO-D4-0007": ["impeller", "seawater", FIXTURE_PART_IMPELLER],
    }

    return FixtureSnapshot(
        snapshot_id="ac-fixture-v1",
        assets=assets,
        sources=sources,
        evidence=evidence,
        claims=claims,
        events=events,
        observations=observations,
        knowledge_objects=kos,
        conflict_statements=conflict_statements,
        part_numbers={FIXTURE_PART_IMPELLER},
        tags=tags,
    )


_DEFAULT: FixtureSnapshot | None = None


def default_snapshot() -> FixtureSnapshot:
    """Lazy singleton frozen pack."""
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = build_ac_fixture_snapshot()
    return _DEFAULT
