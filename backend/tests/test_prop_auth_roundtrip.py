"""Property test for the registration and login round trip (Requirements 3.2, 4.1, 4.7, 4.8, 5.1, 5.2, 41.5).

Every example runs the whole flow through the real ``/auth`` routes against PostgreSQL. Each example
gets its own rolled-back savepoint (``db_example``), and ``get_db`` is re-pointed at that example's
session, so examples cannot see each other's rows.
"""

from __future__ import annotations

from collections.abc import Iterator

import bcrypt
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api import deps
from app.core.config import get_settings
from app.core.security import decode_access_token
from app.main import app as fastapi_app
from app.models import Restaurant, Role, User

GENERIC_401 = {"detail": "Invalid email or password"}

ALNUM = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

# --- strategies -------------------------------------------------------------------------------

_name_part = st.text(alphabet=st.characters(categories=("L",), codec="utf-8"), min_size=2, max_size=40)
names = st.one_of(
    _name_part,
    st.builds(lambda a, b: f"{a} {b}", _name_part, _name_part),
)

_local_part = st.builds(
    lambda first, rest, last: first + rest + last,
    st.sampled_from(ALNUM),
    st.text(alphabet=ALNUM + "_-", max_size=20),
    st.sampled_from(ALNUM),
)
_domain = st.builds(
    lambda label, tld: f"{label}.{tld}",
    st.text(alphabet=ALNUM, min_size=2, max_size=15),
    st.sampled_from(["com", "org", "net", "edu"]),
)
# Mixed-case address; the stored form must be the lowercase of it.
emails = st.builds(lambda local, domain: f"{local}@{domain}", _local_part, _domain).flatmap(
    lambda address: st.lists(st.booleans(), min_size=len(address), max_size=len(address)).map(
        lambda flags: "".join(c.upper() if up else c for c, up in zip(address, flags))
    )
)

# 8..72 characters and at most 72 UTF-8 bytes, so ``bcrypt.checkpw`` can be called on the raw
# bytes (bcrypt 5 raises for longer input). No control characters (NUL) and no padding whitespace.
_password_chars = st.characters(categories=("L", "N", "P", "S"), codec="utf-8")
passwords = st.text(alphabet=_password_chars, min_size=8, max_size=72).filter(lambda p: len(p.encode()) <= 72)
other_passwords = st.text(alphabet=_password_chars, min_size=1, max_size=72).filter(lambda p: len(p.encode()) <= 72)

_phone_edge = st.sampled_from("0123456789+")
phones = st.builds(
    lambda first, middle, last: first + middle + last,
    _phone_edge,
    st.text(alphabet="0123456789+- ", min_size=5, max_size=18),
    _phone_edge,
)

_plain = st.characters(categories=("L", "N"), codec="utf-8")


def _text(min_size: int, max_size: int) -> st.SearchStrategy[str]:
    return st.text(alphabet=_plain, min_size=min_size, max_size=max_size)


addresses = st.one_of(
    st.none(),
    st.text(alphabet=st.characters(categories=("L", "N", "Zs"), codec="utf-8"), max_size=300).map(str.strip),
)

restaurants = st.fixed_dictionaries(
    {
        "name": _text(2, 120),
        "description": _text(1, 1000),
        "cuisine": _text(2, 60),
        "address": _text(5, 300),
    },
    optional={"image_url": st.builds(lambda s: f"https://example.com/img/{s}.png", _text(1, 20))},
)


@st.composite
def register_payloads(draw: st.DrawFn) -> dict:
    role = draw(st.sampled_from(list(Role)))
    payload = {
        "name": draw(names),
        "email": draw(emails),
        "password": draw(passwords),
        "phone": draw(phones),
        "role": role.value,
    }
    address = draw(addresses)
    if address is not None:
        payload["address"] = address
    # Owners must send restaurant details; other roles may send them and they must be ignored.
    if role is Role.RESTAURANT_OWNER or draw(st.booleans()):
        payload["restaurant"] = draw(restaurants)
    return payload


def _recase(email: str, mode: str) -> str:
    return {"lower": email.lower(), "upper": email.upper(), "swap": email.swapcase()}[mode]


# --- the property -----------------------------------------------------------------------------


@given(
    payload=register_payloads(),
    login_case=st.sampled_from(["lower", "upper", "swap"]),
    wrong_password=other_passwords,
    unknown_local=st.text(alphabet=ALNUM, min_size=3, max_size=20),
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
def test_registration_and_login_round_trip(
    client: TestClient, db_example, payload: dict, login_case: str, wrong_password: str, unknown_local: str
) -> None:
    """Feature: campusbite-platform, Property 3: Registration and login round trip

    **Validates: Requirements 3.2, 4.1, 4.7, 4.8, 5.1, 5.2, 41.5**

    Registering returns 201 with the same name, lowercased email and Role and no ``password_hash``;
    the stored hash is a bcrypt hash of the password (and differs from it); an owner gets exactly
    one Restaurant; logging in with the password (any email case) returns a JWT whose ``sub`` and
    ``role`` match the User and which ``/auth/me`` accepts; any different password gets the same
    generic 401 as an unknown email.
    """
    password = payload["password"]
    with db_example() as db:

        def _get_db() -> Iterator[Session]:
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise

        fastapi_app.dependency_overrides[deps.get_db] = _get_db

        # Register.
        res = client.post("/auth/register", json=payload)
        assert res.status_code == 201, res.text
        body = res.json()
        assert set(body) == {"id", "name", "email", "role", "phone", "address"}
        assert "password_hash" not in body and "password" not in body
        assert body["name"] == payload["name"]
        assert body["email"] == payload["email"].lower()
        assert body["role"] == payload["role"]

        # Stored row: lowercased email, bcrypt hash that verifies and differs from the plaintext.
        user = db.scalar(select(User).where(User.id == body["id"]))
        assert user is not None
        assert user.email == payload["email"].lower()
        assert user.role is Role(payload["role"])
        assert user.password_hash != password
        assert user.password_hash.startswith(("$2a$", "$2b$", "$2y$"))
        assert bcrypt.checkpw(password.encode("utf-8"), user.password_hash.encode("utf-8"))

        # Exactly one Restaurant for an owner, none for the other roles.
        expected_restaurants = 1 if payload["role"] == Role.RESTAURANT_OWNER.value else 0
        assert db.scalar(select(func.count()).select_from(Restaurant)) == expected_restaurants
        if expected_restaurants:
            restaurant = db.scalar(select(Restaurant).where(Restaurant.owner_id == user.id))
            assert restaurant is not None
            assert restaurant.name == payload["restaurant"]["name"]
            assert restaurant.cuisine == payload["restaurant"]["cuisine"]

        # Login with the same password, email in another case.
        login_email = _recase(payload["email"], login_case)
        res = client.post("/auth/login", json={"email": login_email, "password": password})
        assert res.status_code == 200, res.text
        token = res.json()
        assert token["token_type"] == "bearer"
        assert token["user"] == body
        claims = decode_access_token(token["access_token"], get_settings())
        assert claims["sub"] == str(body["id"])
        assert claims["role"] == payload["role"]

        # The token identifies the same profile.
        res = client.get("/auth/me", headers={"Authorization": f"Bearer {token['access_token']}"})
        assert res.status_code == 200
        assert res.json() == body

        # Any different password is the generic 401, identical to the unknown-email response.
        if wrong_password.encode("utf-8") != password.encode("utf-8"):
            res = client.post("/auth/login", json={"email": payload["email"], "password": wrong_password})
            assert res.status_code == 401
            assert res.json() == GENERIC_401
            unknown = client.post(
                "/auth/login",
                json={"email": f"{unknown_local}@no-such-domain.example.com", "password": password},
            )
            assert unknown.status_code == 401
            assert unknown.json() == res.json() == GENERIC_401
