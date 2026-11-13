"""RBAC dependencies and ownership helpers (``app.api.deps``), exercised through probe routes."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api import deps
from app.core.errors import NotFoundError, register_exception_handlers
from app.models import Order, OrderStatus, Restaurant, Role, User
from tests.factories import make_customer, make_order, make_owner, make_partner, make_restaurant


@pytest.fixture
def probe(db: Session) -> Iterator[TestClient]:
    app = FastAPI()
    register_exception_handlers(app)

    def _get_db() -> Iterator[Session]:
        yield db

    app.dependency_overrides[deps.get_db] = _get_db

    @app.get("/me")
    def me(user: User = Depends(deps.get_current_user)) -> dict:
        return {"id": user.id, "role": user.role.value}

    @app.get("/customer-only")
    def customer_only(user: User = Depends(deps.require_roles(Role.CUSTOMER))) -> dict:
        return {"id": user.id}

    @app.get("/staff")
    def staff(user: User = Depends(deps.require_roles(Role.RESTAURANT_OWNER, Role.DELIVERY_PARTNER))) -> dict:
        return {"id": user.id}

    @app.get("/my-restaurant")
    def my_restaurant(r: Restaurant = Depends(deps.get_owner_restaurant)) -> dict:
        return {"id": r.id}

    with TestClient(app) as c:
        yield c


def _assert_401(resp, detail: str) -> None:
    assert resp.status_code == 401
    assert resp.headers["www-authenticate"] == "Bearer"
    assert resp.json() == {"detail": detail}


def test_missing_header_is_401(probe: TestClient) -> None:
    _assert_401(probe.get("/me"), "Not authenticated")


def test_garbage_token_is_401(probe: TestClient) -> None:
    _assert_401(probe.get("/me", headers={"Authorization": "Bearer not-a-jwt"}), "Invalid or expired token")


def test_expired_token_is_401(db: Session, probe: TestClient, auth_headers) -> None:
    user = make_customer(db)
    headers = auth_headers(user, expires_in=timedelta(minutes=-5))
    _assert_401(probe.get("/me", headers=headers), "Invalid or expired token")


def test_foreign_secret_token_is_401(db: Session, probe: TestClient, auth_headers) -> None:
    user = make_customer(db)
    headers = auth_headers(user, secret="another-secret-that-is-at-least-32-chars!!")
    _assert_401(probe.get("/me", headers=headers), "Invalid or expired token")


def test_unknown_user_token_is_401(probe: TestClient, auth_headers) -> None:
    ghost = SimpleNamespace(id=2_000_000_000, role=Role.CUSTOMER)
    _assert_401(probe.get("/me", headers=auth_headers(ghost)), "Invalid or expired token")


def test_valid_token_returns_user(db: Session, probe: TestClient, auth_headers) -> None:
    user = make_customer(db)
    resp = probe.get("/me", headers=auth_headers(user))
    assert resp.status_code == 200
    assert resp.json() == {"id": user.id, "role": "CUSTOMER"}


def test_require_roles_allows_and_denies(db: Session, probe: TestClient, auth_headers) -> None:
    customer, owner, partner = make_customer(db), make_owner(db), make_partner(db)

    assert probe.get("/customer-only", headers=auth_headers(customer)).status_code == 200
    denied = probe.get("/customer-only", headers=auth_headers(owner))
    assert denied.status_code == 403
    assert denied.json() == {"detail": "You do not have permission for this action"}

    assert probe.get("/staff", headers=auth_headers(owner)).status_code == 200
    assert probe.get("/staff", headers=auth_headers(partner)).status_code == 200
    assert probe.get("/staff", headers=auth_headers(customer)).status_code == 403


def test_require_roles_unauthenticated_is_401_not_403(probe: TestClient) -> None:
    assert probe.get("/customer-only").status_code == 401


def test_role_is_taken_from_database_not_token(db: Session, probe: TestClient, auth_headers) -> None:
    owner = make_owner(db)
    headers = auth_headers(SimpleNamespace(id=owner.id, role=Role.CUSTOMER))  # token claims CUSTOMER
    assert probe.get("/customer-only", headers=headers).status_code == 403
    assert probe.get("/staff", headers=headers).status_code == 200


def test_get_owner_restaurant(db: Session, probe: TestClient, auth_headers) -> None:
    owner = make_owner(db)
    restaurant = make_restaurant(db, owner)
    make_restaurant(db)  # another owner's restaurant must not be returned
    resp = probe.get("/my-restaurant", headers=auth_headers(owner))
    assert resp.status_code == 200
    assert resp.json() == {"id": restaurant.id}


def test_get_owner_restaurant_without_restaurant_is_404(db: Session, probe: TestClient, auth_headers) -> None:
    resp = probe.get("/my-restaurant", headers=auth_headers(make_owner(db)))
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Restaurant not found"}


def test_get_owner_restaurant_wrong_role_is_403(db: Session, probe: TestClient, auth_headers) -> None:
    assert probe.get("/my-restaurant", headers=auth_headers(make_customer(db))).status_code == 403


@pytest.mark.parametrize("for_update", [False, True])
def test_order_helpers_enforce_tenant(db: Session, for_update: bool) -> None:
    order = make_order(db, OrderStatus.ASSIGNED)
    other_customer, other_partner = make_customer(db), make_partner(db)
    other_restaurant = make_restaurant(db)

    own = {
        deps.get_customer_order: order.customer_id,
        deps.get_restaurant_order: order.restaurant_id,
        deps.get_partner_order: order.delivery_partner_id,
    }
    foreign = {
        deps.get_customer_order: other_customer.id,
        deps.get_restaurant_order: other_restaurant.id,
        deps.get_partner_order: other_partner.id,
    }
    for helper, tenant_id in own.items():
        found = helper(db, order.id, tenant_id, for_update=for_update)
        assert isinstance(found, Order) and found.id == order.id
    for helper, tenant_id in foreign.items():
        with pytest.raises(NotFoundError) as exc:
            helper(db, order.id, tenant_id, for_update=for_update)
        assert exc.value.status_code == 404


def test_order_helpers_unknown_order_and_unassigned_partner(db: Session) -> None:
    placed = make_order(db, OrderStatus.PLACED)  # no delivery partner yet
    partner = make_partner(db)
    with pytest.raises(NotFoundError):
        deps.get_customer_order(db, 2_000_000_000, placed.customer_id)
    with pytest.raises(NotFoundError):
        deps.get_partner_order(db, placed.id, partner.id)


def test_for_update_emits_row_lock(db: Session) -> None:
    from sqlalchemy import event

    order = make_order(db)
    statements: list[str] = []

    def capture(conn, cursor, statement, *args):  # noqa: ANN001
        statements.append(statement)

    event.listen(db.get_bind(), "before_cursor_execute", capture)
    try:
        deps.get_restaurant_order(db, order.id, order.restaurant_id, for_update=True)
        deps.get_restaurant_order(db, order.id, order.restaurant_id)
    finally:
        event.remove(db.get_bind(), "before_cursor_execute", capture)

    selects = [s for s in statements if "FROM orders" in s]
    assert len(selects) == 2
    assert "FOR UPDATE" in selects[0]
    assert "FOR UPDATE" not in selects[1]
