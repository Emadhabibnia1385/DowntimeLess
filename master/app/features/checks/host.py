"""Phase 2 issues from `checks`: listeners, tunnel units, containers, DNAT, conntrack and kernel.

Each rule reads the field it needs from the server's latest report and does nothing when that field is missing or not
the expected shape; the remembered state (memory.py) only adds history to a field that is there now."""
import sqlite3
from typing import Any, Dict, List, Optional

from ..overview.detectors import make
from . import memory as m

UP_STATES = ("active", "activating", "reloading", "refreshing")
CRASH_RISE = 3  # restarts within the 10-minute window that make a crash loop
CRASH_CONTAINER = 3
DNAT_GONE_REPORTS = 2
LISTENER_REPORTS, LISTENER_REPORTS_FRESH = 2, 3
ALWAYS = ("always",)
CLEAN_STOP = (0, 137, 143)  # docker stop: exit 0, or SIGTERM/SIGKILL after the timeout
REVIVED_KEEP_S = 1800
CORE_ROLES = ("relay", "exit", "panel")


def _named(rows: List[Dict[str, Any]], key: str = "name") -> List[str]:
    return sorted(str(r.get(key)) for r in rows if r.get(key))


def listener_problems(s, rep: Dict[str, Any], state: Dict[str, Any], rows: List[sqlite3.Row]) -> Optional[Dict[str, Any]]:
    """The baseline ports that are gone now, or None while the report has no listener list."""
    current = m.listener_keys(m.checks_of(rep).get("listeners")) if m.checks_of(rep) else None
    if current is None:
        return None
    need = LISTENER_REPORTS_FRESH if (m.num(state.get("since_start")) or 0) < 2 else LISTENER_REPORTS
    base = [r for r in rows if m.in_baseline(r)]
    gone = [r for r in base if r["missing"] >= need and (r["proto"], r["port"]) not in current]
    return {"current": len(current), "baseline": len(base), "learning": len(rows) - len(base), "gone": gone, "need": need}


def issues(s, th: Dict[str, float], rep: Dict[str, Any], state: Dict[str, Any], rows: List[sqlite3.Row],
           ignored: Dict[str, set], now: int) -> List[Dict[str, Any]]:
    checks = m.checks_of(rep)
    if checks is None:
        return []
    out: List[Dict[str, Any]] = []
    role = s["role"]

    lp = listener_problems(s, rep, state, rows)
    if th["on_listener_missing"] and lp and lp["gone"]:
        out.append(make(s, "listener_missing", "critical" if role in CORE_ROLES else "warning",
                        "پورتی که همیشه گوش می‌داد دیگر گوش نمی‌دهد",
                        "با ss -ltnp ببینید کدام سرویس (Xray، تانل یا sshd) بسته شده؛ اگر برداشتن پورت عمدی بوده، آن را در کارت سلامت میزبان از خط پایه حذف کنید.",
                        ports=["%s/%d" % (r["proto"], r["port"]) for r in lp["gone"]],
                        procs=sorted({r["proc"] for r in lp["gone"] if r["proc"]}),
                        missing_reports=max(r["missing"] for r in lp["gone"]), baseline=lp["baseline"]))

    units = [u for u in m.dicts(checks.get("units")) or [] if isinstance(u.get("name"), str) and m.UNIT_FAMILY.match(u["name"])]
    memo = state.get("units") if isinstance(state.get("units"), dict) else {}
    stopped = [u for u in units if u.get("enabled") is True and u.get("active") not in UP_STATES and u.get("sub") != "auto-restart"
               and isinstance(u.get("active"), str)]
    if th["on_unit_stopped"] and stopped:
        out.append(make(s, "unit_stopped", "critical", "سرویس تانل یا DNAT فعال (enabled) است ولی اجرا نمی‌شود",
                        "با journalctl -u UNIT علت توقف را بخوانید و فقط بعد از تأیید مالک آن را راه بیندازید؛ systemctl --failed این حالت را همیشه نشان نمی‌دهد.",
                        units=_named(stopped), states=["%s=%s/%s" % (u["name"], u.get("active"), u.get("sub")) for u in stopped]))
    looping = []
    for u in units:
        rise = m.num((memo.get(u["name"]) or {}).get("rise")) or 0
        if u.get("sub") == "auto-restart" or rise >= CRASH_RISE:
            looping.append((u, rise))
    if th["on_unit_crashloop"] and looping:
        forwards = _forward_units(checks)
        owns = [u["name"] for u, _ in looping if u["name"] in forwards or m.FORWARD_UNIT.match(u["name"])]
        out.append(make(s, "unit_crashloop", "critical" if owns else "warning", "سرویس تانل پشت سر هم ری‌استارت می‌شود (crash loop)",
                        "لاگ همان سرویس را از اولین خطا بخوانید (کانفیگ خراب، پورت گرفته‌شده یا کمبود RAM) و پیش از ری‌استارت دستی علت را رفع کنید.",
                        units=sorted(u["name"] for u, _ in looping), restarts_10m=["%s +%d" % (u["name"], r) for u, r in looping],
                        forward_units=sorted(owns)))

    out.extend(_container_issues(s, th, checks, state, ignored, now))

    nft = checks.get("nft") if isinstance(checks.get("nft"), dict) else None
    had = state.get("had_dnat") if isinstance(state.get("had_dnat"), dict) else None
    if (th["on_dnat_missing"] and nft is not None and had and (m.num(state.get("dnat_gone")) or 0) >= DNAT_GONE_REPORTS
            and m.forward_unit_enabled(checks) is not False):
        if nft.get("relay_dnat") is not True and (m.num(nft.get("dnat_rules")) or 0) == 0:
            out.append(make(s, "dnat_missing", "critical", "جدول یا قوانین DNAT که قبلاً بود حالا نیست",
                            "واحد DNAT را بررسی کنید (systemctl status relay-dnat) و با تأیید مالک فایل nft ذخیره‌شده را دوباره بارگذاری کنید؛ اگر حذف عمدی بود، آن را در کارت سلامت میزبان تأیید کنید.",
                            had_rules=m.num(had.get("rules")), had_table=bool(had.get("table")), tables=len(nft.get("tables") or [])))
    forward = m.num(nft.get("ip_forward")) if nft is not None else None
    if forward is None:
        forward = m.num(m.part(rep, "kernel").get("ip_forward"))
    if th["on_ip_forward_off"] and role == "relay" and forward == 0:
        carries = bool(had) or any(isinstance(x, dict) and x.get("kind") in ("gre", "ipip", "sit")
                                   for x in m.part(rep, "tunnels").get("links") or [])
        out.append(make(s, "ip_forward_off", "critical" if carries else "warning", "ip_forward روی رله خاموش است",
                        "بدون ip_forward، DNAT و GRE هیچ بسته‌ای را عبور نمی‌دهند؛ مقدار زنده را با sysctl net.ipv4.ip_forward ببینید و با تأیید مالک روشن و در sysctl.d ماندگار کنید.",
                        ip_forward=0, carries_forwarding=carries))

    out.extend(_kernel_issues(s, th, rep, state, now))
    return out


def _forward_units(checks: Dict[str, Any]) -> set:
    """Units of tunnel configs that carry ports: losing one of them closes a location port."""
    tunnels = checks.get("tunnels") if isinstance(checks.get("tunnels"), dict) else {}
    return {c.get("unit") for c in m.dicts(tunnels.get("configs")) or [] if c.get("unit") and c.get("ports")}


def _container_issues(s, th, checks, state, ignored, now) -> List[Dict[str, Any]]:
    rows = m.dicts(checks.get("containers"))
    if rows is None:
        return []
    memo = state.get("containers") if isinstance(state.get("containers"), dict) else {}
    retired = ignored.get("container", set())
    down, looping, sick, revived = [], [], [], []
    for c in rows:
        name = m.text(c.get("name"), 128)
        if not name or name in retired:
            continue
        st, mem = c.get("state"), memo.get(name) if isinstance(memo.get(name), dict) else {}
        policy, code = c.get("policy"), m.num(c.get("exit_code"))
        if st in ("exited", "dead") and (mem.get("down_since") or policy in ALWAYS
                                         or (policy == "unless-stopped" and code is not None and code not in CLEAN_STOP)):
            down.append("%s (%s%s)" % (name, st, "" if code is None else ", %d" % code))
        rise = m.num(mem.get("rise")) or 0
        if st == "restarting" or rise >= CRASH_CONTAINER:
            looping.append("%s +%d" % (name, rise))
        if st == "running" and c.get("health") == "unhealthy":
            sick.append(name)
        at = m.num(mem.get("revived_at"))
        if st == "running" and at and now - at <= REVIVED_KEEP_S:
            revived.append(name)
    out = []
    if th["on_container_down"] and down:
        out.append(make(s, "container_down", "critical", "کانتینری که کار می‌کرد متوقف شده",
                        "با docker ps -a و docker logs --tail 100 علت توقف را ببینید و با تأیید مالک راهش بیندازید؛ کانتینر بازنشسته را در کارت سلامت میزبان علامت بزنید.",
                        containers=down))
    if th["on_container_restarting"] and looping:
        out.append(make(s, "container_restarting", "warning", "کانتینر پشت سر هم ری‌استارت می‌شود",
                        "docker logs --tail 100 همان کانتینر را بخوانید؛ تداخل پورت، کمبود RAM یا کانفیگ خراب رایج‌ترین علت است.",
                        containers=looping))
    if th["on_container_unhealthy"] and sick:
        out.append(make(s, "container_unhealthy", "warning", "health check کانتینر ناسالم است",
                        "docker inspect --format '{{json .State.Health}}' را ببینید تا بفهمید کدام بررسی شکست می‌خورد.",
                        containers=sick))
    if th["on_container_revived"] and revived:
        out.append(make(s, "container_revived", "info", "ریبوت کانتینری را که متوقف بود دوباره روشن کرد",
                        "بپرسید این کانتینر (مثلاً پنل دوم) باید روشن بماند یا نه؛ توقف عمدی را با docker update --restart=unless-stopped ماندگار کنید.",
                        containers=revived))
    return out


def _events(state: Dict[str, Any], key: str, now: int) -> List[Dict[str, Any]]:
    return [e for e in state.get(key + "_events") or [] if isinstance(e, dict) and now - (m.num(e.get("at")) or 0) <= m.EVENT_KEEP_S]


def _kernel_issues(s, th, rep, state, now) -> List[Dict[str, Any]]:
    out = []
    ct, kernel, apt = m.part(rep, "conntrack"), m.part(rep, "kernel"), m.part(rep, "apt")
    if th["on_conntrack_limits_reset"] and ct.get("module_loaded") is True:
        limit, timeout = m.num(ct.get("max")), m.num(ct.get("tcp_established_timeout"))
        floor = th["ct_max_relay"] if s["role"] == "relay" else th["ct_max_exit"] if s["role"] == "exit" else None
        low = limit is not None and floor is not None and limit < floor
        slow = timeout is not None and timeout > th["ct_timeout_max"]
        if low or slow:
            out.append(make(s, "conntrack_limits_reset", "warning", "حد conntrack زنده به پیش‌فرض برگشته یا کم است",
                            "مقدار زنده (sysctl net.netfilter.nf_conntrack_max و tcp_timeout_established) را با فایل sysctl مقایسه کنید؛ ماژول را در modules-load.d زود بارگذاری کنید.",
                            conntrack_max=limit, expected_max=int(floor) if floor else None, tcp_established_timeout_s=timeout,
                            timeout_max_s=int(th["ct_timeout_max"])))
    drops = _events(state, "ct", now)
    count, cmax = m.num(ct.get("count")), m.num(ct.get("max"))
    fill = 100.0 * count / cmax if count is not None and cmax else None
    # insert_failed from a DNS/UDP race on a nearly empty table loses nothing; only real drops or a filling table matter
    real = sum(m.num(e.get("drop")) or 0 for e in drops) > 0 or fill is None or fill >= 50
    if th["on_conntrack_drops"] and drops and ct and real:
        out.append(make(s, "conntrack_drops", "critical", "conntrack اتصال‌ها را دور می‌ریزد (insert_failed یا drop بالا رفت)",
                        "dmesg را برای «table full, dropping packet» بگردید و nf_conntrack_max را زنده بالا ببرید و timeout اتصال‌های برقرار را کم کنید.",
                        insert_failed_delta=sum(m.num(e.get("insert_failed")) or 0 for e in drops),
                        drop_delta=sum(m.num(e.get("drop")) or 0 for e in drops),
                        last_s_ago=now - max(m.num(e.get("at")) or 0 for e in drops)))
    ooms = _events(state, "oom", now)
    if th["on_oom_kill"] and ooms and kernel:
        out.append(make(s, "oom_kill", "critical", "کرنل پردازه‌ای را به‌خاطر کمبود حافظه کشت (OOM)",
                        "با journalctl -k | grep -i 'out of memory' ببینید کدام پردازه کشته شد؛ بافر تانل‌ها را کم کنید یا swap و RAM اضافه کنید.",
                        oom_kills=sum(m.num(e.get("oom_kill")) or 0 for e in ooms), last_s_ago=now - max(m.num(e.get("at")) or 0 for e in ooms)))
    inode = kernel.get("inode_pct")
    if th["on_inode_high"] and isinstance(inode, (int, float)) and not isinstance(inode, bool) and inode >= th["inode_warn"]:
        out.append(make(s, "inode_high", "warning", "inodeهای دیسک رو به پایان است",
                        "با df -i / ببینید و پوشه‌ای را که پر از فایل‌های ریز شده (کش، سشن یا صف) پیدا کنید و فقط با تأیید مالک پاک کنید.",
                        inode_pct=round(float(inode), 1)))
    journal = kernel.get("journal_mb")
    if th["on_journal_big"] and isinstance(journal, (int, float)) and not isinstance(journal, bool) and journal >= th["journal_warn_mb"]:
        out.append(make(s, "journal_big", "warning", "لاگ journald خیلی بزرگ شده",
                        "با تأیید مالک journalctl --vacuum-size=200M بزنید (کار vacuum_logs در پنل) و SystemMaxUse را در journald.conf محدود کنید.",
                        journal_mb=round(float(journal)), limit_mb=int(th["journal_warn_mb"])))
    since = m.num(state.get("ntp_false_since"))
    if th["on_time_unsynced"] and since and kernel.get("ntp_synced") is False and now - since >= th["ntp_unsynced_min"] * 60:
        out.append(make(s, "time_unsynced", "warning", "ساعت سرور همگام نیست",
                        "timedatectl و systemctl status systemd-timesyncd را ببینید؛ ساعت نادرست گواهی‌ها، توکن‌ها و لاگ‌ها را خراب می‌کند.",
                        unsynced_s=now - since))
    pkgs, audit = m.num(apt.get("reboot_required_pkgs")), m.num(apt.get("dpkg_audit"))
    if th["on_reboot_pending_pkgs"] and pkgs:
        dirty = bool(audit)
        out.append(make(s, "reboot_pending_pkgs", "warning" if dirty else "info",
                        "بسته‌ها ریبوت می‌خواهند ولی dpkg نیمه‌کاره است" if dirty else "بسته‌های به‌روزشده منتظر ریبوت‌اند",
                        "پیش از ریبوت dpkg --audit باید خالی باشد؛ در ساعت کم‌ترافیک و یکی‌یکی ریبوت کنید." if dirty
                        else "در ساعت کم‌ترافیک و با تأیید خودتان ریبوت کنید؛ رله‌ها را یکی‌یکی و میزبان پنل را آخر.",
                        packages=pkgs, dpkg_audit=audit, held_docker=apt.get("held_docker") if isinstance(apt.get("held_docker"), bool) else None))
    return out
