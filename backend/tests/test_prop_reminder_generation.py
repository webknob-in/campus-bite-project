"""Feature: campusbite-platform, Property 29: Reminder generation matches model.

**Validates: Requirements 31.1, 31.2**
"""

from datetime import datetime, timedelta, timezone

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import select

from app.models.admin_reminder_log import AdminReminderLog
from app.models.enums import OrderStatus
from app.services.reminder_service import generate_reminders
from tests.factories import make_order, make_restaurant

NOW = datetime(2030, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
STALE = {OrderStatus.PLACED, OrderStatus.ACCEPTED}

# Offset in seconds relative to the threshold: negative = older than the threshold.
offsets = st.sampled_from([-3600, -61, -1, 0, 1, 61, 3600])
order_spec = st.tuples(st.sampled_from(list(OrderStatus)), offsets, st.integers(0, 2))


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(threshold=st.integers(1, 120), specs=st.lists(order_spec, min_size=1, max_size=8))
def test_reminder_generation_matches_model(db_example, threshold, specs):
    with db_example() as db:
        restaurants = [make_restaurant(db) for _ in range(3)]
        expected: dict[tuple[int, OrderStatus], int] = {}
        for status, offset, r_idx in specs:
            updated = NOW - timedelta(minutes=threshold) + timedelta(seconds=offset)
            order = make_order(
                db,
                status,
                restaurant=restaurants[r_idx],
                created_at=updated - timedelta(minutes=1),
                status_updated_at=updated,
            )
            if status in STALE and updated < NOW - timedelta(minutes=threshold):
                expected[(order.id, status)] = restaurants[r_idx].id
        db.flush()

        count = generate_reminders(db, NOW, threshold)
        rows = db.execute(select(AdminReminderLog)).scalars().all()

        assert count == len(expected) == len(rows)
        assert {(r.order_id, r.status_at_reminder): r.restaurant_id for r in rows} == expected
        for r in rows:
            assert r.is_resolved is False
            assert f"#{r.order_id}" in r.message
            assert r.status_at_reminder in STALE
