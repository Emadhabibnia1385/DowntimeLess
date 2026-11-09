"""One-click fixes: fixed commands only, a pre-check that stops before any change, a backup of the live state."""
import fnmatch
import os

import pytest

import agent


class Host:
    """Stands in for run_cmd: answers by command prefix and records every command."""

    def __init__(self, answers):
        self.answers, self.calls = answers, []

    def __call__(self, argv, timeout=25):
        self.calls.append(list(argv))
        for prefix, out in sorted(self.answers.items(), key=lambda kv: -len(kv[0])):
            if tuple(argv[:len(prefix)]) == prefix:
                return out(argv) if callable(out) else out
        return "", 0

    def ran(self, *prefix):
        return [c for c in self.calls if tuple(c[:len(prefix)]) == prefix]


@pytest.fixture
def box(monkeypatch, tmp_path):
    files = {}
    monkeypatch.setattr(agent, "BACKUP_DIR", str(tmp_path / "bak"))
    monkeypatch.setattr(agent, "read", lambda p: files.get(p, ""))
    monkeypatch.setattr(agent.os.path, "exists", lambda p: p in files or p.startswith(str(tmp_path)))
    monkeypatch.setattr(agent.glob, "glob", lambda pat: sorted(p for p in files if fnmatch.fnmatch(p, pat)))
    monkeypatch.setattr(agent.shutil, "which", lambda b: "/usr/sbin/" + b)

    def install(answers):
        host = Host(answers)
        monkeypatch.setattr(agent, "run_cmd", host)
        return host
    return files, install, tmp_path


def run(kind, args=None):
    return agent.run_job({"id": "f1", "kind": kind, "args": args or {}}, {"permission": "full"})


LOADED = {("systemctl", "show"): ("loaded\n", 0), ("systemctl", "is-active"): ("active\n", 0)}


def test_nft_reload_checks_every_file_then_backs_up_and_restarts_its_unit(box):
    files, install, tmp = box
    files["/etc/nftables-relay-dnat.nft"] = "table ip relay_dnat {}\n"
    host = install({**LOADED, **{("nft", "list"): ("table ip relay_dnat { live }", 0)}})
    res = run("nft_reload")
    assert res["status"] == "ok", res
    assert host.ran("nft", "-c", "-f") == [["nft", "-c", "-f", "/etc/nftables-relay-dnat.nft"]]
    assert host.ran("systemctl", "restart") == [["systemctl", "restart", "--", "relay-dnat.service"]]
    [bak] = res["result"]["backups"]
    assert open(bak).read().startswith("table ip relay_dnat { live }") and oct(os.stat(bak).st_mode)[-3:] == "600"
    assert "relay-dnat.service" in res["result"]["output"] and "nft -f BACKUP" in res["result"]["rollback"]


def test_nft_reload_stops_before_any_change_when_the_syntax_check_fails(box):
    files, install, _ = box
    files["/etc/nftables-relay-dnat.nft"] = "broken"
    files["/etc/nftables-mobin-dnat.nft"] = "ok"
    host = install({**LOADED, **{("nft", "-c", "-f", "/etc/nftables-relay-dnat.nft"): ("Error: syntax error", 1)}})
    res = run("nft_reload")
    assert res["status"] == "error" and "nothing reloaded" in res["error"]
    assert host.ran("systemctl", "restart") == [] and host.ran("nft", "list") == []


@pytest.mark.parametrize("kind", ["nft_reload", "sysctl_apply", "ipset_sync"])
def test_fixes_without_arguments_refuse_any_argument(kind, box):
    _, install, _ = box
    host = install(LOADED)
    res = run(kind, {"file": "/etc/passwd"})
    assert res["status"] == "error" and host.calls == []


def test_sysctl_apply_saves_the_live_values_and_reports_what_changed(box):
    files, install, _ = box
    files["/etc/sysctl.d/99-relay-dnat.conf"] = "net.netfilter.nf_conntrack_max = 262144\nnet.ipv4.ip_forward=1\n"
    files["/proc/sys/net/netfilter/nf_conntrack_max"] = "65536\n"
    files["/proc/sys/net/ipv4/ip_forward"] = "1\n"

    def apply(argv):
        files["/proc/sys/net/netfilter/nf_conntrack_max"] = "262144\n"
        return "", 0
    host = install({("sysctl", "--system"): apply})
    res = run("sysctl_apply")
    assert res["status"] == "ok" and res["result"]["changed"] == ["net.netfilter.nf_conntrack_max"]
    assert res["result"]["still_differ"] == [] and host.calls == [["sysctl", "--system"]]
    assert "net.netfilter.nf_conntrack_max = 65536" in open(res["result"]["backups"][0]).read()


ACCESS = 'TRUSTED_SOURCES="198.51.100.1 198.51.100.2 203.0.113.0/24"\n'


def ipset_host(install, live_before, live_after=None):
    count = [live_before]

    def headers(argv):
        return "Name: nyxon_trusted\nNumber of entries: %d\n" % count[0], 0

    def restart(argv):
        count[0] = live_after if live_after is not None else count[0]
        return "", 0
    return install({**LOADED, **{("ipset", "list"): headers, ("ipset", "save"): ("create nyxon_trusted hash:net", 0),
                                   ("systemctl", "restart"): restart}})


def test_ipset_sync_restarts_the_service_and_checks_the_count(box):
    files, install, _ = box
    files["/etc/nyxon/access.conf"] = ACCESS
    host = ipset_host(install, 1, 3)
    res = run("ipset_sync")
    assert res["status"] == "ok" and res["result"]["equal"] is True
    assert host.ran("systemctl", "restart") == [["systemctl", "restart", "--", "nyxon-access.service"]]
    assert "1 -> 3" in res["result"]["output"] and res["result"]["backups"]


@pytest.mark.parametrize("conf, live", [('TRUSTED_SOURCES=""\n', 0), (ACCESS, 9)])
def test_ipset_sync_refuses_an_empty_or_shrinking_list(box, conf, live):
    files, install, _ = box
    files["/etc/nyxon/access.conf"] = conf
    host = ipset_host(install, live)
    res = run("ipset_sync")
    assert res["status"] == "error" and "pre-check failed" in res["error"] and host.ran("systemctl", "restart") == []


@pytest.mark.parametrize("unit", ["nginx.service", "ssh.service", "backpack-de1", "backpack-x;reboot.service", "$(id).service",
                                  "../backpack-a.service", 5, None])
def test_tunnel_restart_takes_only_a_tunnel_unit_name(box, unit):
    _, install, _ = box
    host = install(LOADED)
    res = run("tunnel_restart", {"unit": unit})
    assert res["status"] == "error" and host.ran("systemctl", "restart") == []


def test_tunnel_restart_refuses_extra_arguments_and_units_this_server_does_not_run(box, monkeypatch):
    _, install, _ = box
    host = install({**LOADED, **{("systemctl", "is-enabled"): ("enabled", 0)}})
    monkeypatch.setattr(agent, "tunnel_units", lambda: {"backpack-de1.service"})
    assert run("tunnel_restart", {"unit": "backpack-de1.service", "cmd": "x"})["status"] == "error"
    assert run("tunnel_restart", {"unit": "backpack-nl9.service"})["status"] == "error"
    res = run("tunnel_restart", {"unit": "backpack-de1.service"})
    assert res["status"] == "ok" and res["result"]["active"] is True
    assert run("tunnel_restart", {"unit": "gre-de1.service"})["status"] == "ok"  # an enabled GRE unit has no config file
    assert host.ran("systemctl", "restart") == [["systemctl", "restart", "--", "backpack-de1.service"],
                                                ["systemctl", "restart", "--", "gre-de1.service"]]


@pytest.mark.parametrize("kind", ["nft_reload", "sysctl_apply", "ipset_sync", "tunnel_restart"])
def test_fixes_are_refused_without_a_permission_level(kind, box):
    _, install, _ = box
    host = install(LOADED)
    res = agent.run_job({"id": "f", "kind": kind, "args": {}}, {"permission": "none"})
    assert res["status"] == "rejected" and host.calls == []
