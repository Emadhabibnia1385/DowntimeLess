import sqlite3
from typing import Any, Dict, List, Optional, Tuple

HOUR, DAY = 3600, 86400
MAX_WINDOW_S = 366 * DAY
HOURLY_UP_TO_S = 8 * DAY  # longer windows are drawn per day
PRESETS = ("24h", "7d", "30d", "90d")
TZ_MIN, TZ_MAX = -720, 840
TOP_DAYS = 10


def _civil(days: int) -> Tuple[int, int, int]:
    """(year, month, day) of a day count since 1970-01-01 (proleptic Gregorian)."""
    z = days + 719468
    era = z // 146097
    doe = z - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    d = doy - (153 * mp + 2) // 5 + 1
    m = mp + 3 if mp < 10 else mp - 9
    return yoe + era * 400 + (1 if m <= 2 else 0), m, d


def local_midnight(ts: int, off: int) -> int:
    """Unix time of the start of the local day that contains `ts`, for a UTC offset in seconds."""
    return (ts + off) // DAY * DAY - off


def day_label(day_start: int, off: int) -> str:
    """ISO date of the local day that starts at `day_start`."""
    y, m, d = _civil((day_start + off) // DAY)
    return "%04d-%02d-%02d" % (y, m, d)


def preset_window(range_: str, now: int, off: int) -> Tuple[int, int]:
    """[since, until) of a rolling preset: whole hours for 24h and 7d, whole local days for 30d and 90d."""
    hour_start = (now + off) // HOUR * HOUR - off
    if range_ == "24h":
        return hour_start - 23 * HOUR, now + 1
    if range_ == "7d":
        return hour_start - 167 * HOUR, now + 1
    days = 30 if range_ == "30d" else 90
    return local_midnight(now, off) - (days - 1) * DAY, now + 1


def _pair(rx: int, tx: int) -> Dict[str, int]:
    return {"rx": rx, "tx": tx, "total": rx + tx}


def _facts(days: Dict[int, Tuple[int, int]], lo: int, hi: int, off: int) -> Dict[str, Any]:
    """Total, daily average (days with traffic only) and peak day over the local days keyed in [lo, hi)."""
    inside = {k: v for k, v in days.items() if lo <= k < hi}
    active = [k for k, v in inside.items() if v[0] + v[1] > 0]
    rx, tx = sum(v[0] for v in inside.values()), sum(v[1] for v in inside.values())
    n = len(active)
    peak = max(active, key=lambda k: (inside[k][0] + inside[k][1], k)) if active else None
    return {
        "period": _pair(rx, tx),
        "avg_per_day": _pair(rx // n, tx // n) if n else _pair(0, 0),
        "active_days": n,
        "peak_day": {"date": day_label(peak, off), **_pair(*inside[peak])} if peak is not None else None,
    }


def _day_sum(days: Dict[int, Tuple[int, int]], lo: int, hi: int) -> Dict[str, int]:
    vals = [v for k, v in days.items() if lo <= k < hi]
    return _pair(sum(v[0] for v in vals), sum(v[1] for v in vals))


def category_cond(db: sqlite3.Connection, ws: int, category: Optional[str], alias: str = "s") -> Tuple[str, List[Any]]:
    """SQL on a `servers` alias for one category of workspace `ws`: an id, 'none' for servers without one, None for all.

    A category id of another workspace (or none at all) matches nothing, never another workspace's rows."""
    if category is None or category == "":
        return "1=1", []
    if category == "none":
        return "%s.category_id IS NULL" % alias, []
    if not db.execute("SELECT 1 FROM categories WHERE id=? AND workspace_id=?", (int(category), ws)).fetchone():
        return "0=1", []
    return "%s.category_id=?" % alias, [int(category)]


def summary(db: sqlite3.Connection, ws: int, now: int, tz_offset_min: int, since: Optional[int], until: Optional[int],
            category: Optional[str] = None) -> Dict[str, Any]:
    """Whole local days: `since` is snapped back to its local midnight, and a day counts when it starts before `until`."""
    off = tz_offset_min * 60
    if since is None or until is None:
        since, until = preset_window("30d", now, off)
    lo, hi = local_midnight(since, off), until
    today = local_midnight(now, off)
    start = min(lo, today - DAY)
    per: Dict[int, Dict[int, Tuple[int, int]]] = {}
    fleet: Dict[int, Tuple[int, int]] = {}
    cond, cargs = category_cond(db, ws, category)
    rows = db.execute(
        "SELECT m.server_id, (m.ts+?)/? AS d, SUM(m.rx_delta) rx, SUM(m.tx_delta) tx FROM metrics m JOIN servers s ON s.id=m.server_id "
        "WHERE s.workspace_id=? AND m.ts>=? AND m.ts<=? AND " + cond + " GROUP BY m.server_id, d",
        [off, DAY, ws, start, now] + cargs,
    )
    for r in rows:
        key = r["d"] * DAY - off
        per.setdefault(r["server_id"], {})[key] = (r["rx"], r["tx"])
        a, b = fleet.get(key, (0, 0))
        fleet[key] = (a + r["rx"], b + r["tx"])

    def facts(days: Dict[int, Tuple[int, int]]) -> Dict[str, Any]:
        return {"today": _day_sum(days, today, today + DAY), "yesterday": _day_sum(days, today - DAY, today), **_facts(days, lo, hi, off)}

    fleet_facts = facts(fleet)
    fleet_total = fleet_facts["period"]["total"]
    servers: List[Dict[str, Any]] = []
    for s in db.execute(
        "SELECT s.id, s.name, s.alias, s.role, s.panel_only, s.country, s.category_id FROM servers s WHERE s.workspace_id=? AND " + cond
        + " ORDER BY s.role, s.name",
        [ws] + cargs,
    ):
        f = facts(per.get(s["id"], {}))
        servers.append({
            "server_id": s["id"], "name": s["name"], "alias": s["alias"],
            "role": "panel_only" if s["role"] == "panel" and s["panel_only"] else s["role"],
            "country": s["country"], "category_id": s["category_id"],
            "share_pct": round(f["period"]["total"] * 100 / fleet_total, 1) if fleet_total else 0.0, **f,
        })
    return {"generated_at": now, "tz_offset_min": tz_offset_min, "since": lo, "until": until, "fleet": fleet_facts, "servers": servers}


def series(db: sqlite3.Connection, ws: int, now: int, since: int, until: int, tz_offset_min: int, server_id: Optional[int],
           category: Optional[str] = None) -> Dict[str, Any]:
    """Hourly buckets for windows up to 8 days, daily ones beyond; the window never reaches past `now`."""
    off = tz_offset_min * 60
    end = min(until, now + 1)
    hourly = until - since <= HOURLY_UP_TO_S
    size = HOUR if hourly else DAY
    first = ((since + off) // size) * size - off
    hour_start = (now + off) // HOUR * HOUR - off
    sql = (
        "SELECT (m.ts+?)/? AS h, SUM(m.rx_delta) rx, SUM(m.tx_delta) tx FROM metrics m JOIN servers s ON s.id=m.server_id "
        "WHERE s.workspace_id=? AND m.ts>=? AND m.ts<?"
    )
    args: List[Any] = [off, HOUR, ws, first, end]
    if server_id is not None:
        sql += " AND m.server_id=?"
        args.append(server_id)
    cond, cargs = category_cond(db, ws, category)
    sql += " AND " + cond
    args += cargs
    hours = {r["h"] * HOUR - off: (r["rx"], r["tx"]) for r in db.execute(sql + " GROUP BY h", args)}  # ws: sql above joins servers by workspace_id

    # one hourly pass feeds the chart, the best days and the hour-of-day profile
    days: Dict[int, List[int]] = {}
    profile: Dict[int, List[int]] = {h: [0, 0, 0] for h in range(24)}
    running: Optional[Tuple[int, int, int]] = None
    for start, (rx, tx) in hours.items():
        d = days.setdefault(local_midnight(start, off), [0, 0])
        d[0] += rx
        d[1] += tx
        hod = ((start + off) // HOUR) % 24
        if start == hour_start:
            running = (hod, rx, tx)  # the running hour is unfinished: used only when nothing else covers that hour
            continue
        p = profile[hod]
        p[0] += rx
        p[1] += tx
        p[2] += 1
    if running and not profile[running[0]][2]:
        profile[running[0]] = [running[1], running[2], 1]

    last = max(first, ((end - 1 + off) // size) * size - off)
    if end <= first:
        points: List[Dict[str, int]] = []
    elif hourly:
        points = [{"ts": t, "rx": hours.get(t, (0, 0))[0], "tx": hours.get(t, (0, 0))[1]} for t in range(first, last + 1, HOUR)]
    else:
        points = [{"ts": t, "rx": days.get(t, [0, 0])[0], "tx": days.get(t, [0, 0])[1]} for t in range(first, last + 1, DAY)]
    best = sorted(((k, v) for k, v in days.items() if v[0] + v[1] > 0), key=lambda kv: (-(kv[1][0] + kv[1][1]), -kv[0]))[:TOP_DAYS]
    return {
        "since": first, "until": until, "server_id": server_id, "tz_offset_min": tz_offset_min, "bucket_s": size, "points": points,
        "rx_total": sum(p["rx"] for p in points), "tx_total": sum(p["tx"] for p in points),
        "top_days": [{"date": day_label(k, off), "ts": k, **_pair(v[0], v[1])} for k, v in best],
        "hour_profile": [{"hour": h, "rx": p[0] // p[2] if p[2] else 0, "tx": p[1] // p[2] if p[2] else 0} for h, p in sorted(profile.items())],
    }
