import ipaddress
import sqlite3
from typing import Any, Dict, List

MAX_PEERS = 64


def peers_for(db: sqlite3.Connection, server: sqlite3.Row) -> List[str]:
    """The addresses a server should count traffic to and from: every other server with a known IPv4."""
    if not server["acct_on"]:
        return []
    rows = db.execute(
        "SELECT public_ip FROM servers WHERE id<>? AND public_ip IS NOT NULL AND public_ip NOT LIKE '%:%' ORDER BY id",
        (server["id"],),
    ).fetchall()
    out: List[str] = []
    for r in rows:
        try:
            ip = str(ipaddress.IPv4Address(r["public_ip"]))
        except ValueError:
            continue
        if ip not in out:
            out.append(ip)
    return out[:MAX_PEERS]


def _count(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def record(db: sqlite3.Connection, server_id: int, acct: Any, now: int) -> None:
    """Turns the agent's cumulative counters into hourly bytes; a counter that went down was reset, so it counts as zero."""
    if not isinstance(acct, dict):
        return
    hour = now - now % 3600
    seen = []
    for ip, c in acct.items():
        try:
            ip = str(ipaddress.IPv4Address(ip))
        except ValueError:
            continue
        if not isinstance(c, dict):
            continue
        cur_in, cur_out = _count(c.get("in")), _count(c.get("out"))
        prev = db.execute("SELECT in_bytes, out_bytes FROM link_prev WHERE server_id=? AND peer_ip=?", (server_id, ip)).fetchone()
        d_in = cur_in - prev["in_bytes"] if prev and cur_in >= prev["in_bytes"] else 0
        d_out = cur_out - prev["out_bytes"] if prev and cur_out >= prev["out_bytes"] else 0
        db.execute(
            "INSERT INTO link_prev (server_id, peer_ip, in_bytes, out_bytes) VALUES (?,?,?,?) "
            "ON CONFLICT(server_id, peer_ip) DO UPDATE SET in_bytes=excluded.in_bytes, out_bytes=excluded.out_bytes",
            (server_id, ip, cur_in, cur_out),
        )
        if d_in or d_out:
            db.execute(
                "INSERT INTO link_traffic (server_id, peer_ip, hour, in_bytes, out_bytes) VALUES (?,?,?,?,?) "
                "ON CONFLICT(server_id, peer_ip, hour) DO UPDATE SET in_bytes=in_bytes+excluded.in_bytes, out_bytes=out_bytes+excluded.out_bytes",
                (server_id, ip, hour, d_in, d_out),
            )
        seen.append(ip)
    # a peer that is no longer counted must not keep an old baseline that would fake a jump when it returns
    for r in db.execute("SELECT peer_ip FROM link_prev WHERE server_id=?", (server_id,)).fetchall():
        if r["peer_ip"] not in seen:
            db.execute("DELETE FROM link_prev WHERE server_id=? AND peer_ip=?", (server_id, r["peer_ip"]))


def prune(db: sqlite3.Connection, now: int) -> None:
    db.execute("DELETE FROM link_traffic WHERE hour<?", (now - 90 * 86400,))
