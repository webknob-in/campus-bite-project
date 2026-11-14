"""Smoke tests for reminder generation, endpoints, background trigger and scheduler (Req 31, 40.10)."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import select

from app import scheduler
from app.main import app as fastapi_app
from app.models.admin_reminder_log import AdminReminderLog
from app.models.enums import OrderStatus
from app.services import reminder_service
from app.services.reminder_service import generate_reminders
from tests.factories import make_order, make_reminder, make_restaurant

NOW = datetime(2030, 1, 1, 12, 0, tzinfo=timezone.utc)


def _ids(db):
    return {(r.order_id, r.status_at_reminder) for r in db.scalars(select(AdminReminderLog))}


def test_generation_threshold_terminal_and_restaurants(db):
    r1, r2 = make_restaurant(db), make_restaurant(db)
    old = make_order(db, OrderStatus.PLACED, restaurant=r1, status_updated_at=NOW - timedelta(minutes=20))
    old2 = make_order(db, OrderStatus.ACCEPTED, restaurant=r2, status_updated_at=NOW - timedelta(minutes=16))
    edge = make_order(db, OrderStatus.PLACED, restaurant=r1, status_updated_at=NOW - timedelta(minutes=15))
    fresh = make_order(db, OrderStatus.PLACED, restaurant=r1, status_updated_at=NOW - timedelta(minutes=5))
    done = make_order(db, OrderStatus.DELIVERED, restaurant=r1, status_updated_at=NOW - timedelta(minutes=99))
    assert generate_reminders(db, NOW, 15) == 2
    assert _ids(db) == {(old.id, OrderStatus.PLACED), (old2.id, OrderStatus.ACCEPTED)}
    assert edge.id not in {o for o, _ in _ids(db)} and fresh.id not in {o for o, _ in _ids(db)}
    assert done.id not in {o for o, _ in _ids(db)}
    row = db.scalars(select(AdminReminderLog).where(AdminReminderLog.order_id == old.id)).one()
    assert row.restaurant_id == r1.id and not row.is_resolved
    assert str(old.id) in row.message and "PLACED" in row.message and "20 minutes" in row.message


def test_generation_idempotent(db):
    make_order(db, OrderStatus.PLACED, status_updated_at=NOW - timedelta(minutes=40))
    assert generate_reminders(db, NOW, 15) == 1
    assert generate_reminders(db, NOW, 15) == 0
    assert len(_ids(db)) == 1


def _owner_setup(db):
    r = make_restaurant(db)
    db.commit()
    return r


def test_list_filter_paging_and_isolation(client, db, auth_headers):
    r = make_restaurant(db)
    other = make_restaurant(db)
    rems = [make_reminder(db, make_order(db, OrderStatus.PLACED, restaurant=r)) for _ in range(3)]
    rems[0].is_resolved = True
    make_reminder(db, make_order(db, OrderStatus.PLACED, restaurant=other))
    db.commit()
    h = auth_headers(r.owner)
    with patch.object(reminder_service, "run_reminders_job"):
        body = client.get("/owner/reminders", headers=h).json()
        assert body["total"] == 3 and body["page"] == 1
        assert [i["id"] for i in body["items"]] == sorted((x.id for x in rems), reverse=True)
        assert client.get("/owner/reminders?resolved=false", headers=h).json()["total"] == 2
        assert client.get("/owner/reminders?resolved=true", headers=h).json()["total"] == 1
        p = client.get("/owner/reminders?page=2&page_size=2", headers=h).json()
        assert len(p["items"]) == 1 and p["total"] == 3
        assert client.get("/owner/reminders?page_size=0", headers=h).status_code == 422


def test_resolve_and_404(client, db, auth_headers):
    r = make_restaurant(db)
    other = make_restaurant(db)
    mine = make_reminder(db, make_order(db, OrderStatus.PLACED, restaurant=r))
    foreign = make_reminder(db, make_order(db, OrderStatus.PLACED, restaurant=other))
    db.commit()
    h = auth_headers(r.owner)
    for _ in range(2):  # idempotent
        res = client.patch(f"/owner/reminders/{mine.id}/resolve", headers=h)
        assert res.status_code == 200 and res.json()["is_resolved"] is True
    assert client.patch(f"/owner/reminders/{foreign.id}/resolve", headers=h).status_code == 404
    assert client.patch("/owner/reminders/999999999/resolve", headers=h).status_code == 404
    assert client.patch(f"/owner/reminders/{10**30}/resolve", headers=h).status_code in (404, 422)
    db.refresh(foreign)
    assert foreign.is_resolved is False


def test_background_task_scheduled(client, db, auth_headers):
    r = make_restaurant(db)
    db.commit()
    h = auth_headers(r.owner)
    with patch.object(reminder_service, "run_reminders_job") as job:
        assert client.get("/owner/reminders", headers=h).status_code == 200
        assert job.call_count == 1
        assert client.get("/owner/stats", headers=h).status_code == 200
        assert job.call_count == 2


def test_scheduler_only_when_enabled():
    for flag, expected in ((False, 0), (True, 1)):
        with patch("app.main.get_settings", return_value=SimpleNamespace(enable_scheduler=flag)), patch(
            "app.scheduler.BackgroundScheduler"
        ) as cls:
            instance = MagicMock()
            cls.return_value = instance
            scheduler._scheduler = None
            with TestClient(fastapi_app):
                assert cls.call_count == expected
                if expected:
                    instance.start.assert_called_once()
            if expected:
                instance.shutdown.assert_called_once()
            assert scheduler._scheduler is None
