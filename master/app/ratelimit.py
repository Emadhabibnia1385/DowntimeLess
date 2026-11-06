import time
from collections import defaultdict, deque
from typing import Deque, Dict

from .errors import DLError

_hits: Dict[str, Deque[float]] = defaultdict(deque)


def hit(key: str, limit: int, window_s: int) -> None:
    now = time.time()
    q = _hits[key]
    while q and q[0] < now - window_s:
        q.popleft()
    if len(q) >= limit:
        raise DLError("rate.limited")
    q.append(now)
