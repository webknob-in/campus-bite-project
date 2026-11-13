"""Schema smoke tests: the Alembic migration builds the 8 brief tables with every constraint.

``alembic upgrade head`` runs in a subprocess against its own scratch databases (created and
dropped here, named after the configured test database), so neither the shared ``engine``
fixture database nor the development database is touched (Req 36.1-36.3, 36.5, 36.6, 37.1,
37.5, 37.8, 38.6).
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models import OrderStatus
from tests.conftest import TEST_DATABASE_URL
from tests.factories import make_order, make_review

BACKEND_DIR = Path(__file__).resolve().parent.parent

EXPECTED_TABLES = {
    "users",
    "restaurants",
    "menu_items",
    "orders",
    "order_items",
    "reviews",
    "payment_ledger",
    "admin_reminder_logs",
}
EXPECTED_ENUMS = {"user_role", "order_status", "payment_status", "return_status", "ledger_type"}

# (table, column) -> (referred table, ondelete rule)
EXPECTED_FKS = {
    ("restaurants", "owner_id"): ("users", "RESTRICT"),
    ("menu_items", "restaurant_id"): ("restaurants", "CASCADE"),
    ("orders", "customer_id"): ("users", "RESTRICT"),
    ("orders", "restaurant_id"): ("restaurants", "RESTRICT"),
    ("orders", "delivery_partner_id"): ("users", "SET NULL"),
    ("order_items", "order_id"): ("orders", "CASCADE"),
    ("order_items", "menu_item_id"): ("menu_items", "SET NULL"),
    ("reviews", "order_id"): ("orders", "RESTRICT"),
    ("reviews", "customer_id"): ("users", "RESTRICT"),
    ("reviews", "restaurant_id"): ("restaurants", "RESTRICT"),
    ("payment_ledger", "order_id"): ("orders", "RESTRICT"),
    ("admin_reminder_logs", "order_id"): ("orders", "CASCADE"),
    ("admin_reminder_logs", "restaurant_id"): ("restaurants", "CASCADE"),
}

EXPECTED_UNIQUES = {
    "users": {("email",)},
    "restaurants": {("owner_id",)},
    "reviews": {("order_id",)},
    "payment_ledger": {("transaction_ref",)},
    "admin_reminder_logs": {("order_id", "status_at_reminder")},
}

# table -> {constraint name: regexes that its normalized SQL must match}
EXPECTED_CHECKS = {
    "menu_items": {"ck_menu_items_price_positive": [r"price\s*>\s*\(?0"]},
    "order_items": {"ck_order_items_quantity_range": [r"quantity\s*>=\s*1", r"quantity\s*<=\s*99"]},
    "reviews": {"ck_reviews_rating_range": [r"rating\s*>=\s*1", r"rating\s*<=\s*5"]},
    "orders": {"ck_orders_total_amount_nonneg": [r"total_amount\s*>=\s*\(?0"]},
}

EXPECTED_INDEXED_COLUMNS = {
    ("orders", "status"),
    ("orders", "created_at"),
    ("orders", "status_updated_at"),
    ("orders", "return_status"),
}


def _server_url():
    return make_url(TEST_DATABASE_URL).set(database="postgres")


def _scratch_url(suffix: str) -> str:
    name = f"{make_url(TEST_DATABASE_URL).database}_{suffix}"
    return make_url(TEST_DATABASE_URL).set(database=name).render_as_string(hide_password=False)


def _run_alembic(database_url: str, *args: str) -> None:
    env = {**os.environ, "DATABASE_URL": database_url}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, f"alembic {' '.join(args)} failed:\n{result.stdout}\n{result.stderr}"


@pytest.fixture
def scratch_database() -> Iterator[callable]:
    """Factory ``create(suffix) -> url`` for empty scratch databases, dropped afterwards."""
    created: list[str] = []
    admin = create_engine(_server_url(), isolation_level="AUTOCOMMIT")

    def create(suffix: str) -> str:
        url = _scratch_url(suffix)
        name = make_url(url).database
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
            conn.execute(text(f'CREATE DATABASE "{name}"'))
        created.append(name)
        return url

    try:
        yield create
    finally:
        with admin.connect() as conn:
            for name in created:
                conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


@pytest.fixture(scope="module")
def migrated_engine() -> Iterator[Engine]:
    """Engine on an empty scratch database after ``alembic upgrade head``."""
    admin = create_engine(_server_url(), isolation_level="AUTOCOMMIT")
    url = _scratch_url("schema")
    name = make_url(url).database
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    eng = create_engine(url)
    try:
        assert not inspect(eng).get_table_names(), "scratch database must start empty"
        _run_alembic(url, "upgrade", "head")
        yield eng
    finally:
        eng.dispose()
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


def _app_tables(engine: Engine) -> set[str]:
    return set(inspect(engine).get_table_names()) - {"alembic_version"}


def _enum_types(engine: Engine) -> set[str]:
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT typname FROM pg_type WHERE typtype = 'e'"))
        return {row[0] for row in rows}


# ------------------------------------------------------------------------- upgrade head


def test_upgrade_head_creates_exactly_the_eight_tables(migrated_engine: Engine) -> None:
    assert _app_tables(migrated_engine) == EXPECTED_TABLES
    assert _app_tables(migrated_engine) == set(Base.metadata.tables)
    assert _enum_types(migrated_engine) == EXPECTED_ENUMS


def test_every_table_has_an_id_primary_key(migrated_engine: Engine) -> None:
    insp = inspect(migrated_engine)
    for table in EXPECTED_TABLES:
        assert insp.get_pk_constraint(table)["constrained_columns"] == ["id"], table


def test_foreign_keys_and_ondelete_rules(migrated_engine: Engine) -> None:
    insp = inspect(migrated_engine)
    actual: dict[tuple[str, str], tuple[str, str | None]] = {}
    for table in EXPECTED_TABLES:
        for fk in insp.get_foreign_keys(table):
            assert len(fk["constrained_columns"]) == 1
            assert fk["referred_columns"] == ["id"]
            actual[(table, fk["constrained_columns"][0])] = (
                fk["referred_table"],
                fk["options"].get("ondelete"),
            )
    assert actual == EXPECTED_FKS


def test_unique_constraints(migrated_engine: Engine) -> None:
    insp = inspect(migrated_engine)
    for table in EXPECTED_TABLES:
        actual = {tuple(uc["column_names"]) for uc in insp.get_unique_constraints(table)}
        assert actual == EXPECTED_UNIQUES.get(table, set()), table


def test_check_constraints(migrated_engine: Engine) -> None:
    insp = inspect(migrated_engine)
    for table in EXPECTED_TABLES:
        actual = {ck["name"]: ck["sqltext"] for ck in insp.get_check_constraints(table)}
        expected = EXPECTED_CHECKS.get(table, {})
        assert set(actual) == set(expected), table
        for name, patterns in expected.items():
            for pattern in patterns:
                assert re.search(pattern, actual[name]), f"{name}: {actual[name]!r} !~ {pattern}"


def test_indexes_cover_status_columns_and_every_foreign_key(migrated_engine: Engine) -> None:
    insp = inspect(migrated_engine)
    leading_columns: dict[str, set[str]] = {}
    for table in EXPECTED_TABLES:
        leading = {ix["column_names"][0] for ix in insp.get_indexes(table)}
        # A unique constraint is backed by an index as well.
        leading |= {uc["column_names"][0] for uc in insp.get_unique_constraints(table)}
        leading_columns[table] = leading

    for table, column in EXPECTED_INDEXED_COLUMNS | set(EXPECTED_FKS):
        assert column in leading_columns[table], f"no index on {table}.{column}"


# ------------------------------------------------------------------------- downgrade base


def test_downgrade_base_removes_tables_and_enum_types(scratch_database) -> None:
    url = scratch_database("schema_down")
    eng = create_engine(url)
    try:
        _run_alembic(url, "upgrade", "head")
        assert _app_tables(eng) == EXPECTED_TABLES
        _run_alembic(url, "downgrade", "base")
        assert _app_tables(eng) == set()
        assert _enum_types(eng) == set()
    finally:
        eng.dispose()


# ------------------------------------------------------------------------- data rule


def test_second_review_for_one_order_raises_integrity_error(db: Session) -> None:
    order = make_order(db, OrderStatus.DELIVERED)
    make_review(db, order, rating=5)

    with pytest.raises(IntegrityError):
        make_review(db, order, rating=3)
