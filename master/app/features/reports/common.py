import sqlite3
import time
from typing import Any, Iterable, List, Optional, Sequence, Tuple

from ...errors import DLError

MAX_WINDOW_S = 366 * 86400
TEHRAN_OFFSET_S = 12600  # UTC+3:30, no daylight saving: the operator's "today"
DAY = 86400


def window(since: Optional[int], until: Optional[int], default_span: int = 7 * DAY) -> Tuple[int, int]:
    now = int(time.time())
    until = until if until is not None else now
    since = since if since is not None else until - default_span
    if since < 0 or until <= since or until - since > MAX_WINDOW_S:
        raise DLError("window.invalid")
    return since, until


def check_format(fmt: str) -> str:
    if fmt not in ("json", "md"):
        raise DLError("report.param_invalid")
    return fmt


def check_detail(detail: str) -> str:
    if detail not in ("brief", "full"):
        raise DLError("report.param_invalid")
    return detail


def day_start(ts: int) -> int:
    """Midnight (Tehran) at or before ts, as a unix time."""
    return (ts + TEHRAN_OFFSET_S) // DAY * DAY - TEHRAN_OFFSET_S


def name_of(row: Any) -> str:
    return row["alias"] or row["name"]


def clip(start: int, end: int, lo: int, hi: int) -> int:
    return max(0, min(end, hi) - max(start, lo))


# ---- Markdown helpers: dense, no decoration ----

def gb(n: Optional[float]) -> str:
    if n is None:
        return "-"
    for unit, size in (("TB", 1e12), ("GB", 1e9), ("MB", 1e6)):
        if abs(n) >= size:
            return "%.1f%s" % (n / size, unit)
    return "%dB" % n


def pct(v: Optional[float]) -> str:
    return "-" if v is None else ("%.1f" % v).rstrip("0").rstrip(".") + "%"


def dur(seconds: Optional[float]) -> str:
    if seconds is None:
        return "-"
    s = int(seconds)
    if s >= 86400:
        return "%dd%dh" % (s // 86400, s % 86400 // 3600)
    if s >= 3600:
        return "%dh%dm" % (s // 3600, s % 3600 // 60)
    if s >= 60:
        return "%dm" % (s // 60)
    return "%ds" % s


def stamp(ts: Optional[int]) -> str:
    return "-" if not ts else time.strftime("%Y-%m-%d %H:%M", time.gmtime(ts))


def cell(v: Any) -> str:
    return str(v).replace("|", "/").replace("\n", " ")


def table(head: Sequence[str], rows: Iterable[Sequence[Any]]) -> str:
    lines = ["| " + " | ".join(head) + " |", "|" + "-|" * len(head)]
    lines += ["| " + " | ".join(cell(c) for c in r) + " |" for r in rows]
    return "\n".join(lines)


def kv(d: dict, skip: Sequence[str] = ()) -> str:
    """Evidence as short key=value pairs."""
    parts: List[str] = []
    for k, v in d.items():
        if k in skip or v is None:
            continue
        if isinstance(v, list):
            v = ",".join(str(x) for x in v[:6])
        parts.append("%s=%s" % (k, v))
    return " ".join(parts)


def cap(items: list, limit: int) -> Tuple[list, bool]:
    return items[:limit], len(items) > limit


def has_column(db: sqlite3.Connection, table_name: str, column: str) -> bool:
    return any(r["name"] == column for r in db.execute("PRAGMA table_info(%s)" % table_name))
