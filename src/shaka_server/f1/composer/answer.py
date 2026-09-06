"""Structured Answer model (EPI-001: Conclusion, Basis, Uncertainty/Conflict, Sources)."""

from __future__ import annotations

from dataclasses import dataclass, field

from shaka_server.f1.core.enums import EpistemicStatus
from shaka_server.f1.core.types import AnswerAudit
from shaka_server.f1.policy.types import PolicyResult


@dataclass(kw_only=True)
class Answer:
    """Read-only composed answer — never invents facts beyond the snapshot."""

    query: str
    conclusion: str
    basis: list[str] = field(default_factory=list)
    uncertainty_conflict: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    epistemic_status: EpistemicStatus | str = EpistemicStatus.UNKNOWN
    policy_results: list[PolicyResult] = field(default_factory=list)
    selected_ids: list[str] = field(default_factory=list)
    snapshot_id: str | None = None
    rejected: bool = False
    audit: AnswerAudit | None = None

    @property
    def text_blob(self) -> str:
        """Lowercased concatenation for test assertions."""
        parts = [
            self.conclusion,
            *self.basis,
            *self.uncertainty_conflict,
            *self.sources,
        ]
        return " ".join(parts).lower()
