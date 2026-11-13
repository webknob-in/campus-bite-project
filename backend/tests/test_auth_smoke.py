"""Smoke test for ``/auth`` (task 3.2). Detailed tests live in the dedicated auth test modules."""

from sqlalchemy import func, select

from app.models import Restaurant, User

PASSWORD = "secret-pass-1"


def _customer(email: str = "Student@Example.com") -> dict:
    return {"name": "Sam Student", "email": email, "password": PASSWORD, "phone": "+91 98765 43210", "role": "CUSTOMER"}


def _owner(email: str = "owner@example.com") -> dict:
    return {
        "name": "Olive Owner",
        "email": email,
        "password": PASSWORD,
        "phone": "9876543210",
        "role": "RESTAURANT_OWNER",
        "restaurant": {
            "name": "Olive Kitchen",
            "description": "Fresh food",
            "cuisine": "Italian",
            "address": "Block A, Campus",
        },
    }


def test_register_login_me_customer(client, db):
    res = client.post("/auth/register", json=_customer())
    assert res.status_code == 201
    body = res.json()
    assert body["email"] == "student@example.com"
    assert body["role"] == "CUSTOMER"
    assert "password_hash" not in body and "password" not in body
    assert db.scalar(select(User).where(User.email == "student@example.com")).password_hash != PASSWORD

    res = client.post("/auth/login", json={"email": "STUDENT@example.com", "password": PASSWORD})
    assert res.status_code == 200
    token = res.json()
    assert token["token_type"] == "bearer"
    assert token["user"]["id"] == body["id"]

    res = client.get("/auth/me", headers={"Authorization": f"Bearer {token['access_token']}"})
    assert res.status_code == 200
    assert res.json() == body


def test_register_owner_creates_restaurant(client, db):
    res = client.post("/auth/register", json=_owner())
    assert res.status_code == 201
    restaurant = db.scalar(select(Restaurant).where(Restaurant.owner_id == res.json()["id"]))
    assert restaurant is not None and restaurant.name == "Olive Kitchen" and restaurant.is_open


def test_owner_without_restaurant_is_422_and_creates_nothing(client, db):
    payload = _owner()
    del payload["restaurant"]
    assert client.post("/auth/register", json=payload).status_code == 422
    assert db.scalar(select(func.count()).select_from(User)) == 0


def test_register_validation(client):
    assert client.post("/auth/register", json={**_customer(), "password": "short"}).status_code == 422
    assert client.post("/auth/register", json={**_customer(), "email": "not-an-email"}).status_code == 422


def test_duplicate_email_is_409_even_with_different_case(client, db):
    assert client.post("/auth/register", json=_customer("dup@example.com")).status_code == 201
    res = client.post("/auth/register", json=_customer("DUP@example.com"))
    assert res.status_code == 409
    assert "detail" in res.json()
    # The session is still usable after the failed insert.
    assert client.post("/auth/register", json=_customer("other@example.com")).status_code == 201


def test_login_failures_share_one_generic_401(client):
    client.post("/auth/register", json=_customer("real@example.com"))
    wrong_password = client.post("/auth/login", json={"email": "real@example.com", "password": "wrong-pass-1"})
    unknown_email = client.post("/auth/login", json={"email": "nobody@example.com", "password": PASSWORD})
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json() == {"detail": "Invalid email or password"}


def test_me_requires_token(client):
    assert client.get("/auth/me").status_code == 401
