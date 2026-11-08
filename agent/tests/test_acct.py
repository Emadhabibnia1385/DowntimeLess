import json

import agent


def listing(counters):
    rules = []
    for ip, c in counters.items():
        for way in ("in", "out"):
            rules.append({"rule": {"family": "inet", "table": "dl_acct", "chain": "x", "comment": "dl:%s:%s" % (way, ip),
                                   "expr": [{"match": {}}, {"counter": {"packets": 1, "bytes": c[way]}}]}})
    return json.dumps({"nftables": [{"metainfo": {}}, {"table": {"name": "dl_acct"}}] + rules})


class FakeNft:
    """Stands in for the nft binary: remembers the loaded script and answers listings."""

    def __init__(self, counters=None, refuse=False):
        self.calls, self.counters, self.refuse, self.loaded, self.exists = [], counters or {}, refuse, None, False

    def __call__(self, args, text=None):
        self.calls.append(args)
        if args[0] == "-c":
            return (1, "syntax error") if self.refuse else (0, "")
        if args[0] == "-f":
            self.loaded, self.exists = text, True
            return 0, ""
        if args[:2] == ["-j", "list"]:
            return (0, listing(self.counters)) if self.exists else (1, "No such file")
        if args[0] == "delete":
            self.exists = False
            return 0, ""
        raise AssertionError(args)


def fresh(monkeypatch, nft):
    monkeypatch.setattr(agent, "nft_run", nft)
    monkeypatch.setattr(agent.shutil, "which", lambda name: "/usr/sbin/nft")
    return agent.new_state({"master": "http://x", "agent_key": "k"})


def test_peers_are_validated_deduplicated_and_capped():
    assert agent.acct_peers(["1.2.3.4", "1.2.3.4", "bad", "::1", 5, "10.0.0.256", "5.6.7.8"]) == ["1.2.3.4", "5.6.7.8"]
    assert agent.acct_peers(None) == [] and agent.acct_peers("1.2.3.4") == []
    assert len(agent.acct_peers(["10.0.%d.%d" % (i // 250, i % 250 + 1) for i in range(500)])) == 64


def test_the_table_only_counts_and_never_changes_a_packet():
    script = agent.acct_ruleset(["198.51.100.20", "198.51.100.21"])
    assert "policy accept" in script and script.count("counter") == 4
    for verb in ("drop", "reject", "accept ", "dnat", "snat", "masquerade", "redirect", "queue", "jump", "goto"):
        assert verb not in script.replace("policy accept", ""), verb
    assert 'ip saddr 198.51.100.20 counter comment "dl:in:198.51.100.20"' in script
    assert 'ip daddr 198.51.100.21 counter comment "dl:out:198.51.100.21"' in script
    assert "hook prerouting priority -300" in script and "hook postrouting priority 300" in script
    assert script.startswith("add table inet dl_acct\ndelete table inet dl_acct\n")  # only its own table


def test_counters_are_read_back_per_peer():
    assert agent.parse_acct(listing({"198.51.100.20": {"in": 7, "out": 9}})) == {"198.51.100.20": {"in": 7, "out": 9}}
    assert agent.parse_acct("not json") is None and agent.parse_acct("{}") is None


def test_the_table_is_built_once_and_counters_reported_each_cycle(monkeypatch):
    nft = FakeNft({"198.51.100.20": {"in": 11, "out": 22}})
    st = fresh(monkeypatch, nft)
    st["acct_peers"] = ["198.51.100.20"]
    assert agent.acct_fields(st) == {"acct": {"198.51.100.20": {"in": 11, "out": 22}}}
    builds = [c for c in nft.calls if c[0] == "-f"]
    assert agent.acct_fields(st)["acct"]
    assert [c for c in nft.calls if c[0] == "-f"] == builds  # no rebuild while the peers are the same
    st["acct_peers"] = ["198.51.100.20", "198.51.100.21"]
    agent.acct_fields(st)
    assert len([c for c in nft.calls if c[0] == "-f"]) == 2  # a new peer rebuilds it


def test_a_vanished_table_is_rebuilt_once(monkeypatch):
    nft = FakeNft({"198.51.100.20": {"in": 1, "out": 2}})
    st = fresh(monkeypatch, nft)
    st["acct_peers"] = ["198.51.100.20"]
    agent.acct_fields(st)
    nft.exists = False  # someone ran `nft flush ruleset`
    assert agent.acct_fields(st) == {"acct": {"198.51.100.20": {"in": 1, "out": 2}}}


def test_a_refused_ruleset_is_reported_not_raised(monkeypatch):
    st = fresh(monkeypatch, FakeNft(refuse=True))
    st["acct_peers"] = ["198.51.100.20"]
    out = agent.acct_fields(st)
    assert "acct" not in out and "refused" in out["acct_error"]


def test_no_nft_binary_is_an_error_not_a_crash(monkeypatch):
    st = fresh(monkeypatch, FakeNft())
    monkeypatch.setattr(agent.shutil, "which", lambda name: None)
    st["acct_peers"] = ["198.51.100.20"]
    assert "not installed" in agent.acct_fields(st)["acct_error"]


def test_switching_it_off_removes_only_our_table(monkeypatch):
    nft = FakeNft({"198.51.100.20": {"in": 1, "out": 2}})
    st = fresh(monkeypatch, nft)
    st["acct_peers"] = ["198.51.100.20"]
    agent.acct_fields(st)
    st["acct_peers"] = []
    assert agent.acct_fields(st) == {}
    assert ["delete", "table", "inet", "dl_acct"] in nft.calls and nft.exists is False
    calls = len(nft.calls)
    agent.acct_fields(st)
    assert len(nft.calls) == calls  # nothing more to do once it is gone


def test_a_fresh_agent_with_counting_off_cleans_a_leftover_table_once(monkeypatch):
    nft = FakeNft()
    nft.exists = True
    st = fresh(monkeypatch, nft)
    agent.acct_fields(st)
    assert nft.exists is False
    n = len(nft.calls)
    agent.acct_fields(st)
    assert len(nft.calls) == n
