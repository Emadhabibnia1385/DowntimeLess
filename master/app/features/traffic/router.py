import sqlite3
import time
from typing import List, Optional, Tuple

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ...db import get_db
from ...deps import Actor, require
from ...errors import DLError
from . import service as svc

router = APIRouter(prefix="/traffic", tags=["traffic"])

DEFAULT_TZ_MIN = 210  # Iran, +03:30


def _now() -> int:
    return int(time.time())


def _tz(minutes: int) -> int:
    if not svc.TZ_MIN <= minutes <= svc.TZ_MAX:
        raise DLError("traffic.tz_invalid")
    return minutes


def _category(value: Optional[str]) -> Optional[str]:
    if value in (None, "", "none"):
        return value or None
    if not value.isdigit():
        raise DLError("traffic.category_invalid")
    return value


def _window(since: Optional[int], until: Optional[int]) -> Optional[Tuple[int, int]]:
    if since is None and until is None:
        return None
    if since is None or until is None or since < 0 or until <= since or until - since > svc.MAX_WINDOW_S:
        raise DLError("traffic.window_invalid")
    return since, until


class Volume(BaseModel):
    rx: int
    tx: int
    total: int


class PeakDay(Volume):
    date: str


class FleetTraffic(BaseModel):
    today: Volume
    yesterday: Volume
    period: Volume
    avg_per_day: Volume
    active_days: int
    peak_day: Optional[PeakDay]


class ServerTraffic(FleetTraffic):
    server_id: int
    name: str
    alias: Optional[str]
    role: str
    country: Optional[str]
    category_id: Optional[int]
    share_pct: float


class TrafficSummary(BaseModel):
    generated_at: int
    tz_offset_min: int
    since: int
    until: int
    fleet: FleetTraffic
    servers: List[ServerTraffic]


class TrafficPoint(BaseModel):
    ts: int
    rx: int
    tx: int


class TopDay(Volume):
    date: str
    ts: int


class HourProfile(BaseModel):
    hour: int
    rx: int
    tx: int


class TrafficSeries(BaseModel):
    since: int
    until: int
    server_id: Optional[int]
    tz_offset_min: int
    bucket_s: int
    points: List[TrafficPoint]
    rx_total: int
    tx_total: int
    top_days: List[TopDay]
    hour_profile: List[HourProfile]


@router.get("/summary", response_model=TrafficSummary, operation_id="traffic_summary")
def summary(
    since: Optional[int] = None, until: Optional[int] = None, tz_offset_min: int = DEFAULT_TZ_MIN,
    category: Optional[str] = None,
    _: Actor = Depends(require("viewer")), db: sqlite3.Connection = Depends(get_db),
):
    """Traffic per server and for the fleet (only one category when `category` is an id or 'none') over a window [since, until) in unix seconds (default: the last 30 days).

    Always today and yesterday; for the window the total, daily average, peak day and share of the fleet.
    Days are local days at the UTC offset in minutes (default +03:30) and the window is counted in whole days (at most 366).
    Download is rx (into the server), upload is tx (out of it).
    """
    window = _window(since, until)
    tz = _tz(tz_offset_min)
    return svc.summary(db, _now(), tz, *(window or (None, None)), category=_category(category))


@router.get("/series", response_model=TrafficSeries, operation_id="traffic_series")
def series(
    since: Optional[int] = None, until: Optional[int] = None, range: Optional[str] = None,
    server_id: Optional[int] = None, tz_offset_min: int = DEFAULT_TZ_MIN, category: Optional[str] = None,
    _: Actor = Depends(require("viewer")), db: sqlite3.Connection = Depends(get_db),
):
    """Traffic over time for a window [since, until) or a preset range (24h, 7d, 30d, 90d), with the busiest days and hours.

    Hourly buckets for windows up to 8 days, daily ones beyond, aligned to the UTC offset. Without server_id: the whole fleet.
    """
    tz = _tz(tz_offset_min)
    window = _window(since, until)
    if window is None:
        if range is not None and range not in svc.PRESETS:
            raise DLError("traffic.range_invalid")
        window = svc.preset_window(range or "24h", _now(), tz * 60)
    if server_id is not None and not db.execute("SELECT 1 FROM servers WHERE id=?", (server_id,)).fetchone():
        raise DLError("server.not_found")
    return svc.series(db, _now(), window[0], window[1], tz, server_id, _category(category))
