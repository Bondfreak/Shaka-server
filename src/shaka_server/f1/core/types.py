"""Canonical F1 entity models (plain dataclasses, snake_case API)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from shaka_server.f1.core.enums import EpistemicStatus, Side

SerialNumber = str  # concrete serial or the sentinel "unknown"

ClaimRole = Literal["symptom", "hypothesis", "cause", "diagnosis", "action", "result", "other"]
ObservationStatus = Literal["provisional", "recorded", "superseded"]
EventRole = Literal["invoiced", "action", "install", "validation", "other"]


@dataclass(kw_only=True)
class KnowledgeObject:
    """Generic knowledge — NEVER holds vessel-specific service Events."""

    id: str
    kind: str = "KnowledgeObject"
    title: str = ""
    scope: str = ""
    function: str | None = None
    variant: str | None = None
    maturity: str | None = None
    lifecycle: str | None = None
    qa_status: str | None = None
    source_ids: list[str] | None = None
    related_ko_ids: list[str] | None = None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass(kw_only=True)
class Asset:
    """Vessel-specific instance. Distinct from KnowledgeObject."""

    id: str
    kind: str = "Asset"
    vessel_id: str = ""
    side: Side | str = Side.UNKNOWN
    location: str | None = None
    asset_type: str = ""
    ko_id: str | None = None
    serial: SerialNumber = "unknown"
    lifecycle: str | None = None
    identity_evidence_ids: list[str] | None = None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass(kw_only=True)
class Source:
    """Immutable document / file record. Distinct from Evidence."""

    id: str
    kind: str = "Source"
    source_type: str = ""
    issuer: str | None = None
    title: str = ""
    revision: str | None = None
    content_hash: str = ""
    mime_type: str = ""
    storage_ref: str = ""
    authority_class: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass(kw_only=True)
class Evidence:
    """Extract/region from a Source — requires source_id."""

    id: str
    kind: str = "Evidence"
    source_id: str = ""
    locator: str | None = None
    extract: str | None = None
    context: str | None = None
    supports_claim_ids: list[str] | None = None
    challenges_claim_ids: list[str] | None = None
    provenance: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass(kw_only=True)
class Claim:
    id: str
    kind: str = "Claim"
    statement: str = ""
    subject_id: str = ""
    predicate: str | None = None
    value: str | None = None
    time_validity: str | None = None
    status: EpistemicStatus | str = EpistemicStatus.UNKNOWN
    evidence_ids: list[str] = field(default_factory=list)
    role: ClaimRole | None = None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass(kw_only=True)
class Observation:
    id: str
    kind: str = "Observation"
    subject_id: str = ""
    side: Side | str = Side.UNKNOWN
    observed_at: str | None = None
    context: str | None = None
    value: str | None = None
    observer: str | None = None
    evidence_ids: list[str] | None = None
    status: ObservationStatus = "provisional"
    created_at: str | None = None
    updated_at: str | None = None


@dataclass(kw_only=True)
class Event:
    id: str
    kind: str = "Event"
    event_type: str = ""
    time_or_period: str = ""
    subject_ids: list[str] = field(default_factory=list)
    participants: list[str] | None = None
    location: str | None = None
    source_ids: list[str] | None = None
    evidence_ids: list[str] | None = None
    outcome: str | None = None
    role: EventRole | None = None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass(kw_only=True)
class Relationship:
    id: str
    kind: str = "Relationship"
    relation_type: str = ""
    from_id: str = ""
    to_id: str = ""
    validity: str | None = None
    status: EpistemicStatus | str | None = None
    evidence_ids: list[str] | None = None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass(kw_only=True)
class AnswerAudit:
    id: str
    kind: str = "AnswerAudit"
    query: str = ""
    intent: str | None = None
    selected_ids: list[str] = field(default_factory=list)
    policy_result: str = ""
    snapshot_id: str | None = None
    model: str | None = None
    response_version: str | None = None
    feedback: str | None = None
    epistemic_status: EpistemicStatus | str = EpistemicStatus.UNKNOWN
    created_at: str | None = None
    updated_at: str | None = None


CanonicalEntity = (
    KnowledgeObject
    | Asset
    | Source
    | Evidence
    | Claim
    | Observation
    | Event
    | Relationship
    | AnswerAudit
)
