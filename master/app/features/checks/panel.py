"""Phase 3 issues and the read-only view from `panel`: PasarGuard nodes, usage per node, resellers, inbounds.

Only servers whose latest report carries `panel` take part. Reseller names are the owner's customers and appear in
issues; nothing else about a user (no password, no token, no subscription) ever reaches the master."""
import sqlite3
import statistics
from typing import Any, Dict, List, Optional, Tuple

from ..overview.detectors import make
from . import memory as m

GIB = 1024 ** 3
MEDIAN_HOURS = 6
MIN_HOURS = 4  # a median needs at least this many of the previous six hours
MIN_USERS, MIN_BYTES = 10, GIB  # a node quieter than this has no meaningful drop
VERSION_KEEP_S = 86400


def _ratio(last: Optional[int], median: Optional[float]) -> Optional[float]:
    return round(last * 100.0 / median, 1) if last is not None and median else None


def node_rows(db: sqlite3.Connection, ws: int, s, rep: Dict[str, Any], state: Dict[str, Any], th: Dict[str, float],
              ignored: Dict[str, set], ctx: Dict[str, Any], now: int) -> List[Dict[str, Any]]:
    """Every node of the panel with its status, last-hour usage, own median and the signals the rules use."""
    panel = m.panel_of(rep) or {}
    nodes = m.dicts(panel.get("nodes")) or []
    usage = panel.get("usage") if isinstance(panel.get("usage"), dict) else {}
    hour = m.num(usage.get("hour_start"))
    last = {m.num(r.get("node_id")): r for r in m.dicts(usage.get("last")) or [] if m.num(r.get("node_id")) is not None}
    has_last = hour is not None and m.dicts(usage.get("last")) is not None
    hist: Dict[int, List[Tuple[int, int]]] = {}
    if has_last:
        for r in db.execute(
            "SELECT node_id, users, bytes FROM node_usage WHERE workspace_id=? AND server_id=? AND hour>=? AND hour<? ORDER BY hour",
            (ws, s["id"], hour - MEDIAN_HOURS * 3600, hour),
        ):
            hist.setdefault(r["node_id"], []).append((r["users"], r["bytes"]))
    bad = state.get("node_bad_since") if isinstance(state.get("node_bad_since"), dict) else {}
    out = []
    for n in nodes:
        nid = m.num(n.get("id"))
        if nid is None:
            continue
        status = m.node_status(n.get("status"))
        h = hist.get(nid, [])
        med_u = statistics.median(x[0] for x in h) if len(h) >= MIN_HOURS else None
        med_b = statistics.median(x[1] for x in h) if len(h) >= MIN_HOURS else None
        # a node with no usage rows in the last hour carried nobody
        lu = (m.num(last.get(nid, {}).get("users")) or 0) if has_last else None
        lb = (m.num(last.get(nid, {}).get("bytes")) or 0) if has_last else None
        since = m.num(bad.get(str(nid)))
        host = ctx.get("by_ip", {}).get(n.get("address")) if isinstance(n.get("address"), str) else None
        unavailable = None
        if host is not None:
            logs = m.dicts((m.checks_of(host) or {}).get("container_logs"))
            if logs is not None:
                unavailable = max([m.num(x.get("unavailable")) or 0 for x in logs] or [0])
        out.append({
            "id": nid, "name": m.text(n.get("name"), 64) or str(nid), "address": m.text(n.get("address"), 100),
            "port": m.num(n.get("port")), "status": status or "unknown", "message": m.text(n.get("message"), 120),
            "enabled": status != m.NODE_OFF, "ignored": str(nid) in ignored.get("node", set()),
            "users_last": lu, "bytes_last": lb,
            "users_median": round(med_u, 1) if med_u is not None else None,
            "bytes_median": int(med_b) if med_b is not None else None,
            "users_pct": _ratio(lu, med_u) if med_u and med_u >= MIN_USERS else None,
            "bytes_pct": _ratio(lb, med_b) if med_b and med_b >= MIN_BYTES else None,
            "down_s": now - since if since else None, "unavailable_10m": unavailable,
        })
    # a node only counts as dropped while the rest of the panel keeps its usual share (no fleet-wide quiet night)
    for n in out:
        n["dropped"] = False
        mine = [p for p in (n["users_pct"], n["bytes_pct"]) if p is not None]
        if not n["enabled"] or n["ignored"] or not mine or min(mine) >= th["node_drop_pct"]:
            continue
        others = [o for o in out if o is not n and o["enabled"] and not o["ignored"] and o["users_median"] and o["users_median"] >= MIN_USERS]
        if not others:
            continue
        share = sum(o["users_last"] or 0 for o in others) * 100.0 / sum(o["users_median"] for o in others)
        n["others_pct"] = round(share, 1)
        n["dropped"] = share >= th["node_others_pct"]
    return out


def reseller_rows(rep: Dict[str, Any], state: Dict[str, Any], th: Dict[str, float], now: int) -> List[Dict[str, Any]]:
    """Resellers (admins with a data limit): share used, burn over the last hour and hours left at that burn."""
    panel = m.panel_of(rep) or {}
    hist = state.get("admin_used") if isinstance(state.get("admin_used"), dict) else {}
    out = []
    for a in m.dicts(panel.get("admins")) or []:
        name, used, limit = m.text(a.get("name"), 64), m.num(a.get("used")), m.num(a.get("limit"))
        if not name or used is None or not limit or limit <= 0:
            continue
        per_hour = None
        samples = [h for h in hist.get(name) or [] if isinstance(h, list) and len(h) == 2]
        old = [h for h in samples if now - h[0] >= 1800]
        if old:
            start = min(old, key=lambda h: abs(now - h[0] - 3600))
            per_hour = max(0.0, (used - start[1]) * 3600.0 / (now - start[0]))
        left = max(0, limit - used)
        hours = round(left / per_hour, 1) if per_hour else None
        pct = round(used * 100.0 / limit, 1)
        level = "ok"
        if pct >= th["reseller_crit"] or (hours is not None and hours <= th["reseller_hours"]):
            level = "critical"
        elif pct >= th["reseller_warn"]:
            level = "warning"
        out.append({"name": name, "used": used, "limit": limit, "used_pct": pct,
                    "per_hour": int(per_hour) if per_hour is not None else None, "hours_left": hours if left else 0.0, "level": level})
    return sorted(out, key=lambda r: -r["used_pct"])


def issues(db, ws, s, th, rep, state, ignored, ctx, now) -> List[Dict[str, Any]]:
    panel = m.panel_of(rep)
    out: List[Dict[str, Any]] = []
    error = rep.get("panel_error") if isinstance(rep.get("panel_error"), str) else None
    if panel is None:
        if th["on_panel_errors"] and error:
            out.append(make(s, "panel_errors", "info", "خواندن پنل PasarGuard ناموفق بود",
                            "agent پنل را پیدا کرد ولی نتوانست آن را بخواند؛ کانتینر پنل و docker logs آن را ببینید.", errors=[error]))
        return out
    for n in node_rows(db, ws, s, rep, state, th, ignored, ctx, now):
        if not n["enabled"] or n["ignored"]:
            continue
        ev = {"node": n["name"], "address": n["address"], "status": n["status"]}
        if n["down_s"] is not None and n["down_s"] >= th["node_down_min"] * 60:
            if th["on_node_down"]:
                out.append(make(s, "node_down:%d" % n["id"], "critical", "نود %s در پنل وصل نیست" % n["name"],
                                "پیام نود در پنل و مسیر پنل تا نود (پورت API) را بررسی کنید؛ با تأیید مالک نود را با همان آدرس و پورت دوباره ذخیره کنید.",
                                message=n["message"], down_s=n["down_s"], **ev))
            continue
        if n["status"] != m.NODE_OK:
            continue
        logs = n["unavailable_10m"] is not None and n["unavailable_10m"] >= th["node_unavailable"]
        collapse = n["dropped"] and min(p for p in (n["users_pct"], n["bytes_pct"]) if p is not None) < th["node_drop_pct"] / 2
        usage_ev = {"users_last_hour": n["users_last"], "users_median": n["users_median"], "users_pct": n["users_pct"],
                    "bytes_pct": n["bytes_pct"], "others_pct": n.get("others_pct")}
        if th["on_node_silent"] and (logs or collapse):
            out.append(make(s, "node_silent:%d" % n["id"], "critical", "نود %s «وصل» است ولی Xray متوقف شده" % n["name"],
                            "به وضعیت connected اعتماد نکنید: روی خود نود ss -ltn پورت‌های اینباند را ببینید و با تأیید مالک نود را دوباره ذخیره کنید تا Xray برگردد.",
                            reason=[r for r, on in (("logs", logs), ("usage", collapse)) if on], unavailable_10m=n["unavailable_10m"],
                            **usage_ev, **ev))
            continue
        if th["on_node_usage_drop"] and n["dropped"]:
            out.append(make(s, "node_usage_drop:%d" % n["id"], "critical" if collapse else "warning",
                            "مصرف نود %s در ساعت گذشته ناگهان افت کرد" % n["name"],
                            "بقیهٔ نودها عادی‌اند؛ مسیر رله‌ها تا این نود، لیسنرهای اینباند و DNS لوکیشن آن را بررسی کنید.", **usage_ev, **ev))
    tags = [t for t in panel.get("inbounds_without_group") or [] if isinstance(t, str) and t not in ignored.get("inbound", set())]
    if th["on_inbound_without_group"] and tags:
        out.append(make(s, "inbound_without_group", "warning", "اینباندی در هیچ گروهی نیست و به هیچ کاربری نمی‌رسد",
                        "با مالک تأیید کنید این اینباند باید در کدام گروه‌ها باشد؛ اگر عمداً بی‌گروه است آن را در صفحهٔ پنل PasarGuard علامت بزنید.",
                        inbounds=sorted(tags)[:30]))
    if th["on_reseller_quota"]:
        for r in reseller_rows(rep, state, th, now):
            if r["level"] == "ok":
                continue
            out.append(make(s, "reseller_quota:%s" % r["name"], r["level"],
                            ("حجم نماینده %s تمام شده" if r["used"] >= r["limit"] else "حجم نماینده %s رو به پایان است") % r["name"],
                            "پیش از تمام شدن به نماینده خبر بدهید یا سقفش را بالا ببرید؛ با disconnect_users_when_limited همهٔ کاربرانش یک‌جا قطع می‌شوند.",
                            reseller=r["name"], used_pct=r["used_pct"], used_gb=round(r["used"] / GIB, 1), limit_gb=round(r["limit"] / GIB, 1),
                            per_hour_gb=round(r["per_hour"] / GIB, 2) if r["per_hour"] is not None else None, hours_left=r["hours_left"]))
    changed = state.get("version_changed") if isinstance(state.get("version_changed"), dict) else None
    if th["on_panel_version_changed"] and changed and now - (m.num(changed.get("at")) or 0) <= VERSION_KEEP_S:
        out.append(make(s, "panel_version_changed", "info", "نسخهٔ پنل PasarGuard عوض شد",
                        "تعداد نودهای connected را با پیش از به‌روزرسانی مقایسه کنید و پیش از اجرای اسکریپت‌های پنل یک فراخوانی فقط‌خواندنی API بزنید.",
                        old_version=m.text(changed.get("old"), 40), new_version=m.text(changed.get("new"), 40)))
    errors = [e for e in panel.get("errors") or [] if isinstance(e, str)][:10]
    if th["on_panel_errors"] and errors:
        out.append(make(s, "panel_errors", "info", "بخشی از اطلاعات پنل PasarGuard خوانده نشد",
                        "نسخهٔ پنل ممکن است ستون یا جدولی را نداشته باشد؛ بقیهٔ اطلاعات معتبر است و این فقط برای پیگیری است.",
                        errors=errors))
    return out


def view(db: sqlite3.Connection, ws: int, s, th, rep, state, ignored, ctx, now) -> Dict[str, Any]:
    panel = m.panel_of(rep) or {}
    status = panel.get("user_status") if isinstance(panel.get("user_status"), dict) else None
    usage = panel.get("usage") if isinstance(panel.get("usage"), dict) else {}
    return {
        "server_id": s["id"], "server_name": s["alias"] or s["name"], "reported_at": s["last_seen"],
        "version": m.text(panel.get("version"), 40), "errors": [e for e in panel.get("errors") or [] if isinstance(e, str)][:10],
        "panel_error": rep.get("panel_error") if isinstance(rep.get("panel_error"), str) else None,
        "available": bool(panel),
        "hour_start": m.num(usage.get("hour_start")),
        "nodes": node_rows(db, ws, s, rep, state, th, ignored, ctx, now) if panel else [],
        "resellers": reseller_rows(rep, state, th, now) if panel else [],
        "user_status": {k: m.num(v) or 0 for k, v in status.items() if m.num(v) is not None} if status else None,
        "inbounds_without_group": [{"tag": t, "ignored": t in ignored.get("inbound", set())}
                                   for t in panel.get("inbounds_without_group") or [] if isinstance(t, str)],
    }
