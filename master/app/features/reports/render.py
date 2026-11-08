from typing import Any, Dict, List

from .common import dur, gb, kv, pct, stamp, table

SEV_MARK = {"critical": "C", "warning": "W", "info": "I"}


def _short(text: str, n: int) -> str:
    return text if len(text) <= n else text[: n - 1] + "…"


def _states(items: List[Dict[str, Any]], key: str) -> str:
    return ", ".join("%s %d/%d/%d" % (g[key], g["online"], g["offline"], g["pending"]) for g in items)


def _flow(t: Dict[str, Any]) -> List[Any]:
    return [gb(t["total"]), gb(t["relay"]), gb(t["exit"]), gb(t["other"])]


def briefing_md(b: Dict[str, Any]) -> str:
    full = b["detail"] == "full"
    f, iss = b["fleet"], b["issues"]
    out = ["# Fleet briefing %s UTC (%s)" % (stamp(b["generated_at"]), b["detail"]),
           "Servers %d: online %d, offline %d, pending %d. Role online/offline/pending: %s. Category: %s." % (
               f["total"], f["online"], f["offline"], f["pending"], _states(f["by_role"], "role"), _states(f["by_category"], "category")),
           "Health bands: %s (failing is below 50 or any hard gate; /api/v1/reports/health)." % ", ".join("%s %d" % kvp for kvp in b["health"]["counts"].items() if kvp[1])]
    out.append("\n## Check first")
    if b["check_first"]:
        for n, s in enumerate(b["check_first"], 1):
            check = s["first_check"] or "see playbook"
            out.append("%d. [%s] %s x%d on %s: %s" % (n, SEV_MARK.get(s["severity"], "I"), s["code"], s["count"], ", ".join(s["servers"]) or "-", check))
    else:
        out.append("No open issues. Spot-check the sections below.")
    out.append("\n## Open issues: critical %d, warning %d, info %d" % (iss["critical"], iss["warning"], iss["info"]))
    for sev in ("critical", "warning", "info"):
        rows = [i for i in iss["items"] if i["severity"] == sev]
        if not rows:
            continue
        out.append("### %s" % sev)
        out.append(table(["server", "code", "evidence", "note"], (
            [i["server"] or "-", i["code"], kv(i["evidence"]) + (" (x%d in 24h)" % i["recent_24h"] if i["recent_24h"] > 1 else ""),
             i["title"] + (" -> " + (i["suggestion"] if full else _short(i["suggestion"], 90)) if i["suggestion"] else "")]
            for i in rows)))
    if iss["truncated"]:
        out.append("(list truncated; detail=full or GET /api/v1/issues for all)")
    if b.get("acknowledged"):
        out.append("\n## Acknowledged by the team (quiet: not counted above, no alerts; undo DELETE /api/v1/issues/ack?key=)")
        out.append(table(["server", "code", "severity", "mode", "until", "by", "note"], (
            [a["server"] or "-", a["code"], a["severity"], a["mode"], stamp(a["until"]) if a["until"] else "-", a["by"] or "-", a["note"] or "-"]
            for a in b["acknowledged"])))
    if b["recurring_24h"]:
        out.append("\n## Recurring in 24h")
        out.append(table(["server", "code", "times", "active", "state"], (
            [r["server"], r["code"], r["occurrences"], dur(r["total_s"]), ("flapping, " if r["flapping"] else "") + ("open now" if r["active_now"] else "closed")]
            for r in b["recurring_24h"])))
    if b["path_problems"]:
        out.append("\n## Path problems (ICMP hypotheses; confirm with data tests from 2 vantage points)")
        out.append(table(["kind", "where", "detail", "from"], ([p["kind"], p["server"], p["detail"], p["source"]] for p in b["path_problems"])))
    h = b["health"]
    if h["attention"]:
        out.append("\n## Health: not healthy")
        out.append(table(["server", "role", "score", "band", "gates", "main penalty"], (
            [a["name"], a["role"], a["score"], a["band"], ",".join(a["gates"]) or "-", a["top_penalty"] or "-"] for a in h["attention"])))
        if h["truncated"]:
            out.append("(more in /api/v1/reports/health)")
    t = b["traffic"]
    out.append("\n## Traffic (NIC rx+tx; relays count each user byte twice; days are Tehran)")
    out.append(table(["window", "total", "relay", "exit", "other"], ([w] + _flow(t[k]) for w, k in (("today", "today"), ("yesterday", "yesterday"), ("7d", "last_7d")))))
    if t["top_servers"]:
        out.append("Top servers 7d: " + ", ".join("%s %s" % (s["server"], gb(s["total"])) for s in t["top_servers"]) + ".")
    if t["pairs_7d"]:
        out.append("Relay-exit pairs 7d (in/out):")
        out.append(table(["server", "peer", "in", "out"], ([p["server"], p["peer"], gb(p["in_bytes"]), gb(p["out_bytes"])] for p in t["pairs_7d"])))
    elif not t["link_counting"]:
        out.append("Pair bytes: counting is off on every server (PATCH /api/v1/servers/{id} acct_on=true).")
    if b["quota"]:
        out.append("\n## Quota (GiB)")
        out.append(table(["server", "used", "of", "pct", "per day", "days left", "resets in"], (
            [q["server_name"], q["used_gb"], q["quota_gb"], pct(q["used_pct"]), q["per_day_gb"] if q["per_day_gb"] is not None else "-",
             q["days_left"] if q["days_left"] is not None else "-", "%sd" % q["resets_in_days"]] for q in b["quota"])))
    if b["certs_at_risk"]:
        out.append("\n## Certificates at risk")
        out.append(table(["name", "server", "days", "level", "auto-renew", "error"], (
            [c["name"], c["server"] or "external", c["days_left"] if c["days_left"] is not None else "-", c["level"], c["auto_renew"], _short(c["error"] or "", 60)] for c in b["certs_at_risk"])))
    if b["agents_outdated"]["servers"]:
        out.append("\nAgents outdated (latest %s): %s." % (b["agents_outdated"]["latest"], ", ".join(b["agents_outdated"]["servers"])))
    out.append("\n## Changes in 24h (%d issue open/close events not listed)" % b["issue_events_24h"])
    if b["changes_24h"]:
        out.append(table(["utc", "server", "kind", "what"], ([stamp(c["ts"])[5:], c["server"] or "-", c["kind"], _short(c["title"], 70)] for c in b["changes_24h"])))
    else:
        out.append("None.")
    out.append("\nNot measured yet: " + "; ".join(b["not_measured"]) + ".")
    out.append("Playbooks: GET /api/v1/reports/playbooks/{code}. Health model: /api/v1/reports/health. "
               "A known issue the team accepts: POST /api/v1/issues/ack {key, mode}.")
    return "\n".join(out) + "\n"


def health_md(h: Dict[str, Any]) -> str:
    out = ["# Health scores %s UTC" % stamp(h["generated_at"]), h["description"], "Counts: " + ", ".join("%s %d" % kvp for kvp in h["counts"].items()), ""]
    out.append(table(["server", "role", "score", "band", "gates", "penalties"], (
        [s["name"], s["role"], s["score"] if s["score"] is not None else "-", s["band"], ",".join(g["key"] for g in s["gates"]) or "-",
         "; ".join("%s -%d (%s)" % (p["key"], p["points"], p["detail"]) for p in s["penalties"]) or "-"] for s in h["servers"])))
    out.append("\nNot measured: " + "; ".join("%s: %s" % (k, ", ".join(v)) for k, v in h["not_measured"].items()) + ".")
    return "\n".join(out) + "\n"


def changes_md(c: Dict[str, Any]) -> str:
    out = ["# Changes %s to %s UTC (%d%s)" % (stamp(c["since"]), stamp(c["until"]), len(c["events"]), "+, truncated" if c["truncated"] else "")]
    out.append(table(["utc", "server", "kind", "what"], ([stamp(e["ts"]), e["server"] or "-", e["kind"], e["title"]] for e in c["events"])))
    return "\n".join(out) + "\n"


def playbook_md(p: Dict[str, Any]) -> str:
    out = ["# Playbook %s [%s] %s" % (p["code"], p["detector"], p["title"]), p["summary_fa"]]
    for label, key in (("Likely causes (in order)", "causes"), ("Read-only checks", "checks"), ("Safe fixes (owner's yes first)", "fixes"), ("Never", "never")):
        out.append("\n## " + label)
        out += ["- " + x for x in p[key]]
    out.append("\nSource: " + "; ".join(p["source"]))
    return "\n".join(out) + "\n"


def playbooks_md(data: Dict[str, Any]) -> str:
    out = ["# Playbooks (%d)" % len(data["playbooks"])] + ["- " + x for x in data["principles"]] + [""]
    out.append(table(["code", "detector", "title"], ([p["code"], p["detector"], p["title"]] for p in data["playbooks"])))
    return "\n".join(out) + "\n"


def daily_md(d: Dict[str, Any]) -> str:
    i, a, t = d["incidents"], d["availability"], d["traffic"]
    out = ["# Daily digest %s to %s UTC" % (stamp(d["since"]), stamp(d["until"])),
           "Incidents opened %d (previous %d), closed %d (previous %d), critical opened %d, still open %d, MTTR %s." % (
               i["opened"], i["previous_opened"], i["closed"], i["previous_closed"], i["critical_opened"], i["still_open"], dur(i["mttr_s"])),
           "Availability fleet %s. Traffic %s (previous %s, change %s); relay %s, exit %s, other %s." % (
               pct(a["fleet_pct"]), gb(t["total"]), gb(t["previous_total"]), pct(t["change_pct"]), gb(t["relay"]), gb(t["exit"]), gb(t["other"])),
           "Health now: " + ", ".join("%s %d" % kvp for kvp in d["health"].items() if kvp[1]) + "."]
    if a["below_100"]:
        out += ["\n## Servers below 100% availability", table(["server", "avail", "down", "outages"], ([x["server"], pct(x["availability_pct"]), dur(x["down_s"]), x["outages"]] for x in a["below_100"]))]
    if d["top_issues"]:
        out += ["\n## Top issues", table(["server", "code", "times", "active", "open now"], ([x["server"], x["code"], x["occurrences"], dur(x["total_s"]), "yes" if x["active_now"] else "no"] for x in d["top_issues"]))]
    out.append("\n## Changes")
    out.append(table(["utc", "server", "kind", "what"], ([stamp(c["ts"]), c["server"] or "-", c["kind"], c["title"]] for c in d["changes"])) if d["changes"] else "None.")
    return "\n".join(out) + "\n"


def incidents_md(r: Dict[str, Any]) -> str:
    t = r["totals"]
    out = ["# Incidents %s to %s UTC" % (stamp(r["since"]), stamp(r["until"])),
           "Opened %d, closed %d, still open %d, critical opened %d, MTTR %s. History is kept %d days." % (t["opened"], t["closed"], t["still_open"], t["critical_opened"], dur(t["mttr_s"]), r["retention_days"])]
    out += ["\n## By code", table(["code", "count", "time active", "resolved", "MTTR"], ([c["code"], c["incidents"], dur(c["total_s"]), c["resolved"], dur(c["mttr_s"])] for c in r["by_code"]))]
    out += ["\n## By server", table(["server", "count", "time active"], ([s["server"], s["incidents"], dur(s["total_s"])] for s in r["by_server"]))]
    if r["flapping"]:
        out += ["\n## Flapping", table(["server", "code", "times"], ([k["server"], k["code"], k["occurrences"]] for k in r["flapping"]))]
    if r["longest"]:
        out += ["\n## Longest", table(["server", "code", "sev", "since", "duration"], ([x["server"] or "-", x["code"], x["severity"], stamp(x["opened_at"]), dur(x["duration_s"])] for x in r["longest"]))]
    if r["truncated"]:
        out.append("(lists truncated)")
    return "\n".join(out) + "\n"


def traffic_md(r: Dict[str, Any]) -> str:
    f = r["fleet"]
    out = ["# Traffic %s to %s UTC" % (stamp(r["since"]), stamp(r["until"])),
           "Fleet %s (rx %s, tx %s): relay %s, exit %s, other %s. %s" % (gb(f["total"]), gb(f["rx"]), gb(f["tx"]), gb(f["relay"]), gb(f["exit"]), gb(f["other"]), r["note"])]
    if r["peak_day"]:
        out.append("Peak day %s %s; peak hour %s UTC %s." % (stamp(r["peak_day"]["day_start"])[:10], gb(r["peak_day"]["bytes"]), stamp(r["peak_hour"]["hour_start"]), gb(r["peak_hour"]["bytes"])))
    out += ["\n## Servers", table(["server", "role", "rx", "tx", "total"], ([s["server"], s["role"], gb(s["rx"]), gb(s["tx"]), gb(s["total"])] for s in r["servers"]))]
    out += ["\n## Days (Tehran)", table(["day", "total"], ([stamp(d["day_start"])[:10], gb(d["total"])] for d in r["daily"]))]
    if r["link_pairs"]:
        out += ["\n## Pairs", table(["server", "peer", "in", "out"], ([p["server"], p["peer"], gb(p["in_bytes"]), gb(p["out_bytes"])] for p in r["link_pairs"]))]
    return "\n".join(out) + "\n"


def availability_md(r: Dict[str, Any]) -> str:
    out = ["# Availability %s to %s UTC: fleet %s" % (stamp(r["since"]), stamp(r["until"]), pct(r["fleet_availability_pct"])), r["method"], ""]
    out.append(table(["server", "role", "avail", "down", "outages", "samples"], ([s["server"], s["role"], pct(s["availability_pct"]), dur(s["down_s"]), s["outages"], s["samples"]] for s in r["servers"])))
    if r["truncated"]:
        out.append("(truncated)")
    return "\n".join(out) + "\n"


def capacity_md(r: Dict[str, Any]) -> str:
    out = ["# Capacity %s to %s UTC" % (stamp(r["since"]), stamp(r["until"])), r["note"], ""]
    out.append(table(["server", "role", "cores", "cpu pk", "peak hr", "steal", "load/core", "conntrack", "ram", "traffic", "growth", "vs siblings"], (
        [s["server"], s["role"], s["cores"] or "-", pct(s["cpu_peak"]), stamp(s["peak_hour"])[5:], pct(s["steal_peak"]), s["load_per_core_peak"] if s["load_per_core_peak"] is not None else "-",
         pct(s["conntrack_peak"]), pct(s["ram_peak"]), gb(s["traffic_bytes"]), pct(s["traffic_growth_pct"]),
         ("%+.0f%s" % (s["vs_sibling_median"], " IMBALANCE" if s["imbalance"] else "")) if s["vs_sibling_median"] is not None else "-"] for s in r["servers"])))
    if r["truncated"]:
        out.append("(truncated)")
    return "\n".join(out) + "\n"


def relays_md(r: Dict[str, Any]) -> str:
    out = ["# Relay-exit paths (last %dm) %s" % (r["ping_window_s"] // 60, "" if r["pairs"] else "no data"), r["note"], ""]
    if r["pairs"]:
        exits = sorted({p["exit"] for p in r["pairs"]})
        relays = sorted({p["relay"] for p in r["pairs"]})
        cellmap = {(p["relay"], p["exit"]): p for p in r["pairs"]}

        def cellf(p: Any) -> str:
            if not p:
                return "-"
            rtt = "" if p["rtt_ms"] is None else " %sms" % p["rtt_ms"]
            return "%s%%%s%s" % (pct(p["loss_pct"]).rstrip("%"), rtt, "" if p["verdict"] == "ok" else " " + p["verdict"])

        out.append(table(["relay \\ exit"] + exits, ([rel] + [cellf(cellmap.get((rel, e))) for e in exits] for rel in relays)))
        pb = [p for p in r["pairs"] if p["in_bytes"] is not None]
        if pb:
            out += ["", "Bytes in window:", table(["relay", "exit", "in", "out"], ([p["relay"], p["exit"], gb(p["in_bytes"]), gb(p["out_bytes"])] for p in pb))]
    return "\n".join(out) + "\n"
