"""TCP (and TLS) probes from Iran relays to the real listening ports of the foreign servers.

ICMP is filtered or rate-limited on many paths while the data flows, and the reverse also happens, so a path verdict
needs a TCP connection to a port users really reach. The master picks the ports from each server's own listener list,
the relay's agent (0.3.2+) connects and reports, and only ports that answered at least once ("proven") decide a verdict:
a firewalled or local-only port then never looks like a blocked path.
"""
import json
import re
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

PROBE_KEEP_S = 2 * 86400
PROVEN_S = 30 * 86400
PER_SERVER = 2  # ports probed per foreign server and cycle
MAX_TARGETS = 24  # ports one relay probes per cycle (the agent caps it as well)
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


def targets_for_relay(db: sqlite3.Connection, ws: int, now: int) -> List[Dict[str, Any]]:
    """The ports a relay of this workspace probes this cycle: proven ports first, then unproven ones in turn."""
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
    return out[:MAX_TARGETS]


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


def record(db: sqlite3.Connection, server: Any, items: Any, now: int) -> None:
    """Store one relay's probe results; ports that answered become proven for its workspace."""
    if server["role"] != "relay" or not isinstance(items, list):
        return
    ws = server["workspace_id"]
    known = {r["public_ip"] for r in db.execute("SELECT public_ip FROM servers WHERE workspace_id=? AND role<>'relay' AND public_ip IS NOT NULL",
                                                 (ws,))}
    for raw in items[:MAX_TARGETS * 2]:
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


def prune(db: sqlite3.Connection, now: int) -> None:
    db.execute("DELETE FROM probes WHERE ts<?", (now - PROBE_KEEP_S,))  # ws: retention - by age, every workspace alike
    db.execute("DELETE FROM probe_ports WHERE last_ok<?", (now - PROVEN_S,))  # ws: retention - by age, every workspace alike

