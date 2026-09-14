"""Bounded fixed-window limiter. One process only; Store can be replaced by Redis.

Do not trust forwarded headers here. IP comes from the ASGI connection scope.
"""
import logging
import math
import threading
import time
from typing import Protocol
from fastapi import Depends, HTTPException
from app.auth.dependencies import require_permission
from app.config import settings

logger = logging.getLogger(__name__)

class Store(Protocol):
    def consume(self, key: tuple[str, str], limit: int, window: int) -> int: ...

class MemoryStore:
    def __init__(self, clock=time.monotonic, max_keys=10000):
        self.clock, self.max_keys = clock, max_keys
        self.buckets = {}
        self.lock = threading.Lock()

    def consume(self, key, limit, window):
        now = self.clock()
        with self.lock:
            # Bound memory without evicting active limits (which would permit bypass).
            if len(self.buckets) >= self.max_keys:
                self.buckets = {k: v for k, v in self.buckets.items() if v[1] > now}
            count, end = self.buckets.get(key, (0, now + window))
            if end <= now:
                count, end = 0, now + window
            if key not in self.buckets and len(self.buckets) >= self.max_keys:
                return max(1, math.ceil(min(v[1] for v in self.buckets.values()) - now))
            if count >= limit:
                return max(1, math.ceil(end - now))
            self.buckets[key] = (count + 1, end)
            return 0

store: Store = MemoryStore()

def check_limit(category: str, identity: str) -> int:
    limit = getattr(settings, "RATE_LIMIT_" + category.upper())
    retry = store.consume((category, identity), limit, 3600 if category == "train" else 60)
    if retry:
        logger.warning("Rate limit triggered category=%s", category)
    return retry

def operation(permission, category):
    def check(user=Depends(require_permission(permission))):
        retry = check_limit(category, str(user.id))
        if retry:
            raise HTTPException(429, detail="Too many requests. Please retry later.", headers={"Retry-After": str(retry)})
        return user
    return check
