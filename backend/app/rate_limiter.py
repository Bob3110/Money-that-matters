"""
One shared rate limiter per upstream HOST, not per fetcher. Two feeds hitting
the same host (SEC EDGAR serves both Form 4 and 8-K) can each individually
stay under a per-fetcher limit while blowing past the host's actual limit
together, so the limiter key is the host, and both fetchers register against
the same instance.

Locks are created lazily, the first time a host is touched, inside whatever
event loop is running at that moment. A module-level `asyncio.Lock()` built
at import time binds to whatever loop happens to exist then (often none, or
the wrong one under a test runner / reload), and every acquire() on it later
raises -- which broad `except Exception` handling in a fetcher can silently
swallow, making the whole limiter a no-op. Instantiating inside
`get_limiter()`, called from within an async function, avoids that.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field


@dataclass
class HostLimiter:
    """Simple token-bucket-ish limiter: at most `max_requests` per
    `period_seconds`, shared across every caller that touches this host."""

    max_requests: int
    period_seconds: float
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)
    _timestamps: list[float] = field(default_factory=list, repr=False)

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            cutoff = now - self.period_seconds
            self._timestamps[:] = [t for t in self._timestamps if t > cutoff]
            if len(self._timestamps) >= self.max_requests:
                sleep_for = self._timestamps[0] + self.period_seconds - now
                if sleep_for > 0:
                    await asyncio.sleep(sleep_for)
            self._timestamps.append(time.monotonic())


class RateLimitRegistry:
    """Lazily creates and caches one HostLimiter per host. Not thread-safe
    across event loops by design -- one process, one loop, per the FastAPI
    app's async runtime."""

    def __init__(self) -> None:
        self._limiters: dict[str, HostLimiter] = {}
        self._creation_lock: asyncio.Lock | None = None

    def _get_creation_lock(self) -> asyncio.Lock:
        # Created on first use inside a running loop -- see module docstring.
        if self._creation_lock is None:
            self._creation_lock = asyncio.Lock()
        return self._creation_lock

    async def get_limiter(self, host: str, *, max_requests: int, period_seconds: float) -> HostLimiter:
        if host in self._limiters:
            return self._limiters[host]
        async with self._get_creation_lock():
            if host not in self._limiters:  # re-check inside lock
                self._limiters[host] = HostLimiter(max_requests=max_requests, period_seconds=period_seconds)
            return self._limiters[host]


# Documented per-source limits from the build spec:
#   SEC EDGAR: descriptive User-Agent required, 10 requests/second
#   GDELT:     roughly one request per 5 seconds
HOST_LIMITS: dict[str, tuple[int, float]] = {
    "www.sec.gov": (10, 1.0),
    "data.sec.gov": (10, 1.0),
    "api.gdeltproject.org": (1, 5.0),
}

registry = RateLimitRegistry()


async def throttle(host: str) -> None:
    """Call before every request to `host`. Falls back to a conservative
    default (1 req/sec) for hosts not explicitly documented above, rather
    than skipping throttling entirely."""
    max_requests, period = HOST_LIMITS.get(host, (1, 1.0))
    limiter = await registry.get_limiter(host, max_requests=max_requests, period_seconds=period)
    await limiter.acquire()
