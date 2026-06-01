"""简单的内存频率限制（开发/单机够用）。"""

import time
from collections import defaultdict
from threading import Lock

_lock = Lock()
_buckets: dict[str, list[float]] = defaultdict(list)


def is_rate_limited(key: str, max_attempts: int, window_seconds: int) -> bool:
    now = time.time()
    cutoff = now - window_seconds
    with _lock:
        attempts = [t for t in _buckets[key] if t > cutoff]
        if len(attempts) >= max_attempts:
            _buckets[key] = attempts
            return True
        attempts.append(now)
        _buckets[key] = attempts
        return False


def reset_rate_limit(key: str) -> None:
    with _lock:
        _buckets.pop(key, None)
