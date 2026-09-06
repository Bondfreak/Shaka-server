"""Keyword / part-number / side / status index over a FixtureSnapshot."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from shaka_server.f1.snapshot.pack import FixtureSnapshot

_TOKEN_RE = re.compile(r"[a-z0-9æøåäöüß]+", re.IGNORECASE)


def _norm(text: str) -> str:
    return text.strip().lower()


def _tokens(text: str) -> list[str]:
    return [_norm(t) for t in _TOKEN_RE.findall(text) if t]


def _entity_text(entity: Any) -> str:
    parts: list[str] = [getattr(entity, "id", ""), getattr(entity, "kind", "")]
    for attr in (
        "title",
        "statement",
        "extract",
        "context",
        "event_type",
        "outcome",
        "asset_type",
        "serial",
        "value",
        "predicate",
        "time_or_period",
        "time_validity",
        "locator",
        "scope",
        "source_type",
        "observed_at",
    ):
        val = getattr(entity, attr, None)
        if isinstance(val, str) and val:
            parts.append(val)
    side = getattr(entity, "side", None)
    if side is not None:
        parts.append(str(side.value if hasattr(side, "value") else side))
    status = getattr(entity, "status", None)
    if status is not None:
        parts.append(str(status.value if hasattr(status, "value") else status))
    role = getattr(entity, "role", None)
    if role is not None:
        parts.append(str(role))
    return " ".join(parts)


@dataclass(frozen=True)
class RetrievalHit:
    entity_id: str
    kind: str
    score: float
    matched: tuple[str, ...] = ()
    entity: Any = None


@dataclass
class SnapshotIndex:
    """In-memory retrieval index for Claims, Events, Sources, Evidence, Assets (+ KO/Obs)."""

    snapshot: FixtureSnapshot
    _docs: dict[str, dict[str, Any]] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        self._docs = {}
        for entity in self.snapshot.all_entities():
            eid = entity.id
            text = _entity_text(entity)
            tag_list = list(self.snapshot.tags.get(eid, []))
            bag = set(_tokens(text)) | {_norm(t) for t in tag_list}
            status = getattr(entity, "status", None)
            if status is not None and hasattr(status, "value"):
                status = status.value
            side = getattr(entity, "side", None)
            if side is not None and hasattr(side, "value"):
                side = side.value
            self._docs[eid] = {
                "entity": entity,
                "kind": entity.kind,
                "tokens": bag,
                "text": _norm(text + " " + " ".join(tag_list)),
                "status": str(status) if status is not None else None,
                "side": str(side) if side is not None else None,
            }

    def has_part_number(self, part_number: str) -> bool:
        return part_number.strip() in self.snapshot.part_numbers

    def search(
        self,
        query: str,
        *,
        keywords: Iterable[str] | None = None,
        part_number: str | None = None,
        side: str | None = None,
        status: str | None = None,
        kinds: Iterable[str] | None = None,
        limit: int = 25,
    ) -> list[RetrievalHit]:
        """Score entities by keyword overlap; optional filters for part/side/status/kind."""
        q_tokens = set(_tokens(query))
        if keywords:
            q_tokens |= {_norm(k) for k in keywords if k}
        if part_number:
            q_tokens.add(_norm(part_number))

        kind_filter = {k for k in kinds} if kinds else None
        side_n = _norm(side) if side else None
        status_n = _norm(status) if status else None
        pn = part_number.strip() if part_number else None

        hits: list[RetrievalHit] = []
        for eid, doc in self._docs.items():
            if kind_filter and doc["kind"] not in kind_filter:
                continue
            if side_n and (doc["side"] is None or _norm(doc["side"]) != side_n):
                # Allow unknown-side assets when filtering for unknown
                if not (side_n == "unknown" and doc["side"] and _norm(doc["side"]) == "unknown"):
                    if doc["side"] is None or _norm(str(doc["side"])) != side_n:
                        continue
            if status_n and (doc["status"] is None or _norm(doc["status"]) != status_n):
                continue
            if pn and pn not in doc["text"] and pn not in self.snapshot.part_numbers:
                # Exact part filter: require token/text presence when filtering by PN that exists
                pass
            if pn and self.has_part_number(pn) and pn not in doc["text"]:
                continue
            if pn and not self.has_part_number(pn):
                # Absence query — no entity should claim the PN; skip PN text match requirement
                continue

            matched = sorted(q_tokens & doc["tokens"])
            # Also count substring hits for multi-digit PNs / invoice numbers
            substr = [t for t in q_tokens if t and t in doc["text"]]
            matched_set = set(matched) | set(substr)
            if not matched_set and q_tokens:
                continue
            score = float(len(matched_set))
            # Slight boost for Events/Claims/Sources over KO when scores tie later
            if doc["kind"] in {"Event", "Claim", "Source", "Evidence"}:
                score += 0.1
            hits.append(
                RetrievalHit(
                    entity_id=eid,
                    kind=doc["kind"],
                    score=score,
                    matched=tuple(sorted(matched_set)),
                    entity=doc["entity"],
                )
            )

        hits.sort(key=lambda h: (-h.score, h.kind, h.entity_id))
        return hits[:limit]
