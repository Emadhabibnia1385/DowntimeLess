"""A realistic 16-server fleet with ten-odd open issues, a week of metrics, incidents and events."""
import json
import time

from app.db import connect
from conftest import make_server, report

RELAYS = ["ir-1", "ir-2", "ir-3", "ir-4", "ir-5"]
EXITS = ["de-1", "de-2", "fi-1", "nl-1", "nl-2", "uk-1", "us-1", "fr-1"]
IPS = {n: "198.51.100.%d" % (i + 10) for i, n in enumerate(EXITS)}
IPS.update({n: "203.0.113.%d" % (i + 10) for i, n in enumerate(RELAYS)})


def seed_fleet(owner):
    now = int(time.time())
    ids, keys = {}, {}
    for name in RELAYS:
        ids[name], keys[name] = make_server(owner, name, "relay")
    for name in EXITS:
        ids[name], keys[name] = make_server(owner, name, "exit")
    ids["panel-1"], keys["panel-1"] = make_server(owner, "panel-1", "panel")
    ids["tools-1"], keys["tools-1"] = make_server(owner, "tools-1", "other")
    ids["new-1"], _ = make_server(owner, "new-1", "exit")  # never reported: pending
    over = {
        "ir-1": dict(conntrack_pct=91.0, cpu_pct=95.0, cpu_cores=2, load1=3.5),
        "ir-3": {}, "nl-1": dict(disk_used_gb=96), "uk-1": dict(ram_avail_mb=60), "us-1": dict(steal_pct=18.0),
        "fr-1": dict(tcp_retrans_pct=7.0), "panel-1": dict(failed_units=["pasarguard.service"]),
        "de-2": dict(reboot_required=True, cpu_pct=92.0),
    }
    for name, key in keys.items():
        extra = dict(over.get(name, {}))
        for _ in range(5):  # the load detectors hold an alert for several reports
            report(owner, key, hostname=name, public_ip=IPS.get(name), agent_version="0.2.8", **extra)
        report(owner, key, hostname=name, public_ip=IPS.get(name), geo={"country": "DE" if name.startswith("de") else "IR" if name.startswith("ir") else "NL"}, agent_version="0.2.8", **extra)
    db = connect()
    db.execute("UPDATE servers SET last_seen=? WHERE id=?", (now - 1000, ids["ir-3"]))  # offline
    certs = [{"name": "panel.example.com", "source": "certbot", "not_after": now + 5 * 86400, "domains": ["panel.example.com"]}]
    rep = json.loads(db.execute("SELECT last_report FROM servers WHERE id=?", (ids["panel-1"],)).fetchone()["last_report"])
    rep["ssl"] = {"certs": certs, "renew": {"certbot_timer_enabled": True, "certbot_timer_active": True}}
    db.execute("UPDATE servers SET last_report=? WHERE id=?", (json.dumps(rep), ids["panel-1"]))
    # pings and TCP probes (port 443, proven) from every online relay to every exit, 8 samples inside the last 10 minutes
    for r in ("ir-1", "ir-2", "ir-4", "ir-5"):
        for e in EXITS:
            loss = 100.0 if e == "de-1" or (e == "fi-1" and r == "ir-2") else 0.0
            for k in range(8):
                db.execute("INSERT INTO pings (server_id, ts, target, loss, rtt) VALUES (?,?,?,?,?)", (ids[r], now - 30 - k * 60, IPS[e], loss, None if loss == 100 else 40.0 + k))
                db.execute("INSERT INTO probes (server_id, ts, target, port, ok, rtt, error) VALUES (?,?,?,?,?,?,?)",
                           (ids[r], now - 30 - k * 60, IPS[e], 443, int(loss == 0), None if loss else 40.0 + k, "timeout" if loss else None))
    for e in EXITS:
        db.execute("INSERT OR REPLACE INTO probe_ports (workspace_id, target, port, last_ok) VALUES (1,?,?,?)", (IPS[e], 443, now))
    # a week of half-hourly metrics
    rows = []
    for name, sid in ids.items():
        if name == "new-1":
            continue
        for k in range(7 * 48):
            ts = now - 120 - k * 1800
            peak = 1 if 16 <= (ts // 3600) % 24 <= 20 else 0
            rows.append((sid, ts, 30 + 40 * peak + (sid % 5), 1.0, 50.0, 40.0, 1000.0, 2000.0, 4_000_000_000, 6_000_000_000, 0.5, 20.0 + 30 * peak, 1.0 + peak, 5.0, 300))
    db.executemany(
        "INSERT INTO metrics (server_id, ts, cpu, steal, ram_pct, disk_pct, rx_bps, tx_bps, rx_delta, tx_delta, retrans, conntrack, load1, swap_pct, conns) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        rows,
    )
    # incident history
    def inc(key, code, name, sev, opened, closed):
        db.execute(
            "INSERT INTO incidents (key, code, server_id, server_name, severity, title, evidence, opened_at, last_seen, closed_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (key, code, ids.get(name), name, sev, "t", "{}", opened, closed or now, closed),
        )
    for n in range(4):
        inc("server:%d:cpu" % ids["de-2"], "cpu", "de-2", "warning", now - 20 * 3600 + n * 3600, now - 20 * 3600 + n * 3600 + 900)
    inc("server:%d:offline" % ids["ir-3"], "offline", "ir-3", "critical", now - 2 * 3600, None)
    inc("server:%d:disk" % ids["nl-1"], "disk", "nl-1", "critical", now - 30 * 3600, now - 26 * 3600)
    # events
    from app.features.reports import events
    events.record(db, 1, "agent_updated", "fr-1: agent 0.2.7 -> 0.2.8", ids["fr-1"], {"old": "0.2.7", "new": "0.2.8"}, ts=now - 3600)
    events.record(db, 1, "rebooted", "ir-2: rebooted (uptime 40s)", ids["ir-2"], ts=now - 7200)
    events.record(db, 1, "job_created", "de-1: reboot", ids["de-1"], {"job_kind": "reboot"}, ts=now - 9000)
    events.record(db, 1, "settings_changed", "settings: cpu_warn", None, {"keys": ["cpu_warn"]}, ts=now - 20000)
    db.close()
    return ids, keys
