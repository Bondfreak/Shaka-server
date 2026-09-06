"""Policy Guard v0 — fail closed / downgrade rather than silent prefer."""

from __future__ import annotations

from typing import Any

from shaka_server.f1.core.types import Claim, Event
from shaka_server.f1.policy.types import PolicyResult, downgrade, ok, reject


def guard_invoice_not_install(event: Event | Any, asserted_role: str) -> PolicyResult:
    """Invoice ≠ install: invoiced Event must not be treated as install."""
    role = getattr(event, "role", None)
    if isinstance(event, dict):
        role = event.get("role")
    if role == "invoiced" and asserted_role in {"install", "installed"}:
        return downgrade(
            "INVOICE_NE_INSTALL",
            "Invoiced material/service is not proof of install",
            "invoiced_without_action",
        )
    if role == "invoiced" and asserted_role == "action":
        return downgrade(
            "INVOICE_NE_INSTALL",
            "Invoice alone does not prove action performed",
            "invoiced_without_action",
        )
    return ok()


def guard_action_not_outcome(
    action_claim: Claim | dict[str, Any] | Any,
    asserted_outcome: str,
) -> PolicyResult:
    """Action ≠ lasting outcome."""
    role = action_claim.get("role") if isinstance(action_claim, dict) else getattr(action_claim, "role", None)
    if role == "action" and asserted_outcome == "lasting_fix":
        return downgrade(
            "ACTION_NE_OUTCOME",
            "Documented action does not prove lasting outcome",
            "unknown",
        )
    return ok()


def guard_hypothesis_not_root_cause(claim: Claim | dict[str, Any] | Any) -> PolicyResult:
    """Hypothesis ≠ root cause."""
    if isinstance(claim, dict):
        role = claim.get("role")
        status = claim.get("status")
    else:
        role = getattr(claim, "role", None)
        status = getattr(claim, "status", None)
        if hasattr(status, "value"):
            status = status.value

    if role == "hypothesis" and status == "documented":
        return downgrade(
            "HYPOTHESIS_NE_ROOT_CAUSE",
            "Hypothesis must not be promoted to documented root cause",
            "inferred",
        )
    if role == "hypothesis":
        return downgrade(
            "HYPOTHESIS_NE_ROOT_CAUSE",
            "Treat as possible cause only; not confirmed root cause",
            "conflicted" if status == "conflicted" else "inferred",
        )
    if role == "cause" and status != "documented":
        return downgrade(
            "HYPOTHESIS_NE_ROOT_CAUSE",
            "Cause claim lacks documented status",
            status if status is not None else "unknown",
        )
    return ok()


def guard_conflict_must_surface(statements: list[dict[str, str]]) -> PolicyResult:
    """Conflicts must surface — never silent prefer."""
    if len(statements) < 2:
        return ok()
    texts = [s["text"].strip().lower() for s in statements]
    unique = set(texts)
    if len(unique) > 1:
        ids = ", ".join(s["id"] for s in statements)
        return downgrade(
            "CONFLICT_MUST_SURFACE",
            f"Conflict among {ids}",
            "conflicted",
        )
    return ok()


def guard_bounded_absence(
    queried_part_number: str,
    found: bool,
    substituted_topic: str | None = None,
) -> PolicyResult:
    """Exact P/N lookup with no hit → bounded_absence (never substitute topic)."""
    if substituted_topic and substituted_topic != queried_part_number:
        return reject(
            "NO_TOPIC_SWITCH",
            f"Refusing topic switch from {queried_part_number} to {substituted_topic}",
            "bounded_absence",
        )
    if not found:
        return downgrade(
            "BOUNDED_ABSENCE",
            f"No record for exact P/N {queried_part_number} in scoped search",
            "bounded_absence",
        )
    return ok()


def guard_no_serial_guess(
    serial: str | None,
    source: str,
) -> PolicyResult:
    """Never invent / guess serial numbers."""
    if source in {"guess", "inferred_from_sibling"}:
        return reject("NO_SERIAL_GUESS", "Refusing to invent or infer serial number", "unknown")
    if serial is None or serial == "" or serial == "unknown" or source == "blank":
        return downgrade("NO_SERIAL_GUESS", "Serial remains unknown", "unknown")
    if source == "documented":
        return ok()
    return reject("NO_SERIAL_GUESS", "Serial source not documented", "unknown")
