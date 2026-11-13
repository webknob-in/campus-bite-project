"""Unit tests for ``GET /health`` (Req 30.6)."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.api import deps
from app.main import app as fastapi_app


class _BrokenSession:
    """Stand-in session whose every query fails like a lost database connection."""

    def execute(self, *args: object, **kwargs: object) -> None:
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))


def test_health_ok_with_database_up(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_health_503_when_database_query_fails(client: TestClient) -> None:
    def _broken_get_db() -> Iterator[_BrokenSession]:
        yield _BrokenSession()

    fastapi_app.dependency_overrides[deps.get_db] = _broken_get_db

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "error", "database": "error"}
