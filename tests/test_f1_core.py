"""F1-T01 core schema tests — ported from navigator-f1-core."""

from __future__ import annotations

import pytest

from shaka_server.f1.core import (
    ValidationError,
    assign_serial_from_evidence,
    normalize_serial,
    side_from_quantity_alone,
    validate_asset,
    validate_evidence,
    validate_knowledge_object,
    validate_source,
)

FIXTURE_SERIALS = {
    "BB_ENGINE": "2004030432",
    "SB_ENGINE": "2004030433",
}

ASSETS = {
    "bbEngine": {
        "id": "AI-D4-BB-ENGINE",
        "kind": "Asset",
        "vesselId": "shaka",
        "side": "BB",
        "assetType": "engine",
        "koId": "KO-D4-0062",
        "serial": FIXTURE_SERIALS["BB_ENGINE"],
    },
    "sbEngine": {
        "id": "AI-D4-SB-ENGINE",
        "kind": "Asset",
        "vesselId": "shaka",
        "side": "SB",
        "assetType": "engine",
        "koId": "KO-D4-0062",
        "serial": FIXTURE_SERIALS["SB_ENGINE"],
    },
    "impellerUnknown": {
        "id": "AI-D4-IMPELLER-KIT",
        "kind": "Asset",
        "vesselId": "shaka",
        "side": "unknown",
        "assetType": "impeller",
        "koId": "KO-D4-0007",
        "serial": "unknown",
    },
}

KNOWLEDGE_OBJECTS = {
    "impeller": {
        "id": "KO-D4-0007",
        "kind": "KnowledgeObject",
        "title": "Seawater pump impeller",
        "scope": "D4-300 / IPS400",
    },
}


class TestF1T01CoreSchema:
    def test_ac_fixture_bb_sb_documented_serials_only(self) -> None:
        bb = validate_asset(ASSETS["bbEngine"])
        sb = validate_asset(ASSETS["sbEngine"])
        assert bb.serial == FIXTURE_SERIALS["BB_ENGINE"]
        assert sb.serial == FIXTURE_SERIALS["SB_ENGINE"]
        assert bb.side == "BB"
        assert sb.side == "SB"

    def test_ko_ne_asset_enforced(self) -> None:
        with pytest.raises(ValidationError):
            validate_knowledge_object({**KNOWLEDGE_OBJECTS["impeller"], "serial": "x"})
        with pytest.raises(ValidationError):
            validate_asset({**ASSETS["bbEngine"], "kind": "KnowledgeObject"})
        assert validate_knowledge_object(KNOWLEDGE_OBJECTS["impeller"]).kind == "KnowledgeObject"

    def test_source_ne_evidence_enforced(self) -> None:
        content_hash = "a" * 64
        with pytest.raises(ValidationError, match=r"Source ≠ Evidence|sourceId"):
            validate_source(
                {
                    "id": "SRC-1",
                    "kind": "Source",
                    "sourceType": "invoice",
                    "title": "t",
                    "contentHash": content_hash,
                    "mimeType": "application/pdf",
                    "storageRef": "blob://x",
                    "sourceId": "nope",
                }
            )
        with pytest.raises(ValidationError, match=r"Source ≠ Evidence|storage"):
            validate_evidence(
                {
                    "id": "EVD-1",
                    "kind": "Evidence",
                    "sourceId": "SRC-1",
                    "contentHash": content_hash,
                }
            )


class TestSerialHelpersNeverInvent:
    def test_normalize_blank_to_unknown(self) -> None:
        assert normalize_serial("") == "unknown"
        assert normalize_serial(None) == "unknown"
        assert normalize_serial(FIXTURE_SERIALS["BB_ENGINE"]) == FIXTURE_SERIALS["BB_ENGINE"]

    def test_refuses_guess(self) -> None:
        with pytest.raises(ValidationError, match=r"invent"):
            assign_serial_from_evidence(None, {"guess": "999"})

    def test_ac02_impeller_x2_without_side_unknown(self) -> None:
        assert side_from_quantity_alone(2) == "unknown"
        asset = validate_asset(ASSETS["impellerUnknown"])
        assert asset.side == "unknown"
