"""F1-T04 retrieval index tests over frozen AC fixture snapshot."""

from __future__ import annotations

from shaka_server.f1.retrieval import SnapshotIndex
from shaka_server.f1.snapshot import (
    FIXTURE_PART_ABSENT,
    FIXTURE_PART_IMPELLER,
    FIXTURE_SERIALS,
    build_ac_fixture_snapshot,
)


def test_snapshot_contains_documented_serials_only() -> None:
    snap = build_ac_fixture_snapshot()
    serials = {a.serial for a in snap.assets}
    assert FIXTURE_SERIALS["BB_ENGINE"] in serials
    assert FIXTURE_SERIALS["SB_ENGINE"] in serials
    assert "unknown" in serials
    invented = serials - {FIXTURE_SERIALS["BB_ENGINE"], FIXTURE_SERIALS["SB_ENGINE"], "unknown"}
    assert invented == set()


def test_index_finds_impeller_invoice_9631() -> None:
    snap = build_ac_fixture_snapshot()
    index = SnapshotIndex(snap)
    hits = index.search("impeller faktura 9631", keywords=["impeller", "9631"])
    ids = {h.entity_id for h in hits}
    assert "EVT-FAKTURA-9631-IMPELLER" in ids
    assert "SRC-FAKTURA-9631" in ids
    event = next(h.entity for h in hits if h.entity_id == "EVT-FAKTURA-9631-IMPELLER")
    assert event.time_or_period
    assert event.role == "invoiced"


def test_index_part_number_3588475() -> None:
    snap = build_ac_fixture_snapshot()
    index = SnapshotIndex(snap)
    assert index.has_part_number(FIXTURE_PART_IMPELLER)
    hits = index.search(FIXTURE_PART_IMPELLER, part_number=FIXTURE_PART_IMPELLER)
    assert any("9631" in h.entity_id or "IMPELLER" in h.entity_id for h in hits)


def test_index_filter_by_side_and_status() -> None:
    snap = build_ac_fixture_snapshot()
    index = SnapshotIndex(snap)
    bb = index.search("engine", side="BB", kinds=["Asset"])
    assert all(getattr(h.entity, "side", None) in ("BB",) for h in bb)
    assert any(h.entity_id == "AI-D4-BB-ENGINE" for h in bb)

    conflicted = index.search("motor", status="conflicted", kinds=["Claim"])
    assert {h.entity_id for h in conflicted} >= {"CLM-MOTOR-TYPE-D4", "CLM-MOTOR-TYPE-D6"}


def test_index_pcu_9273_and_absent_pn() -> None:
    snap = build_ac_fixture_snapshot()
    index = SnapshotIndex(snap)
    hits = index.search("PCU cleaned 9273")
    ids = {h.entity_id for h in hits}
    assert "EVT-FAKTURA-9273-PCU" in ids or "CLM-PCU-CLEAN-2025" in ids
    assert not index.has_part_number(FIXTURE_PART_ABSENT)

