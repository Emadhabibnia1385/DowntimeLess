"""What the master remembers between agent reports, written when a report arrives.

Every reader here is tolerant: a field that is missing, null or oddly shaped changes nothing, so an agent that stops
sending `checks` (an old version, a collector error) never moves a counter and never produces an alarm."""
import json
import re
import sqlite3
from typing import Any, Dict, List, Optional, Set, Tuple

from ...settings import get_settings

BASELINE_AFTER_S = 86400  # a port joins the baseline after this long seen without a gap
EPHEMERAL_UDP = 32768  # xray keeps one UDP socket per client flow up here: never part of the baseline
MAX_BASELINE = 300
RISE_WINDOW_S = 600  # restart counters are compared over this window
EVENT_KEEP_S = 1800  # a counter that rose (drops, OOM kills) stays an issue this long
ADMIN_SAMPLE_S = 300
ADMIN_KEEP_S = 7200
USAGE_KEEP_S = 8 * 86400
NODE_OK = "connected"
NODE_OFF = "disabled"


def num(value: Any) -> Optional[int]:
    """An integer from the report, or None (bools and strings are not numbers)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(value)


def dicts(value: Any) -> Optional[List[Dict[str, Any]]]:
    """A list of objects, or None when the field is not a list at all."""
    return [x for x in value if isinstance(x, dict)] if isinstance(value, list) else None


def text(value: Any, limit: int = 120) -> Optional[str]:
    return value[:limit] if isinstance(value, str) and value else None


def node_status(value: Any) -> str:
    """'NodeStatus.connected', 'Connected' and 'connected' are the same status."""
    return str(value or "").split(".")[-1].strip().lower()


def report_of(row: sqlite3.Row) -> Dict[str, Any]:
    try:
        rep = json.loads(row["last_report"]) if row["last_report"] else {}
    except ValueError:
        return {}
    return rep if isinstance(rep, dict) else {}


def checks_of(rep: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    c = rep.get("checks")
    return c if isinstance(c, dict) else None


def part(rep: Dict[str, Any], name: str) -> Dict[str, Any]:
    """One object block of `checks` (kernel, nft, conntrack, apt, ...), empty when missing or not an object."""
    value = (checks_of(rep) or {}).get(name)
    return value if isinstance(value, dict) else {}


def panel_of(rep: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    p = rep.get("panel")
    return p if isinstance(p, dict) else None


def listener_keys(items: Any) -> Optional[Dict[Tuple[str, int], Optional[str]]]:
    """(proto, port) -> process of the report's listeners; None when the agent did not send a list."""
    rows = dicts(items)
    if rows is None:
        return None
    out: Dict[Tuple[str, int], Optional[str]] = {}
    for x in rows:
        proto, port = x.get("proto"), num(x.get("port"))
        if proto not in ("tcp", "udp") or port is None or not 0 < port < 65536:
            continue  # port 0 is the agent's collapsed UDP summary row
        if proto == "udp" and port >= EPHEMERAL_UDP:
            continue
        out.setdefault((proto, port), text(x.get("proc"), 40))
    return out


# ---- the stored rows ----------------------------------------------------------------------------

def load(db: sqlite3.Connection, ws: int, sid: int) -> Dict[str, Any]:
    row = db.execute("SELECT data FROM check_state WHERE workspace_id=? AND server_id=?", (ws, sid)).fetchone()
    try:
        data = json.loads(row["data"]) if row else {}
    except ValueError:
        data = {}
    return data if isinstance(data, dict) else {}


def save(db: sqlite3.Connection, ws: int, sid: int, data: Dict[str, Any], now: int) -> None:
    db.execute(
        "INSERT INTO check_state (workspace_id, server_id, data, updated_at) VALUES (?,?,?,?) "
        "ON CONFLICT(server_id) DO UPDATE SET data=excluded.data, updated_at=excluded.updated_at WHERE check_state.workspace_id=excluded.workspace_id",
        (ws, sid, json.dumps(data, separators=(",", ":")), now),
    )


def baseline(db: sqlite3.Connection, ws: int, sid: int) -> List[sqlite3.Row]:
    return db.execute(
        "SELECT proto, port, proc, first_seen, last_seen, missing FROM listener_baseline WHERE workspace_id=? AND server_id=? ORDER BY port, proto",
        (ws, sid),
    ).fetchall()


def in_baseline(row: Any) -> bool:
    return row["last_seen"] - row["first_seen"] >= BASELINE_AFTER_S


def ignored(db: sqlite3.Connection, ws: int, sid: int) -> Dict[str, Set[str]]:
    out: Dict[str, Set[str]] = {"container": set(), "node": set(), "inbound": set()}
    for r in db.execute("SELECT kind, name FROM check_ignores WHERE workspace_id=? AND server_id=?", (ws, sid)):
        out.setdefault(r["kind"], set()).add(r["name"])
    return out


# ---- report time --------------------------------------------------------------------------------

def _fresh(server: sqlite3.Row, old: Dict[str, Any], rep: Dict[str, Any], now: int) -> bool:
    """The agent (or the host) started again, or was silent: listeners get one report more before they count."""
    if checks_of(old) is None or not server["last_seen"]:
        return True
    if now - server["last_seen"] > 3 * get_settings().interval_s:
        return True
    if old.get("agent_version") != rep.get("agent_version"):
        return True
    up_old, up_new = num(old.get("uptime_s")), num(rep.get("uptime_s"))
    if up_old is not None and up_new is not None and up_new < up_old:
        return True
    boot_old, boot_new = part(old, "kernel").get("boot_id"), part(rep, "kernel").get("boot_id")
    return bool(boot_old and boot_new and boot_old != boot_new)


def _rise(hist: List[List[int]], value: Optional[int], now: int) -> Tuple[List[List[int]], int]:
    """Keep samples of a monotonic counter inside the window; a drop (reboot, recreate) starts over."""
    if value is None:
        return [], 0
    if hist and value < hist[-1][1]:
        hist = []
    hist = [h for h in hist if isinstance(h, list) and len(h) == 2 and now - h[0] <= RISE_WINDOW_S] + [[now, value]]
    return hist, value - min(h[1] for h in hist)


def _listeners(db: sqlite3.Connection, ws: int, sid: int, items: Any, now: int) -> None:
    current = listener_keys(items)
    if current is None:
        return
    known = {(r["proto"], r["port"]): r for r in baseline(db, ws, sid)}
    for key, row in known.items():
        if key in current:
            db.execute(
                "UPDATE listener_baseline SET last_seen=?, missing=0, proc=? WHERE workspace_id=? AND server_id=? AND proto=? AND port=?",
                (now, current[key], ws, sid, key[0], key[1]),
            )
        elif in_baseline(row):
            db.execute(
                "UPDATE listener_baseline SET missing=missing+1 WHERE workspace_id=? AND server_id=? AND proto=? AND port=?",
                (ws, sid, key[0], key[1]),
            )
        else:  # not yet 24 hours without a gap: it starts over when it comes back
            db.execute("DELETE FROM listener_baseline WHERE workspace_id=? AND server_id=? AND proto=? AND port=?", (ws, sid, key[0], key[1]))
    room = MAX_BASELINE - len(known)
    for (proto, port), proc in sorted(current.items(), key=lambda kv: kv[0][1]):
        if (proto, port) in known or room <= 0:
            continue
        room -= 1
        db.execute(
            "INSERT INTO listener_baseline (workspace_id, server_id, proto, port, proc, first_seen, last_seen) VALUES (?,?,?,?,?,?,?)",
            (ws, sid, proto, port, proc, now, now),
        )


def _units(state: Dict[str, Any], items: Any, now: int) -> None:
    rows = dicts(items)
    if rows is None:
        return
    old = state.get("units") if isinstance(state.get("units"), dict) else {}
    new: Dict[str, Any] = {}
    for u in rows:
        name = text(u.get("name"), 100)
        if not name:
            continue
        prev = old.get(name) if isinstance(old.get(name), dict) else {}
        hist, rise = _rise(prev.get("hist") or [], num(u.get("restarts")), now)
        new[name] = {"hist": hist, "rise": rise}
    state["units"] = new


def _containers(state: Dict[str, Any], items: Any, uptime: Optional[int], now: int) -> None:
    rows = dicts(items)
    if rows is None:
        return
    old = state.get("containers") if isinstance(state.get("containers"), dict) else {}
    new: Dict[str, Any] = {}
    for c in rows:
        name = text(c.get("name"), 128)
        if not name:
            continue
        prev = old.get(name) if isinstance(old.get(name), dict) else {}
        st = text(c.get("state"), 20) or ""
        running = st == "running"
        item = {"state": st, "down_since": prev.get("down_since"), "revived_at": prev.get("revived_at")}
        if running:
            item["down_since"] = None
            started = num(c.get("started_at"))
            # a container that was stopped before and runs again shortly after the host booted: a reboot revived it
            if (prev.get("state") and prev.get("state") != "running" and uptime is not None and uptime < 900
                    and started is not None and now - started < 600):
                item["revived_at"] = now
        elif prev.get("state") == "running" and not item["down_since"]:
            item["down_since"] = now
        item["hist"], item["rise"] = _rise(prev.get("hist") or [], num(c.get("restarts")), now)
        new[name] = item
    state["containers"] = new


def _nft(state: Dict[str, Any], nft: Any, now: int) -> None:
    if not isinstance(nft, dict):
        return
    rules = num(nft.get("dnat_rules"))
    relay_dnat = nft.get("relay_dnat")
    if rules is None and not isinstance(relay_dnat, bool):
        return
    if relay_dnat is True or (rules or 0) > 0:
        had = state.get("had_dnat") if isinstance(state.get("had_dnat"), dict) else {}
        state["had_dnat"] = {"at": now, "rules": max(rules or 0, num(had.get("rules")) or 0), "table": bool(relay_dnat) or bool(had.get("table"))}
        state["dnat_gone"] = 0
    elif state.get("had_dnat"):
        state["dnat_gone"] = (num(state.get("dnat_gone")) or 0) + 1


def _counter_events(state: Dict[str, Any], key: str, values: Dict[str, Optional[int]], now: int) -> None:
    """Remember increases of per-boot counters; a decrease means the host restarted, so it is the new start."""
    prev = state.get(key + "_prev") if isinstance(state.get(key + "_prev"), dict) else {}
    events = [e for e in state.get(key + "_events") or [] if isinstance(e, dict) and now - (num(e.get("at")) or 0) <= EVENT_KEEP_S]
    rises = {}
    for name, value in values.items():
        before = num(prev.get(name))
        if value is not None and before is not None and value > before:
            rises[name] = value - before
    if rises:
        events.append(dict(rises, at=now))
    state[key + "_prev"] = {k: v for k, v in values.items() if v is not None}
    state[key + "_events"] = events


def _kernel(state: Dict[str, Any], kernel: Any, now: int) -> None:
    if not isinstance(kernel, dict):
        return
    _counter_events(state, "oom", {"oom_kill": num(kernel.get("oom_kill"))}, now)
    synced = kernel.get("ntp_synced")
    if synced is False:
        state["ntp_false_since"] = num(state.get("ntp_false_since")) or now
    else:
        state["ntp_false_since"] = None


def _panel(db: sqlite3.Connection, ws: int, sid: int, state: Dict[str, Any], panel: Dict[str, Any], now: int) -> None:
    nodes = dicts(panel.get("nodes"))
    if nodes is not None:
        old = state.get("node_bad_since") if isinstance(state.get("node_bad_since"), dict) else {}
        bad = {}
        for n in nodes:
            nid, st = num(n.get("id")), node_status(n.get("status"))
            if nid is None or st in (NODE_OK, NODE_OFF):
                continue
            bad[str(nid)] = num(old.get(str(nid))) or now
        state["node_bad_since"] = bad
    usage = panel.get("usage") if isinstance(panel.get("usage"), dict) else None
    hour = num(usage.get("hour_start")) if usage else None
    if usage and hour is not None and hour % 3600 == 0 and abs(now - hour) <= 3 * 3600:
        known = {num(n.get("id")) for n in nodes or []} - {None}
        for start, key in ((hour, "last"), (hour - 3600, "prev")):
            rows = dicts(usage.get(key))
            if rows is None:
                continue
            got = {num(r.get("node_id")): r for r in rows if num(r.get("node_id")) is not None}
            for nid in known | set(got):
                r = got.get(nid, {})
                db.execute(
                    "INSERT INTO node_usage (workspace_id, server_id, node_id, hour, users, bytes) VALUES (?,?,?,?,?,?) "
                    "ON CONFLICT(server_id, node_id, hour) DO UPDATE SET users=excluded.users, bytes=excluded.bytes "
                    "WHERE node_usage.workspace_id=excluded.workspace_id",
                    (ws, sid, nid, start, max(0, num(r.get("users")) or 0), max(0, num(r.get("bytes")) or 0)),
                )
        db.execute("DELETE FROM node_usage WHERE workspace_id=? AND server_id=? AND hour<?", (ws, sid, now - USAGE_KEEP_S))
    admins = dicts(panel.get("admins"))
    if admins is not None:
        old = state.get("admin_used") if isinstance(state.get("admin_used"), dict) else {}
        new = {}
        for a in admins:
            name, used = text(a.get("name"), 64), num(a.get("used"))
            if not name or used is None:
                continue
            hist = [h for h in old.get(name) or [] if isinstance(h, list) and len(h) == 2 and now - h[0] <= ADMIN_KEEP_S]
            if hist and used < hist[-1][1]:
                hist = []  # usage was reset
            if not hist or now - hist[-1][0] >= ADMIN_SAMPLE_S:
                hist.append([now, used])
            else:
                hist[-1][1] = used
            new[name] = hist
        state["admin_used"] = new
    version = panel.get("version")
    if isinstance(version, str) and version:
        before = state.get("panel_version")
        if isinstance(before, str) and before and before != version:
            state["version_changed"] = {"at": now, "old": before, "new": version}
        state["panel_version"] = version


def observe(db: sqlite3.Connection, server: sqlite3.Row, rep: Dict[str, Any], now: int) -> None:
    """Fold one report into the server's memory. `server` is the row as it was before this report."""
    ws, sid = server["workspace_id"], server["id"]
    old = report_of(server)
    state = load(db, ws, sid)
    checks = checks_of(rep)
    state["since_start"] = 0 if _fresh(server, old, rep, now) else (num(state.get("since_start")) or 0) + 1
    if checks is not None:
        _listeners(db, ws, sid, checks.get("listeners"), now)
        _units(state, checks.get("units"), now)
        _containers(state, checks.get("containers"), num(rep.get("uptime_s")), now)
        _nft(state, checks.get("nft"), now)
        ct = checks.get("conntrack")
        if isinstance(ct, dict):
            _counter_events(state, "ct", {"insert_failed": num(ct.get("insert_failed")), "drop": num(ct.get("drop"))}, now)
        _kernel(state, checks.get("kernel"), now)
    panel = panel_of(rep)
    if panel is not None:
        _panel(db, ws, sid, state, panel, now)
    save(db, ws, sid, state, now)


UNIT_FAMILY = re.compile(r"^(backpack-|relay-dnat|backhaul|gre-|wattun@|panel-dnat|mobin-dnat|rathole|frp|gost)")
FORWARD_UNIT = re.compile(r"^(relay-dnat|panel-dnat|mobin-dnat)")
