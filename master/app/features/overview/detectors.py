"""Phase 1 detectors: events, sustained load, quota forecast and the cause of a failing ping path."""
import calendar
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from ..servers.service import status_of

GIB = 1024 ** 3
DAY = 86400
REBOOT_KEEP_S = 1800
EVENT_KEEP_S = DAY
# consecutive reports an alert must hold before it opens
HOLD = {"cpu": 5, "steal": 3, "conntrack": 3, "load": 5}
STEAL_STRONG, STEAL_CRIT = 15, 40
QUOTA_WARN_DAYS, QUOTA_CRIT_DAYS, PAIR_GAP_DAYS = 7, 2, 2
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


def quota_forecast(db: sqlite3.Connection, s, th: Dict[str, float], now: int) -> Optional[Dict[str, Any]]:
    """Bytes used this billing month, the recent daily rate and the days until the quota is gone."""
    if not s["quota_gb"] or s["quota_gb"] <= 0:
        return None
    start, reset = quota_period(now, s["quota_reset_day"] or 1)
    expr = "rx_delta+tx_delta" if th["quota_basis"] else "tx_delta"
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
        "resets_in_days": round((reset - now) / DAY, 1), "basis": "both" if th["quota_basis"] else "out",
        "runs_out": days_left is not None and days_left < (reset - now) / DAY,
    }


def quota_issue(s, f: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    ev = {k: f[k] for k in ("used_gb", "quota_gb", "used_pct", "per_day_gb", "days_left", "resets_in_days", "basis")}
    if f["used_pct"] >= 100:
        return make(s, "quota", "critical", "حجم ماهانه تمام شده", "ترافیک را همین حالا به سرور دیگر منتقل کنید یا حجم اضافه بخرید؛ سرور ممکن است محدود یا قطع شود.", **ev)
    if not f["runs_out"]:
        return None
    if f["days_left"] < QUOTA_CRIT_DAYS:
        return make(s, "quota", "critical", "حجم ماهانه کمتر از دو روز دیگر تمام می‌شود",
                    "ترافیک را به سرور دیگر منتقل کنید یا حجم اضافه بخرید و DNS را پیش از تمام شدن تغییر دهید.", **ev)
    if f["days_left"] < QUOTA_WARN_DAYS:
        return make(s, "quota", "warning", "حجم ماهانه تا یک هفته دیگر تمام می‌شود",
                    "مصرف را به رلهٔ دیگر پخش کنید یا حجم اضافه تهیه کنید.", **ev)
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

def classify_paths(th: Dict[str, float], names: Dict[int, Any], by_target: Dict[int, List[Dict[str, Any]]]) -> Tuple[List[Dict[str, Any]], Set[int]]:
    """Name the cause of a failing relay-to-server path; also returns the targets whose plain ping issue it replaces."""
    out: List[Dict[str, Any]] = []
    replaced: Set[int] = set()
    hard, fine = th["loss_crit"], th["loss_warn"]
    cut_off: Dict[int, List[Tuple[Any, Dict[str, Any], List[str]]]] = {}
    for to_id, links in by_target.items():
        target = names.get(to_id)
        if not target or status_of(target) != "online" or len(links) < 2:
            continue
        down = [w for w in links if w["loss"] is not None and w["loss"] >= hard]
        if len(down) == len(links):
            if th["on_blacklisted"]:
                replaced.add(to_id)
                out.append(make(target, "blacklisted", "critical", "IP از داخل ایران مسدود شده",
                                "همهٔ رله‌ها هم‌نظرند و خود سرور آنلاین است؛ آی‌پی جدید بگیرید یا مسیر را از دیتاسنتر دیگری بگذرانید و با TCP تأیید کنید.",
                                relays=sorted(w["from_name"] for w in links), measured_by=len(links),
                                loss_pct=round(sum(w["loss"] for w in links) / len(links), 1)))
        elif len(down) == 1:
            rest = [w for w in links if w is not down[0]]
            if all(w["loss"] is not None and w["loss"] < fine for w in rest):
                cut_off.setdefault(down[0]["server_id"], []).append((target, down[0], sorted(w["from_name"] for w in rest)))
    for relay_id, items in cut_off.items():
        relay = names.get(relay_id)
        if not relay:
            continue
        label = relay["alias"] or relay["name"]
        if len(items) >= 2 and th["on_relay_filtered"]:
            out.append(make(relay, "relay_filtered", "warning", "رلهٔ %s به چند سرور خارجی همزمان نمی‌رسد" % label,
                            "فیلتر ICMP یا مسیر در سطح دیتاسنتر رله محتمل است؛ با TCP تأیید کنید و اگر پایدار ماند رله را به دیتاسنتر دیگری ببرید.",
                            targets=sorted(t["alias"] or t["name"] for t, _, _ in items), count=len(items),
                            loss_pct=round(sum(w["loss"] for _, w, _ in items) / len(items), 1)))
        elif len(items) == 1 and th["on_relay_egress"]:
            target, w, reached = items[0]
            out.append(make(relay, "relay_egress", "warning", "رلهٔ %s به %s نمی‌رسد ولی رله‌های دیگر می‌رسند" % (label, target["alias"] or target["name"]),
                            "فیلتر خروجی روی همین رله محتمل است؛ با TCP از خود رله تست کنید و ترافیک را موقتاً به رلهٔ دیگر بدهید.",
                            target=target["alias"] or target["name"], target_ip=w["target"], loss_pct=round(w["loss"], 1), reached_by=reached))
    return out, replaced
