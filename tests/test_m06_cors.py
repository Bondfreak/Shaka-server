from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from shaka_server.app import DEFAULT_UI_ORIGINS, create_app

ALLOWED_ORIGIN = "https://bondfreak.github.io"
LOCAL_ORIGIN = "http://localhost:8000"
DISALLOWED_ORIGIN = "https://example.invalid"


def test_allowed_ui_origin_receives_cors_header() -> None:
    client = TestClient(create_app(core_client=object(), cors_origins=ALLOWED_ORIGIN))
    response = client.get("/healthz", headers={"Origin": ALLOWED_ORIGIN})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
    assert "access-control-allow-credentials" not in response.headers


def test_localhost_origin_receives_cors_header() -> None:
    client = TestClient(create_app(core_client=object(), cors_origins=LOCAL_ORIGIN))
    response = client.get("/healthz", headers={"Origin": LOCAL_ORIGIN})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == LOCAL_ORIGIN


def test_default_origins_include_localhost_and_gh_pages() -> None:
    defaults = {o.strip() for o in DEFAULT_UI_ORIGINS.split(",") if o.strip()}
    assert "https://bondfreak.github.io" in defaults
    assert "http://localhost:8000" in defaults
    assert "http://127.0.0.1:8000" in defaults
    assert "http://localhost:8080" in defaults

    # create_app without cors_origins uses DEFAULT_UI_ORIGINS (env cleared)
    previous = os.environ.pop("SHAKA_UI_ORIGINS", None)
    try:
        client = TestClient(create_app(core_client=object()))
        for origin in (
            "https://bondfreak.github.io",
            "http://localhost:8000",
            "http://127.0.0.1:8080",
        ):
            response = client.get("/healthz", headers={"Origin": origin})
            assert response.status_code == 200
            assert response.headers["access-control-allow-origin"] == origin
    finally:
        if previous is not None:
            os.environ["SHAKA_UI_ORIGINS"] = previous


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


def test_preflight_allows_f1_answer_post_from_localhost() -> None:
    client = TestClient(create_app(core_client=object(), cors_origins=LOCAL_ORIGIN))
    response = client.options(
        "/api/v1/f1/answer",
        headers={
            "Origin": LOCAL_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == LOCAL_ORIGIN
    assert "POST" in response.headers["access-control-allow-methods"]


def test_wildcard_origin_configuration_fails_closed() -> None:
    with pytest.raises(RuntimeError, match="Wildcard"):
        create_app(core_client=object(), cors_origins="*")
