"""Feature: campusbite-platform, Property 27: AI rate limiter

**Validates: Requirements 29.8**
"""
from hypothesis import given, settings, strategies as st

from app.services.rate_limiter import SlidingWindowLimiter


@st.composite
def scenarios(draw):
    limit = draw(st.integers(1, 10))
    window = draw(st.integers(1, 120))
    n = draw(st.integers(0, 60))
    gaps = draw(st.lists(st.integers(0, max(1, window)), min_size=n, max_size=n))
    keys = draw(st.lists(st.integers(0, 2), min_size=n, max_size=n))
    t = 0
    events = []
    for g, k in zip(gaps, keys):
        t += g
        events.append((k, t))
    return limit, window, events


@settings(max_examples=200, deadline=None)
@given(scenarios())
def test_property_27_ai_rate_limiter(scenario):
    """Feature: campusbite-platform, Property 27: AI rate limiter"""
    limit, window, events = scenario
    lim = SlidingWindowLimiter(limit, float(window))
    accepted: dict[int, list[int]] = {}
    for key, t in events:
        acc = accepted.setdefault(key, [])
        in_win = [a for a in acc if t - window < a <= t]
        res = lim.check(key, float(t))
        if len(in_win) < limit:
            assert res is None
            acc.append(t)
        else:
            assert res is not None
            assert res == min(in_win) + window - t
            assert 0 < res <= window
    for acc in accepted.values():
        for t in acc:
            assert len([a for a in acc if t - window < a <= t]) <= limit
