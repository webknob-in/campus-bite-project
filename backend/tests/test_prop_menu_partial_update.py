"""Property test for partial menu updates (Requirements 16.3, 16.5).

Every example runs through the real ``/owner/menu-items`` routes against PostgreSQL. Each example gets
its own rolled-back savepoint (``db_example``) and ``get_db`` is re-pointed at that example's session.
Setup rows are committed inside the example session (a savepoint release), so the 4xx rollback of the
``get_db`` override cannot discard them.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from typing import Any

from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import deps
from app.main import app as fastapi_app
from app.models import MenuItem
from tests.factories import make_menu_item, make_owner, make_restaurant

COLUMNS = (
    "id",
    "restaurant_id",
    "name",
    "description",
    "price",
    "category",
    "image_url",
    "is_available",
    "created_at",
)
UPDATABLE = ("name", "description", "price", "category", "image_url", "is_available")

# --- strategies -------------------------------------------------------------------------------

_chars = st.characters(categories=("L", "N", "P", "S", "Zs"), codec="utf-8")


def _text(max_size: int, *, min_size: int = 0) -> st.SearchStrategy[str]:
    """Text that survives the schema's whitespace stripping unchanged and is never blank."""
    return (
        st.text(alphabet=_chars, min_size=min_size, max_size=max_size)
        .filter(lambda s: s == s.strip() and s != "")
        .filter(lambda s: len(s) <= max_size)
    )


names = _text(120)
descriptions = st.one_of(st.none(), _text(1000))
categories = st.one_of(st.none(), _text(60))
image_urls = st.one_of(
    st.none(),
    st.builds(
        lambda host, path: f"https://{host}.example.com/img/{path}.png",
        st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789", min_size=1, max_size=20),
        st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789-_", min_size=1, max_size=40),
    ),
)
# 0.01 .. 100000.00 in whole cents.
prices = st.integers(min_value=1, max_value=10_000_000).map(lambda cents: Decimal(cents) / 100)
booleans = st.booleans()

initial_values = st.fixed_dictionaries(
    {
        "name": names,
        "description": descriptions,
        "price": prices,
        "category": categories,
        "image_url": image_urls,
        "is_available": booleans,
    }
)

# A random subset of the updatable fields (possibly empty) with valid values.
patches = st.fixed_dictionaries(
    {},
    optional={
        "name": names,
        "description": descriptions,
        "price": prices,
        "category": categories,
        "image_url": image_urls,
        "is_available": booleans,
    },
)


# --- helpers ----------------------------------------------------------------------------------


def _use_example_session(db: Session) -> None:
    def _get_db() -> Iterator[Session]:
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise

    fastapi_app.dependency_overrides[deps.get_db] = _get_db


def _stored(db: Session, item_id: int) -> dict[str, Any]:
    """The row as stored in PostgreSQL, bypassing the session's identity map."""
    db.expire_all()
    row = db.scalar(select(MenuItem).where(MenuItem.id == item_id))
    assert row is not None
    return {c: getattr(row, c) for c in COLUMNS}


def _wire(value: Any) -> Any:
    return str(value) if isinstance(value, Decimal) else value


def _price_string(price: Decimal) -> str:
    return format(price.quantize(Decimal("0.01")), "f")


def _assert_response_matches_row(body: dict[str, Any], row: dict[str, Any]) -> None:
    assert set(body) == {
        "id",
        "restaurant_id",
        "name",
        "description",
        "price",
        "category",
        "image_url",
        "is_available",
    }
    for column in body:
        expected = _price_string(row[column]) if column == "price" else row[column]
        assert body[column] == expected, column


# --- the properties ---------------------------------------------------------------------------


@given(initial=initial_values, patch=patches)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
def test_patch_changes_exactly_the_supplied_fields(
    client: TestClient, db_example, auth_headers, initial: dict, patch: dict
) -> None:
    """Feature: campusbite-platform, Property 20: Partial menu updates

    **Validates: Requirements 16.3, 16.5**

    PATCH ``/owner/menu-items/{id}`` with any subset of valid fields (including none) changes exactly
    the supplied fields to the supplied values and leaves every other column, ``id``,
    ``restaurant_id`` and ``created_at`` included, unchanged. The response reflects the stored row
    with the price as a two-place string. Another menu item of the same restaurant is untouched.
    """
    with db_example() as db:
        _use_example_session(db)
        owner = make_owner(db)
        restaurant = make_restaurant(db, owner)
        item = make_menu_item(db, restaurant, **initial)
        sibling = make_menu_item(db, restaurant)
        db.commit()

        before = _stored(db, item.id)
        sibling_before = _stored(db, sibling.id)

        body = {k: (str(v) if isinstance(v, Decimal) else v) for k, v in patch.items()}
        res = client.patch(f"/owner/menu-items/{item.id}", json=body, headers=auth_headers(owner))
        assert res.status_code == 200, res.text

        after = _stored(db, item.id)
        for column in COLUMNS:
            if column in patch:
                assert after[column] == patch[column], column
            else:
                assert after[column] == before[column], column
        _assert_response_matches_row(res.json(), after)
        assert _stored(db, sibling.id) == sibling_before

        # Reading the item afterwards returns the supplied values.
        listing = client.get("/owner/menu-items", headers=auth_headers(owner))
        assert listing.status_code == 200, listing.text
        listed = next(i for i in listing.json()["items"] if i["id"] == item.id)
        for column in patch:
            assert listed[column] == (_price_string(patch[column]) if column == "price" else patch[column])


@given(initial=initial_values, new_value=booleans)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
def test_availability_endpoint_changes_only_is_available(
    client: TestClient, db_example, auth_headers, initial: dict, new_value: bool
) -> None:
    """Feature: campusbite-platform, Property 20: Partial menu updates

    **Validates: Requirements 16.3, 16.5**

    PATCH ``/owner/menu-items/{id}/availability`` changes only ``is_available``.
    """
    with db_example() as db:
        _use_example_session(db)
        owner = make_owner(db)
        item = make_menu_item(db, make_restaurant(db, owner), **initial)
        db.commit()

        before = _stored(db, item.id)
        res = client.patch(
            f"/owner/menu-items/{item.id}/availability",
            json={"is_available": new_value},
            headers=auth_headers(owner),
        )
        assert res.status_code == 200, res.text

        after = _stored(db, item.id)
        assert after["is_available"] is new_value
        assert {c: v for c, v in after.items() if c != "is_available"} == {
            c: v for c, v in before.items() if c != "is_available"
        }
        _assert_response_matches_row(res.json(), after)


@given(initial=initial_values, patch=patches, new_value=booleans)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
def test_another_owners_item_is_not_found_and_unchanged(
    client: TestClient, db_example, auth_headers, initial: dict, patch: dict, new_value: bool
) -> None:
    """Feature: campusbite-platform, Property 20: Partial menu updates

    **Validates: Requirements 16.3, 16.5**

    Updating another owner's menu item, by either endpoint, is a 404 and leaves the row unchanged.
    """
    with db_example() as db:
        _use_example_session(db)
        owner = make_owner(db)
        make_restaurant(db, owner)
        other = make_owner(db)
        item = make_menu_item(db, make_restaurant(db, other), **initial)
        db.commit()

        before = _stored(db, item.id)

        body = {k: (str(v) if isinstance(v, Decimal) else v) for k, v in patch.items()}
        res = client.patch(f"/owner/menu-items/{item.id}", json=body, headers=auth_headers(owner))
        assert res.status_code == 404, res.text
        assert _stored(db, item.id) == before

        res = client.patch(
            f"/owner/menu-items/{item.id}/availability",
            json={"is_available": new_value},
            headers=auth_headers(owner),
        )
        assert res.status_code == 404, res.text
        assert _stored(db, item.id) == before
