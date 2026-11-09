"""TCP (and TLS) probes from Iran relays to the real listening ports of the foreign servers.

ICMP is filtered or rate-limited on many paths while the data flows, and the reverse also happens, so a path verdict
needs a TCP connection to a port users really reach. The master picks the ports from each server's own listener list,
the relay's agent (0.3.2+) connects and reports, and only ports that answered at least once ("proven") decide a verdict:
a firewalled or local-only port then never looks like a blocked path.

Agent 0.3.3 relays also probe their own DNAT destinations and the forwarded ports of the other relays of their
workspace (`forwards.py` judges those); these results never enter the relay-to-exit path verdicts.
"""
import json
import re
import sqlite3
from typing import Any, Dict, List, Optional, Set, Tuple

from ..checks import memory as m

PROBE_KEEP_S = 2 * 86400
PROVEN_S = 30 * 86400
PER_SERVER = 2  # ports probed per foreign server and cycle
MAX_TARGETS = 24  # exit ports one relay probes per cycle
OWN_DNAT_MAX = 8  # the relay's own DNAT destinations per cycle
PEER_FORWARD_MAX = 8  # forwarded ports of the other relays per cycle (agent 0.3.3 takes 48 in all, 0.3.2 only 32)
ROTATE_S = 300  # unproven candidates take turns, one set per five minutes
# processes that carry user traffic; sshd and panels' admin ports are often restricted to a few addresses
DATA_PROC = re.compile(r"xray|sing-box|haproxy|nginx|caddy|hysteria|x-ui|pasarguard|marzban|backhaul|backpack|gost|realm|"
                       r"rathole|frp|docker-proxy|v2ray|trojan|tuic", re.I)
TLS_PORTS = {443, 8443, 2053, 2083, 2087, 2096}
TLS_PROC = re.compile(r"nginx|haproxy|caddy", re.I)
LOCAL_ADDR = re.compile(r"^(127\.|::1$|\[::1\]$|localhost$)")
ERRORS = ("timeout", "refused", "unreachable", "error")


def _listeners(last_report: Optional[str]) -> List[Dict[str, Any]]:
    try:
        rep = json.loads(last_report or "{}")
    except ValueError:
        return []
    checks = rep.get("checks") if isinstance(rep, dict) else None
    rows = checks.get("listeners") if isinstance(checks, dict) else None
    return [x for x in rows if isinstance(x, dict)] if isinstance(rows, list) else []


def candidates(last_report: Optional[str]) -> List[Tuple[int, bool]]:
    """(port, tls) a relay may connect to: public TCP listeners of data-plane processes, 443 first."""
    out: Dict[int, bool] = {}
    for x in _listeners(last_report):
        port, proc, addr = x.get("port"), x.get("proc"), x.get("addr")
        if x.get("proto") != "tcp" or not isinstance(port, int) or isinstance(port, bool) or not 0 < port < 65536:
            continue
        if not isinstance(proc, str) or not DATA_PROC.search(proc):
            continue
        if isinstance(addr, str) and LOCAL_ADDR.match(addr):
            continue
        out[port] = port in TLS_PORTS or bool(TLS_PROC.search(proc))
    return sorted(out.items(), key=lambda kv: (kv[0] != 443, not kv[1], kv[0]))


def _rotate(items: List[Any], cap: int, turn: int) -> List[Any]:
    if len(items) <= cap:
        return items
    start = (turn * cap) % len(items)
    return (items[start:] + items[:start])[:cap]


def _pick(items: List[Tuple[str, int]], proven: Set[Tuple[str, int]], cap: int, turn: int) -> List[Tuple[str, int]]:
    """Proven items first, then the others in turn, at most cap."""
    chosen = _rotate([i for i in items if i in proven], cap, turn)
    rest = [i for i in items if i not in proven]
    return chosen + _rotate(rest, cap - len(chosen), turn) if len(chosen) < cap else chosen


def targets_for_relay(db: sqlite3.Connection, ws: int, now: int, relay_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """The ports a relay of this workspace probes this cycle: proven ports first, then unproven ones in turn.

    With relay_id, also its own DNAT destinations and the forwarded ports of the workspace's other relays."""
    proven: Dict[str, List[int]] = {}
    for r in db.execute("SELECT target, port FROM probe_ports WHERE workspace_id=? AND last_ok>=? ORDER BY last_ok DESC",
                        (ws, now - PROVEN_S)):
        proven.setdefault(r["target"], []).append(r["port"])
    out: List[Dict[str, Any]] = []
    turn = now // ROTATE_S
    for s in db.execute("SELECT public_ip, last_report FROM servers WHERE workspace_id=? AND role<>'relay' AND public_ip IS NOT NULL "
                        "AND public_ip NOT LIKE '%:%' ORDER BY id", (ws,)):
        cands = dict(candidates(s["last_report"]))
        if not cands:
            continue
        ip = s["public_ip"]
        chosen = [p for p in proven.get(ip, []) if p in cands][:PER_SERVER]
        if not chosen:
            chosen = [next(iter(cands))]  # the likeliest data port (443, TLS) always takes one slot
        rest = [p for p in cands if p not in chosen]
        if rest and len(chosen) < PER_SERVER:
            start = turn % len(rest)
            chosen += (rest[start:] + rest[:start])[:PER_SERVER - len(chosen)]
        out += [{"target": ip, "port": p, "tls": cands[p]} for p in chosen]
    out = out[:MAX_TARGETS]
    if relay_id is None:
        return out
    seen = {(t["target"], t["port"]) for t in out}
    own: List[Tuple[str, int]] = []
    peers: List[Tuple[str, int]] = []
    for s in db.execute("SELECT id, public_ip, last_report FROM servers WHERE workspace_id=? AND role='relay' ORDER BY id", (ws,)):
        ip = s["public_ip"]
        for r in m.dnat_rules(m.report_of(s)):
            if r["proto"] != "tcp" or r["to"] == ip:
                continue
            if s["id"] == relay_id:
                own.append((r["to"], r["to_port"]))
            elif ip and ":" not in ip:
                peers.append((ip, r["port"]))  # through the peer's DNAT: completes only when its whole path works
    known = proven_ports(db, ws, now)
    for items, cap in ((own, OWN_DNAT_MAX), (peers, PEER_FORWARD_MAX)):
        items = [k for k in dict.fromkeys(items) if k not in seen]
        for target, port in _pick(items, known, cap, turn):
            seen.add((target, port))
            out.append({"target": target, "port": port, "tls": False})
    return out


def _clean(p: Any) -> Optional[Tuple[str, int, int, Optional[float], Optional[str], Optional[int]]]:
    if not isinstance(p, dict):
        return None
    target, port, ok = p.get("target"), p.get("port"), p.get("ok")
    if not isinstance(target, str) or len(target) > 64 or not isinstance(port, int) or isinstance(port, bool) or not 0 < port < 65536:
        return None
    if not isinstance(ok, bool):
        return None
    rtt = p.get("rtt_ms") if isinstance(p.get("rtt_ms"), (int, float)) and not isinstance(p.get("rtt_ms"), bool) else None
    error = None if ok else (p.get("error") if p.get("error") in ERRORS else "error")
    tls = p.get("tls")
    return target, port, int(ok), rtt if ok else None, error, (None if tls is None else int(bool(tls)))


def record(db: sqlite3.Connection, server: Any, items: Any, now: int, own_report: Optional[Dict[str, Any]] = None) -> None:
    """Store one relay's probe results; ports that answered become proven for its workspace.

    Kept: servers of its workspace and the destinations of its own DNAT rules (from `own_report`); nothing else."""
    if server["role"] != "relay" or not isinstance(items, list):
        return
    ws = server["workspace_id"]
    known: Set[str] = set()
    for r in db.execute("SELECT id, role, public_ip FROM servers WHERE workspace_id=? AND public_ip IS NOT NULL", (ws,)):
        if r["id"] != server["id"]:
            known.add(r["public_ip"])  # foreign servers, and other relays whose forwards it probes
    known |= {d["to"] for d in m.dnat_rules(own_report or {})}
    for raw in items[:(MAX_TARGETS + OWN_DNAT_MAX + PEER_FORWARD_MAX) * 2]:
        row = _clean(raw)
        if not row or row[0] not in known:
            continue
        target, port, ok, rtt, error, tls = row
        db.execute(  # ws: agent_server - the relay's own results, about servers of its own workspace
            "INSERT INTO probes (server_id, ts, target, port, ok, rtt, error, tls) VALUES (?,?,?,?,?,?,?,?)",
            (server["id"], now, target, port, ok, rtt, error, tls),
        )
        if ok:
            db.execute(
                "INSERT INTO probe_ports (workspace_id, target, port, last_ok) VALUES (?,?,?,?) "
                "ON CONFLICT(workspace_id, target, port) DO UPDATE SET last_ok=excluded.last_ok",
                (ws, target, port, now),
            )


def windows(db: sqlite3.Connection, ws: int, since: int) -> Dict[Tuple[int, int], Dict[str, Any]]:
    """(relay id, server id) -> TCP results on proven ports since `since`: attempts, failed share, connect time, TLS."""
    rows = db.execute(
        "SELECT p.server_id, t.id AS to_id, COUNT(*) AS n, SUM(CASE WHEN p.ok=0 AND p.error<>'refused' THEN 1 ELSE 0 END) AS fails, "
        "AVG(CASE WHEN p.ok=1 THEN p.rtt END) AS rtt, SUM(CASE WHEN p.tls=1 THEN 1 ELSE 0 END) AS tls_ok, "
        "SUM(CASE WHEN p.tls=0 THEN 1 ELSE 0 END) AS tls_fail "
        "FROM probes p JOIN servers s ON s.id=p.server_id JOIN servers t ON t.public_ip=p.target AND t.workspace_id=s.workspace_id "
        "JOIN probe_ports k ON k.target=p.target AND k.port=p.port AND k.workspace_id=s.workspace_id "
        "WHERE s.workspace_id=? AND s.role='relay' AND t.role<>'relay' AND p.ts>=? GROUP BY p.server_id, t.id",
        (ws, since),
    ).fetchall()
    return {
        (r["server_id"], r["to_id"]): {
            "tcp_n": r["n"], "tcp_loss": round(r["fails"] * 100.0 / r["n"], 1) if r["n"] else None,
            "tcp_rtt": r["rtt"], "tls_ok": r["tls_ok"], "tls_fail": r["tls_fail"],
        }
        for r in rows
    }


def port_windows(db: sqlite3.Connection, ws: int, since: int) -> Dict[Tuple[int, str, int], Dict[str, int]]:
    """(relay id, target, port) -> attempts, failures (refused included) and refusals since `since`, any target."""
    rows = db.execute(
        "SELECT p.server_id, p.target, p.port, COUNT(*) AS n, SUM(CASE WHEN p.ok=0 THEN 1 ELSE 0 END) AS fails, "
        "SUM(CASE WHEN p.error='refused' THEN 1 ELSE 0 END) AS refused "
        "FROM probes p JOIN servers s ON s.id=p.server_id WHERE s.workspace_id=? AND s.role='relay' AND p.ts>=? "
        "GROUP BY p.server_id, p.target, p.port",
        (ws, since),
    ).fetchall()
    return {(r["server_id"], r["target"], r["port"]): {"n": r["n"], "fails": r["fails"], "refused": r["refused"]} for r in rows}


def proven_ports(db: sqlite3.Connection, ws: int, now: int) -> Set[Tuple[str, int]]:
    """(target, port) that accepted a connection from some relay of the workspace within 30 days."""
    return {(r["target"], r["port"]) for r in db.execute(
        "SELECT target, port FROM probe_ports WHERE workspace_id=? AND last_ok>=?", (ws, now - PROVEN_S))}


def prune(db: sqlite3.Connection, now: int) -> None:
    db.execute("DELETE FROM probes WHERE ts<?", (now - PROBE_KEEP_S,))  # ws: retention - by age, every workspace alike
    db.execute("DELETE FROM probe_ports WHERE last_ok<?", (now - PROVEN_S,))  # ws: retention - by age, every workspace alike

