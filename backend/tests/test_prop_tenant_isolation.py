"""Property test for tenant isolation (Requirements 6.3, 6.4, 12.1, 12.3, 16.2, 16.7, 17.1, 21.1,
21.4, 21.8, 31.7, 45.2)."""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import patch

from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import deps
from app.main import app as fastapi_app
from app.models import (
    AdminReminderLog,
    MenuItem,
    Order,
    OrderItem,
    OrderStatus,
    PaymentLedger,
    Review,
    ReturnStatus,
)
from app.services import reminder_service
from tests.factories import (
    make_customer,
    make_menu_item,
    make_order,
    make_owner,
    make_partner,
    make_reminder,
    make_restaurant,
)

_PARTNER_STATUSES = {
    OrderStatus.ASSIGNED,
    OrderStatus.OUT_FOR_DELIVERY,
    OrderStatus.DELIVERED,
    OrderStatus.REFUNDED,
}
_ACTIVE = {OrderStatus.ASSIGNED, OrderStatus.OUT_FOR_DELIVERY}
_HISTORY = {OrderStatus.DELIVERED, OrderStatus.REFUNDED}
_TABLES = (Order, OrderItem, PaymentLedger, Review, AdminReminderLog, MenuItem)

order_specs = st.lists(
    st.fixed_dictionaries(
        {
            "customer": st.integers(0, 1),
            "restaurant": st.integers(0, 1),
            "partner": st.integers(0, 1),
            "status": st.sampled_from(list(OrderStatus)),
            "return_requested": st.booleans(),
            "reminder": st.booleans(),
        }
    ),
    min_size=2,
    max_size=12,
)


def _snapshot(db: Session) -> dict:
    db.expire_all()
    snap = {}
    for model in _TABLES:
        cols = [c.key for c in model.__mapper__.column_attrs]
        rows = db.scalars(select(model)).all()
        snap[model.__tablename__] = sorted(
            (tuple(repr(getattr(r, c)) for c in cols) for r in rows)
        )
    return snap


def _ids(res) -> set[int]:
    assert res.status_code == 200, res.text
    body = res.json()
    assert len(body["items"]) == body["total"], body  # everything fits on one page
    return {i["id"] for i in body["items"]}


@given(specs=order_specs)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
def test_tenant_isolation(client: TestClient, db_example, auth_headers, specs) -> None:
    """Feature: campusbite-platform, Property 2: Tenant isolation

    **Validates: Requirements 6.3, 6.4, 12.1, 12.3, 16.2, 16.7, 17.1, 21.1, 21.4, 21.8, 31.7, 45.2**
    """
    with db_example() as db, patch.object(reminder_service, "run_reminders_job"):

        def _get_db() -> Iterator[Session]:
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise

        fastapi_app.dependency_overrides[deps.get_db] = _get_db

        customers = [make_customer(db), make_customer(db)]
        owners = [make_owner(db), make_owner(db)]
        restaurants = [make_restaurant(db, o) for o in owners]
        partners = [make_partner(db), make_partner(db)]
        menus = [[make_menu_item(db, r), make_menu_item(db, r)] for r in restaurants]

        for s in specs:
            status = s["status"]
            rs = restaurants[s["restaurant"]]
            has_partner = status in _PARTNER_STATUSES
            return_status = (
                ReturnStatus.requested
                if status is OrderStatus.DELIVERED and s["return_requested"]
                else None
            )
            order = make_order(
                db,
                status,
                customer=customers[s["customer"]],
                restaurant=rs,
                items=[(menus[s["restaurant"]][s["partner"]], 1)],
                partner=partners[s["partner"]] if has_partner else False,
                return_status=return_status,
            )
            if s["reminder"]:
                make_reminder(db, order)
        db.commit()

        orders = list(db.scalars(select(Order)))
        reminders = list(db.scalars(select(AdminReminderLog)))
        items = list(db.scalars(select(MenuItem)))

        # ------------------------------------------------------------------ list endpoints
        for idx in (0, 1):
            h = auth_headers(customers[idx])
            got = _ids(client.get("/orders/me?page_size=100", headers=h))
            assert got == {o.id for o in orders if o.customer_id == customers[idx].id}

            h = auth_headers(owners[idx])
            rid = restaurants[idx].id
            mine = [o for o in orders if o.restaurant_id == rid]
            assert _ids(client.get("/owner/orders?page_size=100", headers=h)) == {o.id for o in mine}
            assert _ids(client.get("/owner/menu-items?page_size=100", headers=h)) == {
                i.id for i in items if i.restaurant_id == rid
            }
            assert _ids(client.get("/owner/returns?page_size=100", headers=h)) == {
                o.id for o in mine if o.return_status is not ReturnStatus.none
            }
            assert _ids(client.get("/owner/reminders?page_size=100", headers=h)) == {
                r.id for r in reminders if r.restaurant_id == rid
            }
            stats = client.get("/owner/stats", headers=h)
            assert stats.status_code == 200, stats.text
            sbody = stats.json()
            assert sbody["total_orders"] == len(mine)
            expected_counts: dict[str, int] = {}
            for o in mine:
                expected_counts[o.status.value] = expected_counts.get(o.status.value, 0) + 1
            assert {k: v for k, v in sbody["status_counts"].items() if v} == expected_counts

            h = auth_headers(partners[idx])
            pid = partners[idx].id
            assert _ids(client.get("/partner/orders?page_size=100", headers=h)) == {
                o.id for o in orders if o.delivery_partner_id == pid and o.status in _ACTIVE
            }
            assert _ids(client.get("/partner/history?page_size=100", headers=h)) == {
                o.id for o in orders if o.delivery_partner_id == pid and o.status in _HISTORY
            }

        # ------------------------------------------------- cross-tenant detail / write endpoints
        before = _snapshot(db)

        def expect_404(res) -> None:
            assert res.status_code == 404, (res.request.method, res.request.url, res.status_code, res.text)

        for idx in (0, 1):
            other = 1 - idx
            h = auth_headers(customers[idx])
            for o in (o for o in orders if o.customer_id != customers[idx].id):
                expect_404(client.get(f"/orders/{o.id}", headers=h))
                expect_404(client.post(f"/orders/{o.id}/cancel", headers=h))
                expect_404(client.post(f"/orders/{o.id}/review", json={"rating": 5}, headers=h))
                expect_404(
                    client.post(f"/orders/{o.id}/return", json={"reason": "Food was cold."}, headers=h)
                )

            h = auth_headers(owners[idx])
            rid = restaurants[idx].id
            for o in (o for o in orders if o.restaurant_id != rid):
                expect_404(client.patch(f"/owner/orders/{o.id}/status", json={"status": "ACCEPTED"}, headers=h))
                expect_404(
                    client.post(
                        f"/owner/orders/{o.id}/assign",
                        json={"delivery_partner_id": partners[idx].id},
                        headers=h,
                    )
                )
                expect_404(client.post(f"/owner/returns/{o.id}/approve", headers=h))
                expect_404(client.post(f"/owner/returns/{o.id}/reject", headers=h))
            for i in (i for i in items if i.restaurant_id != rid):
                expect_404(client.patch(f"/owner/menu-items/{i.id}", json={"name": "Hacked"}, headers=h))
                expect_404(
                    client.patch(f"/owner/menu-items/{i.id}/availability", json={"is_available": False}, headers=h)
                )
                expect_404(client.delete(f"/owner/menu-items/{i.id}", headers=h))
            for r in (r for r in reminders if r.restaurant_id != rid):
                expect_404(client.patch(f"/owner/reminders/{r.id}/resolve", headers=h))

            h = auth_headers(partners[idx])
            for o in (o for o in orders if o.delivery_partner_id != partners[idx].id):
                expect_404(client.get(f"/partner/orders/{o.id}", headers=h))
                expect_404(
                    client.patch(f"/partner/orders/{o.id}/status", json={"status": "OUT_FOR_DELIVERY"}, headers=h)
                )
            assert other != idx

        assert _snapshot(db) == before
