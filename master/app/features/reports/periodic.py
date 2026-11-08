import json
import sqlite3
import statistics
import time
from typing import Any, Dict, List, Optional

from ...settings import get_settings
from ..issues import service as incidents_svc
from . import paths
from .common import DAY, TEHRAN_OFFSET_S, cap, clip, name_of

MAX_ROWS = 100


def _servers(db: sqlite3.Connection, ws: int) -> Dict[int, sqlite3.Row]:
    return {r["id"]: r for r in db.execute("SELECT * FROM servers WHERE workspace_id=?", (ws,))}


# ---------- incidents ----------

def incidents_report(db: sqlite3.Connection, ws: int, since: int, until: int) -> Dict[str, Any]:
    rows = db.execute(
        "SELECT * FROM incidents WHERE workspace_id=? AND opened_at<? AND (closed_at IS NULL OR closed_at>=?) ORDER BY opened_at DESC, id DESC",
        (ws, until, since),
    ).fetchall()
    opened = [r for r in rows if r["opened_at"] >= since]
    closed = [r for r in rows if r["closed_at"] is not None and r["closed_at"] < until]
    resolved_in = [r for r in closed if r["opened_at"] >= since]
    resolved_ids = {r["id"] for r in resolved_in}
    by_code: Dict[str, Dict[str, Any]] = {}
    by_server: Dict[str, Dict[str, Any]] = {}
    by_key: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        end = r["closed_at"] if r["closed_at"] is not None else until
        active = clip(r["opened_at"], end, since, until)
        code = (r["code"] or "?").split(":")[0]
        c = by_code.setdefault(code, {"code": code, "incidents": 0, "total_s": 0, "resolved": 0, "_dur": 0})
        c["incidents"] += 1 if r["opened_at"] >= since else 0
        c["total_s"] += active
        if r["id"] in resolved_ids:
            c["resolved"] += 1
            c["_dur"] += r["closed_at"] - r["opened_at"]
        label = r["server_name"] or "-"
        s = by_server.setdefault(label, {"server": label, "server_id": r["server_id"], "incidents": 0, "total_s": 0})
        s["incidents"] += 1 if r["opened_at"] >= since else 0
        s["total_s"] += active
        k = by_key.setdefault(r["key"], {"key": r["key"], "code": code, "server": label, "occurrences": 0, "total_s": 0,
                                         "severity": r["severity"], "active_now": False})
        k["occurrences"] += 1
        k["total_s"] += active
        k["active_now"] = k["active_now"] or r["closed_at"] is None
    for c in by_code.values():
        c["mttr_s"] = int(c["_dur"] / c["resolved"]) if c["resolved"] else None
        del c["_dur"]
    mttr = int(sum(r["closed_at"] - r["opened_at"] for r in resolved_in) / len(resolved_in)) if resolved_in else None
    flapping = sorted((k for k in by_key.values() if k["occurrences"] >= incidents_svc.FLAPPING_AT), key=lambda k: -k["occurrences"])
    longest = sorted(rows, key=lambda r: -clip(r["opened_at"], r["closed_at"] if r["closed_at"] is not None else until, since, until))
    codes, t1 = cap(sorted(by_code.values(), key=lambda c: (-c["incidents"], -c["total_s"])), 25)
    servers, t2 = cap(sorted(by_server.values(), key=lambda s: (-s["incidents"], -s["total_s"])), 25)
    flap, t3 = cap(flapping, 20)
    return {
        "since": since, "until": until, "retention_days": incidents_svc.KEEP_S // DAY,
        "totals": {"opened": len(opened), "closed": len(closed), "still_open": sum(1 for r in rows if r["closed_at"] is None),
                   "critical_opened": sum(1 for r in opened if r["severity"] == "critical"), "mttr_s": mttr},
        "by_code": codes, "by_server": servers, "flapping": flap,
        "longest": [
            {"server": r["server_name"], "server_id": r["server_id"], "code": r["code"], "severity": r["severity"],
             "opened_at": r["opened_at"], "closed_at": r["closed_at"], "duration_s": clip(r["opened_at"], r["closed_at"] if r["closed_at"] is not None else until, since, until)}
            for r in longest[:10]
        ],
        "truncated": t1 or t2 or t3,
    }


# ---------- availability ----------

def availability_report(db: sqlite3.Connection, ws: int, since: int, until: int) -> Dict[str, Any]:
    s = get_settings()
    interval, gap = s.interval_s, s.interval_s * s.offline_after
    servers = _servers(db, ws)
    first = {r["server_id"]: r["f"] for r in db.execute(
        "SELECT m.server_id, MIN(m.ts) f FROM metrics m JOIN servers s ON s.id=m.server_id WHERE s.workspace_id=? GROUP BY m.server_id", (ws,))}
    ends = {r["server_id"]: r for r in db.execute(
        "SELECT m.server_id, COUNT(*) n, MIN(m.ts) lo, MAX(m.ts) hi FROM metrics m JOIN servers s ON s.id=m.server_id WHERE s.workspace_id=? AND m.ts>=? AND m.ts<? GROUP BY m.server_id", (ws, since, until))}
    gaps = {r["server_id"]: r for r in db.execute(
        "SELECT server_id, SUM(ts-prev-?) down, COUNT(*) n FROM ("
        "SELECT m.server_id, m.ts, LAG(m.ts) OVER (PARTITION BY m.server_id ORDER BY m.ts) prev FROM metrics m JOIN servers s ON s.id=m.server_id WHERE s.workspace_id=? AND m.ts>=? AND m.ts<?) "
        "WHERE prev IS NOT NULL AND ts-prev>? GROUP BY server_id", (interval, ws, since, until, gap))}
    off = db.execute(
        "SELECT server_id, opened_at, closed_at FROM incidents WHERE workspace_id=? AND code='offline' AND opened_at<? "
        "AND (closed_at IS NULL OR closed_at>=?)", (ws, until, since)).fetchall()
    out: List[Dict[str, Any]] = []
    for sid, srv in servers.items():
        if sid not in first:
            continue  # never reported: nothing to measure
        start = max(since, first[sid])
        span = until - start
        if span <= 0:
            continue
        e, g = ends.get(sid), gaps.get(sid)
        down = int(g["down"]) if g else 0
        outages = g["n"] if g else 0
        if e is None:
            down, outages = span, 1
        else:
            if e["lo"] - start > gap:
                down += e["lo"] - start - interval
                outages += 1
            if until - e["hi"] > gap:
                down += until - e["hi"] - interval
                outages += 1
        inc = [r for r in off if r["server_id"] == sid]
        inc_s = sum(clip(r["opened_at"], r["closed_at"] if r["closed_at"] is not None else until, start, until) for r in inc)
        down = min(span, max(down, inc_s))
        out.append({
            "server_id": sid, "server": name_of(srv), "role": srv["role"], "availability_pct": round((span - down) * 100.0 / span, 2),
            "down_s": down, "outages": max(outages, len(inc)), "samples": e["n"] if e else 0, "observed_s": span,
        })
    out.sort(key=lambda r: (r["availability_pct"], r["server"]))
    rows, truncated = cap(out, MAX_ROWS)
    total_span = sum(r["observed_s"] for r in out)
    fleet = round((total_span - sum(r["down_s"] for r in out)) * 100.0 / total_span, 2) if total_span else None
    return {"since": since, "until": until, "fleet_availability_pct": fleet, "servers": rows, "truncated": truncated,
            "method": "downtime = gaps between reports longer than %ds, or offline incidents if longer; counted from the server's first report" % gap}


# ---------- traffic ----------

def _bytes(db: sqlite3.Connection, ws: int, since: int, until: int) -> Dict[int, Dict[str, int]]:
    return {r["server_id"]: {"rx": r["rx"], "tx": r["tx"]} for r in db.execute(
        "SELECT m.server_id, COALESCE(SUM(m.rx_delta),0) rx, COALESCE(SUM(m.tx_delta),0) tx "
        "FROM metrics m JOIN servers s ON s.id=m.server_id WHERE s.workspace_id=? AND m.ts>=? AND m.ts<? GROUP BY m.server_id", (ws, since, until))}


def fleet_bytes(db: sqlite3.Connection, ws: int, since: int, until: int) -> Dict[str, Any]:
    """NIC bytes in a window, summed over the fleet and split by server role (a relay's NIC sees each user byte twice)."""
    servers = _servers(db, ws)
    out = {"rx": 0, "tx": 0, "total": 0, "relay": 0, "exit": 0, "other": 0}
    for sid, b in _bytes(db, ws, since, until).items():
        role = servers[sid]["role"] if sid in servers else "other"
        out["rx"] += b["rx"]
        out["tx"] += b["tx"]
        out["total"] += b["rx"] + b["tx"]
        out[role if role in ("relay", "exit") else "other"] += b["rx"] + b["tx"]
    return out


def server_bytes(db: sqlite3.Connection, ws: int, since: int, until: int, limit: int) -> List[Dict[str, Any]]:
    servers = _servers(db, ws)
    rows = [
        {"server_id": sid, "server": name_of(servers[sid]), "role": servers[sid]["role"], "rx": b["rx"], "tx": b["tx"], "total": b["rx"] + b["tx"]}
        for sid, b in _bytes(db, ws, since, until).items() if sid in servers
    ]
    rows.sort(key=lambda r: -r["total"])
    return rows[:limit]


def link_pairs(db: sqlite3.Connection, ws: int, since: int, until: int, limit: int) -> List[Dict[str, Any]]:
    rows = db.execute(
        "SELECT COALESCE(NULLIF(s.alias,''), s.name) AS server, s.role AS server_role, l.peer_ip, "
        "COALESCE(NULLIF(p.alias,''), p.name) AS peer, SUM(l.in_bytes) AS in_bytes, SUM(l.out_bytes) AS out_bytes "
        "FROM link_traffic l JOIN servers s ON s.id=l.server_id LEFT JOIN servers p ON p.public_ip=l.peer_ip AND p.workspace_id=s.workspace_id "
        "WHERE s.workspace_id=? AND l.hour>=? AND l.hour<? GROUP BY l.server_id, l.peer_ip ORDER BY SUM(l.in_bytes)+SUM(l.out_bytes) DESC LIMIT ?",
        (ws, since - since % 3600, until, limit),
    ).fetchall()
    return [{"server": r["server"], "server_role": r["server_role"], "peer": r["peer"] or r["peer_ip"], "in_bytes": r["in_bytes"], "out_bytes": r["out_bytes"]} for r in rows]


def traffic_report(db: sqlite3.Connection, ws: int, since: int, until: int) -> Dict[str, Any]:
    total = fleet_bytes(db, ws, since, until)
    daily = db.execute(
        "SELECT (m.ts+?)/? AS d, SUM(m.rx_delta) rx, SUM(m.tx_delta) tx FROM metrics m JOIN servers s ON s.id=m.server_id WHERE s.workspace_id=? AND m.ts>=? AND m.ts<? GROUP BY d ORDER BY d",
        (TEHRAN_OFFSET_S, DAY, ws, since, until),
    ).fetchall()
    days = [{"day_start": r["d"] * DAY - TEHRAN_OFFSET_S, "rx": r["rx"], "tx": r["tx"], "total": r["rx"] + r["tx"]} for r in daily]
    hour = db.execute(
        "SELECT (m.ts/3600)*3600 AS h, SUM(m.rx_delta+m.tx_delta) b FROM metrics m JOIN servers s ON s.id=m.server_id WHERE s.workspace_id=? AND m.ts>=? AND m.ts<? GROUP BY h ORDER BY b DESC LIMIT 1",
        (ws, since, until)).fetchone()
    peak_day = max(days, key=lambda d: d["total"]) if days else None
    series, truncated = cap(days, 120)
    return {
        "since": since, "until": until, "fleet": total,
        "servers": server_bytes(db, ws, since, until, 30), "daily": series,
        "peak_day": {"day_start": peak_day["day_start"], "bytes": peak_day["total"]} if peak_day else None,
        "peak_hour": {"hour_start": hour["h"], "bytes": hour["b"]} if hour else None,
        "link_pairs": link_pairs(db, ws, since, until, 20), "truncated": truncated,
        "note": "NIC bytes (rx+tx); a relay's NIC carries each user byte twice. Days are Tehran days (UTC+3:30). Metrics are kept 90 days.",
    }


def pct_change(cur: float, prev: float) -> Optional[float]:
    return round((cur - prev) * 100.0 / prev, 1) if prev else None


# ---------- capacity ----------

def capacity_report(db: sqlite3.Connection, ws: int, since: int, until: int) -> Dict[str, Any]:
    servers = _servers(db, ws)
    hourly: Dict[int, List[sqlite3.Row]] = {}
    for r in db.execute(
        "SELECT m.server_id, (m.ts/3600)*3600 AS h, AVG(m.cpu) cpu, AVG(m.steal) steal, AVG(m.load1) load1, AVG(m.conntrack) ct, "
        "AVG(m.ram_pct) ram FROM metrics m JOIN servers s ON s.id=m.server_id WHERE s.workspace_id=? AND m.ts>=? AND m.ts<? GROUP BY m.server_id, h", (ws, since, until)):
        hourly.setdefault(r["server_id"], []).append(r)
    span = until - since
    now_b, prev_b = _bytes(db, ws, since, until), _bytes(db, ws, since - span, since)
    prev_cpu, cur_cpu = ({r["server_id"]: r["c"] for r in db.execute(
        "SELECT m.server_id, AVG(m.cpu) c FROM metrics m JOIN servers s ON s.id=m.server_id "
        "WHERE s.workspace_id=? AND m.ts>=? AND m.ts<? GROUP BY m.server_id", (ws, lo, hi))}
        for lo, hi in ((since - span, since), (since, until)))
    items = []
    for sid, rows in hourly.items():
        srv = servers.get(sid)
        if not srv:
            continue
        best = max(rows, key=lambda r: r["cpu"] if r["cpu"] is not None else -1)
        mx = lambda k: max((r[k] for r in rows if r[k] is not None), default=None)  # noqa: E731
        rep = json.loads(srv["last_report"]) if srv["last_report"] else {}
        cores = rep.get("cpu_cores")
        load = mx("load1")
        cur, prev = sum(now_b.get(sid, {"rx": 0, "tx": 0}).values()), sum(prev_b.get(sid, {"rx": 0, "tx": 0}).values())
        items.append({
            "server_id": sid, "server": name_of(srv), "role": srv["role"], "category_id": srv["category_id"], "cores": cores,
            "peak_hour": best["h"], "cpu_peak": round(best["cpu"], 1) if best["cpu"] is not None else None,
            "steal_peak": _r(mx("steal")), "load1_peak": _r(load), "load_per_core_peak": round(load / cores, 2) if load is not None and cores else None,
            "conntrack_peak": _r(mx("ct")), "ram_peak": _r(mx("ram")),
            "traffic_bytes": cur, "traffic_growth_pct": pct_change(cur, prev),
            "cpu_growth_pct": pct_change(cur_cpu.get(sid) or 0, prev_cpu.get(sid) or 0),
            "sibling_group": None, "vs_sibling_median": None, "imbalance": False,
        })
    groups: Dict[Any, List[Dict[str, Any]]] = {}
    for it in items:
        groups.setdefault((it["category_id"], it["role"]), []).append(it)
    for (cat, role), members in groups.items():
        if len(members) < 2:
            continue
        peaks = [m["cpu_peak"] for m in members if m["cpu_peak"] is not None]
        if len(peaks) < 2:
            continue
        med = statistics.median(peaks)
        for m in members:
            if m["cpu_peak"] is None:
                continue
            m["sibling_group"] = "%s/%s" % (role, cat if cat is not None else "none")
            m["vs_sibling_median"] = round(m["cpu_peak"] - med, 1)
            m["imbalance"] = m["cpu_peak"] >= 40 and (m["cpu_peak"] - med >= 25 or m["cpu_peak"] >= 1.8 * med)
    items.sort(key=lambda i: -(i["cpu_peak"] or 0))
    rows, truncated = cap(items, MAX_ROWS)
    return {"since": since, "until": until, "servers": rows, "truncated": truncated,
            "note": "Peaks are the busiest hour's average. Siblings share category and role. Growth compares with the equal window before."}


def _r(v: Optional[float]) -> Optional[float]:
    return round(v, 1) if v is not None else None


# ---------- relays ----------

def relays_report(db: sqlite3.Connection, ws: int, since: int, until: int) -> Dict[str, Any]:
    pairs = paths.classify(db, ws)
    bytes_by = {(r["server"], r["peer"]): r for r in link_pairs(db, ws, since, until, 200)}
    for p in pairs:
        b = bytes_by.get((p["relay"], p["exit"]))
        p["in_bytes"], p["out_bytes"] = (b["in_bytes"], b["out_bytes"]) if b else (None, None)
    rows, truncated = cap(pairs, 200)
    return {
        "since": since, "until": until, "ping_window_s": 600, "pairs": rows, "truncated": truncated,
        "problems": sum(1 for p in pairs if p["verdict"] not in ("ok",)),
        "note": "Loss and RTT are ICMP averages of the last 10 minutes (6+ samples); verdicts are hypotheses to confirm with a data test and a second vantage point. Bytes need acct_on.",
    }


# ---------- daily digest ----------

def daily_report(db: sqlite3.Connection, ws: int, since: int, until: int, health_counts: Dict[str, int]) -> Dict[str, Any]:
    span = until - since
    prev_since = since - span
    cur_i, prev_i = incidents_report(db, ws, since, until), incidents_report(db, ws, prev_since, since)
    cur_t, prev_t = fleet_bytes(db, ws, since, until), fleet_bytes(db, ws, prev_since, since)
    avail = availability_report(db, ws, since, until)
    top = sorted(({"server": k["server"], "code": k["code"], "occurrences": k["occurrences"], "total_s": k["total_s"], "active_now": k["active_now"]}
                  for k in _top_keys(db, ws, since, until)), key=lambda k: (-k["occurrences"], -k["total_s"]))[:8]
    changes = db.execute(
        "SELECT ts, server_id, kind, title FROM events WHERE workspace_id=? AND ts>=? AND ts<? AND kind NOT IN ('issue_opened','issue_closed') "
        "ORDER BY ts DESC, id DESC LIMIT 20",
        (ws, since, until)).fetchall()
    names = {sid: name_of(r) for sid, r in _servers(db, ws).items()}
    worst = [a for a in avail["servers"] if a["availability_pct"] < 100][:10]
    return {
        "since": since, "until": until, "previous_since": prev_since,
        "incidents": {"opened": cur_i["totals"]["opened"], "closed": cur_i["totals"]["closed"], "critical_opened": cur_i["totals"]["critical_opened"],
                      "still_open": cur_i["totals"]["still_open"], "mttr_s": cur_i["totals"]["mttr_s"],
                      "previous_opened": prev_i["totals"]["opened"], "previous_closed": prev_i["totals"]["closed"]},
        "availability": {"fleet_pct": avail["fleet_availability_pct"], "below_100": worst},
        "traffic": {"total": cur_t["total"], "previous_total": prev_t["total"], "change_pct": pct_change(cur_t["total"], prev_t["total"]),
                    "relay": cur_t["relay"], "exit": cur_t["exit"], "other": cur_t["other"]},
        "top_issues": top, "health": health_counts,
        "changes": [{"ts": r["ts"], "server": names.get(r["server_id"]), "kind": r["kind"], "title": r["title"]} for r in changes],
    }


def _top_keys(db: sqlite3.Connection, ws: int, since: int, until: int) -> List[Dict[str, Any]]:
    rows = db.execute(
        "SELECT key, code, server_name, severity, COUNT(*) n, SUM(MIN(COALESCE(closed_at, ?), ?) - MAX(opened_at, ?)) AS t, MAX(closed_at IS NULL) AS act "
        "FROM incidents WHERE workspace_id=? AND opened_at<? AND (closed_at IS NULL OR closed_at>=?) GROUP BY key",
        (until, until, since, ws, until, since),
    ).fetchall()
    return [{"key": r["key"], "code": (r["code"] or "?").split(":")[0], "server": r["server_name"] or "-", "occurrences": r["n"], "total_s": max(0, r["t"] or 0), "active_now": bool(r["act"])} for r in rows]
