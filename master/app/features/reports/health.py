import sqlite3
import time
from typing import Any, Dict, List, Optional

from ..issues import acks
from ..overview import service as overview
from ..servers.service import latest_of, role_of, status_of
from ..settings.router import thresholds
from . import quota as quota_svc
from .common import name_of

HEALTHY_AT, DEGRADED_AT = 80, 50

WEIGHTS = {
    "relay": {"peer_paths": 15, "retrans": 15, "conntrack": 10, "cpu_steal": 8, "quota": 5, "memory": 5, "disk": 10, "units": 5},
    "exit": {"relay_reachability": 25, "retrans": 15, "conntrack": 10, "cpu_steal": 10, "memory": 5, "disk": 10, "units": 5},
    "other": {"conntrack": 10, "cpu_steal": 10, "memory": 10, "disk": 10, "units": 5},
}
# signals the catalog scores that need collectors the agent does not have yet
NOT_MEASURED = {
    "relay": ["reachability_from_abroad", "forward_integrity (listeners, DNAT table)", "per_peer_user_quality", "bandwidth_headroom"],
    "exit": ["listener_completeness", "container_state (node, Xray)", "per_peer_user_quality"],
    "other": ["listeners", "containers"],
}
DESCRIPTION = (
    "100 minus penalties; bands: healthy >= 80, degraded 50-79, failing < 50 or any hard gate. Hard gates: agent offline, "
    "conntrack at the critical threshold, relay with >= 50% loss to every exit, exit with >= 50% loss from every relay (2+ relays), quota exhausted."
)


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
    for w in overview.ping_windows(db, ws):
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
                    _pen(pens, "peer_paths", w["peer_paths"], sum(_loss_tier(p["loss"], th) for p in paths) / len(paths),
                         "%d exits measured, worst loss %.0f%%" % (len(paths), max(p["loss"] or 0 for p in paths)))
                    if all((p["loss"] or 0) >= th["loss_crit"] for p in paths):
                        gates.append({"key": "all_exits_lossy", "detail": "loss >= %d%% to all %d exits" % (th["loss_crit"], len(paths))})
                q = quota_by.get(s["id"])
                if q:
                    if q["used_pct"] >= 100:
                        gates.append({"key": "quota_exhausted", "detail": "%.0f%% of quota used" % q["used_pct"]})
                    elif q["used_pct"] >= 90 or (q["days_left"] is not None and q["days_left"] <= 3):
                        _pen(pens, "quota", w["quota"], 1.0, "quota %.0f%%, days left %s" % (q["used_pct"], q["days_left"]))
                    elif q["used_pct"] >= 75 or (q["days_left"] is not None and q["days_left"] <= 7):
                        _pen(pens, "quota", w["quota"], 0.5, "quota %.0f%%, days left %s" % (q["used_pct"], q["days_left"]))
            elif variant == "exit":
                paths = by_exit.get(s["id"], [])
                if paths:
                    _pen(pens, "relay_reachability", w["relay_reachability"], sum(_loss_tier(p["loss"], th) for p in paths) / len(paths),
                         "%d relays measure it, worst loss %.0f%%" % (len(paths), max(p["loss"] or 0 for p in paths)))
                    if len(paths) >= 2 and all((p["loss"] or 0) >= th["loss_crit"] for p in paths):
                        gates.append({"key": "unreachable_from_all_relays", "detail": "loss >= %d%% from all %d relays" % (th["loss_crit"], len(paths))})
            score = max(0, 100 - sum(p["points"] for p in pens))
        mine = per_server.get(s["id"], [])
        score, gates, pens = acks.screen_health(st, score, gates, pens, acks.health_quiet(mine))
        not_measured = list(NOT_MEASURED[variant])
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
