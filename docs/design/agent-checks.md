# Agent checks (agent 0.3.0)

Phase 2 and the agent half of Phase 3 of `docs/DETECTION-CATALOG.md`: read-only data the master rules will use
later. Nothing here changes a server. The master already stores the whole report, so no master change is needed
to receive these fields, and every field is optional (0.2.x agents simply do not send them).

## Rules the collectors follow

- Read-only: files under `/proc`, `/sys`, `/etc`, and list/show commands. No restarts, writes or config edits.
- Every command has a timeout: 5 s, docker and journal 8 s. A command that outlives it is killed.
- Each collector runs in its own thread at its own cadence and its result is cached in the agent state. The report
  waits for them at most `CHECKS_BUDGET_S` (4 s, counted from the start of the report, so it overlaps the 1 s CPU
  sampling pause and the pings). A collector still busy at the deadline shows its last value if that is recent
  (within 3 cadences, at least 90 s), otherwise `null` and its name in `checks_error`. It is not started again
  while it runs; after 120 s it is given up and may start again.
- A collector that fails reports `null` and its name in `checks_error`. A missing tool gives `null` without an error.
- Lists are cut to 300 items and strings to 200 characters.
- No secret leaves the server: tunnel configs are read through a whitelist of keys (ports, peer address, interface,
  mode, transport); docker is asked only for the fields listed below (never env, command or labels); logs are
  counted, never shipped; panel answers are re-validated field by field and free text is scrubbed of URLs with
  credentials, `key=value` secrets and long token-like strings.

## Report fields

`checks` (object, always present from 0.3.0), `checks_error` (list of collector names), `panel` (only on a host
that runs a PasarGuard panel), `panel_error` (short class name, only when the panel read failed),
`ssl.node_certs` (only when PasarGuard node certificates exist).

| Field | Source | Cadence | Cost per run | What it is for |
|---|---|---|---|---|
| `checks.listeners` `[{proto, port, proc}]` | `ss -H -tulnp`; ports 0 and >32768 dropped unless the process is a tunnel, xray, nginx or sshd | every report | 1 command, ~10 ms | an expected location, tunnel or SSH port stopped listening (panel says connected, Xray listens on nothing) |
| `checks.units` `[{name, enabled, active, sub, restarts}]` | `systemctl list-unit-files --state=enabled`, `systemctl list-units --all`, one `systemctl show -p Id,ActiveState,SubState,NRestarts,UnitFileState`; names `^(backpack-\|relay-dnat\|backhaul\|gre-\|wattun@\|dl-\|xray\|x-ui\|pasarguard\|panel-dnat\|mobin-dnat\|nginx\|fail2ban)` that are enabled, plus any unit in `auto-restart` | every report | 3 commands, ~30 ms | tunnel enabled but stopped; crash loops that `systemctl --failed` never shows |
| `checks.conntrack` `{module_loaded, count, max, tcp_established_timeout, insert_failed, drop, early_drop}` | `/proc/sys/net/netfilter/*`, `/proc/net/stat/nf_conntrack` (hex, summed over CPUs) | every report | file reads, <1 ms | limits reset to defaults after a reboot, table full, drops; module not loaded on a DNAT relay |
| `checks.containers` `[{name, image, state, status, restarts, health, policy, exit_code, oom_killed, started_at}]` (≤50) | `docker ps -a --format` (id, name, image, state, status) and one `docker inspect --format` asking only restart count, restart policy, health, state, exit code, OOM flag, start time, image; `image` is repo:tag, digest dropped | 60 s | 2 commands, ~100–300 ms | node or panel container down or looping |
| `checks.container_logs` `[{container, unavailable, keepalive, queuepool, certfail}]` | `docker logs --since 10m` of each running PasarGuard panel/node container (database containers excluded, ≤20, ≤30 s in all), streamed and counted: `Code: Unavailable`, `keep alive timeout`, `QueuePool limit`, `CERTIFICATE_VERIFY_FAILED` | 300 s | 1 + N commands, ~20 ms per MB of log, reading stops at 16 MB | node says Connected while Xray is stopped; keep-alive stops; DB pool exhaustion; node cert mismatch |
| `checks.nft` `{tables, relay_dnat, dnat_rules, dnat_by_table, ip_forward}` | `nft list tables`; `nft list ruleset` streamed, `dnat to` lines counted per table (reading stops at 16 MB); `/proc/sys/net/ipv4/ip_forward` | 60 s | 2 commands, ~20 ms (20k rules parse in ~10 ms) | DNAT table gone after a reboot, or present but empty |
| `checks.tunnels.configs` `[{name, type, mode, transport, ports, peer, iface, unit, active, rx_bytes?, tx_bytes?}]` | `/etc/backhaul/*.toml`, `/etc/backpack/*.toml`, `/etc/rathole/*.toml`, `/etc/frp/*.toml\|ini`, `/etc/wattun/*.yml\|yaml` through a key whitelist; unit state from one `systemctl show`; interface bytes from `/sys/class/net/IFACE/statistics` (same numbers as `ip -s link`, no command) | 60 s | file reads + 1 command, ~15 ms | which ports each tunnel should carry (compare with listeners), tunnel unit down, one-sided BackPack link |
| `checks.tunnels.links` `[{iface, kind, mtu, state, rx_bytes, tx_bytes}]` | `/sys/class/net/*/type` 768/776/778/823/65534 (IPIP, SIT, GRE, ip6gre, TUN/WireGuard) | 60 s | file reads | per-link bytes, one-sided GRE, MTU sanity |
| `checks.kernel` `{congestion, qdisc, mtu_probing, ip_forward, reserved_ports, swappiness, oom_kill, boot_id, ntp_synced, inode_pct, journal_mb}` | `/proc/sys/...`, `/proc/vmstat`, `/proc/sys/kernel/random/boot_id`, `timedatectl show -p NTPSynchronized`, `statvfs("/")`, `journalctl --disk-usage` | 300 s | 2 commands, ~50 ms | drift after rebuilds (BBR, fq, mtu probing, reserved ports), OOM kills, reboot/rebuild (`boot_id`), clock sync, inodes, journal size |
| `checks.security` `{ufw, fail2ban, password_auth, sshd_ports}` | `/etc/ufw/ufw.conf` `ENABLED=`; `systemctl show -p LoadState,ActiveState fail2ban.service`; `sshd -T` (`passwordauthentication`); `sshd_ports` from the latest listeners | 300 s | 2 commands, ~30 ms | firewall off, fail2ban down, password login on, sshd moved or gone |
| `checks.apt` `{dpkg_audit, held_docker, reboot_required_pkgs}` | `dpkg --audit` (line count), `apt-mark showhold`, `/var/run/reboot-required.pkgs` | 600 s | 2 commands, ~200 ms | an upgrade that would make the next reboot fail |
| `ssl.node_certs` `[{name, source, not_after, days_left, ips, domains}]` | `openssl x509` on `/var/lib/*/certs/ssl_cert.pem`; listed apart from `ssl.certs` so the master offers no certbot action on them | with the ssl scan (1800 s) | 1 command per cert | node cert expiry; cert SAN IP differs from the server's address after a move |
| `panel` `{container, version, nodes, usage, admins, inbounds_without_group, user_status, errors}` | see below | 60 s (discovery 300 s) | 1 `docker exec`, 0.3–2 s, hard limit 8 s (7 s inside) | panel truth: node status and message, usage collapse per node, reseller quota, inbounds nobody receives, user status surges, panel version |

## The panel reader

Discovery: a running container whose name or image contains `pasarguard` (database images and the
`pasarguard/node` image excluded) and where `docker exec C test -d /code` succeeds. The answer, including "none",
is cached for 300 s and dropped when an exec fails.

Every 60 s the agent pipes one fixed script, `PANEL_SCRIPT` in `agent/agent.py`, into
`docker exec -i -w /code CONTAINER python -`. The script:

- takes the database address from the container's own `SQLALCHEMY_DATABASE_URL` (or `/code/.env`) and never
  prints it; any failure prints `{"error": "<ClassName>"}` and nothing else;
- opens each query on a fresh connection made read-only first: PostgreSQL `SET SESSION CHARACTERISTICS AS
  TRANSACTION READ ONLY` and `statement_timeout = 3000`; MySQL/MariaDB `SET SESSION TRANSACTION READ ONLY` and
  `max_execution_time = 3000` (MariaDB: `max_statement_time = 3`); SQLite `PRAGMA query_only = ON`; then a commit so
  the settings cover the next transaction. `signal.alarm(7)` ends it even when `docker exec` was cut;
- contains no write verb (a test asserts no INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, GRANT, TRUNCATE);
- falls back to a simpler query when a column is missing in the panel's version (`keep_alive`, `used_traffic`,
  `groups.is_disabled`), and quotes `` `groups` `` on MySQL.

| `panel` field | Query |
|---|---|
| `nodes [{id, name, address, port, status, message (≤120), keep_alive}]` | `nodes`, ≤300 rows |
| `usage {hour_start, last [{node_id, users, bytes}], prev [...]}` | `node_user_usages` with `created_at >= :a AND created_at < :b` for the last full hour and the hour before (the indexed column, two windows, `GROUP BY node_id`) |
| `admins [{name, used, limit}]` | `admins.username, used_traffic, data_limit` (no password hash, no token) |
| `inbounds_without_group [tag]` | inbounds with no association to an enabled group |
| `user_status {active, limited, expired, on_hold, disabled, other}` | `users GROUP BY status` |
| `version` | `/code/VERSION` |
| `errors ["part:ClassName"]` | parts that failed; the rest of the answer still arrives |

The agent re-checks every field (types, address pattern, lengths) and scrubs names and messages before they go
into the report.

## Cost per report

Every-report collectors: about 4 commands and a few file reads, ~50 ms on a Linux VPS. Heavier ones run at most
every 60–600 s and in parallel, so a typical report spends well under 1 s on checks and never more than the 4 s
budget, most of which overlaps the existing 1 s sampling pause. Docker log counting and the panel read can take
longer, but they run in the background and their result is picked up by the next report.

## Not covered yet (catalog items left for later)

`dmesg`/`journalctl -k` "table full" lines, fail2ban banned lists, per-peer `ss -Htin` quality, grub device, cloud-init
instance id, WireGuard handshake ages, DB dump age, panel failed logins per source, image digests across nodes.
