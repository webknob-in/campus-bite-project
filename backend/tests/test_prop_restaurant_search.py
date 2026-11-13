"""Property test for restaurant search (Requirement 8.2).

Each example creates a handful of restaurants in its own rolled-back savepoint (``db_example``),
re-points ``get_db`` at that session, calls ``GET /restaurants?search=`` and compares the returned
ids with a pure-Python model of "name or cuisine contains the search text, case-insensitively".
"""

from __future__ import annotations

from collections.abc import Iterator

from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy.orm import Session

from app.api import deps
from app.main import app as fastapi_app
from tests.factories import make_restaurant

# Alphabet: printable ASCII (letters of both cases, digits, spaces and the LIKE metacharacters
# ``%``, ``_``, ``\``) plus a few accented Latin letters. The test database uses the libc
# ``en_US.utf8`` collation, where ``ILIKE`` folds case one character at a time. For these
# characters that agrees with Python's ``str.lower()``. Special Unicode such as ``ß``, ``İ`` or
# the final sigma is deliberately left out because simple lowercasing and ILIKE may differ there.
# NUL, control characters and surrogates are excluded (PostgreSQL rejects NUL).
ALPHABET = "".join(chr(c) for c in range(0x20, 0x7F)) + "éÉàÀñÑüÜöÖçÇ"
# Weighted towards a small alphabet so that random search terms often match something.
_chars = st.one_of(
    st.sampled_from("abcAB1 %_\\éÉ"),
    st.sampled_from(ALPHABET),
)
texts = st.text(alphabet=_chars, min_size=1, max_size=25)
# Names are 1..120 characters and cuisines 1..60 in the schema; keep generated ones short.
# Leading/trailing spaces are kept in stored values (only the *search text* is trimmed).


def _recase(text: str, flags: list[bool]) -> str:
    """Upper/lowercase each character according to ``flags`` (cycled)."""
    return "".join(
        (c.upper() if flags[i % len(flags)] else c.lower()) for i, c in enumerate(text)
    )


@st.composite
def scenarios(draw: st.DrawFn) -> tuple[list[tuple[str, str]], str]:
    """A list of ``(name, cuisine)`` pairs (0..15) and a search text."""
    rows = draw(st.lists(st.tuples(texts, texts), min_size=0, max_size=15))
    kind = draw(st.sampled_from(["substring", "substring", "random", "blank"]))
    if kind == "substring" and rows:
        source = draw(st.sampled_from([value for pair in rows for value in pair]))
        start = draw(st.integers(0, len(source) - 1))
        end = draw(st.integers(start + 1, len(source)))
        flags = draw(st.lists(st.booleans(), min_size=1, max_size=6))
        term = _recase(source[start:end], flags)
        pad = draw(st.sampled_from(["", " ", "  "]))  # surrounding whitespace is trimmed
        term = pad + term + pad
    elif kind == "blank":
        term = draw(st.sampled_from(["", " ", "   "]))
    else:
        term = draw(st.text(alphabet=_chars, min_size=0, max_size=4))
    return rows, term


def _model_ids(restaurants: list[tuple[int, str, str]], term: str) -> set[int]:
    needle = term.strip().lower()
    if not needle:
        return {rid for rid, _, _ in restaurants}
    return {rid for rid, name, cuisine in restaurants if needle in name.lower() or needle in cuisine.lower()}


@given(scenario=scenarios())
@settings(
    max_examples=150,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
def test_restaurant_search_matches_model(client: TestClient, db_example, scenario) -> None:
    """Feature: campusbite-platform, Property 6: Restaurant search matches model

    **Validates: Requirements 8.2**

    ``GET /restaurants?search=`` returns exactly the restaurants whose name or cuisine contains the
    (trimmed) search text ignoring case; ``%``, ``_`` and ``\\`` match literally; a blank search
    applies no filter.
    """
    rows, term = scenario
    with db_example() as db:

        def _get_db() -> Iterator[Session]:
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise

        fastapi_app.dependency_overrides[deps.get_db] = _get_db

        created = []
        for name, cuisine in rows:
            restaurant = make_restaurant(db, name=name, cuisine=cuisine)
            created.append((restaurant.id, name, cuisine))
        expected = _model_ids(created, term)

        # Walk every page (page_size=100 is the maximum).
        returned: list[int] = []
        page = 1
        while True:
            res = client.get("/restaurants", params={"search": term, "page": page, "page_size": 100})
            assert res.status_code == 200, res.text
            body = res.json()
            returned.extend(item["id"] for item in body["items"])
            assert body["total"] == len(expected)
            if not body["items"] or len(returned) >= body["total"]:
                break
            page += 1

        assert len(returned) == len(set(returned)), "a restaurant was returned twice"
        assert set(returned) == expected
