from __future__ import annotations

import time
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
    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = 20.0,
        retry_delay_seconds: float = 5.0,
        retry_count: int = 3,
    ) -> None:
        if retry_count < 0:
            raise ValueError("retry_count must be non-negative")
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._retry_delay = retry_delay_seconds
        self._retry_count = retry_count

    def _request(self, path: str) -> httpx.Response:
        return httpx.get(
            f"{self._base_url}{path}",
            timeout=self._timeout,
            follow_redirects=False,
        )

    def _get(self, path: str) -> CoreResult:
        response: httpx.Response | None = None
        last_transport_error: Exception | None = None

        for attempt in range(self._retry_count + 1):
            try:
                response = self._request(path)
                last_transport_error = None
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_transport_error = exc
                response = None

            transient_status = response is not None and response.status_code in {502, 503, 504}
            if attempt < self._retry_count and (
                last_transport_error is not None or transient_status
            ):
                time.sleep(self._retry_delay)
                continue
            break

        if last_transport_error is not None or response is None:
            raise CoreContractError("core_unavailable") from last_transport_error

        if response.status_code in {502, 504}:
            raise CoreContractError("core_unavailable")

        if response.status_code not in {200, 400, 404, 409, 503}:
            raise CoreContractError("unexpected_core_status")

        try:
            payload = response.json()
        except ValueError as exc:
            raise CoreContractError("malformed_core_response") from exc
        if not isinstance(payload, dict):
            raise CoreContractError("malformed_core_response")
        return CoreResult(response.status_code, payload)

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
