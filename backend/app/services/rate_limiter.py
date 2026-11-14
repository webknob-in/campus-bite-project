"""Per-user sliding window rate limiter (Requirement 29.8)."""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_seconds: float = 60.0):
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[object, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: object, now: float | None = None) -> float | None:
        """Return None if allowed (and record), else seconds until allowed."""
        if now is None:
            now = time.monotonic()
        with self._lock:
            hits = self._hits.get(key)
            if hits is not None:
                while hits and now - hits[0] >= self.window:
                    hits.popleft()
                if not hits:
                    del self._hits[key]
                    hits = None
            if hits is not None and len(hits) >= self.limit:
                return max(hits[0] + self.window - now, 1e-9)
            if self.limit <= 0:
                return self.window
            self._hits[key].append(now)
            return None

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


_ai_limiter: SlidingWindowLimiter | None = None
_ai_lock = threading.Lock()


def get_ai_limiter() -> SlidingWindowLimiter:
    global _ai_limiter
    with _ai_lock:
        if _ai_limiter is None:
            from app.core.config import get_settings

            _ai_limiter = SlidingWindowLimiter(
                get_settings().ai_rate_limit_per_minute, 60.0
            )
        return _ai_limiter


def reset_ai_limiter() -> None:
    global _ai_limiter
    with _ai_lock:
        _ai_limiter = None
