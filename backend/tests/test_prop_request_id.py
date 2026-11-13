"""Property test for request id propagation (Requirements 30.2, 30.3).

The properties need only the middleware, so they hit ``/openapi.json`` through a module-level
``TestClient`` (no lifespan, no database session).
"""

from __future__ import annotations

import logging
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.main import app

REQUEST_ID_HEADER = "X-Request-ID"
PROCESS_TIME_HEADER = "X-Process-Time"
MIDDLEWARE_LOGGER = "app.middleware.request_context"
PROBE_PATH = "/openapi.json"

# 1-128 visible ASCII characters (0x21-0x7E). Space is excluded: HTTP strips leading and
# trailing whitespace from header values, so a padded id could not round-trip by design.
visible_ascii_ids = st.text(
    alphabet=st.characters(min_codepoint=0x21, max_codepoint=0x7E),
    min_size=1,
    max_size=128,
)

PBT_SETTINGS = settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)

_client = TestClient(app)


def _assert_process_time(response) -> None:
    assert float(response.headers[PROCESS_TIME_HEADER]) >= 0


@given(request_id=visible_ascii_ids)
@PBT_SETTINGS
def test_supplied_request_id_is_echoed_and_logged(caplog: pytest.LogCaptureFixture, request_id: str) -> None:
    """Feature: campusbite-platform, Property 28: Request id propagation

    **Validates: Requirements 30.2, 30.3**

    For any ``X-Request-ID`` of 1-128 visible ASCII characters, the response carries the same
    value and a non-negative ``X-Process-Time``, and the access log line carries the same id.
    """
    caplog.clear()
    with caplog.at_level(logging.INFO, logger=MIDDLEWARE_LOGGER):
        response = _client.get(PROBE_PATH, headers={REQUEST_ID_HEADER: request_id})

    assert response.status_code == 200
    assert response.headers[REQUEST_ID_HEADER] == request_id
    _assert_process_time(response)

    access_lines = [
        r.getMessage()
        for r in caplog.records
        if r.name == MIDDLEWARE_LOGGER and r.getMessage().startswith(f"GET {PROBE_PATH} -> 200 in ")
    ]
    assert len(access_lines) == 1
    assert access_lines[0].endswith(f" request_id={request_id}")


@given(request_count=st.integers(min_value=2, max_value=10))
@PBT_SETTINGS
def test_missing_request_id_yields_unique_uuid(request_count: int) -> None:
    """Feature: campusbite-platform, Property 28: Request id propagation

    **Validates: Requirements 30.2, 30.3**

    Without the header, every response carries a valid UUID4 and no two requests share one.
    """
    generated: list[str] = []
    for _ in range(request_count):
        response = _client.get(PROBE_PATH)
        assert response.status_code == 200
        value = response.headers[REQUEST_ID_HEADER]
        assert str(UUID(value)) == value
        assert UUID(value).version == 4
        _assert_process_time(response)
        generated.append(value)

    assert len(set(generated)) == request_count
