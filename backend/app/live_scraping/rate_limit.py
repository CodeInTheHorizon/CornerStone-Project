"""Per-host request pacing.

Each host gets at most one request per `min_interval` seconds (plus jitter so
a fleet of targets does not hit the site on an exact beat). The slot is
reserved under a lock and the wait happens outside it, so several worker
threads sharing one limiter still space their requests correctly.
"""

from __future__ import annotations

import random
import threading
import time
from collections.abc import Callable


class HostRateLimiter:
    def __init__(
        self,
        min_interval: float,
        *,
        jitter_ratio: float = 0.25,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        rng: random.Random | None = None,
    ) -> None:
        if min_interval <= 0:
            raise ValueError("min_interval must be positive")
        self._interval = min_interval
        self._jitter = jitter_ratio
        self._clock = clock
        self._sleep = sleep
        self._rng = rng or random.Random()
        self._next_allowed: dict[str, float] = {}
        self._lock = threading.Lock()

    def wait(self, host: str) -> float:
        """Block until `host` may be requested. Returns the seconds waited."""
        with self._lock:
            now = self._clock()
            start = max(now, self._next_allowed.get(host, now))
            spacing = self._interval * (1 + self._rng.uniform(0, self._jitter))
            self._next_allowed[host] = start + spacing
        delay = start - now
        if delay > 0:
            self._sleep(delay)
        return delay

    def defer(self, host: str, seconds: float) -> None:
        """Push the host's next slot at least `seconds` into the future (after a 429 or a retry)."""
        with self._lock:
            earliest = self._clock() + max(0.0, seconds)
            self._next_allowed[host] = max(self._next_allowed.get(host, 0.0), earliest)
