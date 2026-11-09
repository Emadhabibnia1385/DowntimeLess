"""Forwards a relay carries: DNAT rules whose destination is dead, and forwarded ports other relays cannot get through.

A DNAT rule (agent 0.3.3 `checks.nft.dnat`) is dead when its destination does not answer: the server it names by public
IP does not listen on that port, or the relay's own TCP probe to it fails. The typical case is a rule left pointing at the
old server after a migration. A destination that is no server of the workspace is an info note while it answers.

The other relays of the workspace connect to each forwarded port of a relay. Through DNAT that connection completes only
when the whole path to the destination works, so a broken forward is seen from outside. A verdict needs a port that
answered before (proven) and two relays with a full window each that agree; one relay alone is an info note.
"""
import re
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

from ..checks import memory as m
from ..servers.service import status_of
from . import probes
from .detectors import make

WINDOW_S = 600
PRIVATE = re.compile(r"^(10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.|169\.254\.)")
LOCAL = re.compile(r"^(127\.|::1$|\[::1\]$|localhost$)")
EPHEMERAL = 32768  # the agent keeps listeners up here only for some processes, so absence there proves nothing
LISTENER_GONE = 2  # reports in a row a baseline port must be missing before "not listening" counts


def _pct(w: Dict[str, int]) -> float:
    return w["fails"] * 100.0 / w["n"] if w["n"] else 0.0


def verdict(w: Optional[Dict[str, int]], th: Dict[str, float], min_samples: int) -> Optional[str]:
    """'bad', 'good' or 'mixed' for a full window of probes; None without one."""
    if not w or w["n"] < min_samples:
        return None
    pct = _pct(w)
    return "bad" if pct >= th["loss_crit"] else "good" if pct < th["loss_warn"] else "mixed"


def _listens(db: sqlite3.Connection, ws: int, target: Any, rep: Dict[str, Any], port: int) -> Optional[bool]:
    """Whether the server listens on a public TCP port; None when its report cannot tell."""
    rows = m.dicts((m.checks_of(rep) or {}).get("listeners"))
    if rows is None or port >= EPHEMERAL:
        return None
    for x in rows:
        if x.get("proto") == "tcp" and m.num(x.get("port")) == port and not LOCAL.match(str(x.get("addr") or "")):
            return True
    for r in m.baseline(db, ws, target["id"]):
        if r["proto"] == "tcp" and r["port"] == port and r["missing"] < LISTENER_GONE:
            return None  # just gone: a restart, not yet a dead port
    return False


def _rule(r: Dict[str, Any]) -> str:
    return "%d -> %s:%d" % (r["port"], r["to"], r["to_port"])


def _path_ok(win, relay_id: int, to: str, port: int, th, min_samples: int) -> bool:
    """The relay reaches the same address on another port, so a failure on this one is the port, not the path."""
    return any(k[0] == relay_id and k[1] == to and k[2] != port and verdict(w, th, min_samples) == "good" for k, w in win.items())


def _dead_targets(db, ws, s, rules, by_ip, reps, win, th, min_samples) -> List[Dict[str, Any]]:
    dead: List[Tuple[Dict[str, Any], str, str, Optional[Dict[str, int]], str]] = []
    unknown: List[Tuple[Dict[str, Any], Optional[str]]] = []
    for r in rules:
        to, port = r["to"], r["to_port"]
        if to == s["public_ip"]:
            continue
        w = win.get((s["id"], to, port))
        v = verdict(w, th, min_samples)
        refused = bool(w and w["fails"] and w["refused"] * 2 >= w["fails"])
        target = by_ip.get(to)
        if target is not None:
            if target["id"] == s["id"] or status_of(target) != "online" or v == "good":
                continue  # an offline destination is its own issue
            label = target["alias"] or target["name"]
            listening = _listens(db, ws, target, reps.get(target["id"]) or {}, port)
            if listening is False:
                dead.append((r, label, "critical" if v == "bad" else "warning", w, "not_listening"))
            elif v == "bad" and (refused or _path_ok(win, s["id"], to, port, th, min_samples)):
                dead.append((r, label, "warning", w, "refused" if refused else "unanswered"))
        elif v == "bad":
            dead.append((r, to, "critical" if refused else "warning", w, "refused" if refused else "unanswered"))
        elif not PRIVATE.match(to):
            unknown.append((r, v))
    out: List[Dict[str, Any]] = []
    if dead and th["on_dnat_dead_target"]:
        probed = [d[3] for d in dead if d[3] and d[3]["n"] >= min_samples]
        out.append(make(s, "dnat_dead_target", "critical" if any(d[2] == "critical" for d in dead) else "warning",
                        "قانون DNAT به مقصدی می‌فرستد که جواب نمی‌دهد",
                        "مقصد این قانون‌ها روی آن پورت گوش نمی‌دهد یا اتصال رله به آن شکست می‌خورد؛ معمولاً قانون پس از جابه‌جایی هنوز به سرور قدیمی اشاره می‌کند. "
                        "فایل DNAT را با تأیید مالک به مقصد درست برگردانید و با nft -c -f آزمایش کنید.",
                        ports=["tcp/%d" % d[0]["port"] for d in dead], rules=[_rule(d[0]) for d in dead],
                        targets=[d[1] for d in dead], not_listening=[_rule(d[0]) for d in dead if d[4] == "not_listening"],
                        refused=[_rule(d[0]) for d in dead if d[4] == "refused"],
                        probe_fail_pct=round(max(_pct(w) for w in probed), 1) if probed else None,
                        probe_samples=sum(w["n"] for w in probed) if probed else 0))
    if unknown and th["on_dnat_unknown_target"]:
        out.append(make(s, "dnat_unknown_target", "info", "قانون DNAT به آدرسی می‌فرستد که سرور این فضای کاری نیست",
                        "اگر این آدرس سرور قدیمی پیش از جابه‌جایی است، کاربران این پورت هنوز به آن می‌روند؛ قانون را درست کنید، "
                        "یا اگر عمدی است (سرور بیرون از پنل) این مورد را تأیید کنید.",
                        ports=["tcp/%d" % r["port"] for r, _ in unknown], rules=[_rule(r) for r, _ in unknown],
                        answering=[_rule(r) for r, v in unknown if v == "good"]))
    return out


def _broken_forwards(servers, rules, win, proven, th, min_samples) -> List[Dict[str, Any]]:
    if not th["on_relay_forward_broken"]:
        return []
    relays = [s for s in servers if s["role"] == "relay"]
    names = {s["id"]: s["alias"] or s["name"] for s in relays}
    location: Dict[int, List[int]] = {}  # forwarded port -> relays that forward it (one location, several relays)
    for s in relays:
        for r in rules.get(s["id"], []):
            if s["id"] not in location.setdefault(r["port"], []):
                location[r["port"]].append(s["id"])
    good_on: Dict[int, List[int]] = {}
    found: List[Tuple[Any, Dict[str, Any], List[int], str]] = []
    for y in relays:
        ip = y["public_ip"]
        if not ip or ":" in ip or status_of(y) != "online":
            continue
        measured_ports, broken = 0, []
        for r in rules.get(y["id"], []):
            if r["to"] == ip or (ip, r["port"]) not in proven:
                continue
            seen = [(x["id"], verdict(win.get((x["id"], ip, r["port"])), th, min_samples)) for x in relays if x["id"] != y["id"]]
            seen = [(xid, v) for xid, v in seen if v is not None]
            if not seen:
                continue
            measured_ports += 1
            bad = [xid for xid, v in seen if v == "bad"]
            if all(v == "good" for _, v in seen):
                good_on.setdefault(r["port"], []).append(y["id"])
            if len(seen) >= 2 and len(bad) == len(seen):
                broken.append((r, bad, "critical"))
            elif len(seen) == 1 and bad:
                broken.append((r, bad, "info"))
        crit = [b for b in broken if b[2] == "critical"]
        if len(crit) >= 2 and len(crit) == measured_ports:
            found.append((y, {"all": True, "rules": [b[0] for b in crit]}, sorted({x for b in crit for x in b[1]}), "critical"))
            broken = [b for b in broken if b[2] != "critical"]
        for r, bad, sev in broken:
            found.append((y, {"all": False, "rules": [r]}, bad, sev))
    out = []
    for y, what, bad, sev in found:
        label = names[y["id"]]
        ports = [r["port"] for r in what["rules"]]
        group = sorted({names[i] for p in ports for i in location.get(p, [])})
        working = sorted({names[i] for p in ports for i in good_on.get(p, []) if i != y["id"]})
        ev = dict(probe="tcp", ports=["tcp/%d" % p for p in ports], rules=[_rule(r) for r in what["rules"]],
                  failed_from=sorted(names[i] for i in bad), failed_from_count=len(bad), location_relays=group,
                  location_relays_count=len(group), working_on=working)
        if what["all"]:
            out.append(make(y, "relay_forward_broken:%d:all" % y["id"], "critical",
                            "هیچ‌کدام از فورواردهای رلهٔ %s از رله‌های دیگر کار نمی‌کند" % label,
                            "رله‌های دیگر با اتصال TCP هم‌نظرند که هیچ پورت فورواردشدهٔ این رله به مقصد نمی‌رسد؛ کاربرانی که DNS به این رله می‌فرستد قطع‌اند. "
                            "ip_forward، جدول DNAT و مسیر رله تا مقصد را بررسی کنید و تا رفع، رله را فقط وقتی از DNS بردارید که هر لوکیشن دو رلهٔ سالم دارد.",
                            **ev))
        elif sev == "critical":
            out.append(make(y, "relay_forward_broken:%d:%d" % (y["id"], ports[0]), "critical",
                            "فوروارد یک پورت لوکیشن روی رلهٔ %s کار نمی‌کند" % label,
                            "رله‌های دیگر با اتصال TCP هم‌نظرند که این پورت از این رله به مقصد نمی‌رسد؛ از اتصال‌های این لوکیشن همان سهمی که DNS به این رله می‌دهد خراب است "
                            "(مثلاً ۵ از ۸). مقصد DNAT این پورت و مسیر رله تا آن را بررسی کنید.",
                            **ev))
        else:
            out.append(make(y, "relay_forward_broken:%d:%d" % (y["id"], ports[0]), "info",
                            "فوروارد یک پورت روی رلهٔ %s فقط از یک رله ناموفق دیده شده (تأیید نشده)" % label,
                            "برای حکم دو رلهٔ سنجنده لازم است؛ با رلهٔ دیگر یا یک تست داده از داخل ایران تأیید کنید.",
                            **ev))
    return out


def issues(db: sqlite3.Connection, ws: int, th: Dict[str, float], servers: List[Any], now: int, min_samples: int) -> List[Dict[str, Any]]:
    reps = {s["id"]: m.report_of(s) for s in servers if s["last_report"]}
    rules = {sid: [r for r in m.dnat_rules(rep) if r["proto"] == "tcp"] for sid, rep in reps.items()}
    if not any(rules.values()):
        return []
    by_ip = {s["public_ip"]: s for s in servers if s["public_ip"]}
    win = probes.port_windows(db, ws, now - WINDOW_S)
    out: List[Dict[str, Any]] = []
    for s in servers:
        if rules.get(s["id"]) and status_of(s) == "online":
            out.extend(_dead_targets(db, ws, s, rules[s["id"]], by_ip, reps, win, th, min_samples))
    out.extend(_broken_forwards(servers, rules, win, probes.proven_ports(db, ws, now), th, min_samples))
    return out
