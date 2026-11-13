"""Property test for duplicate email rejection (Requirement 4.5).

Each Hypothesis example runs inside its own rolled-back savepoint (``db_example``), and the
``get_db`` override is re-pointed at that example's session, so examples never see each other's
users. The override mirrors production ``get_db``: commit on success, rollback on error.
"""

from __future__ import annotations

from collections.abc import Iterator

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api import deps
from app.main import app as fastapi_app
from app.models import Restaurant, User
from app.models.enums import Role

PBT_SETTINGS = settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)

_LETTERS = "abcdefghijklmnopqrstuvwxyz"
_LOCAL_CHARS = _LETTERS + "0123456789._-"

local_parts = st.builds(
    lambda head, tail: head + tail,
    st.sampled_from(_LETTERS),
    st.text(alphabet=_LOCAL_CHARS, max_size=20).filter(lambda s: ".." not in s and not s.endswith(".")),
)
domains = st.builds(
    lambda label, tld: f"{label}.{tld}",
    st.text(alphabet=_LETTERS + "0123456789", min_size=1, max_size=12),
    st.sampled_from(["com", "org", "edu", "in"]),
)
emails = st.builds(lambda local, domain: f"{local}@{domain}", local_parts, domains)

passwords = st.text(alphabet=st.characters(min_codepoint=0x21, max_codepoint=0x7E), min_size=8, max_size=72)
names = st.text(alphabet=_LETTERS + " ", min_size=2, max_size=40).filter(lambda s: len(s.strip()) >= 2)
phones = st.from_regex(r"[0-9+\-]{7,20}", fullmatch=True)
addresses = st.none() | st.text(alphabet=_LETTERS + "0123456789 ,", max_size=100)
restaurants = st.fixed_dictionaries(
    {
        "name": st.text(alphabet=_LETTERS, min_size=2, max_size=40),
        "description": st.text(alphabet=_LETTERS, min_size=1, max_size=100),
        "cuisine": st.text(alphabet=_LETTERS, min_size=2, max_size=30),
        "address": st.text(alphabet=_LETTERS, min_size=5, max_size=100),
    }
)
whitespace = st.text(alphabet=" \t", max_size=3)


@st.composite
def registrations(draw: st.DrawFn, email: str) -> dict:
    """A valid ``RegisterIn`` payload (any role) for ``email``."""
    role = draw(st.sampled_from(list(Role)))
    payload = {
        "name": draw(names),
        "email": email,
        "password": draw(passwords),
        "phone": draw(phones),
        "role": role.value,
    }
    address = draw(addresses)
    if address is not None:
        payload["address"] = address
    if role is Role.RESTAURANT_OWNER or draw(st.booleans()):
        payload["restaurant"] = draw(restaurants)  # ignored by the API for non-owner roles
    return payload


@st.composite
def scenarios(draw: st.DrawFn) -> tuple[dict, dict]:
    """(first registration, second registration with a case/whitespace variant of the same email)."""
    email = draw(emails)
    flips = draw(st.lists(st.booleans(), min_size=len(email), max_size=len(email)))
    variant = "".join(c.swapcase() if flip else c for c, flip in zip(email, flips))
    variant = draw(whitespace) + variant + draw(whitespace)
    return draw(registrations(email)), draw(registrations(variant))


def _count(db: Session, model: type) -> int:
    return db.scalar(select(func.count()).select_from(model))


def _users_snapshot(db: Session) -> list[tuple]:
    rows = db.execute(
        select(
            User.id, User.name, User.email, User.password_hash, User.role, User.phone, User.address, User.created_at
        ).order_by(User.id)
    )
    return [tuple(row) for row in rows]


def _restaurants_snapshot(db: Session) -> list[tuple]:
    rows = db.execute(
        select(
            Restaurant.id,
            Restaurant.owner_id,
            Restaurant.name,
            Restaurant.description,
            Restaurant.cuisine,
            Restaurant.address,
        ).order_by(Restaurant.id)
    )
    return [tuple(row) for row in rows]


@given(scenario=scenarios())
@PBT_SETTINGS
def test_duplicate_email_registration_is_rejected(client, db_example, scenario: tuple[dict, dict]) -> None:
    """Feature: campusbite-platform, Property 4: Duplicate emails rejected

    **Validates: Requirements 4.5**

    For any registered email and any case or surrounding-whitespace variant of it, a second
    registration (any role) returns 409, adds no User or Restaurant, leaves the original rows and
    password hash untouched, and the original credentials still log in on the same session.
    """
    first, second = scenario
    with db_example() as db:

        def _override_get_db() -> Iterator[Session]:
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise

        fastapi_app.dependency_overrides[deps.get_db] = _override_get_db

        created = client.post("/auth/register", json=first)
        assert created.status_code == 201, created.text
        original = created.json()

        users_before = _users_snapshot(db)
        restaurants_before = _restaurants_snapshot(db)
        assert len(users_before) == 1
        assert users_before[0][2] == first["email"].lower()

        rejected = client.post("/auth/register", json=second)

        assert rejected.status_code == 409, rejected.text
        assert "detail" in rejected.json()
        assert _count(db, User) == 1
        assert _users_snapshot(db) == users_before  # includes the unchanged password hash
        assert _restaurants_snapshot(db) == restaurants_before  # no extra restaurant row

        # The session is still usable and the original account still works.
        login = client.post("/auth/login", json={"email": first["email"], "password": first["password"]})
        assert login.status_code == 200, login.text
        assert login.json()["user"] == original
