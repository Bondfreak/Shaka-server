"""F1-T03 Policy Guard v0 tests — ported from navigator-f1-core."""

from __future__ import annotations

from shaka_server.f1.core import validate_claim, validate_event
from shaka_server.f1.policy import (
    guard_action_not_outcome,
    guard_bb_sb_integrity,
    guard_bounded_absence,
    guard_conflict_must_surface,
    guard_hypothesis_not_root_cause,
    guard_invoice_not_install,
    guard_no_serial_guess,
    guard_no_topic_switch,
)

FIXTURE_SERIALS = {
    "BB_ENGINE": "2004030432",
    "SB_ENGINE": "2004030433",
}
FIXTURE_PART_ABSENT = "99999999"

IMPELLER_INVOICE_EVENT = validate_event(
    {
        "id": "EVT-FAKTURA-9631-IMPELLER",
        "kind": "Event",
        "eventType": "service_invoice",
        "timeOrPeriod": "2024",
        "subjectIds": ["AI-D4-IMPELLER-KIT"],
        "role": "invoiced",
    }
)

PCU_CLEAN_ACTION = validate_claim(
    {
        "id": "CLM-PCU-CLEAN-2025",
        "kind": "Claim",
        "statement": "PCU connector cleaned",
        "subjectId": "AI-D4-BB-PCU",
        "status": "documented",
        "evidenceIds": ["EVD-FAKTURA-9273"],
        "role": "action",
    }
)

PCU_HYPOTHESIS = validate_claim(
    {
        "id": "CLM-PCU-OIL-HYP",
        "kind": "Claim",
        "statement": "Oiled PCU contact may explain BB no-start",
        "subjectId": "AI-D4-BB-PCU",
        "status": "inferred",
        "evidenceIds": ["EVD-FAKTURA-9273"],
        "role": "hypothesis",
    }
)

LABOUR_CONFLICT = [
    {"id": "DOC-D4-LABOUR", "text": "Labour described as D4 impeller service"},
    {"id": "DOC-D6-LABOUR", "text": "Labour described as D6 related work"},
]


class TestF1T03PolicyGuard:
    def test_cf002_ac01_invoice_ne_install(self) -> None:
        result = guard_invoice_not_install(IMPELLER_INVOICE_EVENT, "install")
        assert result.verdict == "downgrade"
        assert result.code == "INVOICE_NE_INSTALL"
        assert result.epistemic_status == "invoiced_without_action"

    def test_ac02_qty_without_side_bb_sb_integrity(self) -> None:
        result = guard_bb_sb_integrity(quantityWithoutSideEvidence=2)
        assert result.verdict == "downgrade"
        assert result.epistemic_status == "unknown"

    def test_ac03_04_cf003_action_ne_lasting_outcome(self) -> None:
        result = guard_action_not_outcome(PCU_CLEAN_ACTION, "lasting_fix")
        assert result.verdict == "downgrade"
        assert result.code == "ACTION_NE_OUTCOME"
        assert result.epistemic_status == "unknown"

    def test_ac05_hypothesis_ne_root_cause(self) -> None:
        result = guard_hypothesis_not_root_cause(PCU_HYPOTHESIS)
        assert result.verdict == "downgrade"
        assert result.code == "HYPOTHESIS_NE_ROOT_CAUSE"


class TestConflictAndBoundedAbsence:
    def test_cf001_d4_vs_d6_labour_surfaces_conflict(self) -> None:
        result = guard_conflict_must_surface(LABOUR_CONFLICT)
        assert result.verdict == "downgrade"
        assert result.code == "CONFLICT_MUST_SURFACE"
        assert result.epistemic_status == "conflicted"

    def test_ac06_cf006_pn_99999999_bounded_absence(self) -> None:
        result = guard_bounded_absence(FIXTURE_PART_ABSENT, False)
        assert result.verdict == "downgrade"
        assert result.code == "BOUNDED_ABSENCE"
        assert result.epistemic_status == "bounded_absence"

    def test_ac06_no_topic_switch_to_impeller(self) -> None:
        result = guard_bounded_absence(FIXTURE_PART_ABSENT, False, "impeller")
        assert result.verdict == "reject"
        assert result.code == "NO_TOPIC_SWITCH"

    def test_no_serial_guess_documented_fixtures_ok(self) -> None:
        assert guard_no_serial_guess("x", "guess").verdict == "reject"
        assert guard_no_serial_guess(FIXTURE_SERIALS["BB_ENGINE"], "documented").verdict == "allow"
        assert guard_no_serial_guess("unknown", "blank").epistemic_status == "unknown"

    def test_bb_sb_never_merge(self) -> None:
        result = guard_bb_sb_integrity(sideA="BB", sideB="SB", mergeRequested=True)
        assert result.verdict == "reject"
        assert result.code == "BB_SB_INTEGRITY"

    def test_guard_no_topic_switch(self) -> None:
        assert guard_no_topic_switch("99999999", "99999999").verdict == "allow"
        assert guard_no_topic_switch("99999999", "impeller").verdict == "reject"
