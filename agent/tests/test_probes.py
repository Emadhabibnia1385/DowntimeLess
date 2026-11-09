"""TCP/TLS probes: read-only connections to the ports the master names, short timeouts, a bounded list."""
import socket
import threading
import time

import agent


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def listener():
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(8)

    def serve():
        while True:
            try:
                conn, _ = srv.accept()
            except OSError:
                return
            conn.recv(1024)  # a ClientHello arrives and gets no TLS answer
            conn.close()

    threading.Thread(target=serve, daemon=True).start()
    return srv


def test_target_list_is_checked_and_capped():
    raw = [{"target": "198.51.100.2", "port": 443, "tls": True}, {"target": "--help", "port": 443}, {"target": "x", "port": 0},
           {"target": "x", "port": True}, {"target": "x", "port": "443"}, "junk", {"target": "198.51.100.3", "port": 8080}]
    assert agent.probe_targets(raw) == [{"target": "198.51.100.2", "port": 443, "tls": True},
                                        {"target": "198.51.100.3", "port": 8080, "tls": False}]
    many = [{"target": "198.51.100.2", "port": 1000 + k} for k in range(100)]
    assert len(agent.probe_targets(many)) == agent.PROBE_MAX
    assert agent.probe_targets(None) == [] and agent.probe_targets({"a": 1}) == []


def test_an_open_port_connects_and_a_failed_tls_handshake_is_reported():
    srv = listener()
    port = srv.getsockname()[1]
    try:
        plain = agent.tcp_probe({"target": "127.0.0.1", "port": port, "tls": False})
        assert plain["ok"] is True and plain["error"] is None and plain["tls"] is None and plain["rtt_ms"] >= 0
        tls = agent.tcp_probe({"target": "127.0.0.1", "port": port, "tls": True}, timeout=1.0)
        assert tls["ok"] is True and tls["tls"] is False
    finally:
        srv.close()


def test_a_closed_port_is_refused_not_a_timeout():
    res = agent.tcp_probe({"target": "127.0.0.1", "port": free_port(), "tls": False})
    assert res == {"target": "127.0.0.1", "port": res["port"], "ok": False, "rtt_ms": None, "error": "refused", "tls": None}


def test_a_timeout_is_named(monkeypatch):
    def slow(*a, **kw):
        raise socket.timeout("timed out")
    monkeypatch.setattr(agent.socket, "create_connection", slow)
    assert agent.tcp_probe({"target": "198.51.100.2", "port": 443})["error"] == "timeout"


def test_probes_still_running_at_the_budget_are_left_out_not_failed(monkeypatch):
    def probe(item, timeout=agent.PROBE_TIMEOUT_S):
        if item["port"] == 2:
            time.sleep(2)
        return {"target": item["target"], "port": item["port"], "ok": True}
    monkeypatch.setattr(agent, "tcp_probe", probe)
    start = time.monotonic()
    out = agent.run_probes([{"target": "h", "port": p} for p in (1, 2, 3)], budget=0.5)
    assert time.monotonic() - start < 1.5
    assert [r["port"] for r in out] == [1, 3]
    assert agent.run_probes([]) == []
