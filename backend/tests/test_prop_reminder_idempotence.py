"""Property 30: Reminder generation is idempotent.

Feature: campusbite-platform, Property 30: Reminder generation is idempotent

**Validates: Requirements 31.3**
"""

from datetime import datetime, timedelta, timezone

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import func, select

from app.models import AdminReminderLog, OrderStatus
from app.services.reminder_service import generate_reminders
from tests.factories import make_order, make_restaurant

NOW = datetime(2030, 1, 1, 12, 0, tzinfo=timezone.utc)

order_spec = st.tuples(
    st.sampled_from(list(OrderStatus)),
    st.integers(min_value=0, max_value=240),  # age in minutes
    st.integers(min_value=0, max_value=1),  # restaurant index
)


def _snapshot(db):
    rows = db.execute(select(AdminReminderLog).order_by(AdminReminderLog.id)).scalars().all()
    return [
        (r.id, r.order_id, r.status_at_reminder, r.created_at, r.message, r.is_resolved)
        for r in rows
    ]


def _pair_counts_ok(db) -> bool:
    dup = db.execute(
        select(func.count()).select_from(
            select(AdminReminderLog.order_id, AdminReminderLog.status_at_reminder)
            .group_by(AdminReminderLog.order_id, AdminReminderLog.status_at_reminder)
            .having(func.count() > 1)
            .subquery()
        )
    ).scalar_one()
    return dup == 0


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
@given(
    specs=st.lists(order_spec, min_size=1, max_size=6),
    threshold=st.integers(min_value=1, max_value=120),
    later_offsets=st.lists(st.integers(min_value=0, max_value=30), min_size=1, max_size=4),
    resolve_first=st.booleans(),
)
def test_reminder_generation_is_idempotent(db_example, specs, threshold, later_offsets, resolve_first):
    with db_example() as db:
        restaurants = [make_restaurant(db), make_restaurant(db)]
        orders = [
            make_order(
                db,
                status,
                restaurant=restaurants[ri],
                created_at=NOW - timedelta(minutes=age),
                status_updated_at=NOW - timedelta(minutes=age),
            )
            for status, age, ri in specs
        ]
        stale = {
            o.id
            for o, (status, age, _) in zip(orders, specs)
            if status in (OrderStatus.PLACED, OrderStatus.ACCEPTED) and age > threshold
        }

        first = generate_reminders(db, NOW, threshold)
        assert first == len(stale)
        if resolve_first:
            for r in db.execute(select(AdminReminderLog)).scalars():
                r.is_resolved = True
            db.flush()
        before = _snapshot(db)
        assert len(before) == first

        # Same `now`: nothing changes.
        assert generate_reminders(db, NOW, threshold) == 0
        assert _snapshot(db) == before
        # Later `now`: only orders that newly crossed the threshold get a reminder; existing
        # rows are untouched, and repeating the run at the same time inserts nothing.
        known = {r[1] for r in before}
        for offset in sorted(later_offsets):
            t = NOW + timedelta(minutes=offset)
            newly = {
                o.id
                for o, (status, age, _) in zip(orders, specs)
                if status in (OrderStatus.PLACED, OrderStatus.ACCEPTED)
                and age + offset > threshold
            } - known
            assert generate_reminders(db, t, threshold) == len(newly)
            known |= newly
            assert generate_reminders(db, t, threshold) == 0
            current = _snapshot(db)
            assert current[: len(before)] == before
            assert len(current) == len(known)
            assert _pair_counts_ok(db)
        before = _snapshot(db)

        # Status change on a stale order produces exactly one new reminder for the new pair.
        placed = [o for o in orders if o.id in stale and o.status is OrderStatus.PLACED]
        if placed:
            order = placed[0]
            order.status = OrderStatus.ACCEPTED
            order.status_updated_at = NOW + timedelta(minutes=1)
            db.flush()
            later = NOW + timedelta(minutes=threshold + 5)
            # Other still-stale orders keep their existing pairs; only the new pair is inserted.
            extra = {
                o.id
                for o, (status, age, _) in zip(orders, specs)
                if o.id != order.id
                and status in (OrderStatus.PLACED, OrderStatus.ACCEPTED)
                and age + threshold + 5 > threshold
            } - known
            assert generate_reminders(db, later, threshold) == 1 + len(extra)
            assert generate_reminders(db, later, threshold) == 0
            after = _snapshot(db)
            assert after[: len(before)] == before
            assert len(after) == len(before) + 1 + len(extra)
            new_pair = [r for r in after if (r[1], r[2]) == (order.id, OrderStatus.ACCEPTED)]
            assert len(new_pair) == 1 and new_pair[0][5] is False
            assert _pair_counts_ok(db)
