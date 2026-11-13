"""Shared pytest fixtures: a real PostgreSQL test database with per-test rollback.

Environment is configured *before* any ``app`` import, because ``app.db.session`` builds its
engine from ``Settings`` at import time and ``app.main`` builds the FastAPI app at import time.
``DATABASE_URL`` is pointed at the test database so that even code paths that bypass the
``get_db`` override can never touch the development database.

Fixtures
--------
``engine``       session-scoped engine on ``TEST_DATABASE_URL``; ``drop_all`` + ``create_all`` once.
``connection``   per-test connection with an outer transaction that is always rolled back.
``db``           per-test ``Session`` bound with ``join_transaction_mode="create_savepoint"``, so
                 ``commit()`` / ``rollback()`` inside code under test only touch a savepoint.
``client``       ``TestClient`` whose ``get_db`` dependency yields ``db`` (and which overrides
                 ``get_openai_client`` too once that dependency exists).
``auth_headers`` helper ``auth_headers(user) -> {"Authorization": "Bearer <jwt>"}``.
``db_example``   context manager for Hypothesis tests: one rolled-back savepoint per example.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

DEFAULT_TEST_DATABASE_URL = "postgresql+psycopg://campusbite:campusbite@localhost:5432/campusbite_test"
TEST_JWT_SECRET = "test-secret-for-pytest-only-0123456789abcdef"  # >= 32 characters

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL") or DEFAULT_TEST_DATABASE_URL

# Force the test configuration. Real environment values for these must never leak into tests.
os.environ["TEST_DATABASE_URL"] = TEST_DATABASE_URL
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["JWT_SECRET"] = TEST_JWT_SECRET
os.environ["JWT_EXPIRE_MINUTES"] = "60"
os.environ["OPENAI_API_KEY"] = ""
os.environ["ENABLE_SCHEDULER"] = "false"
os.environ["CORS_ORIGINS"] = "http://localhost:5173"

import jwt  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.engine import Connection, Engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

import app.models  # noqa: E402,F401  (registers every table on Base.metadata)
from app.api import deps  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402

JWT_ALGORITHM = "HS256"


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    """Engine on the test database with a freshly created schema (``drop_all`` then ``create_all``)."""
    eng = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    try:
        yield eng
    finally:
        eng.dispose()


@pytest.fixture
def connection(engine: Engine) -> Iterator[Connection]:
    """A connection inside an outer transaction that is rolled back after the test."""
    conn = engine.connect()
    outer = conn.begin()
    try:
        yield conn
    finally:
        if outer.is_active:
            outer.rollback()
        conn.close()


@pytest.fixture
def db(connection: Connection) -> Iterator[Session]:
    """Session joined to the per-test transaction through a SAVEPOINT.

    ``commit()`` releases the savepoint instead of the outer transaction, so service code that
    commits (or ``get_db``) cannot leak rows into other tests.
    """
    session = Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
        autoflush=False,
        expire_on_commit=False,
    )
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    """``TestClient`` with ``get_db`` overridden to yield the per-test ``db`` session.

    The override mirrors the production ``get_db``: commit on success, rollback on error. Both are
    savepoint operations here, so they stay inside the test transaction.
    """

    def _override_get_db() -> Iterator[Session]:
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise

    fastapi_app.dependency_overrides[deps.get_db] = _override_get_db
    with TestClient(fastapi_app) as test_client:
        yield test_client
    fastapi_app.dependency_overrides.clear()


@pytest.fixture
def db_example(connection: Connection) -> Callable[[], object]:
    """Factory for a per-Hypothesis-example context manager.

    Usage::

        @given(...)
        @settings(max_examples=100, deadline=None,
                  suppress_health_check=[HealthCheck.function_scoped_fixture])
        def test_prop(db_example, x):
            with db_example() as db:
                ...  # rows created here are rolled back when the block exits

    Each ``with`` block opens a SAVEPOINT on the per-test connection and a Session joined to it
    (itself using savepoints for ``commit()``/``rollback()``), then rolls the savepoint back.
    """

    @contextmanager
    def _db_example() -> Iterator[Session]:
        with connection.begin_nested() as savepoint:
            session = Session(
                bind=connection,
                join_transaction_mode="create_savepoint",
                autoflush=False,
                expire_on_commit=False,
            )
            try:
                yield session
            finally:
                session.close()
                if savepoint.is_active:
                    savepoint.rollback()

    return _db_example


def make_token(
    user_id: int,
    role: object,
    *,
    expires_in: timedelta = timedelta(minutes=60),
    secret: str = TEST_JWT_SECRET,
) -> str:
    """Mint an HS256 JWT directly with PyJWT: claims ``sub`` (str id), ``role`` and ``exp``."""
    claims = {
        "sub": str(user_id),
        "role": str(getattr(role, "value", role)),
        "exp": datetime.now(timezone.utc) + expires_in,
    }
    return jwt.encode(claims, secret, algorithm=JWT_ALGORITHM)


@pytest.fixture
def auth_headers() -> Callable[..., dict[str, str]]:
    """Return ``auth_headers(user, **token_options) -> {"Authorization": "Bearer ..."}``.

    ``user`` is any object with ``id`` and ``role`` (an ORM ``User``). Pass ``expires_in`` (e.g. a
    negative timedelta) or ``secret`` to build expired or foreign-signed tokens.
    """

    def _auth_headers(user: object, **options: object) -> dict[str, str]:
        token = make_token(user.id, user.role, **options)  # type: ignore[attr-defined]
        return {"Authorization": f"Bearer {token}"}

    return _auth_headers
