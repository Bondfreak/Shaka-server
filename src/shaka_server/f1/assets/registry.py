"""In-memory Asset registry — list/filter by side, type, ko_id."""

from __future__ import annotations

from shaka_server.f1.core.types import Asset


class AssetRegistry:
    """Deterministic registry of vessel Asset Instances."""

    def __init__(self) -> None:
        self._by_id: dict[str, Asset] = {}

    def upsert(self, asset: Asset) -> Asset:
        self._by_id[asset.id] = asset
        return asset

    def get(self, asset_id: str) -> Asset | None:
        return self._by_id.get(asset_id)

    def list(
        self,
        *,
        side: str | None = None,
        asset_type: str | None = None,
        ko_id: str | None = None,
    ) -> list[Asset]:
        items = list(self._by_id.values())
        if side is not None:
            items = [a for a in items if str(a.side) == side]
        if asset_type is not None:
            items = [a for a in items if a.asset_type == asset_type]
        if ko_id is not None:
            items = [a for a in items if a.ko_id == ko_id]
        return sorted(items, key=lambda a: a.id)

    def ids(self) -> list[str]:
        return sorted(self._by_id.keys())

    def __len__(self) -> int:
        return len(self._by_id)

    def clear(self) -> None:
        self._by_id.clear()
