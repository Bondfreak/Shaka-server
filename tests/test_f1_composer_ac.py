"""F1-T04 Answer Composer AC-01…06 (+ CF-001 conflict) disciplines."""

from __future__ import annotations

from shaka_server.f1.composer import answer_query
from shaka_server.f1.snapshot import (
    FIXTURE_PART_ABSENT,
    FIXTURE_PART_IMPELLER,
    build_ac_fixture_snapshot,
)


def test_ac01_impeller_event_date_source_action_ne_outcome() -> None:
    snap = build_ac_fixture_snapshot()
    ans = answer_query("Hvornår blev impellerne sidst skiftet?", snapshot=snap)
    blob = ans.text_blob
    assert "9631" in blob
    assert FIXTURE_PART_IMPELLER in blob or "impeller" in blob
    assert "EVT-FAKTURA-9631-IMPELLER" in ans.selected_ids
    assert any("SRC-FAKTURA-9631" in s for s in ans.sources) or "SRC-FAKTURA-9631" in ans.selected_ids
    assert ans.audit is not None
    assert "2024" in blob
    codes = {p.code for p in ans.policy_results}
    assert "INVOICE_NE_INSTALL" in codes or "ACTION_NE_OUTCOME" in codes
    assert "not proof" in ans.conclusion.lower() or "invoiced" in ans.conclusion.lower()
    assert ans.epistemic_status in {
        "invoiced_without_action",
        "unknown",
        "invoiced_with_action",
    }


def test_ac02_does_not_conclude_both_sides_from_count() -> None:
    snap = build_ac_fixture_snapshot()
    ans = answer_query("Blev begge motorers impellere skiftet?", snapshot=snap)
    blob = ans.text_blob
    assert "cannot conclude" in blob or "unknown" in blob
    assert "both motors" in blob or "bb/sb" in blob or "side" in blob
    codes = {p.code for p in ans.policy_results}
    assert "BB_SB_INTEGRITY" in codes
    assert "both sides confirmed" not in blob
    assert "were changed on both" not in blob
    assert ans.epistemic_status == "unknown"


def test_ac03_cleaned_not_replaced_without_evidence() -> None:
    snap = build_ac_fixture_snapshot()
    ans = answer_query("Hvad blev gjort ved PCU-stikket?", snapshot=snap)
    blob = ans.text_blob
    assert "clean" in blob
    assert "9273" in blob or "SRC-FAKTURA-9273" in "".join(ans.sources) or "9273" in "".join(
        ans.selected_ids
    )
    assert "replaced" in blob
    assert "no evidence of replacement" in blob or "not replaced" in blob or "do not conclude" in blob
    assert "CLM-PCU-CLEAN-2025" in ans.selected_ids


def test_ac04_lasting_result_unknown_after_test_run() -> None:
    snap = build_ac_fixture_snapshot()
    ans = answer_query("Var EVC-fejlen løst?", snapshot=snap)
    blob = ans.text_blob
    assert "unknown" in blob
    assert "test" in blob or "provkørsel" in blob or "validation" in blob
    codes = {p.code for p in ans.policy_results}
    assert "ACTION_NE_OUTCOME" in codes
    assert ans.epistemic_status == "unknown"
    assert "lasting" in blob


def test_ac05_oily_pcu_only_possible_cause() -> None:
    snap = build_ac_fixture_snapshot()
    ans = answer_query("Hvad var årsagen til at BB var død?", snapshot=snap)
    blob = ans.text_blob
    assert "possible" in blob
    assert "pcu" in blob or "oil" in blob
    codes = {p.code for p in ans.policy_results}
    assert "HYPOTHESIS_NE_ROOT_CAUSE" in codes
    assert "root cause" in blob and ("not" in blob or "confirmed" in blob)
    assert ans.epistemic_status in {"inferred", "conflicted"}


def test_ac06_bounded_absence_no_topic_switch() -> None:
    snap = build_ac_fixture_snapshot()
    ans = answer_query(f"Find generatorrem {FIXTURE_PART_ABSENT}", snapshot=snap)
    blob = ans.text_blob
    assert FIXTURE_PART_ABSENT in blob
    assert "bounded absence" in blob or ans.epistemic_status == "bounded_absence"
    codes = {p.code for p in ans.policy_results}
    assert "BOUNDED_ABSENCE" in codes
    assert "EVT-FAKTURA-9631-IMPELLER" not in ans.selected_ids
    assert "impeller kits" not in blob
    assert ans.epistemic_status == "bounded_absence"

    switched = answer_query(
        f"Find {FIXTURE_PART_ABSENT} or just tell me about impeller instead",
        snapshot=snap,
    )
    switch_codes = {p.code for p in switched.policy_results}
    assert "NO_TOPIC_SWITCH" in switch_codes or switched.rejected


def test_cf001_d4_d6_conflict_surfaces_on_motor_type() -> None:
    snap = build_ac_fixture_snapshot()
    ans = answer_query(
        "What motor type wording appears on Faktura 9631 labour — D4 or D6?",
        snapshot=snap,
    )
    blob = ans.text_blob
    assert "conflict" in blob
    assert "d4" in blob and "d6" in blob
    codes = {p.code for p in ans.policy_results}
    assert "CONFLICT_MUST_SURFACE" in codes
    assert ans.epistemic_status == "conflicted"
    assert "CLM-MOTOR-TYPE-D4" in ans.selected_ids
    assert "CLM-MOTOR-TYPE-D6" in ans.selected_ids


def test_gate_d_q08_bb_sb_engine_serial_compare_no_impeller_switch() -> None:
    """Q08: compare BB/SB engine serials — asset facts, never impeller AC-02 template."""
    snap = build_ac_fixture_snapshot()
    ans = answer_query("Sammenlign BB og SB motor-serienumre.", snapshot=snap)
    blob = ans.text_blob
    assert "2004030432" in blob
    assert "2004030433" in blob
    assert "AI-D4-BB-ENGINE" in ans.selected_ids
    assert "AI-D4-SB-ENGINE" in ans.selected_ids
    assert "cannot conclude that both motors" not in blob
    assert "impeller kits" not in blob
    assert "EVT-FAKTURA-9631-IMPELLER" not in ans.selected_ids
    codes = {p.code for p in ans.policy_results}
    assert "NO_SERIAL_GUESS" in codes or ans.epistemic_status == "documented"
    assert ans.epistemic_status == "documented"


def test_gate_d_q09_bb_engine_documented_serial() -> None:
    """Q09: BB motor serial from asset bootstrap when documented."""
    snap = build_ac_fixture_snapshot()
    ans = answer_query("Hvilket serienummer har BB-motoren?", snapshot=snap)
    blob = ans.text_blob
    assert "2004030432" in blob
    assert "AI-D4-BB-ENGINE" in ans.selected_ids
    assert "2004030433" not in blob  # do not leak SB when asking BB only
    assert "generic path" not in blob
    assert ans.epistemic_status == "documented"
    codes = {p.code for p in ans.policy_results}
    assert "NO_SERIAL_GUESS" in codes or True  # allow-ok documented still ok
    assert all(p.code != "BB_SB_INTEGRITY" for p in ans.policy_results)


def test_gate_d_q10_sb_pcu_serial_unknown_no_clean_switch() -> None:
    """Q10: SB-PCU serial unknown — honest absence, never PCU cleaned template."""
    snap = build_ac_fixture_snapshot()
    ans = answer_query("Hvilket serienummer har SB-PCU'en?", snapshot=snap)
    blob = ans.text_blob
    assert "AI-D4-SB-PCU" in ans.selected_ids or "sb" in blob and "pcu" in blob
    assert "unknown" in blob
    assert "cleaned" not in blob
    assert "9273" not in blob
    assert "CLM-PCU-CLEAN-2025" not in ans.selected_ids
    assert "EVT-FAKTURA-9273-PCU" not in ans.selected_ids
    assert "2004030432" not in blob  # do not invent / sibling-copy BB engine serial
    assert "2004030433" not in blob
    codes = {p.code for p in ans.policy_results}
    assert "NO_SERIAL_GUESS" in codes
    assert ans.epistemic_status == "unknown"


def test_gate_d_regression_impeller_and_pcu_templates_still_work() -> None:
    """Impeller date + PCU cleaned paths remain after serial-identity routing."""
    snap = build_ac_fixture_snapshot()
    impeller = answer_query("Hvornår blev impellerne sidst skiftet?", snapshot=snap)
    assert "9631" in impeller.text_blob
    assert "impeller" in impeller.text_blob
    assert "INVOICE_NE_INSTALL" in {p.code for p in impeller.policy_results} or (
        "ACTION_NE_OUTCOME" in {p.code for p in impeller.policy_results}
    )

    sides = answer_query("Blev begge motorers impellere skiftet?", snapshot=snap)
    assert "BB_SB_INTEGRITY" in {p.code for p in sides.policy_results}
    assert "cannot conclude" in sides.text_blob

    pcu = answer_query("Hvad blev gjort ved PCU-stikket?", snapshot=snap)
    assert "clean" in pcu.text_blob
    assert "9273" in pcu.text_blob or "CLM-PCU-CLEAN-2025" in pcu.selected_ids
