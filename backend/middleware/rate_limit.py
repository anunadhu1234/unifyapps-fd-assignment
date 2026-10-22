"""Per-IP rate limiting for the question endpoints.

Every question costs several LLM calls, so a public link needs a ceiling. This
is a sliding-window limiter kept in memory (one process — enough for a single
container deployment): N questions per minute and M per day per client IP.
It applies to every account (both test logins are public).
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from utils.config import get_settings


class SlidingWindowLimiter:
    def __init__(self):
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, per_minute: int, per_day: int) -> tuple[bool, int]:
        """Record a hit. Returns (allowed, retry_after_seconds)."""
        now = time.time()
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] < now - 86_400:
                hits.popleft()
            last_minute = sum(1 for t in hits if t > now - 60)
            if last_minute >= per_minute:
                oldest = next(t for t in hits if t > now - 60)
                return False, int(oldest + 60 - now) + 1
            if len(hits) >= per_day:
                return False, int(hits[0] + 86_400 - now) + 1
            hits.append(now)
            return True, 0


limiter = SlidingWindowLimiter()


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:  # behind the hosting platform's proxy
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(request: Request) -> None:
    s = get_settings()
    allowed, retry_after = limiter.check(client_ip(request), s.rate_limit_per_minute, s.rate_limit_per_day)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Too many questions — please wait {retry_after} seconds and try again.",
            headers={"Retry-After": str(retry_after)},
        )
