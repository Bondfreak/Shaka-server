"""Policy verdict result helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from shaka_server.f1.core.enums import EpistemicStatus

PolicyVerdict = Literal["allow", "reject", "downgrade"]


@dataclass(frozen=True)
class PolicyResult:
    verdict: PolicyVerdict
    code: str
    message: str
    epistemic_status: EpistemicStatus | str | None = None


def ok(message: str = "ok") -> PolicyResult:
    return PolicyResult(verdict="allow", code="OK", message=message)


def reject(
    code: str,
    message: str,
    epistemic_status: EpistemicStatus | str | None = None,
) -> PolicyResult:
    return PolicyResult(verdict="reject", code=code, message=message, epistemic_status=epistemic_status)


def downgrade(
    code: str,
    message: str,
    epistemic_status: EpistemicStatus | str,
) -> PolicyResult:
    return PolicyResult(verdict="downgrade", code=code, message=message, epistemic_status=epistemic_status)
