"""F1-T05 Asset Instance bootstrap (BB/SB) for M/Y Shaka."""

from shaka_server.f1.assets.api import get_asset, list_assets, reset_asset_api
from shaka_server.f1.assets.bootstrap import (
    ASSET_IDS,
    DOCUMENTED_SERIALS,
    KO_IDS,
    VESSEL_ID,
    bootstrap_shaka_assets,
)
from shaka_server.f1.assets.registry import AssetRegistry

__all__ = [
    "ASSET_IDS",
    "DOCUMENTED_SERIALS",
    "KO_IDS",
    "VESSEL_ID",
    "AssetRegistry",
    "bootstrap_shaka_assets",
    "get_asset",
    "list_assets",
    "reset_asset_api",
]
