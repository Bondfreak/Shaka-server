"""F1-T05 Asset Instance bootstrap — Unknown-safe BB/SB identities."""

from __future__ import annotations

import pytest

from shaka_server.f1.assets import (
    ASSET_IDS,
    DOCUMENTED_SERIALS,
    AssetRegistry,
    bootstrap_shaka_assets,
    get_asset,
    list_assets,
    reset_asset_api,
)
from shaka_server.f1.composer import answer_query
from shaka_server.f1.core import (
    ValidationError,
    assign_serial_from_evidence,
    normalize_serial,
    side_from_quantity_alone,
)
from shaka_server.f1.core.helpers import assert_bb_sb_not_merged
from shaka_server.f1.retrieval import SnapshotIndex
from shaka_server.f1.snapshot import build_ac_fixture_snapshot


class TestBootstrapShakaAssets:
    def test_bb_sb_engines_distinct_ids_and_sides(self) -> None:
        assets = {a.id: a for a in bootstrap_shaka_assets()}
        bb = assets[ASSET_IDS["engine_bb"]]
        sb = assets[ASSET_IDS["engine_sb"]]
        assert bb.id != sb.id
        assert bb.side == "BB"
        assert sb.side == "SB"
        assert_bb_sb_not_merged(bb, sb)

    def test_documented_serials_only_where_specified(self) -> None:
        assets = {a.id: a for a in bootstrap_shaka_assets()}
        assert assets[ASSET_IDS["engine_bb"]].serial == DOCUMENTED_SERIALS["BB_ENGINE"]
        assert assets[ASSET_IDS["engine_sb"]].serial == DOCUMENTED_SERIALS["SB_ENGINE"]
        for key in (
            "vessel",
            "ips_bb",
            "ips_sb",
            "pcu_bb",
            "pcu_sb",
            "impeller_kit",
            "impeller_cand_a",
            "impeller_cand_b",
        ):
            assert assets[ASSET_IDS[key]].serial == "unknown", key

    def test_impeller_side_remains_unknown_candidate(self) -> None:
        assets = {a.id: a for a in bootstrap_shaka_assets()}
        kit = assets[ASSET_IDS["impeller_kit"]]
        a = assets[ASSET_IDS["impeller_cand_a"]]
        b = assets[ASSET_IDS["impeller_cand_b"]]
        assert kit.side == "unknown"
        assert a.side == "unknown"
        assert b.side == "unknown"
        assert side_from_quantity_alone(2) == "unknown"
        # Not both installed as BB+SB
        impeller_sides = {str(x.side) for x in (kit, a, b)}
        assert "BB" not in impeller_sides
        assert "SB" not in impeller_sides

    def test_ips_and_pcu_side_aware_placeholders(self) -> None:
        assets = {a.id: a for a in bootstrap_shaka_assets()}
        assert assets[ASSET_IDS["ips_bb"]].side == "BB"
        assert assets[ASSET_IDS["ips_sb"]].side == "SB"
        assert assets[ASSET_IDS["pcu_bb"]].side == "BB"
        assert assets[ASSET_IDS["pcu_sb"]].side == "SB"
        assert assets[ASSET_IDS["vessel"]].asset_type == "vessel"
        assert "NW370" in (assets[ASSET_IDS["vessel"]].location or "")

    def test_list_filter_by_side_type_ko(self) -> None:
        reg = AssetRegistry()
        bootstrap_shaka_assets(reg)
        bb = reg.list(side="BB")
        assert {a.id for a in bb} >= {
            ASSET_IDS["engine_bb"],
            ASSET_IDS["ips_bb"],
            ASSET_IDS["pcu_bb"],
        }
        assert all(str(a.side) == "BB" for a in bb)
        engines = reg.list(asset_type="engine")
        assert len(engines) == 2
        by_ko = reg.list(ko_id="KO-D4-0007")
        assert all(a.ko_id == "KO-D4-0007" for a in by_ko)
        assert ASSET_IDS["impeller_kit"] in {a.id for a in by_ko}

    def test_bootstrap_idempotent_same_ids(self) -> None:
        first = bootstrap_shaka_assets()
        second = bootstrap_shaka_assets()
        assert [a.id for a in first] == [a.id for a in second]
        assert [(a.id, a.side, a.serial, a.asset_type) for a in first] == [
            (a.id, a.side, a.serial, a.asset_type) for a in second
        ]
        reg = AssetRegistry()
        bootstrap_shaka_assets(reg)
        bootstrap_shaka_assets(reg)
        assert len(reg) == len(first)

    def test_serial_helper_never_invents(self) -> None:
        assert normalize_serial("") == "unknown"
        assert normalize_serial(None) == "unknown"
        with pytest.raises(ValidationError, match=r"invent"):
            assign_serial_from_evidence(None, {"guess": "from-sibling"})

    def test_bb_sb_never_merged_into_one_asset(self) -> None:
        assets = {a.id: a for a in bootstrap_shaka_assets()}
        pairs = [
            (ASSET_IDS["engine_bb"], ASSET_IDS["engine_sb"]),
            (ASSET_IDS["ips_bb"], ASSET_IDS["ips_sb"]),
            (ASSET_IDS["pcu_bb"], ASSET_IDS["pcu_sb"]),
        ]
        for left, right in pairs:
            assert assets[left].id != assets[right].id
            assert_bb_sb_not_merged(assets[left], assets[right])

    def test_thin_api_get_and_list(self) -> None:
        reset_asset_api()
        engine = get_asset(ASSET_IDS["engine_bb"])
        assert engine is not None
        assert engine.serial == DOCUMENTED_SERIALS["BB_ENGINE"]
        sb_only = list_assets(side="SB")
        assert all(str(a.side) == "SB" for a in sb_only)
        assert get_asset("AI-DOES-NOT-EXIST") is None
        reset_asset_api()


class TestSnapshotIntegration:
    def test_snapshot_includes_bootstrap_assets(self) -> None:
        snap = build_ac_fixture_snapshot()
        ids = {a.id for a in snap.assets}
        assert ASSET_IDS["engine_bb"] in ids
        assert ASSET_IDS["engine_sb"] in ids
        assert ASSET_IDS["impeller_kit"] in ids
        assert ASSET_IDS["pcu_bb"] in ids
        assert ASSET_IDS["ips_bb"] in ids
        assert ASSET_IDS["vessel"] in ids
        by_id = snap.by_id()
        assert by_id[ASSET_IDS["engine_bb"]].serial == DOCUMENTED_SERIALS["BB_ENGINE"]

    def test_retrieval_resolves_asset_ids(self) -> None:
        snap = build_ac_fixture_snapshot()
        index = SnapshotIndex(snap)
        hits = index.search("engine serial BB", keywords=["serial", "bb", "engine"], limit=10)
        hit_ids = {h.entity_id for h in hits}
        assert ASSET_IDS["engine_bb"] in hit_ids or any(
            ASSET_IDS["engine_bb"] in str(h) for h in hits
        ) or ASSET_IDS["engine_bb"] in snap.by_id()

    def test_composer_still_passes_ac01(self) -> None:
        snap = build_ac_fixture_snapshot()
        ans = answer_query("Hvornår blev impellerne sidst skiftet?", snapshot=snap)
        assert "9631" in ans.text_blob
        assert "EVT-FAKTURA-9631-IMPELLER" in ans.selected_ids
