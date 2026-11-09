import os
import socket
import stat
import time
import types

import pytest

import agent
from fakes import FakeMaster

AGENT_SRC = os.path.join(os.path.dirname(os.path.abspath(agent.__file__)), "agent.py")


@pytest.fixture
def master():
    m = FakeMaster()
    yield m
    m.close()


def state(permission="none", master_url="http://127.0.0.1:9"):
    return agent.new_state({"master": master_url, "agent_key": "k", "permission": permission})


def job(kind, args=None, jid="j1"):
    return {"id": jid, "kind": kind, "args": args or {}}


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class Recorder:
    def __init__(self):
        self.calls = []

    def __call__(self, argv, **kw):
        self.calls.append(argv)

        class Done:
            returncode, stdout, stderr = 0, "", ""
        return Done()


def test_whitelist_is_closed():
    assert set(agent.JOBS) == {"ping", "tcp_check", "speedtest_down", "speedtest_up",
                               "apt_upgrade_safe", "reboot", "self_update", "cert_renew", "cert_delete",
                               "processes", "ports", "disk_usage", "journal", "traceroute", "http_check",
                               "dns_check", "service_restart", "vacuum_logs", "nft_reload", "sysctl_apply", "ipset_sync",
                               "tunnel_restart"}


@pytest.mark.parametrize("kind", ["rm_rf", "shell", "", None, "PING", "ping ", "../reboot"])
def test_unknown_kinds_are_rejected_even_with_full_permission(kind, monkeypatch):
    rec = Recorder()
    monkeypatch.setattr(agent.subprocess, "run", rec)
    res = agent.run_job(job(kind), state("full"))
    assert res["status"] == "rejected"
    assert res["id"] == "j1" and res["result"] == {} and res["error"]
    assert rec.calls == []


@pytest.mark.parametrize("kind", ["apt_upgrade_safe", "reboot"])
@pytest.mark.parametrize("permission", ["none", "readonly", "", "FULL", None])
def test_mutating_jobs_need_safe_or_full(kind, permission, monkeypatch, master):
    rec = Recorder()
    monkeypatch.setattr(agent.subprocess, "run", rec)
    res = agent.run_job(job(kind), state(permission, master.url))
    assert res["status"] == "rejected"
    assert rec.calls == [] and master.requests == []


@pytest.mark.parametrize("permission", ["none", "read", "", None])
def test_self_update_needs_no_permission_level(permission, tmp_path, monkeypatch, master):
    target = tmp_path / "agent.py"
    target.write_text("old")
    monkeypatch.setattr(agent, "SELF_PATH", str(target))
    with open(AGENT_SRC, "rb") as f:
        master.agent_source = f.read()
    res = agent.run_job(job("self_update"), state(permission, master.url))
    assert res["status"] == "ok" and target.read_bytes() == master.agent_source


def test_readonly_jobs_do_not_need_permission(master):
    res = agent.run_job(job("tcp_check", {"target": "127.0.0.1", "port": master.port}), state("none"))
    assert res["status"] == "ok"


@pytest.mark.parametrize("permission", ["safe", "full"])
def test_apt_upgrade_runs_as_transient_unit_without_reboot(permission, monkeypatch):
    rec = Recorder()
    monkeypatch.setattr(agent.subprocess, "run", rec)
    res = agent.run_job(job("apt_upgrade_safe"), state(permission))
    assert res["status"] == "ok" and res["error"] is None
    (argv,) = rec.calls
    assert argv[0] == "systemd-run" and "--unit=dl-apt-upgrade" in argv
    assert "--setenv=DEBIAN_FRONTEND=noninteractive" in argv
    assert "--setenv=NEEDRESTART_MODE=l" in argv
    script = argv[-1]
    assert "--force-confold" in script
    for pkg in ("docker-ce", "docker-ce-cli", "containerd.io", "docker-compose-plugin", "docker-buildx-plugin"):
        assert pkg in script
    assert "apt-mark hold" in script and "reboot" not in script and "shutdown" not in script


def test_reboot_is_scheduled_and_flushes_report_first(monkeypatch):
    rec = Recorder()
    monkeypatch.setattr(agent.subprocess, "run", rec)
    st = state("full")
    res = agent.run_job(job("reboot"), st)
    assert res["status"] == "ok"
    assert rec.calls == [["systemd-run", "--on-active=5", "systemctl", "reboot"]]
    assert st["flush"] is True


def test_failing_systemd_run_is_an_error_not_a_crash(monkeypatch):
    def boom(argv, **kw):
        class Done:
            returncode, stdout, stderr = 1, "", "Unit dl-apt-upgrade.service already exists."
        return Done()
    monkeypatch.setattr(agent.subprocess, "run", boom)
    res = agent.run_job(job("apt_upgrade_safe"), state("safe"))
    assert res["status"] == "error" and "already exists" in res["error"]


def test_self_update_replaces_atomically_and_asks_for_restart(tmp_path, monkeypatch, master):
    target = tmp_path / "agent.py"
    target.write_text("old")
    monkeypatch.setattr(agent, "SELF_PATH", str(target))
    with open(AGENT_SRC, "rb") as f:
        master.agent_source = f.read()
    st = state("safe", master.url)
    res = agent.run_job(job("self_update"), st)
    assert res["status"] == "ok" and res["result"] == {"from": agent.VERSION, "to": agent.VERSION}
    assert target.read_bytes() == master.agent_source
    assert stat.S_IMODE(target.stat().st_mode) == 0o755
    assert st["restart"] and st["flush"]
    assert os.listdir(tmp_path) == ["agent.py"]


@pytest.mark.parametrize("source", [b"def broken(:\n", b"print('not a version')\n", b"import sys; sys.exit(3)\n"])
def test_self_update_refuses_bad_downloads(source, tmp_path, monkeypatch, master):
    target = tmp_path / "agent.py"
    target.write_text("old")
    monkeypatch.setattr(agent, "SELF_PATH", str(target))
    master.agent_source = source
    st = state("full", master.url)
    res = agent.run_job(job("self_update"), st)
    assert res["status"] == "error"
    assert target.read_text() == "old" and os.listdir(tmp_path) == ["agent.py"]
    assert not st["restart"]


def test_tcp_check_open_and_closed(master):
    ok = agent.run_job(job("tcp_check", {"target": "127.0.0.1", "port": master.port}), state())
    assert ok["status"] == "ok" and ok["result"]["open"] is True and ok["result"]["rtt_ms"] >= 0
    closed = agent.run_job(job("tcp_check", {"target": "127.0.0.1", "port": free_port()}), state())
    assert closed["status"] == "ok" and closed["result"] == {"open": False, "rtt_ms": None}


@pytest.mark.parametrize("args", [{}, {"target": "-f", "port": 80}, {"target": "x;reboot", "port": 80},
                                  {"target": "127.0.0.1", "port": 0}, {"target": "127.0.0.1", "port": "80"}])
def test_tcp_check_validates_args(args):
    assert agent.run_job(job("tcp_check", args), state())["status"] == "error"


def test_ping_job_rejects_option_injection(monkeypatch):
    rec = Recorder()
    monkeypatch.setattr(agent.subprocess, "run", rec)
    assert agent.run_job(job("ping", {"target": "-f"}), state())["status"] == "error"
    assert rec.calls == []


def test_ping_job_runs_ping_with_contract_flags(monkeypatch):
    import fixtures as fx

    def fake(argv, **kw):
        assert argv == ["ping", "-c", "5", "-W", "1", "-i", "0.3", "198.51.100.7"]

        class Done:
            returncode, stdout, stderr = 0, fx.PING_OK, ""
        return Done()
    monkeypatch.setattr(agent.subprocess, "run", fake)
    res = agent.run_job(job("ping", {"target": "198.51.100.7"}), state())
    assert res["result"] == {"loss_pct": 0.0, "rtt_ms": 41.2}


def test_speedtests_against_local_server(master):
    down = agent.run_job(job("speedtest_down", {"url": master.url + "/down"}), state())
    assert down["status"] == "ok" and down["result"]["mbps"] > 0
    up = agent.run_job(job("speedtest_up", {"url": master.url + "/up"}), state())
    assert up["status"] == "ok" and up["result"]["mbps"] > 0
    assert master.uploaded == 10 * 1024 * 1024


@pytest.mark.parametrize("kind", ["speedtest_down", "speedtest_up"])
@pytest.mark.parametrize("url", [None, "", "file:///etc/passwd", "ftp://x/y"])
def test_speedtests_only_accept_http_urls(kind, url):
    assert agent.run_job(job(kind, {"url": url}), state())["status"] == "error"


def test_job_exception_becomes_error_status():
    res = agent.run_job(job("tcp_check", None), state())
    assert res["status"] == "error" and res["id"] == "j1"


def test_ping_targets_run_concurrently_and_keep_order(master):
    items = [{"target": "127.0.0.1", "tcp_port": free_port()} for _ in range(9)]
    items.insert(3, {"target": "127.0.0.1", "tcp_port": master.port})
    out = agent.run_pings(items)
    assert [r["loss_pct"] for r in out] == [100.0, 100.0, 100.0, 0.0] + [100.0] * 6
    assert out[3]["rtt_ms"] is not None and out[0]["rtt_ms"] is None


def test_ping_budget_is_enforced(monkeypatch):
    monkeypatch.setattr(agent, "check_target", lambda item: time.sleep(2) or {})
    start = time.monotonic()
    out = agent.run_pings([{"target": "198.51.100.7"}], budget=0.2)
    assert time.monotonic() - start < 1.5
    assert out == [{"target": "198.51.100.7", "loss_pct": 100.0, "rtt_ms": None}]


def test_bad_ping_target_never_reaches_ping(monkeypatch):
    def boom(*a, **kw):
        raise AssertionError("ping must not run")
    monkeypatch.setattr(agent.subprocess, "run", boom)
    assert agent.check_target({"target": "--help"}) == {"target": "--help", "loss_pct": 100.0, "rtt_ms": None}


class CertRecorder:
    def __init__(self, returncode=0):
        self.calls, self.returncode = [], returncode

    def __call__(self, argv, **kw):
        self.calls.append(argv)
        return types.SimpleNamespace(returncode=self.returncode, stdout="Congratulations", stderr="")


@pytest.mark.parametrize("kind,verb", [("cert_renew", "renew"), ("cert_delete", "delete")])
def test_certificate_jobs_call_certbot_for_exactly_that_name(kind, verb, monkeypatch):
    rec = CertRecorder()
    monkeypatch.setattr(agent.subprocess, "run", rec)
    st = state("safe")
    res = agent.run_job(job(kind, {"name": "a.example.com"}), st)
    assert res["status"] == "ok" and rec.calls == [["certbot", verb, "--cert-name", "a.example.com", "--non-interactive"]]
    assert st["ssl"] == (0, None)  # the next report rescans


@pytest.mark.parametrize("bad", ["", "../etc/passwd", "-rf", "a b", "a;ls", "$(id)", "x" * 300, None])
def test_certificate_jobs_refuse_unsafe_names(bad, monkeypatch):
    rec = CertRecorder()
    monkeypatch.setattr(agent.subprocess, "run", rec)
    res = agent.run_job(job("cert_delete", {"name": bad}), state("full"))
    assert res["status"] == "error" and rec.calls == []


@pytest.mark.parametrize("kind", ["cert_renew", "cert_delete"])
@pytest.mark.parametrize("permission", ["none", "read", None])
def test_certificate_jobs_need_safe_or_full(kind, permission, monkeypatch):
    rec = CertRecorder()
    monkeypatch.setattr(agent.subprocess, "run", rec)
    assert agent.run_job(job(kind, {"name": "a.example.com"}), state(permission))["status"] == "rejected"
    assert rec.calls == []


def test_a_failing_certbot_is_an_error_with_its_output(monkeypatch):
    monkeypatch.setattr(agent.subprocess, "run", CertRecorder(returncode=1))
    res = agent.run_job(job("cert_renew", {"name": "a.example.com"}), state("safe"))
    assert res["status"] == "error" and "Congratulations" in res["error"]


@pytest.mark.parametrize("unit", ["", "a b", "x;reboot", "$(id)", "../x", "a" * 101, 5])
def test_service_restart_refuses_odd_unit_names(unit, monkeypatch):
    rec = Recorder()
    monkeypatch.setattr(agent.subprocess, "run", rec)
    res = agent.run_job(job("service_restart", {"unit": unit}), state("full"))
    assert res["status"] == "error" and rec.calls == []


def test_service_restart_runs_systemctl_and_reports_the_state(monkeypatch):
    calls = []

    class Done:
        def __init__(self, out):
            self.returncode, self.stdout, self.stderr = 0, out, ""

    def fake(argv, **kw):
        calls.append(argv)
        return Done("active" if argv[1] == "is-active" else "")

    monkeypatch.setattr(agent.subprocess, "run", fake)
    res = agent.run_job(job("service_restart", {"unit": "nginx.service"}), state("full"))
    assert res["status"] == "ok" and res["result"] == {"output": "nginx.service: active", "active": True}
    assert calls[0] == ["systemctl", "restart", "--", "nginx.service"]


@pytest.mark.parametrize("unit", ["nyxon-access.service", "nyxon-access", "relay-dnat.service", "mobin-dnat", "backpack-de1.service",
                                  "gre-de1", "-Hroot@host", "--root=/x"])
def test_service_restart_leaves_fix_units_to_their_fix_job_and_refuses_options(unit, monkeypatch):
    rec = Recorder()
    monkeypatch.setattr(agent.subprocess, "run", rec)
    res = agent.run_job(job("service_restart", {"unit": unit}), state("full"))
    assert res["status"] == "error" and rec.calls == []


@pytest.mark.parametrize("permission", ["none", "", None])
def test_service_restart_and_log_vacuum_are_refused_without_a_level(permission, monkeypatch):
    rec = Recorder()
    monkeypatch.setattr(agent.subprocess, "run", rec)
    for kind in ("service_restart", "vacuum_logs"):
        res = agent.run_job(job(kind, {"unit": "nginx"}), state(permission))
        assert res["status"] == "rejected"
    assert rec.calls == []


def test_diagnostics_return_text_output(monkeypatch):
    class Done:
        returncode, stdout, stderr = 0, "line1\nline2\n", ""

    monkeypatch.setattr(agent.subprocess, "run", lambda argv, **kw: Done())
    for kind, args in (("processes", {}), ("ports", {}), ("journal", {"unit": "nginx", "lines": 50})):
        res = agent.run_job(job(kind, args), state("none"))
        assert res["status"] == "ok" and res["result"]["output"].startswith("line1"), kind


def test_journal_and_traceroute_check_their_arguments(monkeypatch):
    rec = Recorder()
    monkeypatch.setattr(agent.subprocess, "run", rec)
    assert agent.run_job(job("journal", {"lines": 5}), state("full"))["status"] == "error"
    assert agent.run_job(job("journal", {"lines": 100, "unit": "x;y"}), state("full"))["status"] == "error"
    assert agent.run_job(job("traceroute", {"target": "a b"}), state("full"))["status"] == "error"
    assert agent.run_job(job("dns_check", {"target": "-bad host"}), state("full"))["status"] == "error"
    assert rec.calls == []


def test_dns_check_lists_the_addresses(monkeypatch):
    monkeypatch.setattr(agent.socket, "getaddrinfo", lambda host, port: [(2, 1, 6, "", ("203.0.113.9", 0)), (2, 1, 6, "", ("203.0.113.9", 0))])
    res = agent.run_job(job("dns_check", {"target": "example.test"}), state("none"))
    assert res["result"] == {"output": "203.0.113.9", "count": 1}


def test_a_long_output_is_cut(monkeypatch):
    class Done:
        returncode, stdout, stderr = 0, "x" * 20000, ""

    monkeypatch.setattr(agent.subprocess, "run", lambda argv, **kw: Done())
    out = agent.run_job(job("ports"), state("none"))["result"]["output"]
    assert len(out) < 7000
