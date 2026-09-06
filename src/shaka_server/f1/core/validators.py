"""Entity validators — fail closed; enforce KO≠Asset and Source≠Evidence."""

from __future__ import annotations

import re
from typing import Any, Mapping

from shaka_server.f1.core.enums import EPISTEMIC_STATUSES, ENTITY_KINDS, SIDES
from shaka_server.f1.core.types import (
    AnswerAudit,
    Asset,
    CanonicalEntity,
    Claim,
    Event,
    Evidence,
    KnowledgeObject,
    Observation,
    Relationship,
    Source,
)

_SHA256_RE = re.compile(r"^[a-f0-9]{64}$", re.IGNORECASE)


class ValidationError(ValueError):
    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.code = code
        self.name = "ValidationError"


def _get(raw: Mapping[str, Any], *keys: str) -> Any:
    """Return first present key (supports camelCase wire keys and snake_case)."""
    for key in keys:
        if key in raw:
            return raw[key]
    return None


def _require_string(v: Any, field: str) -> str:
    if not isinstance(v, str) or v.strip() == "":
        raise ValidationError(f"Missing or empty string: {field}", "REQUIRED_STRING")
    return v


def _assert_kind(obj: Mapping[str, Any], expected: str) -> None:
    if obj.get("kind") != expected:
        raise ValidationError(f"Expected kind {expected}, got {obj.get('kind')}", "KIND_MISMATCH")


def _as_str_list(v: Any) -> list[str] | None:
    if not isinstance(v, list):
        return None
    return [str(x) for x in v]


def validate_knowledge_object(raw: Any) -> KnowledgeObject:
    if not isinstance(raw, Mapping):
        raise ValidationError("KO must be object", "TYPE")
    _assert_kind(raw, "KnowledgeObject")
    if "serial" in raw:
        raise ValidationError("KO must not have serial (KO ≠ Asset)", "KO_NE_ASSET")
    if "vesselId" in raw or "vessel_id" in raw:
        raise ValidationError("KO must not have vesselId (KO ≠ Asset)", "KO_NE_ASSET")
    return KnowledgeObject(
        id=_require_string(_get(raw, "id"), "id"),
        kind="KnowledgeObject",
        title=_require_string(_get(raw, "title"), "title"),
        scope=_require_string(_get(raw, "scope"), "scope"),
        function=_get(raw, "function") if isinstance(_get(raw, "function"), str) else None,
        variant=_get(raw, "variant") if isinstance(_get(raw, "variant"), str) else None,
        maturity=_get(raw, "maturity") if isinstance(_get(raw, "maturity"), str) else None,
        lifecycle=_get(raw, "lifecycle") if isinstance(_get(raw, "lifecycle"), str) else None,
        qa_status=_get(raw, "qaStatus", "qa_status") if isinstance(_get(raw, "qaStatus", "qa_status"), str) else None,
        source_ids=_as_str_list(_get(raw, "sourceIds", "source_ids")),
        related_ko_ids=_as_str_list(_get(raw, "relatedKoIds", "related_ko_ids")),
    )


def validate_asset(raw: Any) -> Asset:
    if not isinstance(raw, Mapping):
        raise ValidationError("Asset must be object", "TYPE")
    _assert_kind(raw, "Asset")
    has_scope = "scope" in raw
    has_vessel = "vesselId" in raw or "vessel_id" in raw
    if has_scope and not has_vessel:
        raise ValidationError("Asset confused with KO", "KO_NE_ASSET")
    side = _require_string(_get(raw, "side"), "side")
    if side not in SIDES:
        raise ValidationError(f"Invalid side: {side}", "SIDE")
    serial_raw = _get(raw, "serial")
    if serial_raw is None or serial_raw == "":
        serial = "unknown"
    else:
        serial = str(serial_raw)
    return Asset(
        id=_require_string(_get(raw, "id"), "id"),
        kind="Asset",
        vessel_id=_require_string(_get(raw, "vesselId", "vessel_id"), "vesselId"),
        side=side,
        location=_get(raw, "location") if isinstance(_get(raw, "location"), str) else None,
        asset_type=_require_string(_get(raw, "assetType", "asset_type"), "assetType"),
        ko_id=_get(raw, "koId", "ko_id") if isinstance(_get(raw, "koId", "ko_id"), str) else None,
        serial=serial,
        lifecycle=_get(raw, "lifecycle") if isinstance(_get(raw, "lifecycle"), str) else None,
        identity_evidence_ids=_as_str_list(_get(raw, "identityEvidenceIds", "identity_evidence_ids")),
    )


def validate_source(raw: Any) -> Source:
    if not isinstance(raw, Mapping):
        raise ValidationError("Source must be object", "TYPE")
    _assert_kind(raw, "Source")
    if "sourceId" in raw or "source_id" in raw:
        raise ValidationError("Source must not have sourceId (Source ≠ Evidence)", "SOURCE_NE_EVIDENCE")
    if "extract" in raw or "locator" in raw:
        raise ValidationError("Source must not carry Evidence extract/locator", "SOURCE_NE_EVIDENCE")
    hash_val = _require_string(_get(raw, "contentHash", "content_hash"), "contentHash")
    if not _SHA256_RE.match(hash_val):
        raise ValidationError("contentHash must be sha256 hex", "HASH")
    return Source(
        id=_require_string(_get(raw, "id"), "id"),
        kind="Source",
        source_type=_require_string(_get(raw, "sourceType", "source_type"), "sourceType"),
        issuer=_get(raw, "issuer") if isinstance(_get(raw, "issuer"), str) else None,
        title=_require_string(_get(raw, "title"), "title"),
        revision=_get(raw, "revision") if isinstance(_get(raw, "revision"), str) else None,
        content_hash=hash_val.lower(),
        mime_type=_require_string(_get(raw, "mimeType", "mime_type"), "mimeType"),
        storage_ref=_require_string(_get(raw, "storageRef", "storage_ref"), "storageRef"),
        authority_class=_get(raw, "authorityClass", "authority_class")
        if isinstance(_get(raw, "authorityClass", "authority_class"), str)
        else None,
    )


def validate_evidence(raw: Any) -> Evidence:
    if not isinstance(raw, Mapping):
        raise ValidationError("Evidence must be object", "TYPE")
    _assert_kind(raw, "Evidence")
    if "contentHash" in raw or "content_hash" in raw or "storageRef" in raw or "storage_ref" in raw or "mimeType" in raw or "mime_type" in raw:
        raise ValidationError("Evidence must not carry Source storage fields", "SOURCE_NE_EVIDENCE")
    return Evidence(
        id=_require_string(_get(raw, "id"), "id"),
        kind="Evidence",
        source_id=_require_string(_get(raw, "sourceId", "source_id"), "sourceId"),
        locator=_get(raw, "locator") if isinstance(_get(raw, "locator"), str) else None,
        extract=_get(raw, "extract") if isinstance(_get(raw, "extract"), str) else None,
        context=_get(raw, "context") if isinstance(_get(raw, "context"), str) else None,
        supports_claim_ids=_as_str_list(_get(raw, "supportsClaimIds", "supports_claim_ids")),
        challenges_claim_ids=_as_str_list(_get(raw, "challengesClaimIds", "challenges_claim_ids")),
        provenance=_get(raw, "provenance") if isinstance(_get(raw, "provenance"), str) else None,
    )


def validate_claim(raw: Any) -> Claim:
    if not isinstance(raw, Mapping):
        raise ValidationError("Claim must be object", "TYPE")
    _assert_kind(raw, "Claim")
    status = _require_string(_get(raw, "status"), "status")
    if status not in EPISTEMIC_STATUSES:
        raise ValidationError(f"Invalid epistemic status: {status}", "EPISTEMIC")
    evidence_ids = _get(raw, "evidenceIds", "evidence_ids")
    if not isinstance(evidence_ids, list):
        raise ValidationError("evidenceIds required", "REQUIRED")
    role = _get(raw, "role")
    return Claim(
        id=_require_string(_get(raw, "id"), "id"),
        kind="Claim",
        statement=_require_string(_get(raw, "statement"), "statement"),
        subject_id=_require_string(_get(raw, "subjectId", "subject_id"), "subjectId"),
        predicate=_get(raw, "predicate") if isinstance(_get(raw, "predicate"), str) else None,
        value=_get(raw, "value") if isinstance(_get(raw, "value"), str) else None,
        time_validity=_get(raw, "timeValidity", "time_validity")
        if isinstance(_get(raw, "timeValidity", "time_validity"), str)
        else None,
        status=status,
        evidence_ids=[str(x) for x in evidence_ids],
        role=role if isinstance(role, str) else None,
    )


def validate_observation(raw: Any) -> Observation:
    if not isinstance(raw, Mapping):
        raise ValidationError("Observation must be object", "TYPE")
    _assert_kind(raw, "Observation")
    side = _require_string(_get(raw, "side"), "side")
    if side not in SIDES:
        raise ValidationError(f"Invalid side: {side}", "SIDE")
    status = _require_string(_get(raw, "status"), "status")
    if status not in ("provisional", "recorded", "superseded"):
        raise ValidationError(f"Invalid observation status: {status}", "STATUS")
    return Observation(
        id=_require_string(_get(raw, "id"), "id"),
        kind="Observation",
        subject_id=_require_string(_get(raw, "subjectId", "subject_id"), "subjectId"),
        side=side,
        observed_at=_get(raw, "observedAt", "observed_at")
        if isinstance(_get(raw, "observedAt", "observed_at"), str)
        else None,
        context=_get(raw, "context") if isinstance(_get(raw, "context"), str) else None,
        value=_get(raw, "value") if isinstance(_get(raw, "value"), str) else None,
        observer=_get(raw, "observer") if isinstance(_get(raw, "observer"), str) else None,
        evidence_ids=_as_str_list(_get(raw, "evidenceIds", "evidence_ids")),
        status=status,  # type: ignore[arg-type]
    )


def validate_event(raw: Any) -> Event:
    if not isinstance(raw, Mapping):
        raise ValidationError("Event must be object", "TYPE")
    _assert_kind(raw, "Event")
    subject_ids = _get(raw, "subjectIds", "subject_ids")
    if not isinstance(subject_ids, list) or len(subject_ids) == 0:
        raise ValidationError("subjectIds required", "REQUIRED")
    role = _get(raw, "role")
    return Event(
        id=_require_string(_get(raw, "id"), "id"),
        kind="Event",
        event_type=_require_string(_get(raw, "eventType", "event_type"), "eventType"),
        time_or_period=_require_string(_get(raw, "timeOrPeriod", "time_or_period"), "timeOrPeriod"),
        subject_ids=[str(x) for x in subject_ids],
        participants=_as_str_list(_get(raw, "participants")),
        location=_get(raw, "location") if isinstance(_get(raw, "location"), str) else None,
        source_ids=_as_str_list(_get(raw, "sourceIds", "source_ids")),
        evidence_ids=_as_str_list(_get(raw, "evidenceIds", "evidence_ids")),
        outcome=_get(raw, "outcome") if isinstance(_get(raw, "outcome"), str) else None,
        role=role if isinstance(role, str) else None,
    )


def validate_relationship(raw: Any) -> Relationship:
    if not isinstance(raw, Mapping):
        raise ValidationError("Relationship must be object", "TYPE")
    _assert_kind(raw, "Relationship")
    status = _get(raw, "status")
    return Relationship(
        id=_require_string(_get(raw, "id"), "id"),
        kind="Relationship",
        relation_type=_require_string(_get(raw, "relationType", "relation_type"), "relationType"),
        from_id=_require_string(_get(raw, "fromId", "from_id"), "fromId"),
        to_id=_require_string(_get(raw, "toId", "to_id"), "toId"),
        validity=_get(raw, "validity") if isinstance(_get(raw, "validity"), str) else None,
        status=status if isinstance(status, str) else None,
        evidence_ids=_as_str_list(_get(raw, "evidenceIds", "evidence_ids")),
    )


def validate_answer_audit(raw: Any) -> AnswerAudit:
    if not isinstance(raw, Mapping):
        raise ValidationError("AnswerAudit must be object", "TYPE")
    _assert_kind(raw, "AnswerAudit")
    status = _require_string(_get(raw, "epistemicStatus", "epistemic_status"), "epistemicStatus")
    if status not in EPISTEMIC_STATUSES:
        raise ValidationError(f"Invalid epistemic status: {status}", "EPISTEMIC")
    selected_ids = _get(raw, "selectedIds", "selected_ids")
    if not isinstance(selected_ids, list):
        raise ValidationError("selectedIds required", "REQUIRED")
    return AnswerAudit(
        id=_require_string(_get(raw, "id"), "id"),
        kind="AnswerAudit",
        query=_require_string(_get(raw, "query"), "query"),
        intent=_get(raw, "intent") if isinstance(_get(raw, "intent"), str) else None,
        selected_ids=[str(x) for x in selected_ids],
        policy_result=_require_string(_get(raw, "policyResult", "policy_result"), "policyResult"),
        snapshot_id=_get(raw, "snapshotId", "snapshot_id")
        if isinstance(_get(raw, "snapshotId", "snapshot_id"), str)
        else None,
        model=_get(raw, "model") if isinstance(_get(raw, "model"), str) else None,
        response_version=_get(raw, "responseVersion", "response_version")
        if isinstance(_get(raw, "responseVersion", "response_version"), str)
        else None,
        feedback=_get(raw, "feedback") if isinstance(_get(raw, "feedback"), str) else None,
        epistemic_status=status,
    )


def validate_entity(raw: Any) -> CanonicalEntity:
    if not isinstance(raw, Mapping):
        raise ValidationError("Entity must be object", "TYPE")
    kind = raw.get("kind")
    if not kind or kind not in ENTITY_KINDS:
        raise ValidationError(f"Unknown kind: {kind}", "KIND")
    if kind == "KnowledgeObject":
        return validate_knowledge_object(raw)
    if kind == "Asset":
        return validate_asset(raw)
    if kind == "Source":
        return validate_source(raw)
    if kind == "Evidence":
        return validate_evidence(raw)
    if kind == "Claim":
        return validate_claim(raw)
    if kind == "Observation":
        return validate_observation(raw)
    if kind == "Event":
        return validate_event(raw)
    if kind == "Relationship":
        return validate_relationship(raw)
    if kind == "AnswerAudit":
        return validate_answer_audit(raw)
    raise ValidationError(f"Unhandled kind: {kind}", "KIND")
