"""Unit tests for the scheduler wiring and reminder endpoints (Req 31.5-31.9)."""

from contextlib import nullcontext
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import scheduler
from app.core.config import get_settings
from app.db.base import utcnow
from app.main import create_app
from app.models.admin_reminder_log import AdminReminderLog
from app.models.enums import OrderStatus
from app.services import reminder_service
from tests.factories import make_customer, make_order, make_partner, make_reminder, make_restaurant


@pytest.fixture
def real_job(db):
    """Patch the job so the background task runs the real generation on the test session."""
    with patch.object(reminder_service, "SessionLocal", lambda: nullcontext(db)):
        yield


@pytest.fixture(autouse=True)
def _reset_scheduler():
    scheduler._scheduler = None
    yield
    scheduler._scheduler = None


def _lifespan_run(flag: bool, monkeypatch):
    monkeypatch.setenv("ENABLE_SCHEDULER", "true" if flag else "false")
    get_settings.cache_clear()
    try:
        with patch("app.scheduler.BackgroundScheduler") as cls:
            instance = MagicMock()
            cls.return_value = instance
            with TestClient(create_app()):
                started = instance.start.call_count
                built = cls.call_count
            return built, started, instance.shutdown.call_count
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()


def test_scheduler_not_built_when_disabled(monkeypatch):
    assert _lifespan_run(False, monkeypatch) == (0, 0, 0)


def test_scheduler_started_once_and_stopped_when_enabled(monkeypatch):
    assert _lifespan_run(True, monkeypatch) == (1, 1, 1)
    assert scheduler._scheduler is None


def test_interval_job_registration():
    with patch("app.scheduler.BackgroundScheduler") as cls:
        inst = cls.return_value
        scheduler.start_scheduler()
        scheduler.start_scheduler()  # idempotent
        assert cls.call_count == 1
        args, kwargs = inst.add_job.call_args
        assert args[0] is reminder_service.run_reminders_job or callable(args[0])
        assert args[1] == "interval"
        assert kwargs["seconds"] == 60
        assert kwargs["max_instances"] == 1 and kwargs["coalesce"] is True
        scheduler.stop_scheduler()
        inst.shutdown.assert_called_once()


def test_endpoints_schedule_job_once_each(client, db, auth_headers):
    r = make_restaurant(db)
    db.commit()
    h = auth_headers(r.owner)
    with patch("app.api.routers.owner_insights.reminder_service.run_reminders_job") as job:
        assert client.get("/owner/reminders", headers=h).status_code == 200
        assert job.call_count == 1
        assert client.get("/owner/stats", headers=h).status_code == 200
        assert job.call_count == 2


def test_end_to_end_stale_order_generates_reminder(client, db, auth_headers, real_job):
    r = make_restaurant(db)
    o = make_order(db, OrderStatus.PLACED, restaurant=r, status_updated_at=utcnow() - timedelta(minutes=30))
    fresh = make_order(db, OrderStatus.PLACED, restaurant=r, status_updated_at=utcnow())
    db.commit()
    h = auth_headers(r.owner)
    first = client.get("/owner/reminders", headers=h)  # triggers the job after responding
    assert first.status_code == 200 and first.json()["total"] == 0
    second = client.get("/owner/reminders", headers=h).json()
    assert second["total"] == 1
    item = second["items"][0]
    assert item["order_id"] == o.id and item["is_resolved"] is False
    assert fresh.id not in {i["order_id"] for i in second["items"]}


def test_threshold_setting_honored(client, db, auth_headers, real_job, monkeypatch):
    monkeypatch.setenv("REMINDER_THRESHOLD_MINUTES", "1")
    get_settings.cache_clear()
    try:
        assert get_settings().reminder_threshold_minutes == 1
        r = make_restaurant(db)
        make_order(db, OrderStatus.ACCEPTED, restaurant=r, status_updated_at=utcnow() - timedelta(minutes=3))
        db.commit()
        h = auth_headers(r.owner)
        client.get("/owner/reminders", headers=h)
        assert client.get("/owner/reminders", headers=h).json()["total"] == 1
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()


def test_default_threshold_not_triggered_for_3_minutes(client, db, auth_headers, real_job):
    r = make_restaurant(db)
    make_order(db, OrderStatus.ACCEPTED, restaurant=r, status_updated_at=utcnow() - timedelta(minutes=3))
    db.commit()
    h = auth_headers(r.owner)
    client.get("/owner/reminders", headers=h)
    assert client.get("/owner/reminders", headers=h).json()["total"] == 0


def test_resolve_sets_flag_and_filter(client, db, auth_headers):
    r = make_restaurant(db)
    a = make_reminder(db, make_order(db, OrderStatus.PLACED, restaurant=r))
    b = make_reminder(db, make_order(db, OrderStatus.PLACED, restaurant=r))
    db.commit()
    h = auth_headers(r.owner)
    with patch("app.api.routers.owner_insights.reminder_service.run_reminders_job"):
        res = client.patch(f"/owner/reminders/{a.id}/resolve", headers=h)
        assert res.status_code == 200 and res.json()["is_resolved"] is True
        db.refresh(a)
        assert a.is_resolved is True
        done = client.get("/owner/reminders?resolved=true", headers=h).json()
        assert [i["id"] for i in done["items"]] == [a.id]
        open_ = client.get("/owner/reminders?resolved=false", headers=h).json()
        assert [i["id"] for i in open_["items"]] == [b.id]
        assert set(open_) >= {"items", "total", "page", "page_size"}


def test_other_owner_gets_404_and_reminder_stays_open(client, db, auth_headers):
    ra, rb = make_restaurant(db), make_restaurant(db)
    rem = make_reminder(db, make_order(db, OrderStatus.PLACED, restaurant=ra))
    db.commit()
    assert client.patch(f"/owner/reminders/{rem.id}/resolve", headers=auth_headers(rb.owner)).status_code == 404
    db.refresh(rem)
    assert rem.is_resolved is False
    assert db.scalars(select(AdminReminderLog).where(AdminReminderLog.id == rem.id)).one().is_resolved is False


def test_role_and_auth_checks(client, db, auth_headers):
    cust, partner = make_customer(db), make_partner(db)
    db.commit()
    for user in (cust, partner):
        h = auth_headers(user)
        assert client.get("/owner/reminders", headers=h).status_code == 403
        assert client.patch("/owner/reminders/1/resolve", headers=h).status_code == 403
    assert client.get("/owner/reminders").status_code == 401
    assert client.patch("/owner/reminders/1/resolve").status_code == 401


@pytest.mark.parametrize("rid", ["999999999", "0", "-1", "abc", str(10**30)])
def test_unknown_or_invalid_ids_never_500(client, db, auth_headers, rid):
    r = make_restaurant(db)
    db.commit()
    res = client.patch(f"/owner/reminders/{rid}/resolve", headers=auth_headers(r.owner))
    assert res.status_code in (404, 422)


def test_run_reminders_job_swallows_exceptions():
    with patch.object(reminder_service, "SessionLocal", side_effect=RuntimeError("boom")):
        assert reminder_service.run_reminders_job() is None
    with patch.object(reminder_service, "generate_reminders", side_effect=ValueError("x")), patch.object(
        reminder_service, "SessionLocal", lambda: nullcontext(MagicMock())
    ):
        assert reminder_service.run_reminders_job() is None
