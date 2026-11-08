import sqlite3
import time
from typing import Any, Dict, List

from ..servers.service import latest_of, status_of
from ..settings.router import thresholds
from ..ssl import service as ssl_svc
from . import detectors
from .detectors import make as _issue


def ping_matrix(db: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Latest ping from each Iran relay to each foreign server; foreign-to-foreign and inbound pings do not matter."""
    rows = db.execute(
        "SELECT p.server_id, s.name AS from_name, t.id AS to_id, t.name AS to_name, p.target, p.loss, p.rtt, p.ts "
        "FROM pings p JOIN servers s ON s.id=p.server_id JOIN servers t ON t.public_ip=p.target "
        "WHERE s.role='relay' AND t.role<>'relay' "
        "AND p.ts=(SELECT MAX(ts) FROM pings q WHERE q.server_id=p.server_id AND q.target=p.target) AND p.ts>=?",
        (int(time.time()) - 600,),
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
PING_WINDOW_S = 600
PING_MIN_SAMPLES = 6


def ping_windows(db: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Average loss per Iran relay and foreign server over the last window, with the number of samples."""
    rows = db.execute(
        "SELECT p.server_id, s.name AS from_name, t.id AS to_id, t.public_ip AS target, AVG(p.loss) AS loss, AVG(p.rtt) AS rtt, COUNT(p.loss) AS n "
        "FROM pings p JOIN servers s ON s.id=p.server_id JOIN servers t ON t.public_ip=p.target "
        "WHERE s.role='relay' AND t.role<>'relay' AND p.ts>=? GROUP BY p.server_id, t.id",
        (int(time.time()) - PING_WINDOW_S,),
    ).fetchall()
    return [dict(r) for r in rows if r["n"] >= PING_MIN_SAMPLES]


def issues(db: sqlite3.Connection) -> List[Dict[str, Any]]:
    th, now, out = thresholds(db), int(time.time()), []
    forecasts: List[Any] = []
    servers = db.execute("SELECT * FROM servers").fetchall()
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
        if th["on_reboot"] and lt["reboot_required"]:
            out.append(_issue(s, "reboot_required", "info", "سرور برای اعمال آپدیت نیاز به ریبوت دارد", "در ساعت کم‌ترافیک و با تأیید خودتان ریبوت کنید؛ رله‌ها را یکی‌یکی."))
    names = {s["id"]: s for s in servers}
    by_target: Dict[int, List[Dict[str, Any]]] = {}
    for w in ping_windows(db):
        by_target.setdefault(w["to_id"], []).append(w)
    classified, replaced = detectors.classify_paths(th, names, by_target)
    out.extend(classified)
    if th["on_quota_pair"]:
        out.extend(detectors.quota_pairs(forecasts))
    for to_id, links in by_target.items():
        target = names.get(to_id)
        if to_id in replaced:
            continue
        bad = [w for w in links if w["loss"] is not None and w["loss"] >= th["loss_warn"]]
        if not th["on_ping"] or not target or not bad:
            continue
        loss = sum(w["loss"] for w in bad) / len(bad)
        rtt = [w["rtt"] for w in bad if w["rtt"] is not None]
        evidence = {"relays": sorted(w["from_name"] for w in bad), "measured_by": len(links), "loss_pct": round(loss, 1),
                    "rtt_ms": round(sum(rtt) / len(rtt), 1) if rtt else None}
        if len(bad) >= 2:
            out.append(_issue(
                target, "ping:%s" % target["public_ip"], "critical" if loss >= th["loss_crit"] else "warning",
                "اتصال رله‌های ایران به %s قطع یا ناپایدار است" % (target["alias"] or target["name"]),
                "چند رله هم‌نظرند. با TCP یا یک تست حجمی مسیر را بسنجید و فقط بعد از تأیید دو مبدأ DNS را تغییر دهید.",
                **evidence,
            ))
        elif len(links) == 1:
            out.append(_issue(
                target, "ping:%s" % target["public_ip"], "info",
                "اتصال به %s فقط از یک رله ناپایدار دیده شده (تأیید نشده)" % (target["alias"] or target["name"]),
                "پینگ ICMP روی بعضی میزبان‌ها محدود می‌شود؛ با رلهٔ دوم یا تست TCP تأیید کنید.", **evidence,
            ))
    if th["on_ssl"]:
        out.extend(ssl_svc.issues(db))
    order = {"critical": 0, "warning": 1, "info": 2}
    return sorted(out, key=lambda i: (order[i["severity"]], i["server_name"] or ""))


def traffic_24h(db: sqlite3.Connection) -> Dict[str, int]:
    r = db.execute("SELECT COALESCE(SUM(rx_delta),0) rx, COALESCE(SUM(tx_delta),0) tx FROM metrics WHERE ts>=?", (int(time.time()) - 86400,)).fetchone()
    return {"rx_bytes": r["rx"], "tx_bytes": r["tx"]}
