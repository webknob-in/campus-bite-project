"""Property test for the dish filters (Requirements 9.1, 9.2, 9.3, 9.4, 9.5).

Every example creates 1-3 restaurants with up to 15 dishes in PostgreSQL (its own rolled-back
savepoint, see ``db_example``), then compares the ids returned by ``GET /dishes`` and
``GET /restaurants/{id}/menu`` with a pure-Python model of the filters built on ``Decimal``.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from decimal import Decimal

from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy.orm import Session

from app.api import deps
from app.main import app as fastapi_app
from tests.factories import make_menu_item, make_restaurant

PRICE_FORMAT = re.compile(r"^\d+\.\d{2}$")
CENT = Decimal("0.01")

# --- strategies -------------------------------------------------------------------------------

# Characters whose ``str.lower()`` agrees with PostgreSQL ``ILIKE``: ASCII, a few accented Latin
# letters (both cases) and the LIKE metacharacters ``%``, ``_`` and ``\``.
NAME_ALPHABET = (
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 -'&.,"
    "%_\\"
    "éÉèÈüÜñÑçÇ"
)
_name_chars = st.sampled_from(NAME_ALPHABET)
# Small alphabet for part of the names so that substring searches hit several dishes.
_few_chars = st.sampled_from("aAbB%_\\é É")

dish_names = st.one_of(
    st.text(alphabet=_name_chars, min_size=1, max_size=20),
    st.text(alphabet=_few_chars, min_size=1, max_size=8),
).filter(lambda s: s.strip() != "")

cents = st.integers(min_value=1, max_value=10_000_000)  # 0.01 .. 100000.00


def _money(value: int) -> Decimal:
    return Decimal(value).scaleb(-2)


@dataclass(frozen=True)
class Dish:
    restaurant: int  # index into the generated restaurants
    name: str
    price: Decimal
    is_available: bool


def catalogues(restaurant_count: int) -> st.SearchStrategy[list[Dish]]:
    return st.lists(
        st.builds(
            Dish,
            restaurant=st.integers(min_value=0, max_value=restaurant_count - 1),
            name=dish_names,
            price=cents.map(_money),
            is_available=st.booleans(),
        ),
        min_size=0,
        max_size=15,
    )


@st.composite
def filters(draw: st.DrawFn, dishes: list[Dish]) -> dict:
    """Valid filter combinations: ``search``, ``min_price``, ``max_price`` with min <= max."""
    names = [d.name for d in dishes if d.name]
    prices = [d.price for d in dishes if d.name]

    search = None
    mode = draw(st.sampled_from(["none", "none", "substring", "random", "blank"]))
    if mode == "substring" and names:
        name = draw(st.sampled_from(names))
        start = draw(st.integers(min_value=0, max_value=len(name) - 1))
        end = draw(st.integers(min_value=start + 1, max_value=len(name)))
        search = name[start:end]
        case = draw(st.sampled_from(["same", "lower", "upper", "swap"]))
        search = {
            "same": search,
            "lower": search.lower(),
            "upper": search.upper(),
            "swap": search.swapcase(),
        }[case]
        pad = draw(st.sampled_from(["", " ", "  "]))  # the backend trims the search text
        search = pad + search + pad
    elif mode == "random":
        search = draw(st.text(alphabet=_few_chars, min_size=1, max_size=3))
    elif mode == "blank":
        search = draw(st.sampled_from(["", " ", "   "]))

    def bound() -> st.SearchStrategy[Decimal]:
        options: list[st.SearchStrategy[Decimal]] = [
            st.integers(min_value=0, max_value=10_001_000).map(lambda v: Decimal(v).scaleb(-2)),
            st.integers(min_value=0, max_value=100_010_000).map(lambda v: Decimal(v).scaleb(-3)),
        ]
        if prices:
            options.append(st.sampled_from(prices))  # exercises the inclusive bounds
        return st.one_of(*options)

    low = high = None
    if draw(st.booleans()):
        low = draw(bound())
    if draw(st.booleans()):
        high = draw(bound())
    if low is not None and high is not None and low > high:
        low, high = high, low
    return {"search": search, "min_price": low, "max_price": high}


@st.composite
def scenarios(draw: st.DrawFn) -> tuple[list[Dish], dict, int]:
    restaurant_count = draw(st.integers(min_value=1, max_value=3))
    dishes = draw(catalogues(restaurant_count))
    flt = draw(filters(dishes))
    menu_restaurant = draw(st.integers(min_value=0, max_value=restaurant_count - 1))
    return dishes, {**flt, "_restaurants": restaurant_count}, menu_restaurant


# --- model ------------------------------------------------------------------------------------


def model_matches(dish: Dish, search: str | None, low: Decimal | None, high: Decimal | None) -> bool:
    term = (search or "").replace("\x00", "").strip()
    if term and term.lower() not in dish.name.lower():
        return False
    if low is not None and dish.price < low:
        return False
    if high is not None and dish.price > high:
        return False
    return True


def _params(search: str | None, low: Decimal | None, high: Decimal | None) -> dict[str, str]:
    params: dict[str, str] = {}
    if search is not None:
        params["search"] = search
    if low is not None:
        params["min_price"] = format(low, "f")
    if high is not None:
        params["max_price"] = format(high, "f")
    return params


def _fetch_all(client: TestClient, url: str, params: dict[str, str]) -> tuple[list[dict], int]:
    items: list[dict] = []
    page = 1
    while True:
        res = client.get(url, params={**params, "page": page, "page_size": 100})
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["page"] == page and body["page_size"] == 100
        items.extend(body["items"])
        if not body["items"] or len(items) >= body["total"]:
            return items, body["total"]
        page += 1


def _check_prices(items: list[dict], low: Decimal | None, high: Decimal | None) -> None:
    for item in items:
        assert isinstance(item["price"], str) and PRICE_FORMAT.match(item["price"]), item["price"]
        price = Decimal(item["price"])
        assert price >= CENT
        if low is not None:
            assert price >= low
        if high is not None:
            assert price <= high


# --- the property -----------------------------------------------------------------------------

SETTINGS = settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)


@given(scenario=scenarios())
@SETTINGS
def test_dish_filters_match_model(client: TestClient, db_example, scenario) -> None:
    """Feature: campusbite-platform, Property 7: Dish filters match model

    **Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5**

    ``GET /dishes`` and ``GET /restaurants/{id}/menu`` return exactly the dishes that satisfy
    every supplied filter (name contains ``search`` case-insensitively, ``price >= min_price``,
    ``price <= max_price``); ``/dishes`` items carry the restaurant id and name (9.6).
    """
    dishes, flt, menu_index = scenario
    restaurant_count = flt.pop("_restaurants")
    search, low, high = flt["search"], flt["min_price"], flt["max_price"]

    with db_example() as db:
        _point_get_db_at(db)
        restaurants = [make_restaurant(db) for _ in range(restaurant_count)]
        rows = [
            (
                dish,
                make_menu_item(
                    db,
                    restaurants[dish.restaurant],
                    name=dish.name,
                    price=dish.price,
                    is_available=dish.is_available,
                ),
            )
            for dish in dishes
        ]
        params = _params(search, low, high)

        # GET /dishes: all restaurants.
        expected = {row.id for dish, row in rows if model_matches(dish, search, low, high)}
        items, total = _fetch_all(client, "/dishes", params)
        got = [item["id"] for item in items]
        assert len(got) == len(set(got)), "duplicate dishes across pages"
        assert set(got) == expected
        assert total == len(expected)
        _check_prices(items, low, high)
        by_id = {row.id: (dish, row) for dish, row in rows}
        restaurant_by_id = {r.id: r for r in restaurants}
        for item in items:
            dish, row = by_id[item["id"]]
            restaurant = restaurant_by_id[row.restaurant_id]
            assert item["restaurant_id"] == restaurant.id  # 9.6
            assert item["restaurant_name"] == restaurant.name  # 9.6
            assert item["name"] == dish.name
            assert Decimal(item["price"]) == dish.price
            assert item["is_available"] is dish.is_available

        # GET /restaurants/{id}/menu: one restaurant only.
        menu_restaurant = restaurants[menu_index]
        expected_menu = {
            row.id
            for dish, row in rows
            if dish.restaurant == menu_index and model_matches(dish, search, low, high)
        }
        items, total = _fetch_all(client, f"/restaurants/{menu_restaurant.id}/menu", params)
        got = [item["id"] for item in items]
        assert len(got) == len(set(got))
        assert set(got) == expected_menu
        assert total == len(expected_menu)
        _check_prices(items, low, high)
        assert all(item["restaurant_id"] == menu_restaurant.id for item in items)


# --- invalid filters -> 422 -------------------------------------------------------------------

_NON_NUMERIC = st.sampled_from(["abc", "12abc", "1,5", "--1", "ten", "1.2.3", "$5", "5 5", "0x10"])

invalid_params = st.one_of(
    # min_price > max_price (both valid, non-negative numbers).
    st.tuples(st.integers(min_value=0, max_value=10_000_000), st.integers(min_value=1, max_value=10_000_000)).map(
        lambda t: {
            "min_price": format(_money(t[0] + t[1]), "f"),
            "max_price": format(_money(t[0]), "f"),
        }
    ),
    # A negative price, optionally with a valid counterpart.
    st.tuples(
        st.sampled_from(["min_price", "max_price"]),
        cents.map(lambda v: format(-_money(v), "f")),
        st.one_of(st.none(), cents.map(lambda v: format(_money(v), "f"))),
    ).map(lambda t: {t[0]: t[1], **({} if t[2] is None else {"max_price" if t[0] == "min_price" else "min_price": t[2]})}),
    # A non-numeric price.
    st.tuples(st.sampled_from(["min_price", "max_price"]), _NON_NUMERIC).map(lambda t: {t[0]: t[1]}),
)


@given(params=invalid_params, search=st.one_of(st.none(), st.just("a")))
@SETTINGS
def test_invalid_dish_filters_return_422(client: TestClient, db_example, params: dict, search) -> None:
    """Feature: campusbite-platform, Property 7: Dish filters match model

    **Validates: Requirements 9.5**

    A negative price, a non-numeric price, or ``min_price > max_price`` gives HTTP 422 on both
    dish endpoints.
    """
    with db_example() as db:
        _point_get_db_at(db)
        restaurant = make_restaurant(db)
        make_menu_item(db, restaurant, name="Paneer", price="50.00")
        query = dict(params)
        if search is not None:
            query["search"] = search
        assert client.get("/dishes", params=query).status_code == 422
        assert client.get(f"/restaurants/{restaurant.id}/menu", params=query).status_code == 422


def _point_get_db_at(db: Session) -> None:
    def _get_db() -> Iterator[Session]:
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise

    fastapi_app.dependency_overrides[deps.get_db] = _get_db
