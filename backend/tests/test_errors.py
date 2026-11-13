"""Unit tests for the domain exceptions and their HTTP handlers (Req 41.3, 41.4)."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.errors import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    InvalidTransitionError,
    NotFoundError,
    RateLimitedError,
    ServiceUnavailableError,
    UnauthorizedError,
    UpstreamError,
    register_exception_handlers,
)


class _Body(BaseModel):
    count: int


def _build_client() -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/raise/{kind}")
    def raise_error(kind: str):
        errors = {
            "400": BadRequestError("bad"),
            "401": UnauthorizedError("Invalid or expired token"),
            "403": ForbiddenError("nope"),
            "404": NotFoundError("missing"),
            "409": ConflictError("conflict"),
            "409t": InvalidTransitionError("Cannot change order from PLACED to READY"),
            "429": RateLimitedError(12.2),
            "502": UpstreamError("openai down"),
            "503": ServiceUnavailableError("no key"),
        }
        raise errors[kind]

    @app.get("/boom")
    def boom():
        raise RuntimeError("unexpected")

    @app.post("/validate")
    def validate(body: _Body):
        return body

    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize(
    ("kind", "status", "detail"),
    [
        ("400", 400, "bad"),
        ("401", 401, "Invalid or expired token"),
        ("403", 403, "nope"),
        ("404", 404, "missing"),
        ("409", 409, "conflict"),
        ("409t", 409, "Cannot change order from PLACED to READY"),
        ("429", 429, "Too many requests. Try again in 13 seconds."),
        ("502", 502, "openai down"),
        ("503", 503, "no key"),
    ],
)
def test_domain_errors_map_to_status_and_detail_body(kind, status, detail):
    response = _build_client().get(f"/raise/{kind}")
    assert response.status_code == status
    assert response.json() == {"detail": detail}


def test_unauthorized_sets_www_authenticate_header():
    response = _build_client().get("/raise/401")
    assert response.headers["www-authenticate"] == "Bearer"


def test_rate_limited_sets_retry_after_rounded_up_to_whole_seconds():
    response = _build_client().get("/raise/429")
    assert response.headers["retry-after"] == "13"


def test_other_errors_do_not_set_auth_or_retry_headers():
    response = _build_client().get("/raise/404")
    assert "www-authenticate" not in response.headers
    assert "retry-after" not in response.headers


def test_invalid_transition_is_a_conflict_error():
    assert issubclass(InvalidTransitionError, ConflictError)


def test_unhandled_exception_returns_json_500():
    response = _build_client().get("/boom")
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}


def test_request_validation_error_returns_422_with_detail_list():
    response = _build_client().post("/validate", json={"count": "not-a-number"})
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)
