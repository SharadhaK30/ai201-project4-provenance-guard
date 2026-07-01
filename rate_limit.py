from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    remaining: int
    retry_after_seconds: int


class SlidingWindowRateLimiter:
    def __init__(self, max_requests: int = 30, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, deque[float]] = defaultdict(deque)

    def check(self, client_key: str) -> RateLimitResult:
        now = time.time()
        window_start = now - self.window_seconds
        requests = self._requests[client_key]
        while requests and requests[0] < window_start:
            requests.popleft()

        if len(requests) >= self.max_requests:
            retry_after = max(1, int(self.window_seconds - (now - requests[0])))
            return RateLimitResult(False, 0, retry_after)

        requests.append(now)
        remaining = max(0, self.max_requests - len(requests))
        return RateLimitResult(True, remaining, 0)
