"""Unit tests for the request-context middleware and CORS wiring (Req 30.1, 30.2, 30.4, 30.5)."""

from __future__ import annotations

import logging
import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import create_app

MIDDLEWARE_LOGGER = "app.middleware.request_context"
ALLOWED_ORIGIN = "http://localhost:5173"  # CORS_ORIGINS set in conftest.py
UNLISTED_ORIGIN = "http://evil.example.com"


@pytest.fixture
def test_app() -> FastAPI:
    """A fresh app (same middleware stack as production) with two probe routes."""
    application = create_app()

    @application.get("/_ok")
    def ok() -> dict[str, bool]:
        return {"ok": True}

    @application.get("/_boom")
    def boom() -> dict[str, bool]:
        raise RuntimeError("kaboom")

    return application


@pytest.fixture
def mw_client(test_app: FastAPI) -> TestClient:
    return TestClient(test_app)


def test_access_log_contains_method_path_status_and_duration(
    mw_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger=MIDDLEWARE_LOGGER):
        response = mw_client.get("/_ok")

    assert response.status_code == 200
    records = [r for r in caplog.records if r.name == MIDDLEWARE_LOGGER and r.levelno == logging.INFO]
    assert len(records) == 1
    message = records[0].getMessage()
    assert re.fullmatch(r"GET /_ok -> 200 in \d+\.\d{2}ms request_id=\S+", message), message
    assert response.headers["X-Request-ID"] in message


def test_access_log_omits_query_string(mw_client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger=MIDDLEWARE_LOGGER):
        mw_client.get("/_ok?token=secret")

    assert "secret" not in caplog.text


def test_process_time_header_is_numeric(mw_client: TestClient) -> None:
    response = mw_client.get("/_ok")

    assert float(response.headers["X-Process-Time"]) >= 0


def test_request_id_is_echoed_or_generated(mw_client: TestClient) -> None:
    echoed = mw_client.get("/_ok", headers={"X-Request-ID": "abc-123"})
    generated = mw_client.get("/_ok")

    assert echoed.headers["X-Request-ID"] == "abc-123"
    assert generated.headers["X-Request-ID"]


def test_cors_allows_listed_origin(mw_client: TestClient) -> None:
    response = mw_client.get("/_ok", headers={"Origin": ALLOWED_ORIGIN})

    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN


def test_cors_preflight_allows_listed_origin(mw_client: TestClient) -> None:
    response = mw_client.options(
        "/_ok",
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN


def test_cors_omits_allow_origin_for_unlisted_origin(mw_client: TestClient) -> None:
    response = mw_client.get("/_ok", headers={"Origin": UNLISTED_ORIGIN})

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_unhandled_exception_returns_500_json(
    mw_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger=MIDDLEWARE_LOGGER):
        response = mw_client.get("/_boom")

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert "X-Request-ID" in response.headers
    assert any(r.levelno == logging.ERROR and r.exc_info for r in caplog.records)
    assert "kaboom" not in response.text


def test_500_response_still_carries_cors_headers(mw_client: TestClient) -> None:
    response = mw_client.get("/_boom", headers={"Origin": ALLOWED_ORIGIN})

    assert response.status_code == 500
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
