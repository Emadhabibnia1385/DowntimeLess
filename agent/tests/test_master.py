import json
import os
import stat

import pytest

import agent
from fakes import AGENT_KEY, FakeMaster

REPORT_KEYS = {
    "agent_version", "ts", "hostname", "public_ip", "geo", "uptime_s", "cpu_cores", "cpu_pct", "steal_pct", "load1",
    "ram_total_mb", "ram_avail_mb", "disk_total_gb", "disk_used_gb", "net", "tcp_retrans_pct",
    "conntrack_pct", "failed_units", "reboot_required", "ssl", "ping", "jobs_done",
}
GEO = {"country": "DE", "city": "Falkenstein", "org": "Hetzner Online GmbH"}


@pytest.fixture
def master():
    m = FakeMaster()
    yield m
    m.close()


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    monkeypatch.setenv("DL_AGENT_CONFIG", str(tmp_path / "etc" / "agent.json"))
    monkeypatch.setattr(agent, "lookup_geo", lambda: ("203.0.113.5", GEO))
    real_sleep = agent.time.sleep
    monkeypatch.setattr(agent.time, "sleep", lambda s: real_sleep(min(s, 0.01)))


def enroll(master):
    agent.main(["enroll", "--master", master.url + "/", "--token", "T1"])
    return agent.new_state(agent.load_config())


def test_enroll_writes_private_config(master, tmp_path):
    enroll(master)
    path = tmp_path / "etc" / "agent.json"
    assert json.loads(path.read_text()) == {"master": master.url, "agent_key": AGENT_KEY}
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert master.enrolls == [{"token": "T1", "hostname": agent.socket.gethostname()}]


def test_enroll_failure_exits_and_writes_nothing(master, tmp_path):
    master.close()
    with pytest.raises(SystemExit):
        agent.main(["enroll", "--master", master.url, "--token", "T1"])
    assert not (tmp_path / "etc" / "agent.json").exists()


def test_missing_config_is_a_clear_exit():
    with pytest.raises(SystemExit) as e:
        agent.load_config()
    assert "enroll" in str(e.value)


def test_report_round_trip_matches_contract(master):
    st = enroll(master)
    master.responses = [
        {"interval_s": 17, "permission": "none",
         "ping_targets": [{"target": "127.0.0.1", "tcp_port": master.port}],
         "jobs": [{"id": "j1", "kind": "tcp_check", "args": {"target": "127.0.0.1", "port": master.port}},
                  {"id": "j2", "kind": "format_disk", "args": {}},
                  {"id": "j3", "kind": "reboot", "args": {}}]},
        {"interval_s": 30, "permission": "safe", "ping_targets": [], "jobs": []},
    ]
    assert agent.run_cycle(st) == 17
    assert agent.run_cycle(st) == 30
    assert agent.run_cycle(st) == 30

    first, second, third = (r[1] for r in master.reports)
    headers = master.reports[0][0]
    assert headers["X-Agent-Key"] == AGENT_KEY
    assert headers["User-Agent"] == "DowntimeLess-Agent/" + agent.VERSION
    assert headers["Content-Type"] == "application/json"

    for body in (first, second, third):
        assert set(body) == REPORT_KEYS
        assert body["agent_version"] == agent.VERSION
        assert isinstance(body["ts"], int) and isinstance(body["failed_units"], list)
        assert isinstance(body["reboot_required"], bool)
        assert body["public_ip"] == "203.0.113.5" and body["geo"] == GEO
        assert body["net"] is None or set(body["net"]) == {"iface", "rx_bytes", "tx_bytes", "rx_bps", "tx_bps"}
    assert first["jobs_done"] == [] and first["ping"] == []

    # targets from response 1 are probed in report 2, and its jobs are answered there
    (ping,) = second["ping"]
    assert ping["target"] == "127.0.0.1" and ping["loss_pct"] == 0 and ping["rtt_ms"] >= 0
    done = {j["id"]: j for j in second["jobs_done"]}
    assert set(done) == {"j1", "j2", "j3"}
    assert done["j1"]["status"] == "ok" and done["j1"]["result"]["open"] is True and done["j1"]["error"] is None
    assert done["j2"]["status"] == "rejected"
    assert done["j3"]["status"] == "rejected"  # permission was still "none"
    assert set(done["j1"]) == {"id", "status", "result", "error"}

    assert third["jobs_done"] == []  # delivered results are not repeated


def test_permission_from_response_is_remembered(master):
    st = enroll(master)
    assert st["permission"] == "none"
    master.responses = [{"interval_s": 30, "permission": "safe", "ping_targets": [], "jobs": []},
                        {"interval_s": 30, "ping_targets": [], "jobs": []}]
    agent.run_cycle(st)
    assert st["permission"] == "safe"
    agent.run_cycle(st)
    assert st["permission"] == "safe"  # a response without the field keeps the last value


def test_unsent_results_survive_a_failed_report(master):
    st = enroll(master)
    st["jobs_done"] = [{"id": "j9", "status": "ok", "result": {}, "error": None}]
    master.close()
    with pytest.raises(Exception):
        agent.run_cycle(st)
    assert len(st["jobs_done"]) == 1


def test_interval_is_clamped(master):
    st = enroll(master)
    master.responses = [{"interval_s": 1}, {"interval_s": 99999}, {}]
    assert [agent.run_cycle(st) for _ in range(3)] == [5, 600, 30]


def test_wrong_key_is_an_error(master):
    st = enroll(master)
    st["key"] = "nope"
    with pytest.raises(RuntimeError, match="401"):
        agent.run_cycle(st)


def test_loop_backs_off_5_to_60_and_never_crashes(master, monkeypatch):
    enroll(master)
    master.close()
    sleeps = []

    class Stop(Exception):
        pass

    def fake_sleep(s):
        if s != 1:  # build_report's own cpu sampling pause
            sleeps.append(s)
            if len(sleeps) == 6:
                raise Stop

    monkeypatch.setattr(agent.time, "sleep", fake_sleep)
    with pytest.raises(Stop):
        agent.cmd_run(None)
    assert sleeps == [5, 10, 20, 40, 60, 60]


def test_loop_exits_after_reporting_self_update(master, monkeypatch, tmp_path):
    enroll(master)
    target = tmp_path / "agent.py"
    target.write_text("old")
    monkeypatch.setattr(agent, "SELF_PATH", str(target))
    with open(os.path.join(os.path.dirname(agent.__file__), "agent.py"), "rb") as f:
        master.agent_source = f.read()
    cfg = json.loads((tmp_path / "etc" / "agent.json").read_text())
    cfg["permission"] = "full"
    (tmp_path / "etc" / "agent.json").write_text(json.dumps(cfg))
    master.responses = [{"interval_s": 30, "jobs": [{"id": "u1", "kind": "self_update"}]}]
    with pytest.raises(SystemExit) as e:
        agent.cmd_run(None)
    assert e.value.code == 0
    assert target.read_bytes() == master.agent_source
    sent = [d for r in master.reports for d in r[1]["jobs_done"]]
    assert [d["id"] for d in sent] == ["u1"] and sent[0]["status"] == "ok"


def test_once_prints_one_report(capsys, monkeypatch):
    agent.main(["once"])
    body = json.loads(capsys.readouterr().out)
    assert set(body) == REPORT_KEYS


def test_version_subcommand(capsys):
    agent.main(["version"])
    assert capsys.readouterr().out.strip() == agent.VERSION
