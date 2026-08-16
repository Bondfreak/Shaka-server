from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from shaka_server.app import create_app

ALLOWED_ORIGIN = "https://bondfreak.github.io"
DISALLOWED_ORIGIN = "https://example.invalid"


def test_allowed_ui_origin_receives_cors_header() -> None:
    client = TestClient(create_app(core_client=object(), cors_origins=ALLOWED_ORIGIN))
    response = client.get("/healthz", headers={"Origin": ALLOWED_ORIGIN})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
    assert "access-control-allow-credentials" not in response.headers


def test_unlisted_origin_is_not_authorized() -> None:
    client = TestClient(create_app(core_client=object(), cors_origins=ALLOWED_ORIGIN))
    response = client.get("/healthz", headers={"Origin": DISALLOWED_ORIGIN})
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_preflight_allows_bounded_get_and_kai_post_for_allowed_origin() -> None:
    client = TestClient(create_app(core_client=object(), cors_origins=ALLOWED_ORIGIN))
    get_response = client.options(
        "/api/v1/objects/SYS-0003",
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Accept",
        },
    )
    assert get_response.status_code == 200
    assert get_response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
    assert "GET" in get_response.headers["access-control-allow-methods"]

    post_response = client.options(
        "/api/v1/kai/explain",
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )
    assert post_response.status_code == 200
    assert post_response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
    assert "POST" in post_response.headers["access-control-allow-methods"]


def test_wildcard_origin_configuration_fails_closed() -> None:
    with pytest.raises(RuntimeError, match="Wildcard"):
        create_app(core_client=object(), cors_origins="*")
