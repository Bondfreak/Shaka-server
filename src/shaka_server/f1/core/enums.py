"""Side, epistemic status, and entity-kind enumerations."""

from __future__ import annotations

from enum import Enum
from typing import Final


class Side(str, Enum):
    """Side identity for twin propulsion (BB/SB). Never invent."""

    BB = "BB"
    SB = "SB"
    BOTH = "both"
    UNKNOWN = "unknown"


class EpistemicStatus(str, Enum):
    """Epistemic status ladder for claims / answers."""

    DOCUMENTED = "documented"
    INVOICED_WITH_ACTION = "invoiced_with_action"
    INVOICED_WITHOUT_ACTION = "invoiced_without_action"
    OWNER_REPORTED = "owner_reported"
    CANDIDATE_LINK = "candidate_link"
    CONFLICTED = "conflicted"
    BOUNDED_ABSENCE = "bounded_absence"
    UNKNOWN = "unknown"
    INFERRED = "inferred"


class EntityKind(str, Enum):
    KNOWLEDGE_OBJECT = "KnowledgeObject"
    ASSET = "Asset"
    SOURCE = "Source"
    EVIDENCE = "Evidence"
    CLAIM = "Claim"
    OBSERVATION = "Observation"
    EVENT = "Event"
    RELATIONSHIP = "Relationship"
    ANSWER_AUDIT = "AnswerAudit"


SIDES: Final[tuple[str, ...]] = tuple(s.value for s in Side)
EPISTEMIC_STATUSES: Final[tuple[str, ...]] = tuple(s.value for s in EpistemicStatus)
ENTITY_KINDS: Final[tuple[str, ...]] = tuple(k.value for k in EntityKind)
