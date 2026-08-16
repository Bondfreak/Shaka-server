from __future__ import annotations

import httpx
import pytest

from shaka_server.core_client import CoreClient, CoreContractError


def response(status: int, payload: dict[str, object]) -> httpx.Response:
    request = httpx.Request("GET", "https://core.example/api")
    return httpx.Response(status, json=payload, request=request)


def test_transient_502_can_recover_on_fourth_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    replies = iter(
        [
            response(502, {"error": {"code": "gateway", "message": "waking"}}),
            response(503, {"error": {"code": "starting", "message": "still waking"}}),
            response(504, {"error": {"code": "gateway", "message": "still waking"}}),
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
    assert len(calls) == 4
    assert sleeps == [5.0, 5.0, 5.0]
    assert all(call[1]["timeout"] == 20.0 for call in calls)


def test_transient_timeout_can_recover_after_multiple_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    request = httpx.Request("GET", "https://core.example/api")
    replies = iter(
        [
            httpx.ReadTimeout("waking", request=request),
            httpx.ReadTimeout("still waking", request=request),
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
    assert calls == 3


@pytest.mark.parametrize("status", [502, 504])
def test_persistent_gateway_failure_is_dependency_unavailable_after_bounded_retries(
    monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    calls = 0

    def fake_get(*args, **kwargs):
        nonlocal calls
        calls += 1
        return response(status, {"error": {"code": "gateway", "message": "still waking"}})

    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr("shaka_server.core_client.time.sleep", lambda _: None)

    with pytest.raises(CoreContractError, match="core_unavailable"):
        CoreClient("https://core.example", retry_delay_seconds=0).object_detail("SYS-0003")
    assert calls == 4


def test_persistent_core_503_remains_bounded_503_after_bounded_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def fake_get(*args, **kwargs):
        nonlocal calls
        calls += 1
        return response(503, {"error": {"code": "core_503", "message": "bounded Core error"}})

    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr("shaka_server.core_client.time.sleep", lambda _: None)

    result = CoreClient("https://core.example", retry_delay_seconds=0).object_detail("SYS-0003")
    assert result.status_code == 503
    assert result.payload["error"]["code"] == "core_503"
    assert calls == 4


def test_retry_count_can_be_reduced_for_test_or_local_use(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def fake_get(*args, **kwargs):
        nonlocal calls
        calls += 1
        return response(503, {"error": {"code": "core_503", "message": "bounded Core error"}})

    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr("shaka_server.core_client.time.sleep", lambda _: None)

    result = CoreClient(
        "https://core.example", retry_delay_seconds=0, retry_count=1
    ).object_detail("SYS-0003")
    assert result.status_code == 503
    assert calls == 2


def test_negative_retry_count_is_rejected() -> None:
    with pytest.raises(ValueError, match="retry_count must be non-negative"):
        CoreClient("https://core.example", retry_count=-1)


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
