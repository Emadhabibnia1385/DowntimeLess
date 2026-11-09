import sqlite3
import time
from typing import Any, Dict, List, Tuple

from ..checks import service as checks_svc
from ..issues import acks
from ..servers.service import latest_of, status_of
from ..settings.router import thresholds
from ..ssl import service as ssl_svc
from . import detectors, probes
from .detectors import make as _issue


def ping_matrix(db: sqlite3.Connection, ws: int) -> List[Dict[str, Any]]:
    """Latest ping from each Iran relay to each foreign server of the same workspace; other pings do not matter."""
    rows = db.execute(
        "SELECT p.server_id, s.name AS from_name, t.id AS to_id, t.name AS to_name, p.target, p.loss, p.rtt, p.ts "
        "FROM pings p JOIN servers s ON s.id=p.server_id JOIN servers t ON t.public_ip=p.target AND t.workspace_id=s.workspace_id "
        "WHERE s.workspace_id=? AND s.role='relay' AND t.role<>'relay' "
        "AND p.ts=(SELECT MAX(ts) FROM pings q WHERE q.server_id=p.server_id AND q.target=p.target) AND p.ts>=?",
        (ws, int(time.time()) - 600),
    ).fetchall()
    return [
        {
            "from_id": r["server_id"], "from_name": r["from_name"], "to_id": r["to_id"], "to_name": r["to_name"],
            "target": r["target"], "loss_pct": r["loss"], "rtt_ms": r["rtt"], "ts": r["ts"],
        }
        for r in rows
    ]


# ICMP is rate-limited or dropped by many hosts, so a link counts as bad only on a window of samples
# and only when at least two Iran relays agree; one relay disagreeing with the rest is an artefact.
# The same window and sample count apply to the TCP probes, which alone decide a path verdict.
PING_WINDOW_S = 600
PING_MIN_SAMPLES = 6


def path_windows(db: sqlite3.Connection, ws: int) -> List[Dict[str, Any]]:
    """Per Iran relay and foreign server of one workspace over the last window: ICMP loss and TCP results on proven ports.

    `loss`/`rtt`/`n` are ICMP (loss None below PING_MIN_SAMPLES); `tcp_loss` is the share of connections that failed
    (None below PING_MIN_SAMPLES attempts), `tcp_n` the attempts, `tls_ok`/`tls_fail` handshakes on TLS ports."""
    since = int(time.time()) - PING_WINDOW_S
    rows = db.execute(
        "SELECT p.server_id, s.name AS from_name, t.id AS to_id, t.public_ip AS target, AVG(p.loss) AS loss, AVG(p.rtt) AS rtt, COUNT(p.loss) AS n "
        "FROM pings p JOIN servers s ON s.id=p.server_id JOIN servers t ON t.public_ip=p.target AND t.workspace_id=s.workspace_id "
        "WHERE s.workspace_id=? AND s.role='relay' AND t.role<>'relay' AND p.ts>=? GROUP BY p.server_id, t.id",
        (ws, since),
    ).fetchall()
    out: Dict[Tuple[int, int], Dict[str, Any]] = {}
    for r in rows:
        w = dict(r)
        if w["n"] < PING_MIN_SAMPLES:
            w["loss"] = w["rtt"] = None
        out[(w["server_id"], w["to_id"])] = w
    tcp = probes.windows(db, ws, since)
    if any(key not in out for key in tcp):
        servers = {r["id"]: r for r in db.execute("SELECT id, name, public_ip FROM servers WHERE workspace_id=?", (ws,))}
        for key in tcp:
            if key not in out and key[0] in servers and key[1] in servers:
                out[key] = {"server_id": key[0], "from_name": servers[key[0]]["name"], "to_id": key[1],
                            "target": servers[key[1]]["public_ip"], "loss": None, "rtt": None, "n": 0}
    for key, w in out.items():
        t = tcp.get(key) or {}
        n = t.get("tcp_n") or 0
        w.update(tcp_n=n, tcp_loss=t.get("tcp_loss") if n >= PING_MIN_SAMPLES else None, tcp_rtt=t.get("tcp_rtt"),
                 tls_ok=t.get("tls_ok") or 0, tls_fail=t.get("tls_fail") or 0)
    return [w for w in out.values() if w["loss"] is not None or w["tcp_loss"] is not None]


def issues(db: sqlite3.Connection, ws: int) -> List[Dict[str, Any]]:
    th, now, out = thresholds(db, ws), int(time.time()), []
    forecasts: List[Any] = []
    servers = db.execute("SELECT * FROM servers WHERE workspace_id=?", (ws,)).fetchall()
    ctx = checks_svc.context(servers)
    for s in servers:
        st, lt = status_of(s), latest_of(s)
        if st == "pending":
            if now - s["created_at"] > 3600:
                out.append(_issue(s, "agent_missing", "info", "agent هنوز نصب نشده", "دستور نصب را روی سرور اجرا کنید یا توکن جدید بگیرید."))
            continue
        if st == "offline":
            if th["on_offline"]:
                out.append(_issue(s, "offline", "critical", "سرور گزارش نمی‌دهد", "از سرورهای دیگر ping بگیرید؛ اگر ping هم نیست حجم/وضعیت سرویس‌دهنده را بررسی کنید، وگرنه سرویس agent را ریستارت کنید.", last_seen_s_ago=now - s["last_seen"]))
            continue
        if th["on_disk"] and lt["disk_pct"] is not None and lt["disk_pct"] >= th["disk_warn"]:
            crit = lt["disk_pct"] >= th["disk_crit"]
            out.append(_issue(s, "disk", "critical" if crit else "warning", "دیسک رو به پر شدن است", "لاگ‌ها و بکاپ‌های قدیمی را پاک کنید (journalctl --vacuum-size، docker system df).", disk_pct=lt["disk_pct"]))
        if th["on_ram"] and lt["ram_pct"] is not None and lt["ram_pct"] >= th["ram_warn"]:
            out.append(_issue(s, "ram", "warning", "مصرف RAM بالاست", "پردازش‌های پرمصرف را ببینید؛ پس از اطمینان سرویس مربوط را ریستارت کنید.", ram_pct=lt["ram_pct"]))
        if th["on_retrans"] and lt["tcp_retrans_pct"] is not None and lt["tcp_retrans_pct"] >= th["retrans_warn"]:
            out.append(_issue(s, "retrans", "warning", "ارسال مجدد TCP بالاست (مسیر بد)", "مسیر بین رله و خروج را با تست حجمی بررسی کنید.", retrans_pct=lt["tcp_retrans_pct"]))
        if th["on_failed_units"] and lt["failed_units"]:
            out.append(_issue(s, "failed_units", "warning", "سرویس‌های ناموفق systemd", "با systemctl status وضعیت را ببینید و در صورت نیاز ریستارت کنید.", units=lt["failed_units"]))
        out.extend(detectors.load_issues(s, th, lt, detectors.recent_metrics(db, s["id"])))
        out.extend(detectors.event_issues(s, th, lt, now))
        forecast = detectors.quota_forecast(db, s, th, now) if th["on_quota"] or th["on_quota_pair"] else None
        if forecast:
            forecasts.append((s, forecast))
            found = detectors.quota_issue(s, forecast) if th["on_quota"] else None
            if found:
                out.append(found)
        host = checks_svc.server_issues(db, ws, s, th, now, ctx)
        out.extend(host)
        # agent 0.3 names the packages waiting for the reboot; that issue replaces the bare flag
        if th["on_reboot"] and lt["reboot_required"] and not any(i["code"] == "reboot_pending_pkgs" for i in host):
            out.append(_issue(s, "reboot_required", "info", "سرور برای اعمال آپدیت نیاز به ریبوت دارد", "در ساعت کم‌ترافیک و با تأیید خودتان ریبوت کنید؛ رله‌ها را یکی‌یکی."))
    names = {s["id"]: s for s in servers}
    by_target: Dict[int, List[Dict[str, Any]]] = {}
    for w in path_windows(db, ws):
        by_target.setdefault(w["to_id"], []).append(w)
    classified, replaced = detectors.classify_paths(th, names, by_target)
    out.extend(classified)
    if th["on_quota_pair"]:
        out.extend(detectors.quota_pairs(forecasts))
    if th["on_ping"]:
        out.extend(detectors.path_issues(th, names, by_target, replaced))
    if th["on_ssl"]:
        out.extend(ssl_svc.issues(db, ws))
    order = {"critical": 0, "warning": 1, "info": 2}
    return acks.annotate(db, ws, sorted(out, key=lambda i: (order[i["severity"]], i["server_name"] or "")))


def traffic_24h(db: sqlite3.Connection, ws: int) -> Dict[str, int]:
    r = db.execute(
        "SELECT COALESCE(SUM(m.rx_delta),0) rx, COALESCE(SUM(m.tx_delta),0) tx FROM metrics m JOIN servers s ON s.id=m.server_id "
        "WHERE s.workspace_id=? AND m.ts>=?",
        (ws, int(time.time()) - 86400),
    ).fetchone()
    return {"rx_bytes": r["rx"], "tx_bytes": r["tx"]}
