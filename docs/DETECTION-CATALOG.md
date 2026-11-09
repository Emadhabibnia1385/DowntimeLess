# Detection catalog: from two months of field incidents to panel detectors

The knowledge base of the operator's VPN fleet work (github.com/nyxon-tech/vpnopsnyx: 78 numbered
incidents, the September and October field observations, the capacity, tunnel, filtering, panel and
node-lifecycle references, and the ops scripts) was reviewed by three independent readers on
2026-11-08. They found about 125 incidents and lessons and well over 100 distinct failure modes.
This file is the merged plan: what the panel must detect, in which order, and with which data.

Rules that every detector follows:

- **Read-only collection.** A detector never changes a server. Anything that would (a sysctl, a tunnel
  restart, a DNS edit) is a suggestion in the issue text, done by a person or by an explicit, confirmed job.
- **No secrets in reports.** Collectors ship counts, states and names, never tokens, passwords, panel
  `.env` values or log lines that may carry them.
- **One signal is not a verdict.** Anything about filtering or DNS needs two agreeing vantage points
  (the standing rule: two Iranian relays, 10 minutes, at least 6 samples). ICMP alone never decides.
- **Hysteresis.** An alert needs a duration (3 of 5 cycles or 10 minutes) and clears only after a
  few good cycles. State changes (reboot, IP change) are events, not levels.
- **Never leave a location with one relay.** Redundancy is itself a detector.

## Build order

### Phase 1: master-only, on data the agent already sends (small)

1. **Telegram for the critical issues that are only listed today**: `ping:`, `conntrack`, `failed_units`,
   disk critical. Each rule gets its own destination (a Telegram chat chosen in the panel).
2. **Event detectors**: `uptime_s` dropped (reboot, starts the post-reboot checklist); `public_ip`
   changed (the eight-place checklist: GRE local/remote, dial addresses, DNS, allowlists, nft rules that
   match the old IP, SSH alias, re-measure); `cpu_cores` or `ram_total_mb` dropped (resized or rebuilt).
3. **Cause classification across servers** (TCP since agent 0.3.2, see "TCP probes" below): an exit that
   reports but fails TCP from every relay is blacklisted in-country; exactly one relay failing to an exit is an
   egress filter on that relay; one relay failing to several exits is a datacenter-level filter (one grouped
   issue); a silent agent plus failed probes from others is an outage, not a filter. ICMP loss alone is an info note.
4. **Duration and tiers**: CPU and conntrack alerts need a duration; steal tiers (>10 warn, >15 strong,
   >40 critical for a host with users); `load1 / cpu_cores`.
5. **More probe pairs**: exit to relay (reverse tunnels depend on it), panel to node, and `1.1.1.1` as an
   anycast control (loss there points at the host or its uplink, not the censor).
6. **Quota forecast**: days to quota from the daily byte history and a per-server quota and reset day;
   two relays running out within 48 hours is its own warning. What counts follows the workspace setting `quota_basis`
   (0 = outgoing only, 1 = both directions); a server with `count_upload` off (PATCH `/servers/{id}`, default on) has free
   upload, so only its download counts whatever the setting says. The issue, the briefing's quota table and the health
   quota gate all use that one rule and say "upload free, only download counted"; traffic totals and charts stay raw.

### Phase 2: one new read-only agent block (medium; agent 0.3.0)

| Collector (read-only) | Detects |
|---|---|
| `ss -Hltnp` baseline of listeners | an expected location, tunnel or SSH port stopped listening (the most frequent silent outage: the panel says "connected" while Xray listens on nothing) |
| enabled units matching tunnel names that are not active; `NRestarts` / `auto-restart` | tunnel "up" on paper, crash loops that `systemctl --failed` never shows |
| `docker ps -a` + restart counts + health; counts of known log signatures only | node or panel container down or looping, `Unavailable` floods, keep-alive timeouts, DB pool exhaustion |
| `nft list tables` / presence of the DNAT table | DNAT table gone after a reboot |
| live conntrack max and timeout, `dmesg` "table full", `insert_failed` | limits reset to defaults after a reboot, table full, drops |
| sysctl baseline (BBR, fq, `tcp_mtu_probing`, `ip_forward`, reserved ports) | drift after rebuilds |
| `df -i`, journald and docker size, `oom_kill` delta, swap | inodes, logs, OOM kills |
| time sync (`timedatectl`), `boot_id`, cloud-init instance id | clock skew, provider rebuilds and migrations |
| ufw / fail2ban state and banned list | a relay or peer IP banned |
| `dpkg --audit`, grub device, held docker packages | an upgrade that would make the next reboot fail (the reboot job is blocked while red) |
| per-interface counters of tunnel links (`/sys/class/net/*/statistics`) | tunnel interface bytes per peer, one-sided GRE |
| `ss -Htin` per port and per peer (bytes acked, retransmits, RTT) | real-user quality per relay (MB per connection, RTT, retransmit ratio) |
| counter-only `dl_acct` nftables table (opt in per server; done) | bytes per relay and exit pair |

### Phase 3: panel truth (medium to large)

Read-only SQL through the panel container on the panel host, run by the agent that is already root
there, with no stored credential: nodes (status, message, keep-alive), per-node hourly users and GB,
inbounds in no group, hosts that lost their inbound, reseller quota burn, user status surges, panel
version and node image digests. Also: newest database dump age and `gzip -t`, the scheduled-update
log (`UPDATE FAILED`, rollback), failed logins per source.

### Phase 4: probes and external data (large)

TCP + TLS probes from relays (done in agent 0.3.2, without the camouflage SNI so far; see below); panel and subscription path probes through
every DNS address (GET size and time, a wrong-password POST must answer 401 fast); Cloudflare read
(records that point at dead relays, names with fewer than two healthy IPs, proxied records);
domain expiry and hold through RDAP; a quota ledger.

## Quick wins listed by the readers

The aggregate rules above, `load1 / cpu_cores`, the three event triggers, a duration condition for CPU
and conntrack, and Telegram for the existing critical issues. All use existing data.

## Detector families

| Family | What it covers |
|---|---|
| Listener and tunnel liveness | missing listener, unit active but no connection, crash loops, pool bloat, one-sided GRE, handshake failures, stale clients that steal a control channel |
| Path and filtering | exit-IP blacklist, relay egress filter, datacenter ICMP filter, inbound-from-abroad blackhole, ICMP vs TCP divergence |
| Link quality | per-peer retransmits and MB per connection, throttled pairs, pinned speeds, bandwidth headroom |
| Kernel and network capacity | conntrack size, timeout, drops; BBR; RPS; MTU/MSS; reserved ports; file descriptors |
| Host capacity | CPU, steal, load per core, RAM, OOM, sibling-exit imbalance |
| Quota and volume | quota forecast, two relays together, volume collapse after a threshold, upload cap |
| Topology and drift | fewer than two relays per location, wrong-country port map, forbidden ports, drift from the baseline |
| Lifecycle and events | reboot, IP change, rebuild, probation of new links, leftover test artifacts |
| Panel and node truth | node "connected" with Xray stopped, usage collapse, inbound/host/group integrity, versions, DB pool, backups, updates, brute force |
| Certificates and DNS | node and panel certs, renewed but not deployed, dead-relay records, proxied records, domain expiry |
| Access and security | sshd listener lost, password login on, fail2ban banned a relay, tampered `/etc/hosts` |

## TCP probes (agent 0.3.2, migration 021)

ICMP is dropped or rate-limited on many relay-to-exit paths while the data flows, and once in a while the reverse.
So the path verdicts come from TCP:

- **Ports.** With each report reply the master gives a relay `probe_targets`: per foreign server of its workspace
  (role other than relay) at most 2 TCP ports, 24 in all, taken from that server's own `checks.listeners`: TCP,
  a data-plane process (xray, sing-box, haproxy, nginx, hysteria, backhaul, docker-proxy, ...), not bound to
  loopback (`addr`, sent from 0.3.2), never sshd. Ports that answered before ("proven", table `probe_ports`, 30 days)
  come first, 443 next; the other candidates take turns every 5 minutes. `tls` is set for 443, 8443 and the
  Cloudflare TLS ports, or an nginx/haproxy/caddy listener.
- **Probe.** The relay's agent connects (3 s timeout, 8 in parallel, 12 s budget, running beside the pings) and,
  when `tls` is set, does a TLS handshake without SNI or verification and closes. Nothing is sent after it. A probe
  still running at the budget is left out, never reported as a failure. Results: `ok`, `rtt_ms`,
  `error` (`timeout`, `refused`, `unreachable`, `error`), `tls` (null, true, false); stored in `probes` (2 days).
- **Proven ports only.** Only ports that accepted a connection at least once in 30 days count, so a firewalled or
  local-only port never looks like a blocked path. A refused connection means the address answered: it is not a
  path failure (a closed port is `listener_missing`'s job).
- **Verdicts** (window 10 minutes, at least 6 TCP attempts per relay, two relays): every measuring relay at
  `loss_crit` (50%) failures or more, server online: `blacklisted` (critical); one relay at `loss_crit` while the others
  stay under `loss_warn` (10%): `relay_egress`, or `relay_filtered` when that relay fails 2+ servers (warning);
  2+ relays at `loss_warn`: `ping:<ip>` warning/critical with `probe: "tcp"`; one relay measuring alone: `ping:<ip>` info.
- **ICMP alone** (TCP fine, or not measured because the agents are older than 0.3.2 or no port is proven yet):
  `ping:<ip>` info with `probe: "icmp"` and `tcp_ok`, never a filtering verdict and never a health gate.
- **Health.** Path penalties use the TCP failure share; a path measured only by ICMP counts for at most 30% of its
  weight and never gates. The relays report shows `tcp_fail_pct`, `tcp_samples`, `tls_failed` beside the ICMP loss
  and the verdict `icmp_only` for ICMP-only loss.

## Forwards: DNAT destinations and relay-to-relay probes (agent 0.3.3)

Agent 0.3.3 reports each plain DNAT forward of a host (`checks.nft.dnat`: port and IPv4 destination). The master adds
two kinds of probe target for a relay, after the exit ports (24): its own DNAT destinations (8 per cycle) and the
forwarded ports of the other relays of the workspace (8 per cycle; ports that answered before first, the rest in turn
every 5 minutes). A connection to another relay's forwarded port goes through its DNAT and completes only when the whole
path to the destination works. These results are stored with the other probes but never enter the relay-to-exit path
verdicts. `app/features/overview/forwards.py` judges them (window 10 minutes, at least 6 attempts per relay, TCP only;
UDP forwards are not judged because UDP listeners are collapsed in the report).

| Code | Severity | When |
|---|---|---|
| `dnat_dead_target` | critical / warning | one issue per host, listing every dead rule. A destination that is a server of the workspace (by public IP), online, that does not listen on the port (public TCP listener; below 32768, and a baseline port only after 2 reports missing): warning, critical when the relay's own probe to it also fails (`loss_crit`). A destination that listens but refuses the relay, or does not answer while other ports of it do: warning. An address outside the workspace or a tunnel peer (private range) whose probe fails: critical when mostly refused, warning when it times out. An offline destination is left to `offline`; an answering probe clears the rule. |
| `dnat_unknown_target` | info | a rule to a public address that is no server of the workspace (often the old server of a migration that is still up); acknowledge it when it is deliberate |
| `relay_forward_broken:<relay>:<port>` | critical with 2+ relays, info with one | other relays (each with a full window) all fail (`loss_crit`) to connect to a proven forwarded port of the relay; relays that disagree point at the measuring relay's own path, so nothing is raised. Evidence names the location group (every relay that forwards the same port), the relays where it works and who failed, so "5 of 8 connections of a location fail" maps to one relay. When every measured forward of the relay fails (2+ ports) it is one issue `relay_forward_broken:<relay>:all`. |

Health: both critical codes are hard gates on a relay (`dnat_dead_target`, `forward_broken`) and take 70% of the
`forward_integrity` weight. Switches: `on_dnat_dead_target`, `on_dnat_unknown_target`, `on_relay_forward_broken`.

## Health scores (proposal)

**Relay.** Hard gates (any one means failing): agent offline; a configured forward port not listening or
the DNAT table missing; conntrack at 85% or a "table full" log line; quota exhausted; loss at 50% or more
to every exit (by TCP). Otherwise 100 minus penalties: reachability from abroad (25), forward integrity (20),
peer paths (15), real-user quality per peer (15), kernel capacity (10), CPU and steal (8), headroom (7),
quota burn (5), memory and pool ratio (5). 80 or more healthy, 50 to 79 degraded, below 50 failing.
**Exit/node** has the same shape with listener completeness and container state first, relay-to-exit
reachability second. The weights come from the severity language in the source and need tuning on
real incidents.

## After-reboot verification (automatic)

Trigger: `uptime_s` drops or `boot_id` changes. Window: up to 9 minutes (the panel host up to 3 minutes
longer). All steps are reads: the agent is back and the kernel changed; `dpkg --audit` clean; sshd on
the same ports; no failed units; enabled tunnel units active; `ip_forward` and the DNAT table present;
conntrack and sysctl live values equal the files; containers that were up are up; baseline listeners
restored, each inbound port checked on exits (not the node status); node connected and Xray listening;
usage back within 30 minutes; time in sync; firewall state; certificates; a real data test from another
in-country server; then a 24-hour re-check mark. Reboot order stays: least risky first, panel host last.

## Panel connector

Preferred: read-only SQL through the panel container (no credential stored). Fallback: the panel HTTP API
with a dedicated least-privilege admin, token stored encrypted in the master with an expiry. For
Marzban, Marzneshin, 3x-ui and Hiddify only user-level data (quota, expiry) is reachable; node-level
signals come from the host-side checks.

## Not detectable from a server

Whether users on each mobile carrier can reach a relay (needs a phone hotspot or a third-party probe
network); provider-side quota, billing, throttling, maintenance and silent rebuilds; the choice of tunnel
type per datacenter (a measurement campaign); registrar facts; restore drills (the panel only keeps the
record, it never marks one as passed); the operator's own VPN state when testing from a laptop; secrets
and key handling.

## Thresholds that are proposals, not source facts

Pool ratio above 1.0 (healthy is about 0.33), plateau within 3% of a round number for 30 minutes, usage
under 30% of the same hour's median, reseller burn at 85%, dump age 26 and 72 hours, time-sync skew over
1 second, RAM unaccounted over 1 GB. Ship them as tunable defaults and tune with real incidents. nft
`counter` on a NAT rule counts only the first packet of a flow; byte accounting uses the separate
counter-only table (`dl_acct`).
