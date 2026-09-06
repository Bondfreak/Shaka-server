"""BB/SB integrity and no-topic-switch guards."""

from __future__ import annotations

from typing import Any

from shaka_server.f1.policy.types import PolicyResult, downgrade, ok, reject


def guard_bb_sb_integrity(opts: dict[str, Any] | None = None, **kwargs: Any) -> PolicyResult:
    """BB/SB integrity — never merge sides; qty alone ≠ side."""
    data = dict(opts or {})
    data.update(kwargs)
    side_a = data.get("side_a", data.get("sideA"))
    side_b = data.get("side_b", data.get("sideB"))
    merge_requested = data.get("merge_requested", data.get("mergeRequested"))
    qty = data.get("quantity_without_side_evidence", data.get("quantityWithoutSideEvidence"))

    if merge_requested and side_a and side_b and side_a != side_b:
        return reject("BB_SB_INTEGRITY", "BB and SB identities must never merge", "conflicted")
    if qty is not None and qty > 0:
        return downgrade(
            "BB_SB_INTEGRITY",
            "Quantity without side evidence → side unknown (not BB/SB allocation)",
            "unknown",
        )
    return ok()


def guard_no_topic_switch(queried: str, answered_about: str) -> PolicyResult:
    """No topic switch for exact queries."""
    if queried.strip().lower() != answered_about.strip().lower():
        return reject(
            "NO_TOPIC_SWITCH",
            f"Answer topic {answered_about} does not match query {queried}",
        )
    return ok()
