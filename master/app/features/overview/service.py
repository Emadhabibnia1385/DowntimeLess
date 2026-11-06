import sqlite3
import time
from typing import Any, Dict, List

from ..servers.service import latest_of, status_of
from ..settings.router import thresholds


def ping_matrix(db: sqlite3.Connection) -> List[Dict[str, Any]]:
    by_ip = {r["public_ip"]: r for r in db.execute("SELECT id, name, public_ip FROM servers WHERE public_ip IS NOT NULL")}
    rows = db.execute(
        "SELECT p.server_id, p.target, p.loss, p.rtt, p.ts, s.name FROM pings p JOIN servers s ON s.id=p.server_id "
        "WHERE p.ts=(SELECT MAX(ts) FROM pings q WHERE q.server_id=p.server_id AND q.target=p.target) AND p.ts>=?",
        (int(time.time()) - 600,),
    ).fetchall()
    out = []
    for r in rows:
        to = by_ip.get(r["target"])
        out.append({
            "from_id": r["server_id"], "from_name": r["name"], "to_id": to["id"] if to else None,
            "to_name": to["name"] if to else r["target"], "target": r["target"],
            "loss_pct": r["loss"], "rtt_ms": r["rtt"], "ts": r["ts"],
        })
    return out


def _issue(row, code: str, severity: str, title: str, suggestion: str, **evidence: Any) -> Dict[str, Any]:
    return {
        "id": "server:%d:%s" % (row["id"], code), "server_id": row["id"], "server_name": row["alias"] or row["name"],
        "code": code, "severity": severity, "title": title, "suggestion": suggestion, "evidence": evidence,
    }


def issues(db: sqlite3.Connection) -> List[Dict[str, Any]]:
    th, now, out = thresholds(db), int(time.time()), []
    servers = db.execute("SELECT * FROM servers").fetchall()
    for s in servers:
        st, lt = status_of(s), latest_of(s)
        if st == "pending":
            if now - s["created_at"] > 3600:
                out.append(_issue(s, "agent_missing", "info", "agent هنوز نصب نشده", "دستور نصب را روی سرور اجرا کنید یا توکن جدید بگیرید."))
            continue
        if st == "offline":
            out.append(_issue(s, "offline", "critical", "سرور گزارش نمی‌دهد", "از سرورهای دیگر ping بگیرید؛ اگر ping هم نیست حجم/وضعیت سرویس‌دهنده را بررسی کنید، وگرنه سرویس agent را ریستارت کنید.", last_seen_s_ago=now - s["last_seen"]))
            continue
        if lt["disk_pct"] is not None and lt["disk_pct"] >= th["disk_warn"]:
            crit = lt["disk_pct"] >= th["disk_crit"]
            out.append(_issue(s, "disk", "critical" if crit else "warning", "دیسک رو به پر شدن است", "لاگ‌ها و بکاپ‌های قدیمی را پاک کنید (journalctl --vacuum-size، docker system df).", disk_pct=lt["disk_pct"]))
        if lt["ram_pct"] is not None and lt["ram_pct"] >= th["ram_warn"]:
            out.append(_issue(s, "ram", "warning", "مصرف RAM بالاست", "پردازش‌های پرمصرف را ببینید؛ پس از اطمینان سرویس مربوط را ریستارت کنید.", ram_pct=lt["ram_pct"]))
        if lt["cpu_pct"] is not None and lt["cpu_pct"] >= th["cpu_warn"]:
            out.append(_issue(s, "cpu", "warning", "مصرف CPU بالاست", "بررسی کنید ترافیک کاربران یا یک پردازش گیرکرده باعث آن شده است.", cpu_pct=lt["cpu_pct"]))
        if lt["steal_pct"] is not None and lt["steal_pct"] >= th["steal_warn"]:
            out.append(_issue(s, "steal", "warning", "steal بالا: میزبان مجازی شلوغ است", "اگر پایدار است به سرویس‌دهنده تیکت بدهید یا سرور را منتقل کنید.", steal_pct=lt["steal_pct"]))
        if lt["tcp_retrans_pct"] is not None and lt["tcp_retrans_pct"] >= th["retrans_warn"]:
            out.append(_issue(s, "retrans", "warning", "ارسال مجدد TCP بالاست (مسیر بد)", "مسیر بین رله و خروج را با تست حجمی بررسی کنید.", retrans_pct=lt["tcp_retrans_pct"]))
        if lt["conntrack_pct"] is not None and lt["conntrack_pct"] >= th["conntrack_crit"]:
            out.append(_issue(s, "conntrack", "critical", "جدول conntrack نزدیک پر شدن است", "nf_conntrack_max را بالا ببرید و timeout اتصال‌های برقرار را کم کنید.", conntrack_pct=lt["conntrack_pct"]))
        if lt["failed_units"]:
            out.append(_issue(s, "failed_units", "warning", "سرویس‌های ناموفق systemd", "با systemctl status وضعیت را ببینید و در صورت نیاز ریستارت کنید.", units=lt["failed_units"]))
        if lt["reboot_required"]:
            out.append(_issue(s, "reboot_required", "info", "سرور برای اعمال آپدیت نیاز به ریبوت دارد", "در ساعت کم‌ترافیک و با تأیید خودتان ریبوت کنید؛ رله‌ها را یکی‌یکی."))
    names = {s["id"]: s for s in servers}
    for m in ping_matrix(db):
        s = names.get(m["from_id"])
        if not s or m["loss_pct"] is None or m["loss_pct"] < th["loss_warn"]:
            continue
        crit = m["loss_pct"] >= th["loss_crit"]
        out.append(_issue(
            s, "ping:%s" % m["target"], "critical" if crit else "warning",
            "اتصال به %s قطع یا ناپایدار است" % m["to_name"],
            "همین ارتباط را از یک سرور دیگر هم بسنجید؛ فقط وقتی دو مبدأ هم‌نظر باشند DNS را تغییر دهید.",
            to=m["to_name"], loss_pct=m["loss_pct"], rtt_ms=m["rtt_ms"],
        ))
    order = {"critical": 0, "warning": 1, "info": 2}
    return sorted(out, key=lambda i: (order[i["severity"]], i["server_name"]))


def traffic_24h(db: sqlite3.Connection) -> Dict[str, int]:
    r = db.execute("SELECT COALESCE(SUM(rx_delta),0) rx, COALESCE(SUM(tx_delta),0) tx FROM metrics WHERE ts>=?", (int(time.time()) - 86400,)).fetchone()
    return {"rx_bytes": r["rx"], "tx_bytes": r["tx"]}
