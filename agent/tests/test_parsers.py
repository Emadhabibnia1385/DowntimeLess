import agent
import fixtures as fx


def test_cpu_and_steal_from_two_samples():
    a, b = agent.parse_cpu(fx.PROC_STAT_1), agent.parse_cpu(fx.PROC_STAT_2)
    assert a == (10000, 8500, 0)
    assert b == (10400, 8680, 80)
    assert agent.cpu_usage(a, b) == (55.0, 20.0)


def test_cpu_usage_survives_no_time_passing_and_garbage():
    a = agent.parse_cpu(fx.PROC_STAT_1)
    assert agent.cpu_usage(a, a) == (0.0, 0.0)
    assert agent.parse_cpu("") is None


def test_meminfo_in_mb():
    assert agent.parse_meminfo(fx.PROC_MEMINFO) == (4000, 2500)
    assert agent.parse_meminfo("") is None


def test_meminfo_without_memavailable_falls_back_to_memfree():
    assert agent.parse_meminfo("MemTotal: 2048000 kB\nMemFree: 1024000 kB\n") == (2000, 1000)


def test_load_and_uptime_first_field():
    assert agent.parse_first_float("0.42 0.30 0.20 1/200 999\n") == 0.42
    assert agent.parse_first_float("123456.78 99999.00\n") == 123456.78
    assert agent.parse_first_float("") is None


def test_tcp_snmp_and_retrans_delta():
    a, b = agent.parse_tcp_snmp(fx.PROC_SNMP_1), agent.parse_tcp_snmp(fx.PROC_SNMP_2)
    assert a == (100000, 400)
    assert b == (110000, 450)
    assert agent.retrans_pct(a, b) == 0.5


def test_retrans_handles_idle_and_counter_reset():
    assert agent.retrans_pct((100, 5), (100, 5)) == 0.0
    assert agent.retrans_pct((100, 5), (50, 1)) == 0.0
    assert agent.parse_tcp_snmp("Udp: A\nUdp: 1\n") is None


def test_default_iface_picks_lowest_metric_default_route():
    assert agent.parse_default_iface(fx.PROC_NET_ROUTE) == "eth0"
    assert agent.parse_default_iface("Iface\tDestination\n") is None
    assert agent.parse_default_iface("") is None


def test_default_iface_from_ip_route():
    assert agent.parse_ip_route(fx.IP_ROUTE) == "ens3"
    assert agent.parse_ip_route("") is None


def test_bps_from_counter_delta():
    assert agent.bps(1000, 2000, 2.0) == 4000
    assert agent.bps(2000, 1000, 2.0) == 0  # counter reset
    assert agent.bps(1000, 2000, 0) == 0


def test_conntrack_pct():
    assert agent.conntrack_pct("3000\n", "100000\n") == 3.0
    assert agent.conntrack_pct("", "") is None
    assert agent.conntrack_pct("5", "0") is None


def test_failed_units_with_and_without_bullet():
    assert agent.parse_failed_units(fx.SYSTEMCTL_FAILED) == ["fail2ban.service", "backup.timer"]
    assert agent.parse_failed_units(fx.SYSTEMCTL_FAILED_PLAIN) == ["fail2ban.service"]
    assert agent.parse_failed_units("") == []


def test_ping_output():
    assert agent.parse_ping(fx.PING_OK) == (0.0, 41.2)
    assert agent.parse_ping(fx.PING_LOSSY) == (20.0, 50.5)
    assert agent.parse_ping(fx.PING_DEAD) == (100.0, None)
    assert agent.parse_ping("ping: unknown host nope") == (100.0, None)


def test_geo_providers():
    want = ("203.0.113.5", {"country": "DE", "city": "Falkenstein", "org": "Hetzner Online GmbH"})
    assert agent.parse_ipinfo(fx.IPINFO) == want
    assert agent.parse_ipwho(fx.IPWHO) == want
    assert agent.parse_ipinfo({}) is None
    assert agent.parse_ipwho({"success": False, "message": "limit"}) is None


def test_geo_is_cached_and_failures_retry_sooner(monkeypatch):
    clock = [1000.0]
    calls = []
    answers = [None, ("203.0.113.5", {"country": "DE"}), ("203.0.113.6", {"country": "DE"})]
    monkeypatch.setattr(agent.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(agent, "lookup_geo", lambda ip="": calls.append(1) or answers[len(calls) - 1])
    state = {}
    assert agent.geo_cached(state) == (None, None)  # failure is non-fatal
    clock[0] += 60
    agent.geo_cached(state)
    assert len(calls) == 1  # not retried yet
    clock[0] += agent.GEO_RETRY_S
    assert agent.geo_cached(state)[0] == "203.0.113.5"
    clock[0] += agent.GEO_TTL_S - 1
    agent.geo_cached(state)
    assert len(calls) == 2  # cached for 6h
    clock[0] += 2
    assert agent.geo_cached(state)[0] == "203.0.113.6"
    assert len(calls) == 3


def test_version_matches_user_agent():
    assert agent.UA == "DowntimeLess-Agent/" + agent.VERSION


def test_cert_end_and_names_from_openssl_output():
    out = "notAfter=Feb  4 12:33:37 2027 GMT\nX509v3 Subject Alternative Name: \n    DNS:a.example.com, DNS:*.example.com\n"
    assert agent.parse_cert_end(out) == 1801744417
    assert agent.parse_cert_names(out) == ["a.example.com", "*.example.com"]
    assert agent.parse_cert_end("garbage") is None


def test_ssl_report_is_none_without_certs_or_certbot(monkeypatch):
    monkeypatch.setattr(agent, "CERT_GLOBS", ())
    monkeypatch.setattr(agent, "renew_status", lambda: {"certbot_installed": False})
    assert agent.ssl_report() is None


def test_ssl_report_lists_days_left(monkeypatch, tmp_path):
    cert = tmp_path / "live" / "x.example.com" / "cert.pem"
    cert.parent.mkdir(parents=True)
    cert.write_text("x")
    monkeypatch.setattr(agent, "CERT_GLOBS", (str(tmp_path / "live" / "*" / "cert.pem"),))
    monkeypatch.setattr(agent, "renew_status", lambda: {"certbot_installed": True})
    monkeypatch.setattr(agent, "run_text", lambda argv, timeout=10: "notAfter=Feb  4 12:33:37 2027 GMT\nDNS:x.example.com\n")
    rep = agent.ssl_report(now=1801744417 - 10 * 86400 - 5)
    assert rep["certs"][0]["days_left"] == 10 and rep["certs"][0]["domains"] == ["x.example.com"]


def test_own_ipv4_prefers_a_public_local_address(monkeypatch):
    import agent

    monkeypatch.setattr(agent, "local_ipv4", lambda: "45.144.17.212")
    assert agent.own_ipv4("205.252.135.59") == "45.144.17.212"
    monkeypatch.setattr(agent, "local_ipv4", lambda: "10.0.0.5")
    assert agent.own_ipv4("205.252.135.59") == "205.252.135.59"
    assert agent.own_ipv4("2a14:4f80::1") is None


def test_ipv4_only_restricts_and_restores_lookups(monkeypatch):
    import socket

    import agent

    seen = []
    monkeypatch.setattr(socket, "getaddrinfo", lambda host, port, family=0, *a, **k: seen.append(family) or [])
    real = socket.getaddrinfo
    with agent.ipv4_only():
        socket.getaddrinfo("example.com", 443)
    assert seen == [socket.AF_INET]
    assert socket.getaddrinfo is real


def test_geo_is_asked_for_the_servers_own_address_when_it_is_public(monkeypatch):
    asked = []
    monkeypatch.setattr(agent, "local_ipv4", lambda: "94.139.179.119")
    monkeypatch.setattr(agent, "lookup_geo", lambda ip="": asked.append(ip) or ("94.20.158.222", {"country": "IR"}))
    agent.geo_cached(agent.new_state({"master": "http://x", "agent_key": "k"}))
    assert asked == ["94.139.179.119"]
    monkeypatch.setattr(agent, "local_ipv4", lambda: "10.0.0.5")
    asked.clear()
    agent.geo_cached(agent.new_state({"master": "http://x", "agent_key": "k"}))
    assert asked == [""]  # behind NAT the outbound address is the only public one


def test_geo_urls_name_the_address_or_the_caller():
    ipinfo, ipwho = agent.GEO_URLS
    assert (ipinfo(""), ipinfo("1.2.3.4")) == ("https://ipinfo.io/json", "https://ipinfo.io/1.2.3.4/json")
    assert (ipwho(""), ipwho("1.2.3.4")) == ("https://ipwho.is/", "https://ipwho.is/1.2.3.4")


NGINX = """
server { listen 80; server_name app.example.com www.example.com; }
server {
    listen 443 ssl;
    server_name app.example.com *.wild.example.com ~^re.*$ _ localhost 10.0.0.1 Panel.Example.org;
}
server { listen [::]:443 ssl; server_name second.example.net; }
server { server_name no-listen.example.com; ssl_certificate /x.pem; }
"""


def test_nginx_domains_are_the_public_names_of_tls_blocks_only():
    assert agent.nginx_domains(NGINX) == ["app.example.com", "no-listen.example.com", "panel.example.org", "second.example.net"]
    assert agent.nginx_domains("") == []


def test_backup_folders_are_skipped_by_the_scan(monkeypatch, tmp_path):
    for name in ("live-a.example.com", "a.example.com.bak-20261103"):
        d = tmp_path / name
        d.mkdir()
        (d / "cert.pem").write_text("x")
    monkeypatch.setattr(agent, "CERT_GLOBS", (str(tmp_path / "*" / "cert.pem"),))
    monkeypatch.setattr(agent, "renew_status", lambda: {"certbot_installed": True})
    monkeypatch.setattr(agent, "run_text", lambda argv, timeout=10: "notAfter=Feb  4 12:33:37 2027 GMT\nDNS:x.example.com\n" if argv[0] == "openssl" else "")
    assert [c["name"] for c in agent.ssl_report()["certs"]] == ["live-a.example.com"]


def test_system_facts_from_proc_and_os_files():
    assert agent.parse_os_release('NAME="Ubuntu"\nPRETTY_NAME="Ubuntu 24.04.4 LTS"\nID=ubuntu\n') == "Ubuntu 24.04.4 LTS"
    assert agent.parse_os_release("") is None
    assert agent.parse_cpu_model("processor : 0\nmodel name\t: Intel(R)  Xeon(R) CPU E5-2680 v4 @ 2.40GHz\n") == "Intel(R) Xeon(R) CPU E5-2680 v4 @ 2.40GHz"
    assert agent.parse_cpu_model("Hardware\t: BCM2835\n") == "BCM2835"
    assert agent.parse_loadavg("0.52 0.40 0.35 2/512 12345\n") == (0.52, 0.40, 0.35)
    assert agent.parse_loadavg("garbage") is None
    assert agent.parse_swap("SwapTotal: 2097152 kB\nSwapFree: 1048576 kB\n") == (2048, 1024)
    assert agent.parse_swap("SwapTotal: 0 kB\nSwapFree: 0 kB\n") is None
    snmp = "Tcp: RtoAlgorithm RtoMin CurrEstab InSegs\nTcp: 1 200 87 5000\n"
    assert agent.parse_curr_estab(snmp) == 87
    assert agent.parse_curr_estab("") is None
    out = "2: eth0    inet6 2a01:4f8:1c1b::1/64 scope global \\       valid_lft forever\n"
    assert agent.parse_ipv6(out) == "2a01:4f8:1c1b::1"
    assert agent.parse_ipv6("") is None


def test_system_info_caches_the_ipv6_lookup(monkeypatch):
    calls = []
    monkeypatch.setattr(agent, "run_text", lambda argv, timeout=10: calls.append(argv) or "2: eth0 inet6 2001:db8::5/64 scope global")
    state = agent.new_state({"master": "http://x", "agent_key": "k"})
    first = agent.system_info(state, 3600.0)
    agent.system_info(state, 3601.0)
    assert len(calls) == 1 and first["ipv6"] == "2001:db8::5" and first["boot_ts"] > 0
