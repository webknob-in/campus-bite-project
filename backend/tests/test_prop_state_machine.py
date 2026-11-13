"""Property test for the Order_Status state machine table.

Feature: campusbite-platform, Property 15: State machine allows exactly the defined transitions

**Validates: Requirements 13.1, 17.4, 18.2, 21.5, 21.6, 22.2, 22.3, 22.4, 22.6**

The model below is written independently of ``app.services.order_state.TRANSITIONS`` (it uses plain
strings), so a typo in the implementation table cannot hide behind the assertion.
"""

from __future__ import annotations

import itertools
from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.core.errors import InvalidTransitionError
from app.models import OrderStatus
from app.services.order_state import TERMINAL, TRANSITIONS, Actor, is_allowed, transition
from tests.factories import make_order

# Independent model of Requirement 22: (from, to) -> the one actor that may perform it.
MODEL: dict[tuple[str, str], str] = {
    ("PLACED", "CANCELLED"): "order_customer",
    ("PLACED", "ACCEPTED"): "restaurant_owner",
    ("ACCEPTED", "PREPARING"): "restaurant_owner",
    ("PREPARING", "READY"): "restaurant_owner",
    ("READY", "ASSIGNED"): "restaurant_owner",
    ("ASSIGNED", "OUT_FOR_DELIVERY"): "assigned_partner",
    ("OUT_FOR_DELIVERY", "DELIVERED"): "assigned_partner",
    ("DELIVERED", "REFUNDED"): "restaurant_owner",
}
MODEL_TERMINAL = {"CANCELLED", "REFUNDED"}

STATUSES = list(OrderStatus)
ACTORS = list(Actor)
ALL_TRIPLES = list(itertools.product(STATUSES, STATUSES, ACTORS))


def model_allows(current: OrderStatus, target: OrderStatus, actor: Actor) -> bool:
    return MODEL.get((current.name, target.name)) == actor.value


def test_model_has_eight_transitions_and_matches_enums() -> None:
    assert len(MODEL) == 8
    assert {s.name for s in OrderStatus} == {
        "PLACED", "ACCEPTED", "PREPARING", "READY", "ASSIGNED",
        "OUT_FOR_DELIVERY", "DELIVERED", "CANCELLED", "REFUNDED",
    }
    assert {a.value for a in Actor} == {"order_customer", "restaurant_owner", "assigned_partner"}
    assert len(TRANSITIONS) == 8
    assert {s.name for s in TERMINAL} == MODEL_TERMINAL


def test_is_allowed_matches_model_for_every_combination() -> None:
    """Exhaustive: 9 statuses x 9 targets x 3 actors."""
    assert len(ALL_TRIPLES) == 243
    for current, target, actor in ALL_TRIPLES:
        assert is_allowed(current, target, actor) == model_allows(current, target, actor), (
            current, target, actor,
        )
    assert sum(is_allowed(*t) for t in ALL_TRIPLES) == 8


def test_terminal_states_allow_nothing() -> None:
    for current in (OrderStatus.CANCELLED, OrderStatus.REFUNDED):
        for target, actor in itertools.product(STATUSES, ACTORS):
            assert not is_allowed(current, target, actor)


_aware_times = st.datetimes(
    min_value=datetime(2020, 1, 1),
    max_value=datetime(2035, 1, 1),
    timezones=st.just(timezone.utc),
)


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    current=st.sampled_from(STATUSES),
    target=st.sampled_from(STATUSES),
    actor=st.sampled_from(ACTORS),
    now=_aware_times,
)
def test_property_15_transition_applies_exactly_the_allowed_change(
    db_example, current: OrderStatus, target: OrderStatus, actor: Actor, now: datetime
) -> None:
    """Feature: campusbite-platform, Property 15: State machine allows exactly the defined transitions"""
    expected = model_allows(current, target, actor)
    assert is_allowed(current, target, actor) == expected

    with db_example() as db:
        old_time = now - timedelta(hours=1)
        order = make_order(db, current, created_at=old_time)
        before = {
            "status": order.status,
            "status_updated_at": order.status_updated_at,
            "updated_at": order.updated_at,
            "delivered_at": order.delivered_at,
        }

        if expected:
            result = transition(db, order, target, actor, now=now)
            assert result is order
            assert order.status == target
            assert order.status_updated_at == now
            assert order.updated_at == now
            if target is OrderStatus.DELIVERED:
                assert order.delivered_at == now
            else:
                assert order.delivered_at == before["delivered_at"]
            assert current.name not in MODEL_TERMINAL
        else:
            with pytest.raises(InvalidTransitionError):
                transition(db, order, target, actor, now=now)
            after = {
                "status": order.status,
                "status_updated_at": order.status_updated_at,
                "updated_at": order.updated_at,
                "delivered_at": order.delivered_at,
            }
            assert after == before


@pytest.mark.parametrize(
    ("current", "target", "actor"),
    [(c, t, a) for c, t, a in ALL_TRIPLES if model_allows(c, t, a)],
    ids=lambda v: getattr(v, "name", None) or getattr(v, "value", str(v)),
)
def test_each_defined_transition_is_applied(db, current, target, actor) -> None:
    """Random sampling rarely hits the 8 allowed triples out of 243, so cover each one explicitly."""
    now = datetime(2030, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    order = make_order(db, current, created_at=now - timedelta(hours=1))
    transition(db, order, target, actor, now=now)
    assert order.status == target
    assert order.status_updated_at == now
    assert order.updated_at == now
    assert (order.delivered_at == now) == (target is OrderStatus.DELIVERED)
