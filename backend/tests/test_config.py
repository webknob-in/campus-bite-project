"""Unit tests for ``Settings`` validation and the ``build_engine`` factory (Req 39.6, 44.3)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from sqlalchemy.pool import NullPool, QueuePool

from app.core.config import Settings
from app.db.session import build_engine

VALID_SECRET = "x" * 32
VALID_URL = "postgresql+psycopg://u:p@localhost:5432/db"


def _set_env(monkeypatch: pytest.MonkeyPatch, *, database_url: str | None, jwt_secret: str | None) -> None:
    for name, value in (("DATABASE_URL", database_url), ("JWT_SECRET", jwt_secret)):
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)


def test_settings_load_when_required_variables_present(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_env(monkeypatch, database_url=VALID_URL, jwt_secret=VALID_SECRET)

    settings = Settings(_env_file=None)

    assert settings.database_url == VALID_URL
    assert settings.jwt_secret == VALID_SECRET


def test_missing_jwt_secret_raises_validation_error_naming_it(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_env(monkeypatch, database_url=VALID_URL, jwt_secret=None)

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)

    assert [e["loc"] for e in exc_info.value.errors()] == [("jwt_secret",)]
    assert "jwt_secret" in str(exc_info.value)


def test_missing_database_url_raises_validation_error_naming_it(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_env(monkeypatch, database_url=None, jwt_secret=VALID_SECRET)

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)

    assert [e["loc"] for e in exc_info.value.errors()] == [("database_url",)]
    assert "database_url" in str(exc_info.value)


def test_short_jwt_secret_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_env(monkeypatch, database_url=VALID_URL, jwt_secret="too-short")

    with pytest.raises(ValidationError, match="jwt_secret"):
        Settings(_env_file=None)


def test_build_engine_uses_null_pool_for_port_6543() -> None:
    engine = build_engine("postgresql+psycopg://u:p@pooler.example.com:6543/postgres?sslmode=require")
    try:
        assert isinstance(engine.pool, NullPool)
    finally:
        engine.dispose()


def test_build_engine_uses_queue_pool_for_other_ports() -> None:
    engine = build_engine(VALID_URL)
    try:
        assert isinstance(engine.pool, QueuePool)
    finally:
        engine.dispose()
