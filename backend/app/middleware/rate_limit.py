"""简易内存限流器。

按 (用户或 IP, 接口标识) 在滑动时间窗内计数。
单实例部署够用；多实例部署应换 Redis，理由见 design.md。
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock

from app.core.errors import RateLimitedError


class SlidingWindowLimiter:
    """滑动窗口计数器。"""

    def __init__(self, limit: int, window_seconds: float = 60.0) -> None:
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str) -> None:
        """记录一次请求；超限则抛出 RateLimitedError。

        Raises:
            RateLimitedError: 窗口内请求数已达上限。
        """
        now = time.monotonic()
        with self._lock:
            bucket = self._hits[key]
            cutoff = now - self.window
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= self.limit:
                raise RateLimitedError()
            bucket.append(now)

    def reset(self, key: str | None = None) -> None:
        """清空计数（测试用）。"""
        with self._lock:
            if key is None:
                self._hits.clear()
            else:
                self._hits.pop(key, None)