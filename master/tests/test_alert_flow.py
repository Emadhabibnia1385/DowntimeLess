from app import alerts
from app.db import connect
from app.features.issues import service as svc
from conftest import make_server, report

NOW = 1_800_000_000
HOUR = 3600


def issue(code="cpu", key=None, severity="warning", server_id=None, name="de-1", **evidence):
    return {"id": key or "server:1:" + code, "server_id": server_id, "server_name": name, "code": code, "severity": severity,
            "title": "مصرف <CPU> بالاست", "suggestion": "یک پردازش را ببینید.", "evidence": evidence or {"cpu_pct": 97}}


def step(db, tg, found, now):
    alerts.dispatch(db, tg, svc.record(db, now, found), now)


def sent(tg):
    return [m[1] for m in tg.sent if m[0] == 111 and "ورود" not in m[1]]


def route(owner, rule, to):
    assert owner.put("/api/v1/telegram/routes", json={rule: to}).status_code == 200


def test_open_and_recovery_are_one_message_each(owner, tg):
    route(owner, "cpu", "admins")
    db = connect()
    step(db, tg, [issue()], NOW)
    (msg,) = sent(tg)
    assert msg.startswith("🟠 <b>de-1</b>: مصرف &lt;CPU&gt; بالاست")  # escaped, warning emoji, server name first
    assert "یک پردازش را ببینید." in msg and "<code>cpu_pct=97</code>" in msg
    step(db, tg, [issue()], NOW + 15)
    step(db, tg, [issue()], NOW + 30)
    assert len(sent(tg)) == 1  # a running incident says nothing more
    step(db, tg, [], NOW + 45)
    assert len(sent(tg)) == 1  # still inside the grace period
    step(db, tg, [], NOW + 70)
    done = sent(tg)
    assert len(done) == 2 and done[1].startswith("🟢 <b>de-1</b>") and "برطرف شد" in done[1]
    step(db, tg, [], NOW + 100)
    assert len(sent(tg)) == 2  # the recovery goes out once
    db.close()


def test_a_critical_issue_uses_the_red_emoji(owner, tg):
    route(owner, "disk", "admins")
    db = connect()
    step(db, tg, [issue("disk", severity="critical", disk_pct=97)], NOW)
    assert sent(tg)[0].startswith("🔴")
    db.close()


def test_a_panel_route_sends_nothing_and_lists_only(owner, tg):
    route(owner, "cpu", "panel")
    db = connect()
    step(db, tg, [issue()], NOW)
    step(db, tg, [], NOW + 100)
    assert sent(tg) == []
    assert db.execute("SELECT COUNT(*) FROM incidents").fetchone()[0] == 1  # the incident log still has it
    db.close()


def test_a_channel_route_posts_to_the_channel_not_to_the_admins(owner, tg):
    ch = owner.post("/api/v1/telegram/channels", json={"name": "کانال", "chat_id": "-1009999999"}).json()
    route(owner, "cpu", "channel:%d" % ch["id"])
    db = connect()
    step(db, tg, [issue()], NOW)
    step(db, tg, [], NOW + 100)
    assert sent(tg) == []
    assert [m[0] for m in tg.sent if m[1].startswith(("🟠", "🟢"))] == [-1009999999, -1009999999]
    db.close()


def test_no_recovery_message_when_no_open_message_was_sent(owner, tg):
    route(owner, "cpu", "panel")
    db = connect()
    step(db, tg, [issue()], NOW)
    route(owner, "cpu", "admins")  # chosen while the incident was already running
    step(db, tg, [], NOW + 100)
    assert sent(tg) == []
    db.close()


def test_a_rule_switched_off_neither_opens_nor_recovers(owner, tg):
    route(owner, "cpu", "admins")
    db = connect()
    step(db, tg, [issue()], NOW)
    assert len(sent(tg)) == 1
    owner.put("/api/v1/settings", json={"on_cpu": 0})
    step(db, tg, [], NOW + 100)
    assert len(sent(tg)) == 1
    step(db, tg, [issue(key="server:1:cpu2")], NOW + 200)
    assert len(sent(tg)) == 1
    db.close()


def test_offline_and_ssl_incidents_are_not_sent_twice(owner, tg):
    db = connect()
    step(db, tg, [issue("offline", severity="critical"), issue("ssl_expiry", key="ssl:a", severity="critical")], NOW)
    assert sent(tg) == []  # their own flows in the monitor already tell the admins
    db.close()


def test_issues_without_a_rule_stay_in_the_panel(owner, tg):
    db = connect()
    step(db, tg, [issue("agent_missing", severity="info"), issue("mystery", key="server:1:mystery")], NOW)
    assert sent(tg) == []
    db.close()


def test_rebooted_is_only_sent_for_relays_and_exits(owner, tg):
    relay, _ = make_server(owner, "iran-1", "relay")
    other, _ = make_server(owner, "misc", "other")
    db = connect()
    step(db, tg, [issue("rebooted", key="server:%d:rebooted" % relay, server_id=relay, severity="info"),
                  issue("rebooted", key="server:%d:rebooted" % other, server_id=other, severity="info")], NOW)
    assert len(sent(tg)) == 1 and sent(tg)[0].startswith("🔵")
    db.close()


def test_three_openings_in_an_hour_send_one_unstable_note_then_silence(owner, tg):
    route(owner, "cpu", "admins")
    db = connect()
    t = NOW
    for n in range(2):  # two normal incidents, each with an opening and a recovery message
        step(db, tg, [issue()], t)
        step(db, tg, [], t + 60)
        t += 120
    assert len(sent(tg)) == 4
    step(db, tg, [issue()], t)  # the third opening inside the hour
    notes = sent(tg)
    assert len(notes) == 5 and notes[-1].startswith("🟡") and "ناپایدار" in notes[-1] and "3 بار" in notes[-1]
    step(db, tg, [], t + 60)
    t += 120
    for n in range(3):  # more flapping: nothing at all
        step(db, tg, [issue()], t)
        step(db, tg, [], t + 60)
        t += 120
    assert len(sent(tg)) == 5
    # quiet for an hour: the key is stable again, so the next incident is announced normally
    step(db, tg, [], t + HOUR + 10)
    assert db.execute("SELECT COUNT(*) FROM flapping").fetchone()[0] == 0
    step(db, tg, [issue()], t + HOUR + 100)
    assert len(sent(tg)) == 6 and sent(tg)[-1].startswith("🟠")
    db.close()


def test_two_openings_are_not_flapping_and_other_keys_are_independent(owner, tg):
    route(owner, "cpu", "admins")
    db = connect()
    t = NOW
    for n in range(2):
        step(db, tg, [issue(), issue(key="server:2:cpu", name="de-2")], t)
        step(db, tg, [], t + 60)
        t += 120
    assert len(sent(tg)) == 8 and not any("ناپایدار" in m for m in sent(tg))
    step(db, tg, [issue()], t)  # only de-1 reaches its third opening
    step(db, tg, [issue(key="server:2:cpu", name="de-2")], t + 200)
    assert sum("ناپایدار" in m for m in sent(tg)) == 2
    db.close()


def test_a_long_incident_stays_quiet_and_does_not_count_as_flapping(owner, tg):
    route(owner, "cpu", "admins")
    db = connect()
    for n in range(40):
        step(db, tg, [issue()], NOW + n * 15)
    assert len(sent(tg)) == 1
    db.close()


def test_the_monitor_sweep_sends_the_open_message_once(owner, tg):
    from app.monitor import sweep

    sid, key = make_server(owner)
    report(owner, key, disk_used_gb=96)
    sweep(tg)
    sweep(tg)
    assert [m for m in sent(tg) if "دیسک" in m and m.startswith("🔴")] and sum("دیسک" in m for m in sent(tg)) == 1
    msg = next(m for m in sent(tg) if "دیسک" in m)
    assert "<b>de-1</b>" in msg and "journalctl" in msg and "disk_pct=96.0" in msg


def test_a_new_incident_found_by_the_sweep_respects_a_panel_route(owner, tg):
    from app.monitor import sweep

    sid, key = make_server(owner)
    route(owner, "disk", "panel")
    report(owner, key, disk_used_gb=96)
    sweep(tg)
    assert not any("دیسک" in m for m in sent(tg))


def test_a_failing_dispatch_never_stops_the_sweep(owner, tg, monkeypatch):
    from app import monitor

    def boom(*a, **k):
        raise RuntimeError("x")

    monkeypatch.setattr(monitor.alerts, "dispatch", boom)
    sid, key = make_server(owner)
    report(owner, key)
    owner.app.state.tg = tg
    monitor.sweep(tg)  # must not raise


def _go_quiet(sid):
    import time

    db = connect()
    db.execute("UPDATE servers SET last_seen=? WHERE id=?", (int(time.time()) - 1000, sid))
    db.close()


def test_offline_and_online_messages_follow_the_offline_route(owner, tg):
    from app.monitor import sweep

    ch = owner.post("/api/v1/telegram/channels", json={"name": "کانال", "chat_id": "-1009999999"}).json()
    route(owner, "offline", "channel:%d" % ch["id"])
    sid, key = make_server(owner)
    report(owner, key)
    _go_quiet(sid)
    sweep(tg)
    sweep(tg)
    assert sent(tg) == []  # the incident log does not repeat it to the admins
    assert [m[0] for m in tg.sent if "گزارش نمی‌دهد" in m[1]] == [-1009999999]
    report(owner, key)
    sweep(tg)
    assert [m[0] for m in tg.sent if "آنلاین" in m[1]] == [-1009999999]
    route(owner, "offline", "panel")
    _go_quiet(sid)
    before = len(tg.sent)
    sweep(tg)
    assert len(tg.sent) == before


def test_ssl_alerts_follow_the_ssl_route(owner, tg):
    from app import monitor
    from test_ssl import cert

    ch = owner.post("/api/v1/telegram/channels", json={"name": "کانال", "chat_id": "@ssl_alerts"}).json()
    route(owner, "ssl", "channel:%d" % ch["id"])
    sid, key = make_server(owner)
    report(owner, key, ssl={"certs": [cert("x.example.com", 3)], "renew": {"certbot_installed": True}})
    db = connect()
    monitor._ssl_alerts(db, tg)
    db.close()
    assert [m[0] for m in tg.sent if "x.example.com" in m[1]] == ["@ssl_alerts"]
