from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


class CoreContractError(RuntimeError):
    pass


@dataclass(frozen=True)
class CoreResult:
    status_code: int
    payload: dict[str, Any]


class CoreClient:
    def __init__(self, base_url: str, *, timeout_seconds: float = 3.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds

    def _get(self, path: str) -> CoreResult:
        try:
            response = httpx.get(
                f"{self._base_url}{path}",
                timeout=self._timeout,
                follow_redirects=False,
            )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise CoreContractError("core_unavailable") from exc

        if response.status_code not in {200, 400, 404, 409, 503}:
            raise CoreContractError("unexpected_core_status")

        try:
            payload = response.json()
        except ValueError as exc:
            raise CoreContractError("malformed_core_response") from exc
        if not isinstance(payload, dict):
            raise CoreContractError("malformed_core_response")
        return CoreResult(response.status_code, payload)

    def health(self) -> CoreResult:
        return self._get("/healthz")

    def asset_instance_detail(self, public_id: str) -> CoreResult:
        return self._get(f"/api/v1/asset-instances/{public_id}")

    def graph(self, public_id: str) -> CoreResult:
        return self._get(f"/api/v1/asset-instances/{public_id}/graph?depth=1")

    def resolve_asset_instance(self, context_public_id: str, asset_public_id: str) -> CoreResult:
        return self._get(
            f"/api/v1/asset-instances/{context_public_id}/resolve-asset/{asset_public_id}"
        )

    def object_detail(self, public_id: str) -> CoreResult:
        return self._get(f"/api/v1/objects/{public_id}")
