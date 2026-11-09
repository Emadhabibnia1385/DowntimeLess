"""The 0.3.0 read-only checks: parsers, collectors on a fake host, cadence, time budget, caps and secret hygiene."""
import json
import os
import re
import subprocess
import threading
import time

import pytest

import agent
import checks_fixtures as cx
from fakes import FakeMaster


class FakeHost:
    """Answers run_check / stream_lines from canned output, records every command and its timeout."""

    def __init__(self, tools=()):
        self.tools = set(tools)
        self.handlers = []
        self.calls = []

    def on(self, prefix, out, code=0):
        self.handlers.append((list(prefix), out, code))
        return self

    def has(self, binary):
        return binary in self.tools

    def run_check(self, argv, timeout=agent.CMD_TIMEOUT_S, ok=(0,), input=None):
        self.calls.append((list(argv), timeout, input))
        assert timeout <= 8, "every command needs a short timeout"
        # the longest matching prefix wins; among equals, the one registered last
        matches = [(len(h[0]), i, h) for i, h in enumerate(self.handlers) if argv[:len(h[0])] == h[0]]
        for _, _, (prefix, out, code) in sorted(matches, reverse=True)[:1]:
            text = out(argv) if callable(out) else out
            if isinstance(text, BaseException):
                raise text
            if code not in ok:
                raise RuntimeError("%s exited %d" % (argv[0], code))
            return code, text
        raise FileNotFoundError(argv[0])

    def stream_lines(self, argv, on_line, timeout, max_bytes=16 << 20, merge_stderr=False):
        code, text = self.run_check(argv, timeout)
        for line in text.splitlines(True):
            on_line(line.encode())
        return code

    def install(self, monkeypatch, files=None):
        monkeypatch.setattr(agent, "has", self.has)
        monkeypatch.setattr(agent, "run_check", self.run_check)
        monkeypatch.setattr(agent, "stream_lines", self.stream_lines)
        if files is not None:
            monkeypatch.setattr(agent, "read", lambda path: files.get(path, ""))
        return self


def argv_names(argv):
    return argv[argv.index("--") + 1:]


def systemd_host():
    return (FakeHost({"systemctl"})
            .on(["systemctl", "list-unit-files"], cx.UNIT_FILES)
            .on(["systemctl", "list-units"], cx.LIST_UNITS)
            .on(["systemctl", "show", "-p", "Id,ActiveState,SubState,NRestarts,UnitFileState"],
                lambda argv: cx.systemctl_show(argv_names(argv)))
            .on(["systemctl", "show", "-p", "Id,LoadState,ActiveState"],
                lambda argv: cx.systemctl_show(argv_names(argv), ("Id", "LoadState", "ActiveState"))))


def docker_host():
    return (FakeHost({"docker"})
            .on(["docker", "ps", "-a"], cx.DOCKER_PS)
            .on(["docker", "ps"], "\n".join(l for l in cx.DOCKER_PS.splitlines() if "\trunning\t" in l) + "\n")
            .on(["docker", "inspect"], cx.DOCKER_INSPECT))


# ---- parsers ----

def test_listeners_are_deduplicated_and_ephemeral_ports_dropped_unless_a_tunnel_owns_them():
    got = agent.parse_ss_listeners(cx.SS_TULNP)
    assert got == [
        {"proto": "tcp", "port": 22, "proc": "sshd", "addr": "0.0.0.0"},
        {"proto": "udp", "port": 53, "proc": "systemd-resolve", "addr": "127.0.0.53"},
        {"proto": "tcp", "port": 80, "proc": "nginx", "addr": "0.0.0.0"},
        {"proto": "tcp", "port": 443, "proc": "backhaul", "addr": "*"},
        {"proto": "udp", "port": 443, "proc": "backhaul", "addr": "0.0.0.0"},
        {"proto": "tcp", "port": 2222, "proc": "sshd", "addr": "0.0.0.0"},
        {"proto": "tcp", "port": 62789, "proc": "xray", "addr": "127.0.0.1"},
    ]
    assert agent.parse_ss_listeners("") == []


def test_listeners_are_capped():
    lines = "".join('tcp LISTEN 0 4096 0.0.0.0:%d 0.0.0.0:* users:(("xray",pid=1,fd=3))\n' % p for p in range(1000, 1500))
    assert len(agent.parse_ss_listeners(lines)) == agent.LIST_MAX


def test_systemctl_parsers():
    assert agent.parse_unit_files(cx.UNIT_FILES)[:3] == ["ssh.service", "backhaul-de1.service", "backpack-bpde.service"]
    assert "wattun@.service" not in agent.parse_unit_files(cx.UNIT_FILES)
    assert ("backpack-bpde.service", "activating", "auto-restart") in agent.parse_list_units(cx.LIST_UNITS)
    blocks = agent.parse_systemctl_show(cx.systemctl_show(["relay-dnat.service", "nope.service"]))
    assert blocks[0]["SubState"] == "dead" and blocks[1]["NRestarts"] == "[not set]"


def test_units_lists_enabled_tunnel_units_and_crash_loops(monkeypatch):
    systemd_host().install(monkeypatch)
    units = {u["name"]: u for u in agent.collect_units({})}
    assert set(units) == {"backhaul-de1.service", "backpack-bpde.service", "relay-dnat.service", "nginx.service",
                          "dl-agent.service", "wattun@nl.service", "myapp.service"}
    assert units["relay-dnat.service"] == {"name": "relay-dnat.service", "enabled": True, "active": "inactive",
                                           "sub": "dead", "restarts": 0}
    assert units["backpack-bpde.service"]["sub"] == "auto-restart" and units["backpack-bpde.service"]["restarts"] == 17
    assert units["myapp.service"]["enabled"] is False  # not ours, but crash-looping
    assert "ssh.service" not in units and "cron.service" not in units


def test_units_and_listeners_are_none_without_the_tools(monkeypatch):
    FakeHost().install(monkeypatch)
    assert agent.collect_units({}) is None and agent.collect_listeners({}) is None
    assert agent.collect_containers({}) is None and agent.collect_nft({}) is None and agent.collect_apt({}) is None


def test_docker_parsers():
    rows = agent.parse_docker_ps(cx.DOCKER_PS)
    assert [r["name"] for r in rows] == ["pasarguard-pasarguard-1", "pasarguard-mysql-1", "node-de", "old-node"]
    assert agent.parse_docker_time("2026-11-08T07:15:02.123456789Z") == 1794122102
    assert agent.parse_docker_time("0001-01-01T00:00:00Z") is None
    assert set(agent.parse_docker_inspect(cx.DOCKER_INSPECT + "not json\n")) == {cx.PANEL_ID, cx.DB_ID, cx.NODE_ID, cx.OLD_ID}
    assert agent.image_tag("pasarguard/node:v0.1.4@sha256:77aa") == "pasarguard/node:v0.1.4"


def test_containers_report_state_restarts_health_and_tag_only(monkeypatch):
    host = docker_host().install(monkeypatch)
    got = {c["name"]: c for c in agent.collect_containers({})}
    assert got["node-de"] == {"name": "node-de", "image": "pasarguard/node:v0.1.4", "state": "running", "status": "Up 2 days",
                              "restarts": 41, "health": "unhealthy", "policy": "unless-stopped", "exit_code": 0,
                              "oom_killed": False, "started_at": 1794186000}
    assert got["old-node"]["exit_code"] == 255 and got["old-node"]["oom_killed"] is True
    assert got["old-node"]["started_at"] is None and "sha256" not in got["old-node"]["image"]
    inspect = [c for c, _, _ in host.calls if c[:2] == ["docker", "inspect"]][0]
    assert "Env" not in inspect[3] and "Cmd" not in inspect[3]  # never asked for, so never held


def test_container_log_counts_only_pasarguard_containers_and_only_numbers(monkeypatch):
    log = ("2026/11/09 10:00:01 Method: SyncUser, Code: Unavailable token=SECRET-in-log\n" * 4 +
           "disconnect automatically due to keep alive timeout\n" +
           "sqlalchemy.exc.TimeoutError: QueuePool limit of size 5 overflow 5 reached\n" * 2 +
           "ssl.SSLCertVerificationError: CERTIFICATE_VERIFY_FAILED IP address mismatch\n")
    host = docker_host().on(["docker", "logs"], log).install(monkeypatch)
    got = agent.collect_container_logs({})
    assert got == [
        {"container": "pasarguard-pasarguard-1", "unavailable": 4, "keepalive": 1, "queuepool": 2, "certfail": 1},
        {"container": "node-de", "unavailable": 4, "keepalive": 1, "queuepool": 2, "certfail": 1},
    ]
    assert all(t == 8 for c, t, _ in host.calls if c[:2] == ["docker", "logs"])
    assert "SECRET" not in json.dumps(got)


def test_nft_tables_relay_dnat_and_rule_count(monkeypatch):
    FakeHost({"nft"}).on(["nft", "list", "tables"], cx.NFT_TABLES).on(["nft", "list", "ruleset"], cx.NFT_RULESET) \
        .install(monkeypatch, {"/proc/sys/net/ipv4/ip_forward": "1\n"})
    got = agent.collect_nft({})
    assert got == {"tables": ["inet filter", "ip relay_dnat", "ip nat", "inet dl_acct"], "relay_dnat": True, "dnat_rules": 3,
                   "dnat_by_table": {"relay_dnat": 2, "nat": 1}, "ip_forward": 1, "dnat_unparsed": 0,
                   "dnat": [{"table": "relay_dnat", "proto": "tcp", "port": 21001, "to": "198.51.100.10", "to_port": 21001},
                            {"table": "relay_dnat", "proto": "tcp", "port": 21002, "to": "10.77.1.2", "to_port": 21002}]}
    assert agent.parse_nft_tables("table ip nat\n")[0] == "ip nat"


def test_dnat_rule_lines_keep_only_plain_one_port_forwards():
    p = agent.parse_dnat_rule
    assert p("tcp dport 19444 counter packets 5 bytes 300 dnat to 159.195.193.165:19444") == ("tcp", 19444, "159.195.193.165", 19444)
    assert p("ip daddr 203.0.113.1 udp dport 53 dnat ip to 198.51.100.9") == ("udp", 53, "198.51.100.9", 53)
    assert p("tcp dport 8000 dnat to 198.51.100.9:80 comment \"old\"") == ("tcp", 8000, "198.51.100.9", 80)
    for odd in ("tcp dport 2000-2010 dnat to 198.51.100.9", "tcp dport { 1, 2 } dnat to 198.51.100.9",
                "tcp dport 443 dnat to numgen random mod 2 map { 0 : 198.51.100.9 }", "tcp dport 443 dnat to 300.1.1.1:443",
                "tcp dport 443 dnat to 198.51.100.9:2000-2010", "tcp dport 70000 dnat to 198.51.100.9", "masquerade"):
        assert p(odd) is None, odd
    by_table, on_line = agent.nft_dnat_counter()
    for line in ("table ip relay_dnat {", "chain pre {", "tcp dport 2000-2010 dnat to 198.51.100.9", "tcp dport 1 dnat to 198.51.100.9"):
        on_line(line.encode())
    assert by_table == {"relay_dnat": 2} and on_line.odd == [1] and len(on_line.rules) == 1


def test_nft_without_relay_table(monkeypatch):
    FakeHost({"nft"}).on(["nft", "list", "tables"], "table inet filter\n").on(["nft", "list", "ruleset"], "table inet filter {\n}\n") \
        .install(monkeypatch, {})
    got = agent.collect_nft({})
    assert got["relay_dnat"] is False and got["dnat_rules"] == 0 and got["ip_forward"] is None


def test_conntrack_live_values_and_counters_summed_across_cpus(monkeypatch):
    base = "/proc/sys/net/netfilter/"
    FakeHost().install(monkeypatch, {base + "nf_conntrack_count": "2588\n", base + "nf_conntrack_max": "262144\n",
                                     base + "nf_conntrack_tcp_timeout_established": "7200\n",
                                     "/proc/net/stat/nf_conntrack": cx.NF_CONNTRACK_STAT})
    assert agent.collect_conntrack({}) == {"module_loaded": True, "count": 2588, "max": 262144, "tcp_established_timeout": 7200,
                                           "insert_failed": 3, "drop": 16, "early_drop": 1}
    assert agent.parse_nf_conntrack_stat("") is None


def test_conntrack_module_not_loaded(monkeypatch):
    FakeHost().install(monkeypatch, {})
    monkeypatch.setattr(agent.os.path, "isdir", lambda p: False)
    got = agent.collect_conntrack({})
    assert got["module_loaded"] is False and got["count"] is None and got["drop"] is None


def test_kernel_parsers():
    assert agent.parse_vmstat(cx.VMSTAT, "oom_kill") == 3
    assert agent.parse_vmstat("", "oom_kill") is None
    assert agent.parse_journal_usage(cx.JOURNAL_USAGE) == 1228.8
    assert agent.parse_journal_usage(cx.JOURNAL_USAGE_OLD) == 56.0
    assert agent.parse_journal_usage("garbage") is None
    assert agent.parse_timedatectl(cx.TIMEDATECTL) is True
    assert agent.parse_timedatectl("no\n") is False and agent.parse_timedatectl("") is None


def test_kernel_baseline(monkeypatch):
    p = "/proc/sys/"
    FakeHost({"timedatectl", "journalctl"}).on(["timedatectl"], cx.TIMEDATECTL).on(["journalctl"], cx.JOURNAL_USAGE) \
        .install(monkeypatch, {p + "net/ipv4/tcp_congestion_control": "bbr\n", p + "net/core/default_qdisc": "fq\n",
                               p + "net/ipv4/tcp_mtu_probing": "0\n", p + "net/ipv4/ip_forward": "1\n",
                               p + "net/ipv4/ip_local_reserved_ports": "443,2053,8443,21001-21010" + ",9" * 200 + "\n",
                               p + "vm/swappiness": "10\n", "/proc/vmstat": cx.VMSTAT,
                               p + "kernel/random/boot_id": "6a1f7a3c-29f4-4d39-9a6e-0d2f3b2e1c11\n"})
    got = agent.collect_kernel({})
    assert got["congestion"] == "bbr" and got["qdisc"] == "fq" and got["mtu_probing"] == 0 and got["ip_forward"] == 1
    assert got["swappiness"] == 10 and got["oom_kill"] == 3 and got["ntp_synced"] is True and got["journal_mb"] == 1228.8
    assert got["boot_id"] == "6a1f7a3c-29f4-4d39-9a6e-0d2f3b2e1c11"
    assert got["reserved_ports"].startswith("443,2053") and len(got["reserved_ports"]) == agent.STR_MAX
    assert isinstance(got["inode_pct"], float)


def test_kernel_survives_missing_tools(monkeypatch):
    FakeHost().install(monkeypatch, {})
    got = agent.collect_kernel({})
    assert got["ntp_synced"] is None and got["journal_mb"] is None and got["congestion"] is None


def test_security_parsers_and_collector(monkeypatch):
    assert agent.parse_ufw_conf(cx.UFW_CONF) == "active"
    assert agent.parse_ufw_conf("ENABLED=no\n") == "inactive"
    assert agent.parse_sshd_password_auth(cx.SSHD_T) is False
    assert agent.parse_sshd_password_auth("passwordauthentication yes\n") is True
    FakeHost({"systemctl", "sshd"}).on(["systemctl", "show", "-p", "LoadState,ActiveState"], "LoadState=loaded\nActiveState=active\n") \
        .on(["sshd", "-T"], cx.SSHD_T).install(monkeypatch, {"/etc/ufw/ufw.conf": cx.UFW_CONF})
    assert agent.collect_security({}) == {"ufw": "active", "fail2ban": "active", "password_auth": False}


def test_security_without_ufw_fail2ban_or_sshd(monkeypatch):
    FakeHost({"systemctl"}).on(["systemctl", "show"], "LoadState=not-found\nActiveState=inactive\n").install(monkeypatch, {})
    assert agent.collect_security({}) == {"ufw": None, "fail2ban": None, "password_auth": None}


def test_apt_audit_holds_and_reboot_packages(monkeypatch):
    FakeHost({"dpkg", "apt-mark"}) \
        .on(["dpkg", "--audit"], "The following packages are only half configured:\n linux-image-6.1.0-27-amd64\n", code=1) \
        .on(["apt-mark", "showhold"], "docker-ce\ncontainerd.io\n") \
        .install(monkeypatch, {"/var/run/reboot-required.pkgs": "linux-base\nlinux-base\nlibc6\n"})
    assert agent.collect_apt({}) == {"dpkg_audit": 2, "held_docker": True, "reboot_required_pkgs": 2}


# ---- tunnels and secret hygiene ----

@pytest.fixture
def tunnel_dirs(tmp_path, monkeypatch):
    files = {"backhaul/de1.toml": cx.BACKHAUL_SERVER, "backhaul/client.toml": cx.BACKHAUL_CLIENT,
             "backhaul/de1.toml.bak-20261101": cx.BACKHAUL_SERVER, "backpack/bpde.toml": cx.BACKPACK_L3,
             "rathole/main.toml": cx.RATHOLE_SERVER, "frp/frpc.toml": cx.FRPC_TOML, "wattun/nl.yml": cx.WATTUN_YML}
    for rel, text in files.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text)
    net = tmp_path / "net"
    for iface, kind, rx, tx in (("bpde", 65534, 1000, 2000), ("gre1", 778, 5, 6), ("eth0", 1, 9, 9)):
        (net / iface / "statistics").mkdir(parents=True)
        (net / iface / "type").write_text("%d\n" % kind)
        (net / iface / "mtu").write_text("1400\n")
        (net / iface / "operstate").write_text("unknown\n")
        (net / iface / "statistics" / "rx_bytes").write_text("%d\n" % rx)
        (net / iface / "statistics" / "tx_bytes").write_text("%d\n" % tx)
    monkeypatch.setattr(agent, "TUNNEL_GLOBS", tuple((k, str(tmp_path / d / pat)) for k, d, pat in (
        ("backhaul", "backhaul", "*.toml"), ("backpack", "backpack", "*.toml"), ("rathole", "rathole", "*.toml"),
        ("frp", "frp", "*.toml"), ("wattun", "wattun", "*.yml"))))
    monkeypatch.setattr(agent, "SYS_NET", str(net))
    cx.UNIT_SHOW["backhaul-client.service"] = ("active", "running", "0", "enabled")
    cx.UNIT_SHOW["wattun@nl.service"] = ("active", "running", "1", "enabled")
    yield tmp_path
    del cx.UNIT_SHOW["backhaul-client.service"]


def test_tunnel_configs_keep_ports_peer_and_iface_only(tunnel_dirs, monkeypatch):
    systemd_host().install(monkeypatch)
    got = agent.collect_tunnels({})
    by = {(t["type"], t["name"]): t for t in got["configs"]}
    assert set(by) == {("backhaul", "de1"), ("backhaul", "client"), ("backpack", "bpde"), ("rathole", "main"),
                       ("frp", "frpc"), ("wattun", "nl")}  # the .bak copy is skipped
    assert by["backhaul", "de1"] == {"name": "de1", "type": "backhaul", "mode": "server", "transport": "tcpmux",
                                     "ports": [443, 2000, 2001, 2002, 2003, 3080, 8443], "peer": None, "iface": None,
                                     "unit": "backhaul-de1.service", "active": "active"}
    assert by["backhaul", "client"]["peer"] == "203.0.113.20:3080" and by["backhaul", "client"]["mode"] == "client"
    assert by["backhaul", "client"]["ports"] == [] and by["backhaul", "client"]["active"] == "active"
    bp = by["backpack", "bpde"]
    assert bp["mode"] == "dial" and bp["transport"] == "xdi" and bp["peer"] == "10.77.1.2" and bp["iface"] == "bpde"
    assert bp["rx_bytes"] == 1000 and bp["tx_bytes"] == 2000 and bp["unit"] == "backpack-bpde.service"
    assert bp["active"] == "activating"
    assert by["rathole", "main"]["ports"] == [2333, 5202] and by["rathole", "main"]["unit"] is None
    assert by["frp", "frpc"]["peer"] == "198.51.100.30" and by["frp", "frpc"]["ports"] == [6443]
    assert by["wattun", "nl"]["peer"] == "198.51.100.40:8443" and by["wattun", "nl"]["unit"] == "wattun@nl.service"
    assert {link["iface"]: link["kind"] for link in got["links"]} == {"bpde": "tun", "gre1": "gre"}
    assert "SECRET" not in json.dumps(got) and "wat1" not in json.dumps(got) and "10.77.1.1/30" not in json.dumps(got)


def test_tunnels_none_when_nothing_is_configured(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "TUNNEL_GLOBS", (("backhaul", str(tmp_path / "*.toml")),))
    monkeypatch.setattr(agent, "SYS_NET", str(tmp_path / "net"))
    assert agent.collect_tunnels({}) is None


def test_config_items_ignore_comments_and_multiline_arrays():
    items = list(agent.config_items('a = "x#y" # c\nports = [\n "1",\n "2" ]\n[s]\nb: 3\n'))
    assert items == [("", "a", '"x#y"'), ("", "ports", '[ "1", "2" ]'), ("s", "b", "3")]
    assert agent.map_ports('["0.0.0.0:443=1.1.1.1:443", 80, "70000"]') == [443, 80]


def test_secret_scrubber():
    for text in ("token=abc123", "password: hunter2", "mysql://u:p@h:3306/db", "x" * 40, "API_KEY = zzz"):
        assert agent.clean_text("before " + text, scrub=True) in ("before [redacted]", "before")
    assert agent.clean_text("failed to listen TCP on 8443", scrub=True) == "failed to listen TCP on 8443"
    assert agent.clean_text(None) is None and len(agent.clean_text("a" * 500)) == agent.STR_MAX


# ---- certificates ----

def test_node_certs_are_listed_apart_with_san_ips(tmp_path, monkeypatch):
    cert = tmp_path / "pg-node-de" / "certs" / "ssl_cert.pem"
    cert.parent.mkdir(parents=True)
    cert.write_text("x")
    monkeypatch.setattr(agent, "NODE_CERT_GLOBS", (str(tmp_path / "*" / "certs" / "ssl_cert.pem"),))
    monkeypatch.setattr(agent, "CERT_GLOBS", (str(tmp_path / "live" / "*" / "cert.pem"),))
    monkeypatch.setattr(agent, "renew_status", lambda: {"certbot_installed": False})
    out = ("notAfter=Feb  4 12:33:37 2027 GMT\nX509v3 Subject Alternative Name:\n"
           "    IP Address:198.51.100.10, IP Address:127.0.0.1, DNS:localhost\n")
    monkeypatch.setattr(agent, "run_text", lambda argv, timeout=10: out if argv[0] == "openssl" else "")
    rep = agent.ssl_report(now=1801744417 - 10 * 86400 - 5)
    assert rep["certs"] == [] and rep["node_certs"] == [{
        "name": "pg-node-de", "source": "pasarguard-node", "not_after": 1801744417, "days_left": 10,
        "ips": ["198.51.100.10", "127.0.0.1"], "domains": ["localhost"]}]


def test_ssl_report_unchanged_without_node_certs(monkeypatch, tmp_path):
    monkeypatch.setattr(agent, "NODE_CERT_GLOBS", (str(tmp_path / "none" / "*.pem"),))
    monkeypatch.setattr(agent, "CERT_GLOBS", ())
    monkeypatch.setattr(agent, "renew_status", lambda: {"certbot_installed": True})
    monkeypatch.setattr(agent, "run_text", lambda argv, timeout=10: "")
    assert set(agent.ssl_report()) == {"certs", "renew", "domains"}


# ---- panel ----

PANEL_EXEC = ["docker", "exec", "-i", "-w", "/code", "pasarguard-pasarguard-1", "python", "-"]


def panel_host():
    return docker_host().on(["docker", "exec", "pasarguard-pasarguard-1", "test"], "", code=0).on(PANEL_EXEC, cx.PANEL_OUTPUT)


def test_panel_script_has_no_write_verbs_and_compiles():
    assert not re.search(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|GRANT|TRUNCATE)\b", agent.PANEL_SCRIPT, re.I)
    assert "READ ONLY" in agent.PANEL_SCRIPT and "statement_timeout" in agent.PANEL_SCRIPT
    assert "max_execution_time" in agent.PANEL_SCRIPT and "query_only" in agent.PANEL_SCRIPT
    assert "`groups`" in agent.PANEL_SCRIPT
    compile(agent.PANEL_SCRIPT, "<panel>", "exec")
    # it prints class names only, never an exception text or the database address
    assert "str(e)" not in agent.PANEL_SCRIPT and "print(db_url" not in agent.PANEL_SCRIPT


def test_panel_discovery_is_none_without_docker_or_without_a_panel(monkeypatch):
    FakeHost().install(monkeypatch)
    assert agent.find_panel_container() is None and agent.collect_panel({}) is None
    FakeHost({"docker"}).on(["docker", "ps"], "abc\tnginx-1\tnginx:1.27\trunning\tUp 1 hour\n").install(monkeypatch)
    assert agent.find_panel_container() is None


def test_panel_discovery_skips_node_and_database_containers(monkeypatch):
    host = panel_host().install(monkeypatch)
    assert agent.find_panel_container() == "pasarguard-pasarguard-1"
    execs = [c for c, _, _ in host.calls if c[:2] == ["docker", "exec"]]
    assert execs == [["docker", "exec", "pasarguard-pasarguard-1", "test", "-d", "/code"]]


def test_panel_without_code_dir_is_not_a_panel(monkeypatch):
    docker_host().on(["docker", "exec"], "", code=1).install(monkeypatch)
    assert agent.find_panel_container() is None


def test_panel_reader_keeps_known_fields_and_drops_every_secret(monkeypatch):
    host = panel_host().install(monkeypatch)
    memo = {}
    got = agent.collect_panel(memo)
    assert got["container"] == "pasarguard-pasarguard-1" and got["version"] == "5.6.0"
    assert got["nodes"][0] == {"id": 1, "name": "de-1", "address": "198.51.100.10", "port": 62050, "status": "connected",
                               "message": None, "keep_alive": 60}
    assert got["nodes"][1]["status"] == "error" and "auth failed" in got["nodes"][1]["message"]
    assert got["usage"] == {"hour_start": 1762646400, "last": [{"node_id": 1, "users": 812, "bytes": 51234567890}],
                            "prev": [{"node_id": 1, "users": 790, "bytes": 49000000000}, {"node_id": 2, "users": 3, "bytes": 1200}]}
    assert got["admins"] == [{"name": "reseller-a", "used": 900000000000, "limit": 1000000000000},
                             {"name": "root", "used": None, "limit": None}]
    assert got["inbounds_without_group"] == ["tunnel-fi"]
    assert got["user_status"] == {"active": 5200, "limited": 40, "expired": 310, "on_hold": 12, "disabled": 7, "other": 2}
    assert got["errors"] == ["admins:OperationalError"]
    dumped = json.dumps(got)
    assert "SECRET" not in dumped and "asyncmy" not in dumped and "hashed" not in dumped and "api_key" not in dumped
    (argv, timeout, stdin), = [c for c in host.calls if c[0][:3] == ["docker", "exec", "-i"]]
    assert timeout == 8 and stdin == agent.PANEL_SCRIPT
    # discovery is cached: a second read does not look for the container again
    agent.collect_panel(memo)
    assert len([c for c, _, _ in host.calls if c[-3:] == ["test", "-d", "/code"]]) == 1


@pytest.mark.parametrize("out,short", [
    ('{"error": "OperationalError"}\n', "OperationalError"),
    ('{"error": "mysql://root:SECRET@db"}\n', "PanelError"),
    ("Traceback (most recent call last):\n  password=SECRET\n", "BadOutput"),
    ("{not json\n", "BadOutput"),
])
def test_panel_errors_are_short_class_names(monkeypatch, out, short):
    panel_host().on(PANEL_EXEC, out).install(monkeypatch)
    monkeypatch.setattr(agent, "COLLECTORS", ())
    st = {}
    agent.start_checks(st)
    fields = agent.checks_fields(st, time.monotonic())
    assert fields["panel_error"] == short and "panel" not in fields and "SECRET" not in json.dumps(fields)


def test_panel_exec_timeout_and_failure(monkeypatch):
    panel_host().on(PANEL_EXEC, subprocess.TimeoutExpired("docker", 8)).install(monkeypatch)
    with pytest.raises(agent.PanelError) as e:
        agent.collect_panel({})
    assert e.value.short == "Timeout"
    panel_host().on(PANEL_EXEC, RuntimeError("docker exited 1")).install(monkeypatch)
    memo = {}
    with pytest.raises(agent.PanelError) as e:
        agent.collect_panel(memo)
    assert e.value.short == "ExecFailed" and memo["found_at"] < 0  # looks for the container again next time


PANEL_PYTHON = os.environ.get("DL_PANEL_PYTHON")  # an interpreter with sqlalchemy + aiosqlite, to run the real script


@pytest.mark.skipif(not PANEL_PYTHON, reason="set DL_PANEL_PYTHON to a python with sqlalchemy and aiosqlite")
def test_panel_script_runs_read_only_against_sqlite(tmp_path):
    import datetime
    import sqlite3
    db = tmp_path / "db.sqlite3"
    c = sqlite3.connect(db)
    hour = datetime.datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    c.executescript("""
        CREATE TABLE nodes (id INTEGER PRIMARY KEY, name TEXT, address TEXT, port INT, status TEXT, message TEXT, keep_alive INT);
        CREATE TABLE node_user_usages (id INTEGER PRIMARY KEY, created_at DATETIME, user_id INT, node_id INT, used_traffic INT);
        CREATE TABLE admins (id INTEGER PRIMARY KEY, username TEXT, hashed_password TEXT, used_traffic INT, data_limit INT);
        CREATE TABLE inbounds (id INTEGER PRIMARY KEY, tag TEXT);
        CREATE TABLE groups (id INTEGER PRIMARY KEY, name TEXT, is_disabled BOOLEAN);
        CREATE TABLE inbounds_groups_association (inbound_id INT, group_id INT);
        CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, status TEXT);
        INSERT INTO nodes VALUES (1, 'de-1', '198.51.100.10', 62050, 'connected', NULL, 60);
        INSERT INTO admins VALUES (1, 'reseller-a', 'SECRET-hash', 900, 1000);
        INSERT INTO inbounds VALUES (1, 'vless-de'), (2, 'tunnel-fi'), (3, 'only-disabled');
        INSERT INTO groups VALUES (1, 'main', 0), (2, 'old', 1);
        INSERT INTO inbounds_groups_association VALUES (1, 1), (3, 2);
        INSERT INTO users VALUES (1, 'a', 'active'), (2, 'b', 'active'), (3, 'c', 'on_hold');
    """)
    one = datetime.timedelta(hours=1)
    rows = [(hour - one, 1, 1, 100), (hour - one, 2, 1, 50), (hour - 2 * one, 1, 1, 7), (hour, 1, 1, 999)]
    c.executemany("INSERT INTO node_user_usages (created_at, user_id, node_id, used_traffic) VALUES (?,?,?,?)",
                  [(t.strftime("%Y-%m-%d %H:%M:%S.000000"), u, n, b) for t, u, n, b in rows])
    c.commit()
    c.close()
    before = db.read_bytes()
    env = dict(os.environ, SQLALCHEMY_DATABASE_URL="sqlite+aiosqlite:///%s" % db)
    r = subprocess.run([PANEL_PYTHON, "-"], input=agent.PANEL_SCRIPT, capture_output=True, text=True, timeout=20, env=env)
    got = agent.parse_panel_output(r.stdout, "pasarguard-pasarguard-1")
    assert got["errors"] == [], r.stdout + r.stderr
    assert got["nodes"][0]["name"] == "de-1" and got["nodes"][0]["keep_alive"] == 60
    assert got["usage"]["last"] == [{"node_id": 1, "users": 2, "bytes": 150}]
    assert got["usage"]["prev"] == [{"node_id": 1, "users": 1, "bytes": 7}]
    assert got["admins"] == [{"name": "reseller-a", "used": 900, "limit": 1000}]
    assert got["inbounds_without_group"] == ["only-disabled", "tunnel-fi"]
    assert got["user_status"]["active"] == 2 and got["user_status"]["on_hold"] == 1
    assert "SECRET" not in r.stdout and str(db) not in r.stdout
    assert db.read_bytes() == before


# ---- runner: cadence, cache, budget, caps ----

class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def counting(name, calls, value=None):
    def fn(memo):
        calls.append(name)
        return value if value is not None else {"n": calls.count(name)}
    return fn


def run_once(st, clock, budget=1.0):
    agent.start_checks(st, clock)
    return agent.finish_checks(st, clock() + budget, clock)


def test_cadence_and_cache_with_a_fake_clock(monkeypatch):
    calls = []
    monkeypatch.setattr(agent, "COLLECTORS", (("fast", counting("fast", calls), 0), ("slow", counting("slow", calls), 60)))
    monkeypatch.setattr(agent, "PANEL_COLLECTOR", ("panel", lambda memo: None, 60))
    clock, st = Clock(), {}
    checks, errors, _, _ = run_once(st, clock)
    assert checks == {"fast": {"n": 1}, "slow": {"n": 1}} and errors == []
    clock.t += 30
    checks, _, _, _ = run_once(st, clock)
    assert checks == {"fast": {"n": 2}, "slow": {"n": 1}}  # slow is served from the cache
    clock.t += 31
    checks, _, _, _ = run_once(st, clock)
    assert checks == {"fast": {"n": 3}, "slow": {"n": 2}}
    assert calls.count("slow") == 2 and calls.count("fast") == 3


def test_a_failing_collector_is_null_and_named(monkeypatch):
    def boom(memo):
        raise ValueError("secret detail token=SECRET")
    monkeypatch.setattr(agent, "COLLECTORS", (("ok", lambda m: [1], 0), ("bad", boom, 60)))
    monkeypatch.setattr(agent, "PANEL_COLLECTOR", ("panel", lambda memo: None, 60))
    checks, errors, panel, panel_error = run_once({}, Clock())
    assert checks == {"ok": [1], "bad": None} and errors == ["bad"] and panel is None and panel_error is None


def test_a_hanging_collector_is_cut_by_the_budget_and_does_not_delay_the_report(monkeypatch):
    release = threading.Event()

    def hang(memo):
        release.wait(10)
        return {"late": True}
    monkeypatch.setattr(agent, "COLLECTORS", (("ok", lambda m: {"fine": 1}, 0), ("hang", hang, 0)))
    monkeypatch.setattr(agent, "PANEL_COLLECTOR", ("panel", lambda memo: None, 60))
    st = {}
    t0 = time.monotonic()
    agent.start_checks(st)
    checks, errors, _, _ = agent.finish_checks(st, t0 + 0.3)
    took = time.monotonic() - t0
    assert took < 1.0
    assert checks == {"ok": {"fine": 1}, "hang": None} and errors == ["hang"]
    # next cycle: still running, so it is not started a second time
    agent.start_checks(st)
    assert agent.finish_checks(st, time.monotonic() + 0.1)[1] == ["hang"]
    release.set()
    time.sleep(0.05)
    checks, errors, _, _ = agent.finish_checks(st, time.monotonic() + 0.5)
    assert checks["hang"] == {"late": True} and errors == []


def test_a_busy_collector_with_a_recent_value_keeps_it(monkeypatch):
    clock, st, gate = Clock(), {}, threading.Event()
    gate.set()

    def slow(memo):
        gate.wait(10)
        return {"v": 1}
    monkeypatch.setattr(agent, "COLLECTORS", (("slow", slow, 60),))
    monkeypatch.setattr(agent, "PANEL_COLLECTOR", ("panel", lambda memo: None, 60))
    assert run_once(st, clock)[0] == {"slow": {"v": 1}}
    gate.clear()
    clock.t += 61
    agent.start_checks(st, clock)
    checks, errors, _, _ = agent.finish_checks(st, time.monotonic() + 0.05, clock)
    assert checks == {"slow": {"v": 1}} and errors == []
    gate.set()


def test_a_stuck_collector_is_given_up_and_restarted(monkeypatch):
    clock, st, gate = Clock(), {}, threading.Event()
    runs = []

    def stuck(memo):
        runs.append(1)
        gate.wait(10)
    monkeypatch.setattr(agent, "COLLECTORS", (("stuck", stuck, 0),))
    monkeypatch.setattr(agent, "PANEL_COLLECTOR", ("panel", lambda memo: None, 60))
    agent.start_checks(st, clock)
    clock.t += agent.STUCK_S + 1
    agent.start_checks(st, clock)
    time.sleep(0.05)
    assert len(runs) == 2
    gate.set()


def test_outputs_are_capped(monkeypatch):
    monkeypatch.setattr(agent, "COLLECTORS", (("big", lambda m: {"items": list(range(1000)), "s": "x" * 1000,
                                                                  "nested": [["y" * 999] * 999]}, 0),))
    monkeypatch.setattr(agent, "PANEL_COLLECTOR", ("panel", lambda memo: {"nodes": [{"n": "z" * 500}] * 900}, 60))
    checks, _, panel, _ = run_once({}, Clock())
    assert len(checks["big"]["items"]) == 300 and len(checks["big"]["s"]) == 200
    assert len(checks["big"]["nested"][0]) == 300 and len(checks["big"]["nested"][0][0]) == 200
    assert len(panel["nodes"]) == 300 and len(panel["nodes"][0]["n"]) == 200


def test_sshd_ports_come_from_the_listeners(monkeypatch):
    monkeypatch.setattr(agent, "COLLECTORS", (("listeners", lambda m: agent.parse_ss_listeners(cx.SS_TULNP), 0),
                                              ("security", lambda m: {"ufw": None}, 300)))
    monkeypatch.setattr(agent, "PANEL_COLLECTOR", ("panel", lambda memo: None, 60))
    checks, _, _, _ = run_once({}, Clock())
    assert checks["security"]["sshd_ports"] == [22, 2222]


def test_real_collectors_on_a_host_without_any_tool_give_none_or_empty_parts(monkeypatch, tmp_path):
    FakeHost().install(monkeypatch, {})
    monkeypatch.setattr(agent, "TUNNEL_GLOBS", ())
    monkeypatch.setattr(agent, "SYS_NET", str(tmp_path))
    monkeypatch.setattr(agent, "SYSCTL_FILES", ())
    checks, errors, panel, panel_error = run_once({}, Clock())
    assert set(checks) == {"listeners", "units", "conntrack", "containers", "nft", "tunnels", "kernel", "security",
                           "container_logs", "apt", "drift", "paths", "tunnel_logs"}
    assert errors == [] and panel is None and panel_error is None
    for name in ("listeners", "units", "containers", "nft", "tunnels", "container_logs", "apt", "drift", "paths", "tunnel_logs"):
        assert checks[name] is None
    assert checks["security"]["sshd_ports"] is None


def test_docker_daemon_down_is_an_error_not_absence(monkeypatch):
    FakeHost({"docker"}).on(["docker"], RuntimeError("docker exited 1")).install(monkeypatch, {})
    monkeypatch.setattr(agent, "COLLECTORS", (("containers", agent.collect_containers, 60),))
    checks, errors, panel, panel_error = run_once({}, Clock())
    assert checks == {"containers": None} and errors == ["containers"]
    assert panel is None and panel_error == "RuntimeError"


# ---- the whole report ----

@pytest.fixture
def master():
    m = FakeMaster()
    yield m
    m.close()


@pytest.fixture
def full_host(tunnel_dirs, monkeypatch):
    host = systemd_host()
    for prefix, out, code in panel_host().handlers:
        host.on(prefix, out, code)
    host.tools |= {"docker", "ss", "nft"}
    host.on(["ss"], cx.SS_TULNP).on(["nft", "list", "tables"], cx.NFT_TABLES).on(["nft", "list", "ruleset"], cx.NFT_RULESET)
    host.on(["docker", "logs"], "Code: Unavailable password=SECRET\n")
    host.install(monkeypatch)
    monkeypatch.setattr(agent, "lookup_geo", lambda ip="": ("203.0.113.5", {"country": "DE", "city": None, "org": None}))
    real_sleep = time.sleep
    monkeypatch.setattr(agent.time, "sleep", lambda s: real_sleep(min(s, 0.01)))
    return host


def test_report_carries_checks_and_panel_and_no_secret(full_host, master):
    st = agent.new_state({"master": master.url, "agent_key": "k-123"})
    master.responses = [{"interval_s": 30}]  # an older master: none of the newer response fields
    assert agent.run_cycle(st) == 30
    body = master.reports[0][1]
    assert body["agent_version"] == agent.VERSION
    assert body["checks"]["nft"]["relay_dnat"] is True and body["checks"]["listeners"][0]["port"] == 22
    assert body["checks"]["container_logs"][0]["unavailable"] == 1
    assert body["panel"]["nodes"][0]["name"] == "de-1" and "panel_error" not in body
    assert body["checks_error"] == []
    dumped = json.dumps(body)
    for leak in ("SECRET", "wat1", "asyncmy", "hashed_password", "api_key"):
        assert leak not in dumped
    # existing fields are unchanged
    for key in ("cpu_pct", "ram_total_mb", "failed_units", "ssl", "ping", "jobs_done", "info", "conntrack_pct"):
        assert key in body


def test_report_without_a_panel_has_no_panel_key(master, monkeypatch):
    monkeypatch.setattr(agent, "lookup_geo", lambda ip="": (None, None))
    real_sleep = time.sleep
    monkeypatch.setattr(agent.time, "sleep", lambda s: real_sleep(min(s, 0.01)))
    st = agent.new_state({"master": master.url, "agent_key": "k-123"})
    agent.run_cycle(st)
    body = master.reports[0][1]
    assert "panel" not in body and "panel_error" not in body and isinstance(body["checks"], dict)


def test_checks_never_hold_the_report_past_the_budget(master, monkeypatch):
    release = threading.Event()
    monkeypatch.setattr(agent, "COLLECTORS", (("hang", lambda m: release.wait(10), 0),))
    monkeypatch.setattr(agent, "CHECKS_BUDGET_S", 0.5)
    monkeypatch.setattr(agent, "lookup_geo", lambda ip="": (None, None))
    real_sleep = time.sleep
    monkeypatch.setattr(agent.time, "sleep", lambda s: real_sleep(min(s, 0.01)))
    st = agent.new_state({"master": master.url, "agent_key": "k-123"})
    t0 = time.monotonic()
    agent.run_cycle(st)
    assert time.monotonic() - t0 < 2.0
    assert master.reports[0][1]["checks_error"] == ["hang"]
    release.set()



def test_a_docker_that_rejects_the_health_template_falls_back_to_the_next_format(monkeypatch):
    # New Docker errors on a missing .State.Health; the agent must try the other templates, never give up
    seen = []
    real = agent.check_out

    def fake(argv, timeout=agent.CMD_TIMEOUT_S, ok=(0,)):
        if argv[:2] == ["docker", "inspect"]:
            seen.append(argv[3])
            if len(seen) == 1:
                raise RuntimeError("template parsing error: map has no entry for key \"Health\"")
            return cx.DOCKER_INSPECT
        if argv[:2] == ["docker", "ps"]:
            return cx.DOCKER_PS
        return real(argv, timeout, ok)

    monkeypatch.setattr(agent, "has", lambda name: True)
    monkeypatch.setattr(agent, "check_out", fake)
    got = {c["name"]: c for c in agent.collect_containers({})}
    assert len(seen) == 2 and seen[0] != seen[1]
    assert got["node-de"]["restarts"] == 41


def test_every_inspect_template_avoids_the_fields_that_hold_secrets():
    for fmt in agent.INSPECT_FORMATS:
        assert ".Config.Env" not in fmt and ".Config.Cmd" not in fmt and ".Args" not in fmt and "Log" not in fmt


def test_a_process_with_hundreds_of_udp_sockets_is_one_summary_row():
    text = "\n".join("udp UNCONN 0 0 *:%d *:* users:((\"xray\",pid=7,fd=%d))" % (2000 + i, i) for i in range(300))
    text += '\ntcp LISTEN 0 4096 0.0.0.0:443 0.0.0.0:* users:(("xray",pid=7,fd=3))\n'
    got = agent.parse_ss_listeners(text)
    assert {"proto": "udp", "port": 0, "proc": "xray", "count": 300} in got
    assert {"proto": "tcp", "port": 443, "proc": "xray", "addr": "0.0.0.0"} in got
    assert len(got) == 2


def test_a_listener_on_loopback_and_on_all_addresses_keeps_the_public_one():
    lines = ('tcp LISTEN 0 4096 127.0.0.1:8443 0.0.0.0:* users:(("xray",pid=1,fd=3))\n'
             'tcp LISTEN 0 4096 [::]:8443 [::]:* users:(("xray",pid=1,fd=4))\n')
    assert agent.parse_ss_listeners(lines) == [{"proto": "tcp", "port": 8443, "proc": "xray", "addr": "[::]"}]


# ---- drift: live state against the files that rebuild it (agent 0.3.3) ----

ACCESS_CONF = '''# nyxon-access
API_TOKEN=s3cr3t-value-that-must-not-leave
TRUSTED_SOURCES="198.51.100.10 198.51.100.11
  203.0.113.0/24 198.51.100.10"  # duplicate counted once
PORTS="443 853"
'''
IPSET_T = "Name: nyxon_trusted\nType: hash:net\nNumber of entries: 2\nName: other\nNumber of entries: 9\n"
DNAT_FILE = "table ip relay_dnat {\n chain pre {\n  tcp dport 21001 counter dnat to 198.51.100.10:21001\n" \
            "  tcp dport 21003 counter dnat to 198.51.100.12:21003\n }\n}\n"
SYSCTL_A = "net.ipv4.ip_forward = 1\nnet.netfilter.nf_conntrack_max=262144\n-net.nope.key = 1\n# c\n"
SYSCTL_B = "net.ipv4.tcp_congestion_control = bbr\n"


def drift_host(monkeypatch, files, exists):
    host = FakeHost({"ipset", "nft"}).on(["ipset", "list", "-t"], IPSET_T).on(["nft", "list", "ruleset"], cx.NFT_RULESET)
    host.install(monkeypatch, files)
    monkeypatch.setattr(agent.os.path, "exists", lambda p: p in exists)
    monkeypatch.setattr(agent.glob, "glob", lambda pat: sorted(p for p in exists if __import__("fnmatch").fnmatch(p, pat)))


def test_drift_counts_access_entries_ipsets_dnat_and_sysctl_without_contents(monkeypatch):
    files = {"/etc/nyxon/access.conf": ACCESS_CONF, "/etc/nftables-relay-dnat.nft": DNAT_FILE,
             "/etc/sysctl.d/99-relay-dnat.conf": SYSCTL_A, "/etc/sysctl.d/98-bbr.conf": SYSCTL_B,
             "/proc/sys/net/ipv4/ip_forward": "1\n", "/proc/sys/net/netfilter/nf_conntrack_max": "65536\n",
             "/proc/sys/net/ipv4/tcp_congestion_control": "bbr\n"}
    exists = set(files) - {"/proc/sys/net/nope/key"}
    drift_host(monkeypatch, files, exists)
    got = agent.collect_drift({})
    [ips] = got["ipset"]
    assert ips["set"] == "nyxon_trusted" and ips["live"] == 2 and ips["file"] == 3 and len(ips["file_hash"]) == 12
    [dn] = got["dnat"]
    assert dn["table"] == "relay_dnat" and dn["live"] == 2 and dn["file_rules"] == 2 and dn["ports"] == [21002, 21003]
    assert dn["live_hash"] != dn["file_hash"]
    sc = got["sysctl"]
    assert sc["checked"] == 4 and sc["absent"] == ["net.nope.key"]
    assert sc["mismatch"] == [{"key": "net.netfilter.nf_conntrack_max", "live": "65536", "file": "262144",
                               "source": "/etc/sysctl.d/99-relay-dnat.conf"}]
    text = json.dumps(got)
    assert "s3cr3t" not in text and "198.51.100" not in text  # counts and hashes, never the list itself


def test_drift_without_tools_or_files_is_empty_not_an_error(monkeypatch):
    drift_host(monkeypatch, {}, set())
    monkeypatch.setattr(agent, "has", lambda b: False)
    assert agent.collect_drift({}) is None


def test_shell_vars_and_ipset_save_parsing():
    assert agent.parse_shell_vars('A=1\nB="x y"\nexport C=\'z\'\n')["C"] == "z"
    assert agent.parse_ipset_save("create s hash:ip\nadd s 1.2.3.4\nadd s 1.2.3.5\ncreate t hash:ip\n") == {"s": 2, "t": 0}


# ---- real-user path quality and tunnel log counts (agent 0.3.3) ----

SS_LISTEN = ("tcp LISTEN 0 4096 0.0.0.0:21001 0.0.0.0:* users:((\"xray\",pid=1,fd=3))\n"
             "tcp LISTEN 0 128 0.0.0.0:22 0.0.0.0:* users:((\"sshd\",pid=2,fd=3))\n"
             "tcp LISTEN 0 4096 *:53671 *:* users:((\"xray\",pid=1,fd=4))\n")
SS_INFO = """0 0 198.51.100.2:21001 203.0.113.1:40001
\t cubic wscale:7,7 rto:204 rtt:100/20 mss:1448 bytes_acked:2000000 segs_out:1000 retrans:0/100
0 0 198.51.100.2:21001 203.0.113.1:40002
\t cubic rtt:300/20 bytes_acked:0 segs_out:1000
0 0 [::ffff:198.51.100.2]:53671 [::ffff:10.77.1.2]:5000
\t cubic rtt:50/5 bytes_acked:500000 segs_out:10
0 0 198.51.100.2:21001 192.0.2.99:1234
\t cubic rtt:900/5 bytes_acked:1000 segs_out:4 retrans:0/2
0 0 198.51.100.2:22 192.0.2.50:5555
\t cubic rtt:9/1 bytes_acked:99999 segs_out:10
0 0 198.51.100.2:45000 203.0.113.1:443
\t cubic rtt:9/1 bytes_acked:99999 segs_out:10
"""


def test_paths_sum_per_listening_port_and_known_peer_and_hide_user_addresses(monkeypatch):
    FakeHost({"ss"}).on(["ss", "-H", "-tulnp"], SS_LISTEN).on(["ss", "-Htin"], SS_INFO).install(monkeypatch, {})
    got = agent.collect_paths({"peers": ["203.0.113.1"]})
    assert got == [
        {"port": 21001, "peer": "203.0.113.1", "conns": 2, "mb_per_conn": 1.0, "rtt_ms": 200.0, "retrans_pct": 5.0},
        {"port": 21001, "peer": "other", "conns": 1, "mb_per_conn": 0.001, "rtt_ms": 900.0, "retrans_pct": 50.0},
        {"port": 53671, "peer": "10.77.1.2", "conns": 1, "mb_per_conn": 0.5, "rtt_ms": 50.0, "retrans_pct": 0.0},
    ]
    assert "192.0.2.99" not in json.dumps(got)  # a user's address never leaves the server


def test_tunnel_logs_count_backpack_signatures_per_active_unit(monkeypatch):
    log = "x handshake did not complete\ny did not answer in 6 attempts\nz did not answer in 6 attempts\nTOKEN=abc\n"
    host = FakeHost({"systemctl", "journalctl"}).on(["systemctl", "list-units"], "backpack-de1.service loaded active running x\n") \
        .on(["journalctl"], log).install(monkeypatch, {})
    got = agent.collect_tunnel_logs({})
    assert got == [{"unit": "backpack-de1.service", "no_answer": 2, "handshake_fail": 1, "wrong_tag": 0}]
    assert all(t <= 8 for _, t, _ in host.calls)
