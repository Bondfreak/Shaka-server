"""Thin Asset lookup API over the Shaka bootstrap registry."""

from __future__ import annotations

from shaka_server.f1.assets.bootstrap import bootstrap_shaka_assets
from shaka_server.f1.assets.registry import AssetRegistry
from shaka_server.f1.core.types import Asset

_REGISTRY: AssetRegistry | None = None


def _registry() -> AssetRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = AssetRegistry()
        bootstrap_shaka_assets(_REGISTRY)
    return _REGISTRY


def reset_asset_api() -> None:
    """Test helper — clear module singleton."""
    global _REGISTRY
    _REGISTRY = None


def get_asset(asset_id: str) -> Asset | None:
    """Return one Asset by id, or None."""
    return _registry().get(asset_id)


def list_assets(
    *,
    side: str | None = None,
    asset_type: str | None = None,
    ko_id: str | None = None,
) -> list[Asset]:
    """List Assets filtered by optional side / asset_type / ko_id."""
    return _registry().list(side=side, asset_type=asset_type, ko_id=ko_id)
