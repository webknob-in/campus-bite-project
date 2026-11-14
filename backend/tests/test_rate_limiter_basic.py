import threading

from app.services.rate_limiter import SlidingWindowLimiter


def test_allows_n_then_blocks():
    lim = SlidingWindowLimiter(3, 60)
    assert all(lim.check("u", t) is None for t in (0, 1, 2))
    wait = lim.check("u", 3)
    assert wait is not None and 0 < wait <= 60
    assert wait == 57


def test_recovers_after_window_boundary():
    lim = SlidingWindowLimiter(1, 60)
    assert lim.check("u", 0) is None
    assert lim.check("u", 59.9) is not None
    assert lim.check("u", 60) is None


def test_keys_independent():
    lim = SlidingWindowLimiter(1, 60)
    assert lim.check("a", 0) is None
    assert lim.check("b", 0) is None
    assert lim.check("a", 1) is not None


def test_rejected_not_recorded():
    lim = SlidingWindowLimiter(1, 60)
    assert lim.check("u", 0) is None
    assert lim.check("u", 30) is not None
    assert lim.check("u", 60) is None


def test_thread_safety():
    lim = SlidingWindowLimiter(5, 60)
    results = []

    def run():
        results.append(lim.check("u", 1.0))

    ts = [threading.Thread(target=run) for _ in range(40)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert results.count(None) == 5


def test_reset_and_default_now():
    lim = SlidingWindowLimiter(1, 60)
    assert lim.check("u") is None
    assert lim.check("u") is not None
    lim.reset()
    assert lim.check("u") is None
