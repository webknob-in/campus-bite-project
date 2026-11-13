"""Property test for pagination (Requirements 27.1, 27.2, 27.3, 27.4).

Runs against the real ``GET /restaurants`` list endpoint (public, ordered by ``name, id``) on
PostgreSQL. Each example creates its rows inside a rolled-back savepoint (``db_example``) and
``get_db`` is re-pointed at that example's session.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from fastapi.testclient import TestClient
from hypothesis import HealthCheck, example, given, settings
from hypothesis import strategies as st
from sqlalchemy.orm import Session

from app.api import deps
from app.main import app as fastapi_app
from app.schemas.common import MAX_PAGE
from tests.factories import make_restaurant

SETTINGS = settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)

# Single uppercase letters sort identically under every collation, and a small alphabet
# produces many equal names, so the ``id`` tie-breaker is exercised.
restaurant_names = st.lists(st.sampled_from("ABCDE"), min_size=0, max_size=25)
page_sizes = st.one_of(st.integers(1, 6), st.integers(1, 100))


@contextmanager
def _seeded(db_example, client: TestClient, names: list[str]) -> Iterator[list[tuple[str, int]]]:
    """Create one Restaurant per name and point ``get_db`` at the example session.

    Yields the expected ``(name, id)`` listing order.
    """
    with db_example() as db:

        def _get_db() -> Iterator[Session]:
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise

        fastapi_app.dependency_overrides[deps.get_db] = _get_db
        rows = [make_restaurant(db, name=name) for name in names]
        yield sorted((r.name, r.id) for r in rows)


def _get(client: TestClient, **params: object):
    return client.get("/restaurants", params=params)


@given(names=restaurant_names, page_size=page_sizes, data=st.data())
@SETTINGS
def test_pages_partition_the_listing(client: TestClient, db_example, names, page_size, data) -> None:
    """Feature: campusbite-platform, Property 24: Pagination

    **Validates: Requirements 27.1, 27.2, 27.3**

    For N rows and any valid ``page``/``page_size``: ``total == N``, ``page`` and ``page_size`` are
    echoed, ``items`` has ``max(0, min(page_size, N - (page-1)*page_size))`` entries, and
    concatenating every page yields each row exactly once in the endpoint's (name, id) order.
    """
    n = len(names)
    last_page = max(1, -(-n // page_size))
    page = data.draw(st.integers(1, last_page + 3), label="page")
    with _seeded(db_example, client, names) as expected:
        res = _get(client, page=page, page_size=page_size)
        assert res.status_code == 200, res.text
        body = res.json()
        assert set(body) == {"items", "total", "page", "page_size"}
        assert body["total"] == n
        assert body["page"] == page
        assert body["page_size"] == page_size
        assert len(body["items"]) == max(0, min(page_size, n - (page - 1) * page_size))

        collected: list[int] = []
        for number in range(1, last_page + 1):
            body = _get(client, page=number, page_size=page_size).json()
            assert body["total"] == n
            collected.extend(item["id"] for item in body["items"])
        assert collected == [row_id for _, row_id in expected]
        assert len(set(collected)) == n

        # The page after the last one is empty but still reports the total.
        beyond = _get(client, page=last_page + 1, page_size=page_size).json()
        assert beyond["items"] == [] and beyond["total"] == n


@given(n=st.integers(0, 25))
@SETTINGS
def test_defaults_are_page_1_size_10(client: TestClient, db_example, n: int) -> None:
    """Feature: campusbite-platform, Property 24: Pagination

    **Validates: Requirements 27.1, 27.2, 27.3**

    Without parameters the response is page 1 with ``page_size`` 10.
    """
    with _seeded(db_example, client, ["A"] * n) as expected:
        body = _get(client).json()
        assert body["page"] == 1 and body["page_size"] == 10 and body["total"] == n
        assert [item["id"] for item in body["items"]] == [row_id for _, row_id in expected][:10]


invalid_pages = st.one_of(
    st.integers(max_value=0),
    st.sampled_from(["abc", "1.5", "", "1e3", "NaN", "null", "0x10"]),
)
invalid_page_sizes = st.one_of(
    st.integers(max_value=0),
    st.integers(min_value=101),
    st.sampled_from(["abc", "10.5", "", "1e1", "NaN", "null"]),
)


@given(
    page=st.one_of(st.none(), invalid_pages),
    page_size=st.one_of(st.none(), invalid_page_sizes),
    valid_page=st.integers(1, 5),
    valid_size=st.integers(1, 100),
)
@example(page=0, page_size=None, valid_page=1, valid_size=10)
@example(page=-1, page_size=None, valid_page=1, valid_size=10)
@example(page=None, page_size=0, valid_page=1, valid_size=10)
@example(page=None, page_size=101, valid_page=1, valid_size=10)
@SETTINGS
def test_invalid_params_return_422(client: TestClient, page, page_size, valid_page, valid_size) -> None:
    """Feature: campusbite-platform, Property 24: Pagination

    **Validates: Requirements 27.4**

    Any ``page`` < 1 or non-integer, or ``page_size`` outside 1-100 or non-integer, is HTTP 422.
    The other parameter may be valid or invalid; one bad parameter is enough.
    """
    if page is None and page_size is None:
        return
    params = {
        "page": valid_page if page is None else page,
        "page_size": valid_size if page_size is None else page_size,
    }
    assert _get(client, **params).status_code == 422, params


@given(names=st.lists(st.sampled_from("ABC"), max_size=3), page=st.integers(10**9, MAX_PAGE))
@example(names=["A"], page=10**12)
@example(names=[], page=MAX_PAGE)
@SETTINGS
def test_huge_page_is_an_empty_page(client: TestClient, db_example, names, page: int) -> None:
    """Feature: campusbite-platform, Property 24: Pagination

    **Validates: Requirements 27.1, 27.3**

    A page far beyond the data (up to ``MAX_PAGE``) returns no items and the correct ``total``.
    """
    with _seeded(db_example, client, names):
        res = _get(client, page=page, page_size=100)
        assert res.status_code == 200, res.text
        assert res.json() == {"items": [], "total": len(names), "page": page, "page_size": 100}


@given(page=st.one_of(st.integers(MAX_PAGE + 1, 10**40), st.integers(2**63 - 1000, 2**63 + 1000)))
@example(page=10**18)
@example(page=2**63)
@SETTINGS
def test_astronomical_page_is_rejected_not_500(client: TestClient, page: int) -> None:
    """Feature: campusbite-platform, Property 24: Pagination

    **Validates: Requirements 27.4**

    A ``page`` whose OFFSET could overflow PostgreSQL's BIGINT is rejected with 422, never 500.
    """
    assert _get(client, page=page, page_size=100).status_code == 422
