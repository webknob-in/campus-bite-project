"""Unit tests for ``/auth`` edge cases (task 3.7).

Covers owner registration (User + Restaurant), validation failures that must create no rows,
password length boundaries, ``/auth/me`` profile shape and expired-token rejection.
Happy-path round trips live in ``test_auth_smoke.py`` and the ``test_prop_*`` modules.
"""

from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.models import Restaurant, Role, User
from tests.factories import make_customer

PASSWORD = "secret-pass-1"


def _customer(email: str = "edge-customer@example.com", **overrides) -> dict:
    payload = {
        "name": "Casey Customer",
        "email": email,
        "password": PASSWORD,
        "phone": "9876543210",
        "role": "CUSTOMER",
    }
    payload.update(overrides)
    return payload


def _restaurant(**overrides) -> dict:
    data = {
        "name": "Edge Kitchen",
        "description": "Edge-case food",
        "cuisine": "Fusion",
        "address": "Block B, Campus",
    }
    data.update(overrides)
    return data


def _owner(email: str = "edge-owner@example.com", **overrides) -> dict:
    payload = _customer(email, name="Olive Owner", role="RESTAURANT_OWNER", restaurant=_restaurant())
    payload.update(overrides)
    return payload


def _count(db, model) -> int:
    return db.scalar(select(func.count()).select_from(model))


# ------------------------------------------------------------------ owner registration (Req 4.3, 4.4)


def test_owner_registration_creates_user_and_linked_restaurant(client, db):
    res = client.post("/auth/register", json=_owner())

    assert res.status_code == 201
    body = res.json()
    assert body["role"] == "RESTAURANT_OWNER"
    assert _count(db, User) == 1
    restaurants = db.scalars(select(Restaurant)).all()
    assert len(restaurants) == 1
    restaurant = restaurants[0]
    assert restaurant.owner_id == body["id"]
    assert (restaurant.name, restaurant.cuisine, restaurant.address) == (
        "Edge Kitchen",
        "Fusion",
        "Block B, Campus",
    )
    assert restaurant.is_open is True


def test_owner_without_restaurant_is_422_and_creates_no_rows(client, db):
    payload = _owner()
    del payload["restaurant"]

    res = client.post("/auth/register", json=payload)

    assert res.status_code == 422
    assert isinstance(res.json()["detail"], list)
    assert _count(db, User) == 0
    assert _count(db, Restaurant) == 0


def test_owner_with_null_restaurant_is_422_and_creates_no_rows(client, db):
    assert client.post("/auth/register", json=_owner(restaurant=None)).status_code == 422
    assert _count(db, User) == 0
    assert _count(db, Restaurant) == 0


def test_owner_with_invalid_restaurant_is_422_and_creates_no_rows(client, db):
    res = client.post("/auth/register", json=_owner(restaurant=_restaurant(name="x")))

    assert res.status_code == 422
    assert _count(db, User) == 0
    assert _count(db, Restaurant) == 0


@pytest.mark.parametrize("role", ["CUSTOMER", "DELIVERY_PARTNER"])
def test_non_owner_with_restaurant_payload_creates_no_restaurant(client, db, role):
    res = client.post("/auth/register", json=_customer(role=role, restaurant=_restaurant()))

    assert res.status_code == 201
    assert res.json()["role"] == role
    assert _count(db, User) == 1
    assert _count(db, Restaurant) == 0


# ------------------------------------------------------------------ validation (Req 4.6, 41)


def test_short_password_is_422_and_creates_no_user(client, db):
    res = client.post("/auth/register", json=_customer(password="short"))

    assert res.status_code == 422
    assert _count(db, User) == 0


def test_bad_email_is_422_and_creates_no_user(client, db):
    res = client.post("/auth/register", json=_customer(email="not-an-email"))

    assert res.status_code == 422
    assert _count(db, User) == 0


@pytest.mark.parametrize("email", ["plainaddress", "a@", "@example.com", "a b@example.com", "a@@example.com", ""])
def test_invalid_email_formats_are_422(client, email):
    assert client.post("/auth/register", json=_customer(email=email)).status_code == 422


@pytest.mark.parametrize("length", [8, 72])
def test_password_length_boundaries_accepted(client, length):
    password = "p" * length
    email = f"len{length}@example.com"

    assert client.post("/auth/register", json=_customer(email, password=password)).status_code == 201
    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200


@pytest.mark.parametrize("length", [7, 73])
def test_password_length_boundaries_rejected(client, db, length):
    res = client.post("/auth/register", json=_customer(password="p" * length))

    assert res.status_code == 422
    assert _count(db, User) == 0


def test_multibyte_72_char_password_does_not_500(client):
    # 72 characters but 144 UTF-8 bytes: bcrypt's 72-byte limit must not surface as a 500.
    password = "é" * 72
    email = "multibyte@example.com"

    reg = client.post("/auth/register", json=_customer(email, password=password))
    assert reg.status_code == 201
    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    assert client.post("/auth/login", json={"email": email, "password": "wrong-pass-1"}).status_code == 401


def test_empty_body_is_422_with_detail_list(client, db):
    res = client.post("/auth/register", json={})

    assert res.status_code == 422
    detail = res.json()["detail"]
    assert isinstance(detail, list) and detail
    missing = {tuple(err["loc"])[-1] for err in detail}
    assert {"name", "email", "password", "phone", "role"} <= missing
    assert _count(db, User) == 0


@pytest.mark.parametrize("field", ["name", "email", "password", "phone", "role"])
def test_each_missing_required_field_is_422(client, field):
    payload = _customer()
    del payload[field]

    res = client.post("/auth/register", json=payload)

    assert res.status_code == 422
    assert isinstance(res.json()["detail"], list)


def test_unknown_role_is_422_and_creates_no_user(client, db):
    res = client.post("/auth/register", json=_customer(role="ADMIN"))

    assert res.status_code == 422
    assert isinstance(res.json()["detail"], list)
    assert _count(db, User) == 0


def test_login_missing_fields_is_422_with_detail_list(client):
    res = client.post("/auth/login", json={})

    assert res.status_code == 422
    assert isinstance(res.json()["detail"], list)


# ------------------------------------------------------------------ /auth/me (Req 4.8, 5.3)


def test_me_returns_profile_without_password_hash(client, db, auth_headers):
    user = make_customer(db, name="Pat Profile", email="pat@example.com", phone="9123456780", address="Hostel 2")

    res = client.get("/auth/me", headers=auth_headers(user))

    assert res.status_code == 200
    assert res.json() == {
        "id": user.id,
        "name": "Pat Profile",
        "email": "pat@example.com",
        "role": "CUSTOMER",
        "phone": "9123456780",
        "address": "Hostel 2",
    }
    assert "password_hash" not in res.json()
    assert "password" not in res.json()


def test_register_and_login_responses_never_expose_password_hash(client):
    reg = client.post("/auth/register", json=_customer("nohash@example.com"))
    login = client.post("/auth/login", json={"email": "nohash@example.com", "password": PASSWORD})

    assert "password_hash" not in reg.json()
    assert "password_hash" not in login.json()["user"]
    assert PASSWORD not in reg.text and PASSWORD not in login.text


# ------------------------------------------------------------------ expired token (Req 6.6)


def test_expired_token_is_401_with_bearer_challenge(client, db, auth_headers):
    user = make_customer(db)

    res = client.get("/auth/me", headers=auth_headers(user, expires_in=timedelta(minutes=-1)))

    assert res.status_code == 401
    assert res.headers["WWW-Authenticate"] == "Bearer"
    assert "detail" in res.json()


def test_unexpired_token_for_same_user_is_accepted(client, db, auth_headers):
    user = make_customer(db)

    res = client.get("/auth/me", headers=auth_headers(user, expires_in=timedelta(minutes=1)))

    assert res.status_code == 200
    assert res.json()["id"] == user.id


def test_expired_token_for_freshly_registered_owner_is_401(client, db, auth_headers):
    res = client.post("/auth/register", json=_owner("expired-owner@example.com"))
    user = db.get(User, res.json()["id"])
    assert user.role is Role.RESTAURANT_OWNER

    expired = auth_headers(user, expires_in=timedelta(minutes=-1))

    assert client.get("/auth/me", headers=expired).status_code == 401
