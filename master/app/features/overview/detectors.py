"""Phase 1 detectors: events, sustained load, quota forecast and the cause of a failing ping path."""
import calendar
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from ..servers.service import status_of

GIB = 1024 ** 3
DAY = 86400
REBOOT_KEEP_S = 600
EVENT_KEEP_S = DAY
# consecutive reports an alert must hold before it opens
HOLD = {"cpu": 5, "steal": 3, "conntrack": 3, "load": 5}
STEAL_STRONG, STEAL_CRIT = 15, 40
QUOTA_WARN_DAYS, QUOTA_CRIT_DAYS, PAIR_GAP_DAYS = 7, 2, 2
UPLOAD_FREE_NOTE = "آپلود این سرور رایگان است و فقط دانلود در سهمیه شمرده می‌شود."
IP_CHECKLIST = (
    "آی‌پی عوض شده؛ این هشت مورد را درست کنید: ۱) GRE local ۲) GRE remote ۳) آدرس dial تونل‌ها ۴) رکوردهای DNS "
    "۵) allowlistها ۶) قوانین nft که آی‌پی قدیمی را دارند ۷) alias اس‌اس‌اچ ۸) اندازه‌گیری دوبارهٔ همهٔ حالت‌ها."
)


def make(row, code: str, severity: str, title: str, suggestion: str, **evidence: Any) -> Dict[str, Any]:
    return {
        "id": "server:%d:%s" % (row["id"], code), "server_id": row["id"], "server_name": row["alias"] or row["name"],
        "code": code, "severity": severity, "title": title, "suggestion": suggestion, "evidence": evidence,
    }


def recent_metrics(db: sqlite3.Connection, server_id: int, n: int = 5) -> List[sqlite3.Row]:
    """The last n report rows of a server, newest first."""
    return db.execute(
        "SELECT cpu, steal, conntrack, load1 FROM metrics WHERE server_id=? ORDER BY ts DESC, rowid DESC LIMIT ?",  # ws: caller_row - the server row of the caller's workspace
        (server_id, n),
    ).fetchall()


def sustained(rows: List[sqlite3.Row], col: str, n: int) -> Optional[float]:
    """The lowest value over the last n reports: what the server held the whole time; None when it did not."""
    got = rows[:n]
    if len(got) < n or any(r[col] is None for r in got):
        return None
    return min(r[col] for r in got)


def load_issues(s, th: Dict[str, float], lt: Dict[str, Any], rows: List[sqlite3.Row]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if th["on_cpu"]:
        held = sustained(rows, "cpu", HOLD["cpu"])
        if held is not None and held >= th["cpu_warn"]:
            out.append(make(s, "cpu", "warning", "مصرف CPU بالاست", "بررسی کنید ترافیک کاربران یا یک پردازش گیرکرده باعث آن شده است.",
                            cpu_pct=lt["cpu_pct"], held_reports=HOLD["cpu"]))
    if th["on_conntrack"]:
        held = sustained(rows, "conntrack", HOLD["conntrack"])
        if held is not None and held >= th["conntrack_crit"]:
            out.append(make(s, "conntrack", "critical", "جدول conntrack نزدیک پر شدن است",
                            "nf_conntrack_max را بالا ببرید و timeout اتصال‌های برقرار را کم کنید.",
                            conntrack_pct=lt["conntrack_pct"], held_reports=HOLD["conntrack"]))
    if th["on_steal"]:
        held = sustained(rows, "steal", HOLD["steal"])
        if held is not None and held >= th["steal_warn"]:
            ev = {"steal_pct": lt["steal_pct"], "held_reports": HOLD["steal"]}
            if held >= STEAL_CRIT and s["role"] != "other":
                out.append(make(s, "steal", "critical", "steal بسیار بالا: کاربران همین حالا کند می‌شوند",
                                "سرور را فوراً به میزبان دیگری ببرید یا از سرویس‌دهنده انتقال بخواهید؛ بار را به سرور دیگر بدهید.", **ev))
            elif held >= STEAL_STRONG:
                out.append(make(s, "steal", "warning", "steal شدید: میزبان مجازی خیلی شلوغ است",
                                "تیکت فوری به سرویس‌دهنده بدهید و انتقال سرور را آماده کنید.", **ev))
            else:
                out.append(make(s, "steal", "warning", "steal بالا: میزبان مجازی شلوغ است",
                                "اگر پایدار است به سرویس‌دهنده تیکت بدهید یا سرور را منتقل کنید.", **ev))
    cores = lt["cpu_cores"]
    if th["on_load_per_core"] and cores:
        held = sustained(rows, "load1", HOLD["load"])
        if held is not None and held / cores >= 1.0:
            out.append(make(s, "load_per_core", "warning", "بار سیستم از ظرفیت هسته‌ها بیشتر است",
                            "پردازش‌های پرمصرف را ببینید یا هسته اضافه کنید؛ بار پایدار بالای ۱ به‌ازای هر هسته یعنی صف.",
                            load1=lt["load1"], cpu_cores=cores, per_core=round(held / cores, 2), held_reports=HOLD["load"]))
    return out


def event_issues(s, th: Dict[str, float], lt: Dict[str, Any], now: int) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if th["on_rebooted"] and s["rebooted_at"] and now - s["rebooted_at"] <= REBOOT_KEEP_S:
        out.append(make(s, "rebooted", "info", "سرور ریبوت شد",
                        "چک‌لیست پس از ریبوت: سرویس‌های failed، تونل‌ها، قوانین nft/DNAT و conntrack را بررسی کنید و ۱۰ دقیقه صبر کنید.",
                        uptime_s=lt["uptime_s"], rebooted_s_ago=now - s["rebooted_at"]))
    if th["on_ip_changed"] and s["ip_changed_at"] and now - s["ip_changed_at"] <= EVENT_KEEP_S:
        out.append(make(s, "ip_changed", "critical", "آی‌پی عمومی سرور عوض شد", IP_CHECKLIST,
                        old_ip=s["prev_ip"], new_ip=s["public_ip"], changed_s_ago=now - s["ip_changed_at"]))
    if th["on_resized"] and s["resized_at"] and now - s["resized_at"] <= EVENT_KEEP_S:
        try:
            was = json.loads(s["resized_from"] or "{}")
        except ValueError:
            was = {}
        out.append(make(s, "resized", "warning", "منابع سرور کم شد (تغییر پلن یا ساخت دوباره)",
                        "با سرویس‌دهنده بررسی کنید پلن عوض شده یا سرور از نو ساخته شده و تنظیمات کرنل و تونل را دوباره بسنجید.",
                        changed_s_ago=now - s["resized_at"],
                        **{"%s_%s" % (k, side): v[i] for k, v in was.items() for i, side in enumerate(("before", "now"))}))
    return out


# ---- quota -------------------------------------------------------------------------------------

def _reset_at(year: int, month: int, day: int) -> int:
    day = min(day, calendar.monthrange(year, month)[1])
    return int(datetime(year, month, day, tzinfo=timezone.utc).timestamp())


def quota_period(now: int, reset_day: int) -> Tuple[int, int]:
    """Start of the current billing month and the moment it resets, in UTC."""
    d = datetime.fromtimestamp(now, timezone.utc)
    this = _reset_at(d.year, d.month, reset_day)
    if now >= this:
        ny, nm = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
        return this, _reset_at(ny, nm, reset_day)
    py, pm = (d.year - 1, 12) if d.month == 1 else (d.year, d.month - 1)
    return _reset_at(py, pm, reset_day), this


def quota_counted(s, th: Dict[str, float]) -> Tuple[str, str]:
    """The metrics column and basis name a server's quota counts; free upload means only download (rx) counts."""
    if "count_upload" in s.keys() and not s["count_upload"]:
        return "rx_delta", "download"
    return ("rx_delta+tx_delta", "both") if th["quota_basis"] else ("tx_delta", "out")


def quota_forecast(db: sqlite3.Connection, s, th: Dict[str, float], now: int) -> Optional[Dict[str, Any]]:
    """Bytes used this billing month, the recent daily rate and the days until the quota is gone."""
    if not s["quota_gb"] or s["quota_gb"] <= 0:
        return None
    start, reset = quota_period(now, s["quota_reset_day"] or 1)
    expr, basis = quota_counted(s, th)
    used = db.execute("SELECT COALESCE(SUM(%s),0) FROM metrics WHERE server_id=? AND ts>=?" % expr, (s["id"], start)).fetchone()[0]  # ws: caller_row - the server row of the caller's workspace
    window = min(now - start, 3 * DAY)
    rate = None
    if window >= 6 * 3600:  # a rate over a few hours would be noise
        got = db.execute("SELECT COALESCE(SUM(%s),0) FROM metrics WHERE server_id=? AND ts>=?" % expr, (s["id"], now - window)).fetchone()[0]  # ws: caller_row - the server row of the caller's workspace
        rate = got * DAY / window
    quota = s["quota_gb"] * GIB
    if used >= quota:
        days_left: Optional[float] = 0.0
    else:
        days_left = (quota - used) / rate if rate else None
    return {
        "used_gb": round(used / GIB, 1), "quota_gb": s["quota_gb"], "used_pct": round(used * 100 / quota, 1),
        "per_day_gb": round(rate / GIB, 2) if rate is not None else None,
        "days_left": round(days_left, 1) if days_left is not None else None,
        "resets_in_days": round((reset - now) / DAY, 1), "basis": basis,
        "runs_out": days_left is not None and days_left < (reset - now) / DAY,
    }


def quota_issue(s, f: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    ev = {k: f[k] for k in ("used_gb", "quota_gb", "used_pct", "per_day_gb", "days_left", "resets_in_days", "basis")}
    note = " " + UPLOAD_FREE_NOTE if f["basis"] == "download" else ""
    if f["used_pct"] >= 100:
        return make(s, "quota", "critical", "حجم ماهانه تمام شده", "ترافیک را همین حالا به سرور دیگر منتقل کنید یا حجم اضافه بخرید؛ سرور ممکن است محدود یا قطع شود." + note, **ev)
    if not f["runs_out"]:
        return None
    if f["days_left"] < QUOTA_CRIT_DAYS:
        return make(s, "quota", "critical", "حجم ماهانه کمتر از دو روز دیگر تمام می‌شود",
                    "ترافیک را به سرور دیگر منتقل کنید یا حجم اضافه بخرید و DNS را پیش از تمام شدن تغییر دهید." + note, **ev)
    if f["days_left"] < QUOTA_WARN_DAYS:
        return make(s, "quota", "warning", "حجم ماهانه تا یک هفته دیگر تمام می‌شود",
                    "مصرف را به رلهٔ دیگر پخش کنید یا حجم اضافه تهیه کنید." + note, **ev)
    return None


def quota_pairs(servers: List[Tuple[Any, Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Relays whose quotas run out within 48 hours of each other: users would lose the location together."""
    due = sorted(((f["days_left"], s) for s, f in servers if s["role"] == "relay" and f["runs_out"] and f["days_left"] <= QUOTA_WARN_DAYS),
                 key=lambda x: x[0])
    groups: List[List[Tuple[float, Any]]] = []
    for item in due:
        if groups and item[0] - groups[-1][0][0] <= PAIR_GAP_DAYS:
            groups[-1].append(item)
        else:
            groups.append([item])
    out = []
    for g in (g for g in groups if len(g) >= 2):
        names = [s["alias"] or s["name"] for _, s in g]
        ids = "-".join(str(s["id"]) for _, s in sorted(g, key=lambda x: x[1]["id"]))
        out.append({
            "id": "quota_pair:%s" % ids, "server_id": None, "server_name": " + ".join(names), "code": "quota_pair", "severity": "warning",
            "title": "حجم چند رله نزدیک هم تمام می‌شود", "suggestion": "یکی از رله‌ها را زودتر شارژ کنید یا ترافیکش را جابه‌جا کنید تا یک موقعیت یک‌باره بدون رله نماند.",
            "evidence": {"relays": names, "days_left": [d for d, _ in g], "gap_hours": round((g[-1][0] - g[0][0]) * 24, 1)},
        })
    return out


# ---- cause of a failing path ---------------------------------------------------------------------
# Verdicts come from TCP connections to proven ports only (two relays, each with a full window of samples).
# ICMP loss alone is a note: many paths drop or rate-limit ping while the data flows.

def tcp_measured(w: Dict[str, Any]) -> bool:
    return w.get("tcp_loss") is not None


def _icmp_at(w: Dict[str, Any], level: float) -> bool:
    return w.get("loss") is not None and w["loss"] >= level


def classify_paths(th: Dict[str, float], names: Dict[int, Any], by_target: Dict[int, List[Dict[str, Any]]]) -> Tuple[List[Dict[str, Any]], Set[int]]:
    """Name the cause of a failing relay-to-server path from TCP; also returns the targets whose plain issue it replaces."""
    out: List[Dict[str, Any]] = []
    replaced: Set[int] = set()
    hard, fine = th["loss_crit"], th["loss_warn"]
    cut_off: Dict[int, List[Tuple[Any, Dict[str, Any], List[str]]]] = {}
    for to_id, links in by_target.items():
        target = names.get(to_id)
        measured = [w for w in links if tcp_measured(w)]
        if not target or status_of(target) != "online" or len(measured) < 2:
            continue
        down = [w for w in measured if w["tcp_loss"] >= hard]
        if len(down) == len(measured):
            if th["on_blacklisted"]:
                replaced.add(to_id)
                out.append(make(target, "blacklisted", "critical", "IP از داخل ایران مسدود شده",
                                "همهٔ رله‌ها با اتصال TCP هم‌نظرند و خود سرور آنلاین است؛ آی‌پی جدید بگیرید یا مسیر را از دیتاسنتر دیگری بگذرانید.",
                                probe="tcp", relays=sorted(w["from_name"] for w in measured), measured_by=len(measured),
                                loss_pct=round(sum(w["tcp_loss"] for w in measured) / len(measured), 1),
                                icmp_loss_pct=_avg_icmp(measured)))
        elif len(down) == 1:
            rest = [w for w in measured if w is not down[0]]
            if all(w["tcp_loss"] < fine for w in rest):
                cut_off.setdefault(down[0]["server_id"], []).append((target, down[0], sorted(w["from_name"] for w in rest)))
    for relay_id, items in cut_off.items():
        relay = names.get(relay_id)
        if not relay:
            continue
        label = relay["alias"] or relay["name"]
        if len(items) >= 2 and th["on_relay_filtered"]:
            out.append(make(relay, "relay_filtered", "warning", "رلهٔ %s به چند سرور خارجی همزمان نمی‌رسد" % label,
                            "اتصال TCP از این رله به چند سرور شکست می‌خورد در حالی که رله‌های دیگر می‌رسند؛ فیلتر در سطح دیتاسنتر رله محتمل است.",
                            probe="tcp", targets=sorted(t["alias"] or t["name"] for t, _, _ in items), count=len(items),
                            loss_pct=round(sum(w["tcp_loss"] for _, w, _ in items) / len(items), 1)))
        elif len(items) == 1 and th["on_relay_egress"]:
            target, w, reached = items[0]
            out.append(make(relay, "relay_egress", "warning", "رلهٔ %s به %s نمی‌رسد ولی رله‌های دیگر می‌رسند" % (label, target["alias"] or target["name"]),
                            "اتصال TCP فقط از همین رله شکست می‌خورد؛ فیلتر خروجی همین رله محتمل است؛ ترافیک را موقتاً به رلهٔ دیگر بدهید.",
                            probe="tcp", target=target["alias"] or target["name"], target_ip=w["target"], loss_pct=round(w["tcp_loss"], 1),
                            icmp_loss_pct=None if w.get("loss") is None else round(w["loss"], 1), reached_by=reached))
    return out, replaced


def _avg_icmp(links: List[Dict[str, Any]]) -> Optional[float]:
    vals = [w["loss"] for w in links if w.get("loss") is not None]
    return round(sum(vals) / len(vals), 1) if vals else None


def path_issues(th: Dict[str, float], names: Dict[int, Any], by_target: Dict[int, List[Dict[str, Any]]],
                replaced: Set[int]) -> List[Dict[str, Any]]:
    """The plain loss issue per foreign server: TCP decides its level; ICMP-only loss is an info note."""
    out: List[Dict[str, Any]] = []
    for to_id, links in by_target.items():
        target = names.get(to_id)
        if not target or to_id in replaced:
            continue
        label = target["alias"] or target["name"]
        measured = [w for w in links if tcp_measured(w)]
        tcp_bad = [w for w in measured if w["tcp_loss"] >= th["loss_warn"]]
        icmp_bad = [w for w in links if _icmp_at(w, th["loss_warn"])]
        if len(tcp_bad) >= 2:
            loss = sum(w["tcp_loss"] for w in tcp_bad) / len(tcp_bad)
            rtt = [w["tcp_rtt"] for w in tcp_bad if w.get("tcp_rtt") is not None]
            out.append(make(target, "ping:%s" % target["public_ip"], "critical" if loss >= th["loss_crit"] else "warning",
                            "اتصال رله‌های ایران به %s قطع یا ناپایدار است" % label,
                            "چند رله با اتصال TCP هم‌نظرند. با یک تست حجمی مسیر را بسنجید و فقط بعد از تأیید دو مبدأ DNS را تغییر دهید.",
                            probe="tcp", relays=sorted(w["from_name"] for w in tcp_bad), measured_by=len(measured), loss_pct=round(loss, 1),
                            rtt_ms=round(sum(rtt) / len(rtt), 1) if rtt else None, icmp_loss_pct=_avg_icmp(tcp_bad)))
        elif len(tcp_bad) == 1 and len(measured) == 1:
            out.append(make(target, "ping:%s" % target["public_ip"], "info",
                            "اتصال TCP به %s فقط از یک رله ناپایدار دیده شده (تأیید نشده)" % label,
                            "برای حکم دو رله لازم است؛ با رلهٔ دوم یا یک تست حجمی تأیید کنید.",
                            probe="tcp", relays=[tcp_bad[0]["from_name"]], measured_by=1, loss_pct=round(tcp_bad[0]["tcp_loss"], 1)))
        elif icmp_bad and not tcp_bad and (len(icmp_bad) >= 2 or len(links) == 1):
            tcp_fine = [w for w in icmp_bad if tcp_measured(w)]
            title = ("افت ICMP به %s دیده می‌شود ولی اتصال TCP سالم است" if tcp_fine
                     else "افت ICMP به %s دیده می‌شود (با TCP تأیید نشده)") % label
            hint = ("ping روی این مسیر محدود می‌شود ولی داده عبور می‌کند؛ کاری لازم نیست مگر کاربران مشکل گزارش کنند." if tcp_fine
                    else "پینگ ICMP روی بعضی مسیرها محدود می‌شود؛ تا پورت‌های داده با TCP سنجیده نشوند این فقط یک یادداشت است.")
            loss = sum(w["loss"] for w in icmp_bad) / len(icmp_bad)
            rtt = [w["rtt"] for w in icmp_bad if w.get("rtt") is not None]
            out.append(make(target, "ping:%s" % target["public_ip"], "info", title, hint,
                            probe="icmp", relays=sorted(w["from_name"] for w in icmp_bad), measured_by=len(links), loss_pct=round(loss, 1),
                            rtt_ms=round(sum(rtt) / len(rtt), 1) if rtt else None, tcp_ok=bool(tcp_fine)))
    return out
