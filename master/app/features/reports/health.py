import sqlite3
import time
from typing import Any, Dict, List, Optional

from ..checks import memory as m
from ..checks import service as checks_svc
from ..issues import acks
from ..overview import service as overview
from ..servers.service import latest_of, role_of, status_of
from ..settings.router import thresholds
from . import quota as quota_svc
from .common import name_of

HEALTHY_AT, DEGRADED_AT = 80, 50

WEIGHTS = {
    "relay": {"peer_paths": 15, "retrans": 15, "conntrack": 10, "cpu_steal": 8, "quota": 5, "memory": 5, "disk": 10, "units": 5,
              "forward_integrity": 20, "kernel": 7},
    "exit": {"relay_reachability": 25, "retrans": 15, "conntrack": 10, "cpu_steal": 10, "memory": 5, "disk": 10, "units": 5,
             "listeners": 10, "containers": 7, "kernel": 3},
    "other": {"conntrack": 10, "cpu_steal": 10, "memory": 10, "disk": 10, "units": 5, "listeners": 10, "containers": 10, "kernel": 5,
              "panel_nodes": 10},
}
# signals the catalog scores that need collectors the agent does not have yet
NOT_MEASURED = {
    "relay": ["reachability_from_abroad", "per_peer_user_quality", "bandwidth_headroom"],
    "exit": ["per_peer_user_quality"],
    "other": [],
}
# what a server without `checks` (agent older than 0.3.0, or every collector failed) cannot be scored on
NO_CHECKS = "host checks: listeners, tunnel units, containers, DNAT, live conntrack (agent older than 0.3.0)"
# issue code -> (penalty key per variant, share of its weight); a code listed in GATES also fails the server
CHECK_PENALTIES = {
    "listener_missing": ({"relay": "forward_integrity", "exit": "listeners", "other": "listeners"}, 1.0),
    "dnat_missing": ({"relay": "forward_integrity"}, 1.0),
    "ip_forward_off": ({"relay": "forward_integrity"}, 1.0),
    "unit_stopped": ({"relay": "forward_integrity", "exit": "units", "other": "units"}, 0.6),
    "unit_crashloop": ({"relay": "forward_integrity", "exit": "units", "other": "units"}, 0.4),
    "container_down": ({"relay": "units", "exit": "containers", "other": "containers"}, 1.0),
    "container_restarting": ({"relay": "units", "exit": "containers", "other": "containers"}, 0.5),
    "container_unhealthy": ({"relay": "units", "exit": "containers", "other": "containers"}, 0.4),
    "conntrack_drops": ({"relay": "kernel", "exit": "kernel", "other": "kernel"}, 1.0),
    "conntrack_limits_reset": ({"relay": "kernel", "exit": "kernel", "other": "kernel"}, 0.5),
    "oom_kill": ({"relay": "memory", "exit": "memory", "other": "memory"}, 1.0),
    "node_down": ({"other": "panel_nodes"}, 0.34),
    "node_silent": ({"other": "panel_nodes"}, 0.34),
    "node_usage_drop": ({"other": "panel_nodes"}, 0.15),
    "dnat_dead_target": ({"relay": "forward_integrity", "exit": "units", "other": "units"}, 0.7),
    "relay_forward_broken": ({"relay": "forward_integrity"}, 0.7),
}
# critical issues that are hard gates on a relay: a forward port closed, the DNAT table gone, forwarding off
GATES = {"listener_missing": "forward_port_closed", "dnat_missing": "dnat_missing", "ip_forward_off": "ip_forward_off",
         "dnat_dead_target": "dnat_dead_target", "relay_forward_broken": "forward_broken"}
DESCRIPTION = (
    "100 minus penalties; bands: healthy >= 80, degraded 50-79, failing < 50 or any hard gate. Hard gates: agent offline, "
    "conntrack at the critical threshold, relay whose TCP probes fail >= 50% to every exit, exit whose TCP probes fail >= 50% from every relay "
    "(2+ relays), quota exhausted, "
    "relay with a baseline forward port not listening, its DNAT table gone, ip_forward off, a DNAT rule to a dead destination or a "
    "forward other relays agree is broken (critical issues). Path penalties use TCP "
    "probes to proven ports; a path measured only by ICMP counts for at most 30% of its weight and never gates."
)
ICMP_ONLY_SHARE = 0.3


def band(score: Optional[int], gates: List[Dict[str, Any]]) -> str:
    if score is None:
        return "unknown"
    if gates or score < DEGRADED_AT:
        return "failing"
    return "healthy" if score >= HEALTHY_AT else "degraded"


def _loss_tier(loss: Optional[float], th: Dict[str, float]) -> float:
    if loss is None:
        return 0.0
    if loss >= th["loss_crit"]:
        return 1.0
    if loss >= th["loss_warn"]:
        return 0.6
    return 0.2 if loss >= 2 else 0.0


def _path_tier(p: Dict[str, Any], th: Dict[str, float]) -> float:
    if p.get("tcp_loss") is not None:
        return _loss_tier(p["tcp_loss"], th)
    return _loss_tier(p.get("loss"), th) * ICMP_ONLY_SHARE


def _path_detail(paths: List[Dict[str, Any]], what: str) -> str:
    tcp = [p["tcp_loss"] for p in paths if p.get("tcp_loss") is not None]
    icmp = [p["loss"] for p in paths if p.get("loss") is not None]
    parts = ["%d %s" % (len(paths), what)]
    if tcp:
        parts.append("worst TCP failure %.0f%% (%d by TCP)" % (max(tcp), len(tcp)))
    if icmp:
        parts.append("worst ICMP loss %.0f%%" % max(icmp))
    return ", ".join(parts)


def _all_tcp_dead(paths: List[Dict[str, Any]], th: Dict[str, float]) -> bool:
    return bool(paths) and all(p.get("tcp_loss") is not None and p["tcp_loss"] >= th["loss_crit"] for p in paths)


def variant_of(role: str) -> str:
    return role if role in ("relay", "exit") else "other"


def _pen(out: List[Dict[str, Any]], key: str, weight: int, fraction: float, detail: str) -> None:
    pts = int(weight * min(1.0, fraction) + 0.5)
    if pts > 0:
        out.append({"key": key, "points": pts, "max": weight, "detail": detail})


def _host_penalties(out: List[Dict[str, Any]], lt: Dict[str, Any], w: Dict[str, int], th: Dict[str, float]) -> None:
    if "retrans" in w and lt["tcp_retrans_pct"] is not None:
        r = lt["tcp_retrans_pct"]
        _pen(out, "retrans", w["retrans"], 1.0 if r >= th["retrans_warn"] else 0.4 if r >= 2 else 0, "tcp retransmits %.1f%%" % r)
    ct = lt["conntrack_pct"]
    if ct is not None:
        _pen(out, "conntrack", w["conntrack"], 1.0 if ct >= 70 else 0.5 if ct >= 50 else 0, "conntrack %.1f%%" % ct)
    cpu, steal = lt["cpu_pct"], lt["steal_pct"]
    cores, load = lt.get("cpu_cores"), lt["load1"]
    frac, why = 0.0, []
    if cpu is not None and cpu >= th["cpu_warn"]:
        frac += 0.5
        why.append("cpu %.0f%%" % cpu)
    if steal is not None and steal >= th["steal_warn"]:
        frac += 1.0 if steal >= 40 else 0.75 if steal >= 15 else 0.5
        why.append("steal %.0f%%" % steal)
    if cores and load is not None and load / cores >= 1:
        frac += 0.5 if load / cores >= 2 else 0.25
        why.append("load/core %.1f" % (load / cores))
    if frac:
        _pen(out, "cpu_steal", w["cpu_steal"], frac, ", ".join(why))
    ram, swap = lt["ram_pct"], lt["swap_pct"]
    frac, why = 0.0, []
    if ram is not None and ram >= 80:
        frac += 1.0 if ram >= th["ram_warn"] else 0.4
        why.append("ram %.0f%%" % ram)
    if swap is not None and swap >= 50:
        frac += 0.4
        why.append("swap %.0f%%" % swap)
    if "memory" in w and frac:
        _pen(out, "memory", w["memory"], frac, ", ".join(why))
    disk = lt["disk_pct"]
    if disk is not None and disk >= th["disk_warn"]:
        _pen(out, "disk", w["disk"], 1.0 if disk >= th["disk_crit"] else 0.5, "disk %.0f%%" % disk)
    if lt["failed_units"]:
        _pen(out, "units", w["units"], 1.0, "failed units: %s" % ",".join(lt["failed_units"][:3]))


def _check_penalties(pens: List[Dict[str, Any]], gates: List[Dict[str, Any]], mine: List[Dict[str, Any]], variant: str,
                     w: Dict[str, int]) -> None:
    """Penalties and relay gates from this server's host-check and panel issues."""
    shares: Dict[str, float] = {}
    why: Dict[str, List[str]] = {}
    for i in mine:
        code = i["code"].split(":")[0]
        rule = CHECK_PENALTIES.get(code)
        key = rule[0].get(variant) if rule else None
        if key and key in w:
            shares[key] = shares.get(key, 0.0) + rule[1]
            if code not in why.setdefault(key, []):
                why[key].append(code)
        if variant == "relay" and code in GATES and i["severity"] == "critical":
            gates.append({"key": GATES[code], "detail": i["title"]})
    for key, share in shares.items():
        _pen(pens, key, w[key], share, ", ".join(why[key]))


def compute(db: sqlite3.Connection, ws: int, found: Optional[List[Dict[str, Any]]] = None, now: Optional[int] = None) -> Dict[str, Any]:
    now = now or int(time.time())
    th = thresholds(db, ws)
    found = overview.issues(db, ws) if found is None else found
    per_server: Dict[int, List[Dict[str, Any]]] = {}
    for i in found:
        if i["server_id"] is not None:
            per_server.setdefault(i["server_id"], []).append(i)
    by_relay: Dict[int, List[Dict[str, Any]]] = {}
    by_exit: Dict[int, List[Dict[str, Any]]] = {}
    for w in overview.path_windows(db, ws):
        by_relay.setdefault(w["server_id"], []).append(w)
        by_exit.setdefault(w["to_id"], []).append(w)
    quotas = quota_svc.forecast(db, ws, now)
    quota_by = {q["server_id"]: q for q in quotas or []}
    items: List[Dict[str, Any]] = []
    for s in db.execute("SELECT * FROM servers WHERE workspace_id=? ORDER BY role, name", (ws,)):
        variant = variant_of(s["role"])
        st, w = status_of(s), WEIGHTS[variant]
        gates: List[Dict[str, Any]] = []
        pens: List[Dict[str, Any]] = []
        score: Optional[int]
        if st == "pending":
            score = None
        elif st == "offline":
            gates.append({"key": "agent_offline", "detail": "no report for %ds" % (now - (s["last_seen"] or now))})
            score = 0
        else:
            lt = latest_of(s)
            _host_penalties(pens, lt, w, th)
            if lt["conntrack_pct"] is not None and lt["conntrack_pct"] >= th["conntrack_crit"]:
                gates.append({"key": "conntrack_full", "detail": "conntrack %.1f%%" % lt["conntrack_pct"]})
            if variant == "relay":
                paths = by_relay.get(s["id"], [])
                if paths:
                    _pen(pens, "peer_paths", w["peer_paths"], sum(_path_tier(p, th) for p in paths) / len(paths),
                         _path_detail(paths, "exits measured"))
                    if _all_tcp_dead(paths, th):
                        gates.append({"key": "all_exits_lossy", "detail": "TCP failure >= %d%% to all %d exits" % (th["loss_crit"], len(paths))})
                q = quota_by.get(s["id"])
                if q:
                    free = " (upload free, only download counted)" if q["basis"] == "download" else ""
                    if q["used_pct"] >= 100:
                        gates.append({"key": "quota_exhausted", "detail": "%.0f%% of quota used%s" % (q["used_pct"], free)})
                    elif q["used_pct"] >= 90 or (q["days_left"] is not None and q["days_left"] <= 3):
                        _pen(pens, "quota", w["quota"], 1.0, "quota %.0f%%, days left %s%s" % (q["used_pct"], q["days_left"], free))
                    elif q["used_pct"] >= 75 or (q["days_left"] is not None and q["days_left"] <= 7):
                        _pen(pens, "quota", w["quota"], 0.5, "quota %.0f%%, days left %s%s" % (q["used_pct"], q["days_left"], free))
            elif variant == "exit":
                paths = by_exit.get(s["id"], [])
                if paths:
                    _pen(pens, "relay_reachability", w["relay_reachability"], sum(_path_tier(p, th) for p in paths) / len(paths),
                         _path_detail(paths, "relays measure it"))
                    if len(paths) >= 2 and _all_tcp_dead(paths, th):
                        gates.append({"key": "unreachable_from_all_relays", "detail": "TCP failure >= %d%% from all %d relays" % (th["loss_crit"], len(paths))})
            _check_penalties(pens, gates, per_server.get(s["id"], []), variant, w)
            score = max(0, 100 - sum(p["points"] for p in pens))
        mine = per_server.get(s["id"], [])
        score, gates, pens = acks.screen_health(st, score, gates, pens, acks.health_quiet(mine))
        not_measured = list(NOT_MEASURED[variant])
        if st != "pending" and not checks_svc.has_data(m.report_of(s)):
            not_measured.append(NO_CHECKS)
        if variant == "relay" and s["id"] not in quota_by:
            not_measured.append("quota (not set for this server)")
        items.append({
            "server_id": s["id"], "name": name_of(s), "role": role_of(s),
            "country": s["country"], "category_id": s["category_id"], "status": st, "variant": variant,
            "score": score, "band": band(score, gates), "gates": gates, "penalties": sorted(pens, key=lambda p: -p["points"]),
            "open_issues": len(acks.loud(mine)), "acked_issues": len(acks.acked(mine)), "not_measured": not_measured,
        })
    order = {"failing": 0, "degraded": 1, "healthy": 2, "unknown": 3}
    items.sort(key=lambda i: (order[i["band"]], i["score"] if i["score"] is not None else 101, i["name"]))
    counts = {b: sum(1 for i in items if i["band"] == b) for b in order}
    return {
        "generated_at": now, "counts": counts, "servers": items, "description": DESCRIPTION,
        "weights": WEIGHTS, "not_measured": NOT_MEASURED, "quota_measured": bool(quotas),
    }
