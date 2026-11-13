"""Property test for invalid menu prices and names (Requirement 16.6).

Every example runs through the real ``POST /owner/menu-items`` and ``PATCH /owner/menu-items/{id}``
routes against PostgreSQL. Each example gets its own rolled-back savepoint (``db_example``) and
``get_db`` is re-pointed at that example's session.

Bodies are serialised with ``json.dumps`` and sent as raw content, so ``NaN`` / ``Infinity`` reach the
server (the HTTP client's own ``json=`` argument refuses them).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from decimal import Decimal
from typing import Any

from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api import deps
from app.main import app as fastapi_app
from app.models import MenuItem
from tests.factories import make_menu_item, make_owner, make_restaurant

URL = "/owner/menu-items"
JSON_HEADERS = {"Content-Type": "application/json"}

# --- strategies -------------------------------------------------------------------------------

_int_part = st.integers(min_value=0, max_value=99999)


@st.composite
def _too_many_decimals(draw: st.DrawFn) -> str:
    """A positive amount <= 99999.999999 with 3..6 decimal places whose last digit is not zero."""
    places = draw(st.integers(min_value=3, max_value=6))
    head = draw(st.text(alphabet="0123456789", min_size=places - 1, max_size=places - 1))
    last = draw(st.sampled_from("123456789"))
    return f"{draw(_int_part)}.{head}{last}"


def _as_number_or_string(text: str) -> st.SearchStrategy[Any]:
    return st.sampled_from([text, float(text)])


def _not_a_decimal(text: str) -> bool:
    try:
        Decimal(text.strip())
    except ArithmeticError:  # decimal.InvalidOperation
        return True
    return False


invalid_prices = st.one_of(
    # zero and negatives, with up to 2 decimal places
    st.integers(min_value=-10_000_000, max_value=0).map(lambda cents: f"{Decimal(cents) / 100:.2f}"),
    st.integers(min_value=-100_000, max_value=0),
    st.floats(max_value=0.0, allow_nan=False, allow_infinity=True),
    # above 100000 (integers, floats and strings)
    st.integers(min_value=100_001, max_value=10**12),
    st.floats(min_value=100_000.01, max_value=1e15, allow_nan=False, allow_infinity=False).map(
        lambda f: float(f"{f:.2f}") if f"{f:.2f}" != "100000.00" else 100_000.01
    ),
    st.integers(min_value=10_000_001, max_value=10**14).map(lambda cents: f"{Decimal(cents) / 100:.2f}"),
    # 3 or more decimal places, as a string or a JSON number
    _too_many_decimals().flatmap(_as_number_or_string),
    # NaN / Infinity as numbers and as text
    st.sampled_from([float("nan"), float("inf"), float("-inf")]),
    st.sampled_from(["NaN", "nan", "Infinity", "-Infinity", "inf", "-inf", "sNaN"]),
    # non-numeric text
    st.sampled_from(["", " ", "abc", "$5", "1,5", "ten", "1.2.3", "--1", "0x10"]),
    st.text(max_size=20).filter(_not_a_decimal),
    # wrong JSON types
    st.booleans(),
    st.none(),
    st.lists(st.one_of(st.integers(), st.text(max_size=5)), max_size=3),
    st.dictionaries(st.text(max_size=5), st.integers(), max_size=3),
)

invalid_names = st.one_of(
    # blank after stripping
    st.text(alphabet=" \t\n\r", max_size=10),
    # longer than 120 characters once stripped
    st.text(alphabet=st.characters(categories=("L", "N"), codec="utf-8"), min_size=121, max_size=200),
)

# 0.01 .. 100000.00 with at most 2 decimal places
valid_cents = st.integers(min_value=1, max_value=10_000_000)
valid_forms = st.sampled_from(["string", "number"])


def _price_literal(cents: int, form: str) -> Any:
    amount = Decimal(cents) / 100
    return f"{amount:.2f}" if form == "string" else float(amount)


# --- helpers ----------------------------------------------------------------------------------


def _use_session(db: Session) -> None:
    def _get_db() -> Iterator[Session]:
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise

    fastapi_app.dependency_overrides[deps.get_db] = _get_db


def _send(client: TestClient, method: str, url: str, headers: dict[str, str], body: dict[str, Any]):
    return client.request(method, url, headers={**headers, **JSON_HEADERS}, content=json.dumps(body))


def _snapshot(db: Session, item_id: int) -> tuple[Any, ...]:
    db.expire_all()
    row = db.get(MenuItem, item_id)
    assert row is not None
    return (row.name, row.price, row.description, row.category, row.image_url, row.is_available)


def _count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(MenuItem)) or 0


# --- the properties ---------------------------------------------------------------------------

_SETTINGS = settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)


@given(price=invalid_prices)
@_SETTINGS
def test_invalid_prices_are_rejected_and_nothing_changes(
    client: TestClient, db_example, auth_headers, price: Any
) -> None:
    """Feature: campusbite-platform, Property 21: Invalid menu prices rejected

    **Validates: Requirements 16.6**

    A price that is <= 0, > 100000, has more than 2 decimal places, or is not a number (NaN,
    Infinity, text, boolean, null, list, object) is answered with 422 by both create and update, and
    the Menu_Item set (row count on create, every stored field of the item on update) is unchanged.
    """
    with db_example() as db:
        _use_session(db)
        owner = make_owner(db)
        restaurant = make_restaurant(db, owner)
        item = make_menu_item(db, restaurant, name="Original", price="12.34", description="Keep me")
        db.commit()
        headers = auth_headers(owner)
        before_rows = _count(db)
        before_item = _snapshot(db, item.id)

        created = _send(client, "POST", URL, headers, {"name": "New dish", "price": price})
        assert created.status_code == 422, (price, created.status_code, created.text)
        assert _count(db) == before_rows

        updated = _send(client, "PATCH", f"{URL}/{item.id}", headers, {"price": price})
        assert updated.status_code == 422, (price, updated.status_code, updated.text)
        assert _snapshot(db, item.id) == before_item
        assert _count(db) == before_rows

        # A bad price next to other valid changes must not apply those changes either.
        mixed = _send(client, "PATCH", f"{URL}/{item.id}", headers, {"name": "Renamed", "price": price})
        assert mixed.status_code == 422, (price, mixed.status_code, mixed.text)
        assert _snapshot(db, item.id) == before_item


@given(name=invalid_names)
@_SETTINGS
def test_invalid_names_are_rejected_and_nothing_changes(
    client: TestClient, db_example, auth_headers, name: str
) -> None:
    """Feature: campusbite-platform, Property 21: Invalid menu prices rejected

    **Validates: Requirements 16.6**

    A blank name or one longer than 120 characters is answered with 422 by create and update, and
    the Menu_Item set is unchanged.
    """
    with db_example() as db:
        _use_session(db)
        owner = make_owner(db)
        restaurant = make_restaurant(db, owner)
        item = make_menu_item(db, restaurant, name="Original", price="12.34")
        db.commit()
        headers = auth_headers(owner)
        before_rows = _count(db)
        before_item = _snapshot(db, item.id)

        created = _send(client, "POST", URL, headers, {"name": name, "price": "10.00"})
        assert created.status_code == 422, (name, created.status_code, created.text)
        assert _count(db) == before_rows

        updated = _send(client, "PATCH", f"{URL}/{item.id}", headers, {"name": name})
        assert updated.status_code == 422, (name, updated.status_code, updated.text)
        assert _snapshot(db, item.id) == before_item


@given(cents=valid_cents, form=valid_forms)
@_SETTINGS
def test_valid_prices_are_accepted_and_stored_exactly(
    client: TestClient, db_example, auth_headers, cents: int, form: str
) -> None:
    """Feature: campusbite-platform, Property 21: Invalid menu prices rejected

    **Validates: Requirements 16.6**

    Control: every price from 0.01 to 100000.00 with at most 2 decimal places, sent as a JSON string
    or a JSON number, is accepted by create (201) and update (200) and stored exactly (no float
    drift), both in the response and in the database.
    """
    expected = Decimal(cents) / 100
    price = _price_literal(cents, form)
    with db_example() as db:
        _use_session(db)
        owner = make_owner(db)
        restaurant = make_restaurant(db, owner)
        item = make_menu_item(db, restaurant, name="Original", price="12.34")
        db.commit()
        headers = auth_headers(owner)

        created = _send(client, "POST", URL, headers, {"name": "New dish", "price": price})
        assert created.status_code == 201, (price, created.text)
        assert Decimal(created.json()["price"]) == expected
        db.expire_all()
        stored = db.scalar(select(MenuItem.price).where(MenuItem.id == created.json()["id"]))
        assert stored == expected and isinstance(stored, Decimal)

        updated = _send(client, "PATCH", f"{URL}/{item.id}", headers, {"price": price})
        assert updated.status_code == 200, (price, updated.text)
        assert Decimal(updated.json()["price"]) == expected
        db.expire_all()
        assert db.scalar(select(MenuItem.price).where(MenuItem.id == item.id)) == expected
