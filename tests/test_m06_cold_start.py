from __future__ import annotations

import httpx
import pytest

from shaka_server.core_client import CoreClient, CoreContractError


def response(status: int, payload: dict[str, object]) -> httpx.Response:
    request = httpx.Request("GET", "https://core.example/api")
    return httpx.Response(status, json=payload, request=request)


def test_transient_502_retries_once_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    replies = iter(
        [
            response(502, {"error": {"code": "gateway", "message": "waking"}}),
            response(200, {"data": {"id": "SYS-0003", "type": "system"}, "meta": {"schemaVersion": "1.0"}}),
        ]
    )

    def fake_get(*args, **kwargs):
        calls.append((args, kwargs))
        return next(replies)

    sleeps = []
    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr("shaka_server.core_client.time.sleep", sleeps.append)

    client = CoreClient("https://core.example", timeout_seconds=20.0, retry_delay_seconds=5.0)
    result = client.object_detail("SYS-0003")

    assert result.status_code == 200
    assert len(calls) == 2
    assert sleeps == [5.0]
    assert calls[0][1]["timeout"] == 20.0


def test_transient_timeout_retries_once_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    request = httpx.Request("GET", "https://core.example/api")
    replies = iter(
        [
            httpx.ReadTimeout("waking", request=request),
            response(200, {"data": {"id": "SYS-0003", "type": "system"}, "meta": {"schemaVersion": "1.0"}}),
        ]
    )
    calls = 0

    def fake_get(*args, **kwargs):
        nonlocal calls
        calls += 1
        item = next(replies)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr("shaka_server.core_client.time.sleep", lambda _: None)

    result = CoreClient("https://core.example", retry_delay_seconds=0).object_detail("SYS-0003")
    assert result.status_code == 200
    assert calls == 2


@pytest.mark.parametrize("status", [502, 504])
def test_persistent_gateway_failure_is_dependency_unavailable(
    monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    monkeypatch.setattr(
        httpx,
        "get",
        lambda *args, **kwargs: response(status, {"error": {"code": "gateway", "message": "still waking"}}),
    )
    monkeypatch.setattr("shaka_server.core_client.time.sleep", lambda _: None)

    with pytest.raises(CoreContractError, match="core_unavailable"):
        CoreClient("https://core.example", retry_delay_seconds=0).object_detail("SYS-0003")


def test_persistent_core_503_remains_bounded_503(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        httpx,
        "get",
        lambda *args, **kwargs: response(503, {"error": {"code": "core_503", "message": "bounded Core error"}}),
    )
    monkeypatch.setattr("shaka_server.core_client.time.sleep", lambda _: None)

    result = CoreClient("https://core.example", retry_delay_seconds=0).object_detail("SYS-0003")
    assert result.status_code == 503
    assert result.payload["error"]["code"] == "core_503"


def test_non_transient_unexpected_status_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def fake_get(*args, **kwargs):
        nonlocal calls
        calls += 1
        return response(418, {"error": {"code": "teapot", "message": "unexpected"}})

    monkeypatch.setattr(httpx, "get", fake_get)

    with pytest.raises(CoreContractError, match="unexpected_core_status"):
        CoreClient("https://core.example", retry_delay_seconds=0).object_detail("SYS-0003")
    assert calls == 1
