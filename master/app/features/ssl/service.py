import ipaddress
import json
import re
import socket
import sqlite3
import ssl
import time
from typing import Any, Dict, List, Optional

from ..servers.service import status_of
from ..settings.router import thresholds

RECHECK_S = 6 * 3600
STALE_AUTO_S = 7 * 86400
# a folder like "example.com.bak-20261103" is a backup of a certificate, not a certificate
BACKUP_RE = re.compile(r"\.bak|\.old$|\.orig$|backup", re.I)
HOST_RE = re.compile(r"^(?=.{4,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
MAX_NEW_PER_REPORT = 20
PROBE_BUDGET_S = 20  # one sweep never spends longer than this on certificates


def domain_count(db: sqlite3.Connection, ws: int) -> int:
    return db.execute("SELECT COUNT(*) FROM domains WHERE workspace_id=?", (ws,)).fetchone()[0]


def adopt_domains(db: sqlite3.Connection, server: sqlite3.Row, names: List[Any]) -> None:
    """Domains an agent found in its web server's config join its workspace's list; ones seen again are kept fresh."""
    from ...workspaces import domain_cap

    now, added = int(time.time()), 0
    ws, server_id = server["workspace_id"], server["id"]
    room = domain_cap(db, ws) - domain_count(db, ws)
    for raw in sorted({str(n).lower().strip() for n in names})[:200]:
        if not HOST_RE.match(raw):
            continue
        row = db.execute("SELECT id, source FROM domains WHERE workspace_id=? AND host=? AND port=443", (ws, raw)).fetchone()
        if row:
            if row["source"] == "auto":
                db.execute("UPDATE domains SET seen_at=?, server_id=? WHERE id=? AND workspace_id=?", (now, server_id, row["id"], ws))
            continue
        if added >= min(MAX_NEW_PER_REPORT, room) or not is_public_host(raw):  # a name that does not resolve has nothing to probe
            continue
        db.execute(
            "INSERT INTO domains (workspace_id, host, port, note, source, server_id, seen_at, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (ws, raw, 443, "", "auto", server_id, now, now),
        )
        added += 1


def drop_stale_auto(db: sqlite3.Connection) -> None:
    db.execute("DELETE FROM domains WHERE source='auto' AND seen_at<?", (int(time.time()) - STALE_AUTO_S,))  # ws: retention - by age, every workspace alike


def public_address(host: str) -> Optional[str]:
    """One public address of `host`, or None when it does not resolve or any of its addresses is internal."""
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return None
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
            return None
    return infos[0][4][0] if infos else None


def is_public_host(host: str) -> bool:
    """Refuse loopback, private and link-local targets so the probe cannot be aimed at the inside network."""
    return public_address(host) is not None


def probe(host: str, port: int) -> Dict[str, Any]:
    # resolve once, check, and connect to that very address: a name that re-resolves to the inside is never reached
    address = public_address(host)
    if address is None:
        return {"not_after": None, "issuer": None, "error": "اتصال ممکن نشد: آدرس عمومی پیدا نشد"}
    ctx = ssl.create_default_context()
    try:
        with socket.create_connection((address, port), timeout=8) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as tls:
                cert = tls.getpeercert()
        issuer = dict(x[0] for x in cert.get("issuer", ())).get("organizationName")
        return {"not_after": int(ssl.cert_time_to_seconds(cert["notAfter"])), "issuer": issuer, "error": None}
    except ssl.SSLCertVerificationError as exc:
        return {"not_after": None, "issuer": None, "error": "گواهی معتبر نیست: %s" % exc.verify_message}
    except (OSError, ssl.SSLError) as exc:
        return {"not_after": None, "issuer": None, "error": "اتصال ممکن نشد: %s" % (exc.__class__.__name__)}


def probe_due(db: sqlite3.Connection, limit: int = 5, budget_s: float = PROBE_BUDGET_S) -> None:
    """The monitor's round over the due domains of every workspace, taken in turns (the oldest of each workspace, then
    the next of each...), so one workspace's long list never delays another's; stops when the time budget is spent."""
    now = int(time.time())
    rows = db.execute(  # ws: probe_queue - each row is probed for itself and written back to its own row
        "SELECT * FROM (SELECT d.*, ROW_NUMBER() OVER (PARTITION BY d.workspace_id ORDER BY COALESCE(d.last_checked, 0), d.id) AS turn "
        "FROM domains d WHERE d.last_checked IS NULL OR d.last_checked<?) ORDER BY turn, workspace_id LIMIT ?",
        (now - RECHECK_S, limit),
    ).fetchall()
    started = time.monotonic()
    for r in rows:
        if time.monotonic() - started > budget_s:
            break
        _store(db, r)


def probe_one(db: sqlite3.Connection, ws: int, domain_id: int) -> None:
    r = db.execute("SELECT * FROM domains WHERE id=? AND workspace_id=?", (domain_id, ws)).fetchone()
    if r:
        _store(db, r)


def _store(db: sqlite3.Connection, r: sqlite3.Row) -> None:
    res = probe(r["host"], r["port"])
    db.execute(
        "UPDATE domains SET not_after=?, issuer=?, error=?, last_checked=? WHERE id=? AND workspace_id=?",
        (res["not_after"], res["issuer"], res["error"], int(time.time()), r["id"], r["workspace_id"]),
    )


def level(days_left: Optional[int], error: Optional[str], th: Dict[str, float]) -> str:
    if error:
        return "critical"
    if days_left is None:
        return "ok"
    if days_left <= th["ssl_crit_days"]:
        return "critical"
    if days_left <= th["ssl_warn_days"]:
        return "warning"
    return "ok"


def _auto_renew(cert: Dict[str, Any], renew: Dict[str, Any]) -> str:
    if cert.get("source") == "acme.sh":
        return "on" if renew.get("acme_sh_cron") else "off"
    return "on" if (renew.get("certbot_timer_enabled") and renew.get("certbot_timer_active")) or renew.get("certbot_cron") else "off"


def rows(db: sqlite3.Connection, ws: int) -> List[Dict[str, Any]]:
    th, now, out = thresholds(db, ws), time.time(), []
    for s in db.execute("SELECT * FROM servers WHERE workspace_id=? AND last_report IS NOT NULL", (ws,)):
        ssl_rep = (json.loads(s["last_report"]) or {}).get("ssl")
        if not ssl_rep:
            continue
        renew, stale = ssl_rep.get("renew") or {}, status_of(s) == "offline"
        for c in ssl_rep.get("certs") or []:
            if BACKUP_RE.search(c["name"]):
                continue
            days = int((c["not_after"] - now) // 86400)
            certbot = c.get("source", "certbot") != "acme.sh"
            out.append({
                "key": "s%d:%s" % (s["id"], c["name"]), "kind": "file", "source": c.get("source", "certbot"),
                "server_id": s["id"], "server_name": s["alias"] or s["name"], "name": c["name"], "domains": c.get("domains") or [c["name"]],
                "not_after": c["not_after"], "days_left": days, "issuer": None, "error": None,
                "auto_renew": _auto_renew(c, renew), "renew_failed": bool(renew.get("certbot_last_run_failed")) and c.get("source") != "acme.sh",
                "level": level(days, None, th), "checked_at": s["last_seen"], "stale": stale,
                "auto": False, "can_renew": certbot, "can_delete": certbot,
            })
    probes = db.execute(
        "SELECT d.*, s.name AS sname, s.alias AS salias FROM domains d "
        "LEFT JOIN servers s ON s.id=d.server_id AND s.workspace_id=d.workspace_id "
        "WHERE d.workspace_id=? AND d.ignored=0 ORDER BY d.host",
        (ws,),
    )
    for d in probes:
        days = int((d["not_after"] - now) // 86400) if d["not_after"] else None
        auto = d["source"] == "auto"
        lvl = level(days, d["error"], th) if d["last_checked"] else "ok"
        if auto and d["error"]:
            lvl = "warning"  # a discovered name that does not answer on 443 is not necessarily broken
        out.append({
            "key": "d%d" % d["id"], "kind": "probe", "source": "probe", "server_id": d["server_id"] if auto else None,
            "server_name": (d["salias"] or d["sname"]) if auto else None,
            "name": d["host"] if d["port"] == 443 else "%s:%d" % (d["host"], d["port"]), "domains": [d["host"]],
            "not_after": d["not_after"], "days_left": days, "issuer": d["issuer"], "error": d["error"],
            "auto_renew": "unknown", "renew_failed": False, "level": lvl,
            "checked_at": d["last_checked"], "stale": False, "note": d["note"], "id": d["id"],
            "auto": auto, "can_renew": False, "can_delete": True,
        })
    order = {"critical": 0, "warning": 1, "ok": 2}
    return sorted(out, key=lambda r: (order[r["level"]], r["days_left"] if r["days_left"] is not None else -1))


def issues(db: sqlite3.Connection, ws: int) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    off: Dict[int, List[Dict[str, Any]]] = {}
    failed: Dict[int, Dict[str, Any]] = {}
    for r in rows(db, ws):
        if r["stale"] or (r.get("auto") and r["error"]):
            continue
        base = {"server_id": r["server_id"], "server_name": r["server_name"] or "SSL"}
        if r["level"] != "ok":
            where = ("روی %s" % r["server_name"]) if r["server_name"] else "(بررسی از بیرون)"
            title = "گواهی %s %s: %s" % (r["name"], where, r["error"] or ("منقضی شده" if r["days_left"] < 0 else "%d روز تا انقضا" % r["days_left"]))
            hint = "تمدید را دستی اجرا کنید (certbot renew) و علت شکست را در journalctl -u certbot ببینید." if r["kind"] == "file" else "گواهی و تنظیم وب‌سرور دامنه را بررسی کنید."
            out.append({**base, "id": "ssl:%s" % r["key"], "code": "ssl_expiry", "severity": r["level"], "title": title, "suggestion": hint,
                        "evidence": {"name": r["name"], "days_left": r["days_left"], "error": r["error"]}})
        elif r["kind"] == "file" and r["auto_renew"] == "off" and r["days_left"] is not None and r["days_left"] <= 45:
            off.setdefault(r["server_id"], []).append(r)
        if r["kind"] == "file" and r["renew_failed"]:
            failed.setdefault(r["server_id"], r)
    # renewal is one thing per server, not one per certificate on it
    for sid, certs in off.items():
        first = certs[0]
        out.append({"server_id": sid, "server_name": first["server_name"], "id": "ssl:s%d:auto" % sid, "code": "ssl_auto_renew_off",
                    "severity": "warning", "title": "تمدید خودکار گواهی‌ها روی %s فعال نیست" % first["server_name"],
                    "suggestion": "systemctl enable --now certbot.timer را اجرا کنید یا کرون تمدید را برگردانید.",
                    "evidence": {"certs": len(certs), "days_left": min(c["days_left"] for c in certs)}})
    for sid, r in failed.items():
        out.append({"server_id": sid, "server_name": r["server_name"], "id": "ssl:s%d:failed" % sid, "code": "ssl_renew_failed",
                    "severity": "warning", "title": "آخرین تمدید خودکار certbot ناموفق بوده (%s)" % r["server_name"],
                    "suggestion": "journalctl -u certbot را بخوانید؛ معمولاً DNS، پورت ۸۰ یا مسیر چالش .well-known یک گواهی باعث آن است.",
                    "evidence": {}})
    return out
