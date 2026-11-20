"""Sign-in throttling, in memory.

Behind the Vercel rewrite every request comes from Vercel's addresses, so limiting by IP would lock
everyone out together. Failures are counted per e-mail (guessing one account's password), and all
attempts against a global ceiling (spraying many accounts). The API runs as one process, so memory is
shared by every request; a restart resets the counters, which only errs toward letting people in.
"""

import threading
import time
from collections import defaultdict, deque


class SlidingWindow:
    def __init__(self, limit: int, seconds: float) -> None:
        self.limit = limit
        self.seconds = seconds
        self._hits: defaultdict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> deque[float]:
        hits = self._hits[key]
        while hits and hits[0] <= now - self.seconds:
            hits.popleft()
        return hits

    def blocked(self, key: str) -> bool:
        with self._lock:
            return len(self._prune(key, time.monotonic())) >= self.limit

    def hit(self, key: str) -> None:
        with self._lock:
            now = time.monotonic()
            self._prune(key, now).append(now)

    def clear(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._hits.clear()
            else:
                self._hits.pop(key, None)


failed_by_email = SlidingWindow(limit=5, seconds=15 * 60)
all_attempts = SlidingWindow(limit=60, seconds=60)
