"""Bootstrap Shaka twin-propulsion Asset Instances — Unknown-safe, no invented serials."""

from __future__ import annotations

from typing import Any

from shaka_server.f1.assets.registry import AssetRegistry
from shaka_server.f1.core.helpers import (
    assert_bb_sb_not_merged,
    assign_serial_from_evidence,
    normalize_serial,
    side_from_quantity_alone,
)
from shaka_server.f1.core.types import Asset
from shaka_server.f1.core.validators import validate_asset

# Documented engine serials only (fixtures / Phase 5). Never invent others.
DOCUMENTED_SERIALS = {
    "BB_ENGINE": "2004030432",
    "SB_ENGINE": "2004030433",
}

VESSEL_ID = "shaka"

# Stable Asset Instance IDs — AC fixtures depend on engines / impeller / BB PCU.
ASSET_IDS = {
    "vessel": "AI-SHAKA-VESSEL",
    "engine_bb": "AI-D4-BB-ENGINE",
    "engine_sb": "AI-D4-SB-ENGINE",
    "ips_bb": "AI-D4-BB-IPS",
    "ips_sb": "AI-D4-SB-IPS",
    "pcu_bb": "AI-D4-BB-PCU",
    "pcu_sb": "AI-D4-SB-PCU",
    "impeller_kit": "AI-D4-IMPELLER-KIT",
    # Two unknown-side candidates (CF-002: ×2 kits ≠ BB/SB install split).
    "impeller_cand_a": "AI-D4-IMPELLER-CANDIDATE-A",
    "impeller_cand_b": "AI-D4-IMPELLER-CANDIDATE-B",
}

# KO links only where platform mapping is known from EXP-001 / fixtures.
KO_IDS = {
    "engine": "KO-D4-0062",
    "impeller": "KO-D4-0007",
    "pcu": "KO-D4-0190",
    "ips": "KO-D4-0103",
}


def _asset(
    *,
    asset_id: str,
    side: str,
    asset_type: str,
    serial_documented: str | None,
    ko_id: str | None = None,
    location: str | None = None,
    lifecycle: str | None = None,
) -> Asset:
    """Build a validated Asset; serial via helper (blank → unknown, never invent)."""
    serial = assign_serial_from_evidence(serial_documented)
    raw: dict[str, Any] = {
        "id": asset_id,
        "kind": "Asset",
        "vesselId": VESSEL_ID,
        "side": side,
        "assetType": asset_type,
        "serial": normalize_serial(serial),
    }
    if ko_id is not None:
        raw["koId"] = ko_id
    if location is not None:
        raw["location"] = location
    if lifecycle is not None:
        raw["lifecycle"] = lifecycle
    return validate_asset(raw)


def _specs() -> list[dict[str, Any]]:
    """Ordered deterministic bootstrap specs for M/Y Shaka (NW370 Fly 2009)."""
    # Impeller: qty alone must not allocate sides (CF-002).
    impeller_side = side_from_quantity_alone(2)
    return [
        {
            "asset_id": ASSET_IDS["vessel"],
            "side": "unknown",  # vessel-level; N/A → unknown
            "asset_type": "vessel",
            "serial_documented": None,
            "ko_id": None,
            "location": "NW370 Fly 2009",
            "lifecycle": "in_service",
        },
        {
            "asset_id": ASSET_IDS["engine_bb"],
            "side": "BB",
            "asset_type": "engine",
            "serial_documented": DOCUMENTED_SERIALS["BB_ENGINE"],
            "ko_id": KO_IDS["engine"],
            "location": "port_engine_room",
        },
        {
            "asset_id": ASSET_IDS["engine_sb"],
            "side": "SB",
            "asset_type": "engine",
            "serial_documented": DOCUMENTED_SERIALS["SB_ENGINE"],
            "ko_id": KO_IDS["engine"],
            "location": "starboard_engine_room",
        },
        {
            "asset_id": ASSET_IDS["ips_bb"],
            "side": "BB",
            "asset_type": "ips",
            "serial_documented": None,  # unknown unless documented
            "ko_id": KO_IDS["ips"],
            "location": "port_drive",
        },
        {
            "asset_id": ASSET_IDS["ips_sb"],
            "side": "SB",
            "asset_type": "ips",
            "serial_documented": None,
            "ko_id": KO_IDS["ips"],
            "location": "starboard_drive",
        },
        {
            # CF-003 context: BB PCU service documented; serial still unknown.
            "asset_id": ASSET_IDS["pcu_bb"],
            "side": "BB",
            "asset_type": "pcu",
            "serial_documented": None,
            "ko_id": KO_IDS["pcu"],
            "location": "port_pcu",
            "lifecycle": "in_service",
        },
        {
            # Side-aware SB placeholder — inventory incomplete; serial unknown.
            "asset_id": ASSET_IDS["pcu_sb"],
            "side": "SB",
            "asset_type": "pcu",
            "serial_documented": None,
            "ko_id": KO_IDS["pcu"],
            "location": "starboard_pcu",
            "lifecycle": "placeholder",
        },
        {
            # Explicit unknown-side kit (invoice ×2 does not install both sides).
            "asset_id": ASSET_IDS["impeller_kit"],
            "side": impeller_side,
            "asset_type": "impeller",
            "serial_documented": None,
            "ko_id": KO_IDS["impeller"],
            "lifecycle": "invoiced_candidate",
        },
        {
            "asset_id": ASSET_IDS["impeller_cand_a"],
            "side": "unknown",
            "asset_type": "impeller",
            "serial_documented": None,
            "ko_id": KO_IDS["impeller"],
            "lifecycle": "candidate",
        },
        {
            "asset_id": ASSET_IDS["impeller_cand_b"],
            "side": "unknown",
            "asset_type": "impeller",
            "serial_documented": None,
            "ko_id": KO_IDS["impeller"],
            "lifecycle": "candidate",
        },
    ]


def bootstrap_shaka_assets(registry: AssetRegistry | None = None) -> list[Asset]:
    """
    Create Shaka Asset Instances with Unknown-safe fields.

    Idempotent: same IDs and field values on every call. Never invents serials.
    Preserves BB/SB as distinct Asset identities (never merged).
    """
    assets = [_asset(**spec) for spec in _specs()]

    by_id = {a.id: a for a in assets}
    assert_bb_sb_not_merged(by_id[ASSET_IDS["engine_bb"]], by_id[ASSET_IDS["engine_sb"]])
    assert_bb_sb_not_merged(by_id[ASSET_IDS["ips_bb"]], by_id[ASSET_IDS["ips_sb"]])
    assert_bb_sb_not_merged(by_id[ASSET_IDS["pcu_bb"]], by_id[ASSET_IDS["pcu_sb"]])

    # Impellers must not claim installed BB/SB from quantity alone.
    for impeller in (
        by_id[ASSET_IDS["impeller_kit"]],
        by_id[ASSET_IDS["impeller_cand_a"]],
        by_id[ASSET_IDS["impeller_cand_b"]],
    ):
        if str(impeller.side) in {"BB", "SB"}:
            raise ValueError(
                f"Impeller {impeller.id} must not have BB/SB side without side evidence"
            )

    if registry is not None:
        for asset in assets:
            registry.upsert(asset)

    return sorted(assets, key=lambda a: a.id)
