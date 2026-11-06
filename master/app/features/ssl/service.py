import ipaddress
import json
import socket
import sqlite3
import ssl
import time
from typing import Any, Dict, List, Optional

from ..servers.service import status_of
from ..settings.router import thresholds

RECHECK_S = 6 * 3600


def is_public_host(host: str) -> bool:
    """Refuse loopback, private and link-local targets so the probe cannot be aimed at the inside network."""
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
            return False
    return bool(infos)


def probe(host: str, port: int) -> Dict[str, Any]:
    ctx = ssl.create_default_context()
    try:
        with socket.create_connection((host, port), timeout=8) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as tls:
                cert = tls.getpeercert()
        issuer = dict(x[0] for x in cert.get("issuer", ())).get("organizationName")
        return {"not_after": int(ssl.cert_time_to_seconds(cert["notAfter"])), "issuer": issuer, "error": None}
    except ssl.SSLCertVerificationError as exc:
        return {"not_after": None, "issuer": None, "error": "گواهی معتبر نیست: %s" % exc.verify_message}
    except (OSError, ssl.SSLError) as exc:
        return {"not_after": None, "issuer": None, "error": "اتصال ممکن نشد: %s" % (exc.__class__.__name__)}


def probe_due(db: sqlite3.Connection, limit: int = 5, force_id: Optional[int] = None) -> None:
    now = int(time.time())
    if force_id is not None:
        rows = db.execute("SELECT * FROM domains WHERE id=?", (force_id,)).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM domains WHERE last_checked IS NULL OR last_checked<? ORDER BY last_checked LIMIT ?", (now - RECHECK_S, limit)
        ).fetchall()
    for r in rows:
        res = probe(r["host"], r["port"])
        db.execute(
            "UPDATE domains SET not_after=?, issuer=?, error=?, last_checked=? WHERE id=?",
            (res["not_after"], res["issuer"], res["error"], int(time.time()), r["id"]),
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


def rows(db: sqlite3.Connection) -> List[Dict[str, Any]]:
    th, now, out = thresholds(db), time.time(), []
    for s in db.execute("SELECT * FROM servers WHERE last_report IS NOT NULL"):
        ssl_rep = (json.loads(s["last_report"]) or {}).get("ssl")
        if not ssl_rep:
            continue
        renew, stale = ssl_rep.get("renew") or {}, status_of(s) == "offline"
        for c in ssl_rep.get("certs") or []:
            days = int((c["not_after"] - now) // 86400)
            out.append({
                "key": "s%d:%s" % (s["id"], c["name"]), "kind": "file", "source": c.get("source", "certbot"),
                "server_id": s["id"], "server_name": s["alias"] or s["name"], "name": c["name"], "domains": c.get("domains") or [c["name"]],
                "not_after": c["not_after"], "days_left": days, "issuer": None, "error": None,
                "auto_renew": _auto_renew(c, renew), "renew_failed": bool(renew.get("certbot_last_run_failed")) and c.get("source") != "acme.sh",
                "level": level(days, None, th), "checked_at": s["last_seen"], "stale": stale,
            })
    for d in db.execute("SELECT * FROM domains ORDER BY host"):
        days = int((d["not_after"] - now) // 86400) if d["not_after"] else None
        out.append({
            "key": "d%d" % d["id"], "kind": "probe", "source": "probe", "server_id": None, "server_name": None,
            "name": d["host"] if d["port"] == 443 else "%s:%d" % (d["host"], d["port"]), "domains": [d["host"]],
            "not_after": d["not_after"], "days_left": days, "issuer": d["issuer"], "error": d["error"],
            "auto_renew": "unknown", "renew_failed": False, "level": level(days, d["error"], th) if d["last_checked"] else "ok",
            "checked_at": d["last_checked"], "stale": False, "note": d["note"], "id": d["id"],
        })
    order = {"critical": 0, "warning": 1, "ok": 2}
    return sorted(out, key=lambda r: (order[r["level"]], r["days_left"] if r["days_left"] is not None else -1))


def issues(db: sqlite3.Connection) -> List[Dict[str, Any]]:
    out = []
    for r in rows(db):
        if r["stale"]:
            continue
        base = {"server_id": r["server_id"], "server_name": r["server_name"] or "SSL"}
        if r["level"] != "ok":
            where = ("روی %s" % r["server_name"]) if r["server_name"] else "(بررسی از بیرون)"
            title = "گواهی %s %s: %s" % (r["name"], where, r["error"] or ("منقضی شده" if r["days_left"] < 0 else "%d روز تا انقضا" % r["days_left"]))
            hint = "تمدید را دستی اجرا کنید (certbot renew) و علت شکست را در journalctl -u certbot ببینید." if r["kind"] == "file" else "گواهی و تنظیم وب‌سرور دامنه را بررسی کنید."
            out.append({**base, "id": "ssl:%s" % r["key"], "code": "ssl_expiry", "severity": r["level"], "title": title, "suggestion": hint,
                        "evidence": {"days_left": r["days_left"], "error": r["error"]}})
        elif r["kind"] == "file" and r["auto_renew"] == "off" and r["days_left"] is not None and r["days_left"] <= 45:
            out.append({**base, "id": "ssl:%s:auto" % r["key"], "code": "ssl_auto_renew_off", "severity": "warning",
                        "title": "تمدید خودکار گواهی %s فعال نیست" % r["name"], "suggestion": "systemctl enable --now certbot.timer را اجرا کنید یا کرون تمدید را برگردانید.",
                        "evidence": {"days_left": r["days_left"]}})
        if r["kind"] == "file" and r["renew_failed"]:
            out.append({**base, "id": "ssl:%s:failed" % r["key"], "code": "ssl_renew_failed", "severity": "warning",
                        "title": "آخرین تمدید خودکار certbot ناموفق بوده (%s)" % r["server_name"],
                        "suggestion": "journalctl -u certbot را بخوانید؛ معمولاً DNS یا پورت ۸۰ یا یک گواهی قدیمی خراب باعث آن است.", "evidence": {}})
    return out
