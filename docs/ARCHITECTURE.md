# DowntimeLess architecture

DowntimeLess watches a VPN fleet from one **master** server. Every monitored server runs a tiny **agent**.
The agent only makes outbound HTTPS calls to the master, so no SSH key or root credential ever leaves a server.

```
 browser / Telegram Mini App ──HTTPS──▶ nginx ──▶ master (FastAPI + SQLite, serves web/dist)
                                                    ▲   │ Telegram bot (login approval, alerts, dev log)
                                    HTTPS (outbound)│   │ Cloudflare API (DNS, later)
                                        agent ──────┘   │ panel APIs: PasarGuard / 3x-ui / Marzban (later)
```

## Repository layout

| Path | What |
| --- | --- |
| `master/` | FastAPI backend, plain `def` handlers, SQLite, one feature per folder (`router.py`, `schemas.py`, `service.py`, `repo.py`) |
| `agent/` | Python 3 standard-library only collector, one file, runs as a systemd service |
| `web/` | React 19 + Vite + Tailwind 4 + `@nyxon/nasim`, Persian RTL, dark/light, `dist/` is committed |
| `install.sh` | Master manager menu: install, update, edit env, status, logs, restart, uninstall (fa/en) |
| `docs/` | Architecture, API, roadmap |

## Workspaces and roles (see `docs/design/workspaces.md`)

A workspace is one account's whole fleet; a person can belong to several and switches in the header
(`GET /auth/workspaces`, `POST /auth/workspace`). Everything (servers, categories, domains, settings, keys, channels, routes,
incidents, change log) is scoped to the active workspace; another workspace's ids are 404. Roles are per workspace:

- `owner`: the person whose workspace it is (workspace 1: whoever opened the installer's claim link); manages members and keys.
- `admin`: added by the owner (`/members`, by Telegram id); everything except members and API keys.
- `operator`: viewer plus safe and diagnostic jobs (ping, TCP, speed tests, processes, ports, journal, traceroute...).
- `viewer`: read-only.

Only Telegram ids that are a member of some workspace can sign in; the first sign-in creates the person's own empty workspace.

## Login (modelled on KasbBook)

1. `POST /api/v1/auth/telegram/start` creates a challenge (5 min) and returns `deep_link` + `poll_secret`.
2. User opens `https://t.me/<bot>?start=wl_<token>`; the bot shows "was this you?" with IP and user agent.
3. Approve/Deny buttons; the browser polls `POST /api/v1/auth/telegram/poll` every 2 s and receives the session once.
4. Optional password afterwards (`PUT /api/v1/auth/me/password`, Argon2id, one error message for every failure).
5. Session = opaque server-side token in an HttpOnly cookie. All secrets are stored only as hashes.

## Agent protocol

- The panel creates a server record and shows `curl -fsSL https://<panel>/agent/install.sh | sudo bash -s -- --token <enroll>`.
- The agent exchanges the enroll token for a long-lived agent key (stored 0600 in `/etc/downtimeless/agent.json`).
- Every 30 s: `POST /api/agent/v1/report` with metrics and results of the last jobs.
  The response carries the next `ping_targets` and queued `jobs`.
- Jobs are a closed whitelist: `ping`, `tcp_check`, `speedtest_down`, `speedtest_up`, `apt_upgrade_safe`, `reboot`, `self_update`,
  `cert_renew`, `cert_delete` (certbot only, the certificate name is validated by both sides), the diagnostics, and the
  one-click fixes below.
- One-click fixes (agent 0.3.3): `nft_reload`, `sysctl_apply`, `ipset_sync`, `tunnel_restart`. Offered only from the matching
  alert (`dnat_*`/`drift_dnat`, `drift_sysctl`, `drift_ipset`, `tunnel_unhealthy`) to an admin signed in to the panel, after a
  confirm dialog that shows the exact commands; API keys (even `full`) are refused (`job.human_only`), a server at level `read`
  refuses (`job.permission`), and the same fix cannot be queued twice before its result (`job.pending`, also a partial unique
  index, migration 022; a fix with no result after 30 minutes is marked `error` and stops blocking). `service_restart` refuses
  the units these fixes own (`nyxon-access`, `*dnat*`, tunnel families) and every unit name must start with a letter or digit;
  the agent's report reply now carries the server's real permission level, so the agent refuses mutating jobs on `read` too. The agent runs only
  fixed commands from the vpnopsnyx playbooks; the only argument is `tunnel_restart`'s unit, which must be one of the tunnel units
  the server itself reported (checked by the master and again by the agent). Each fix runs a pre-check first and stops before
  any change when it fails or when the backup cannot be written, saves the live state under `/var/backups/downtimeless/`
  (a root-owned 0700 directory, never a symlink; files 0600, the newest 50 kept) and returns a rollback note; jobs that arrive
  while the agent restarts are reported `rejected`, not dropped:
  - `nft_reload`: `nft -c -f` on every `/etc/nftables-*dnat*.nft` whose unit is loaded, the whole live ruleset saved, then
    `systemctl restart -- <unit>` per file within a 180 s deadline (existing flows keep their conntrack mapping); a failure
    names the units already restarted.
  - `sysctl_apply`: the live value of every key any directory of `sysctl --system` sets is saved, then `sysctl --system`; the
    result lists what changed and what still differs.
  - `ipset_sync`: refused when `TRUSTED_SOURCES` in `/etc/nyxon/access.conf` is empty, when the live `nyxon_trusted` set
    cannot be read, or when any live member is missing from the file (removing a trusted source stays a manual step);
    otherwise `ipset save` and
    `systemctl restart nyxon-access.service`, then the live count against the file.
  - `tunnel_restart`: `systemctl restart -- <unit>` for a loaded tunnel unit (a tunnel config's unit, or an enabled unit of a
    tunnel family), the same rule on the master and the agent.
  Both the request and the result go to the change log. There is no reboot-risk gate on jobs today, so none applies here.
- The agent also reports the domains its nginx answers for on TLS (`ssl.domains`); the master adds them to the SSL list as
  `auto` domains, probes them from outside, drops them a week after they vanish, and never re-adds one the owner removed.
  Mutating jobs (`apt_upgrade_safe`, `reboot`) run only if the server's permission level is `safe`/`full`, and are always
  created by a human from the panel.

### Report body

```json
{
  "agent_version": "0.1.0",
  "ts": 1790000000,
  "hostname": "de-1",
  "public_ip": "203.0.113.5",
  "geo": {"country": "DE", "city": "Falkenstein", "org": "Hetzner Online GmbH"},
  "uptime_s": 123456,
  "cpu_pct": 12.5, "steal_pct": 0.0, "load1": 0.4,
  "ram_total_mb": 4096, "ram_avail_mb": 2500,
  "disk_total_gb": 80.0, "disk_used_gb": 21.0,
  "net": {"iface": "eth0", "rx_bytes": 1, "tx_bytes": 2, "rx_bps": 0, "tx_bps": 0},
  "tcp_retrans_pct": 0.4, "conntrack_pct": 3.0,
  "failed_units": [], "reboot_required": false,
  "ping": [{"target": "198.51.100.7", "loss_pct": 0, "rtt_ms": 41.2}],
  "jobs_done": [{"id": "j1", "status": "ok", "result": {}, "error": null}]
}
```

`rx_bytes`/`tx_bytes` are monotonic NIC counters; the master derives per-period traffic from deltas and tolerates resets.

### Report response

```json
{ "interval_s": 30,
  "ping_targets": [{"target": "198.51.100.7", "tcp_port": null}],
  "jobs": [{"id": "j1", "kind": "speedtest_down", "args": {"url": "https://speed.cloudflare.com/__down?bytes=25000000"}}] }
```

## Master HTTP API (v1, all JSON, errors `{code, message}` with Persian `message`)

| Method + path | Purpose |
| --- | --- |
| `POST /auth/telegram/start`, `POST /auth/telegram/poll`, `POST /auth/telegram/webapp` | login |
| `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`, `PUT /auth/me/password` | session + password |
| `GET /servers`, `POST /servers`, `GET /servers/{id}`, `PATCH /servers/{id}`, `DELETE /servers/{id}` | fleet (`POST` returns the install command once) |
| `GET /servers/{id}/metrics?range=1h|24h|7d|30d` | time series |
| `GET /servers/{id}/jobs`, `POST /servers/{id}/jobs` | whitelisted actions |
| `GET /overview`, `GET /issues`, `GET /ping-matrix`, `GET /snapshot` | counts; current problems with evidence and a suggested next step; link matrix; the whole fleet in one secret-free JSON |
| `GET /auth/workspaces`, `POST /auth/workspace` | my workspaces with my role; switch the session's workspace |
| `GET/POST /members`, `PATCH/DELETE /members/{user_id}` | members of the current workspace (owner, signed in) |
| `GET/POST/DELETE /keys` | API keys of the current workspace (owner). Token shown once, only a SHA-256 is stored |
| `GET /settings`, `PUT /settings` | alert thresholds, intervals |
| `POST /agent/v1/enroll`, `POST /agent/v1/report` | agent side (agent key header `X-Agent-Key`) |
| `GET /agent/install.sh`, `GET /agent/agent.py` | served by master, unauthenticated |
| `GET /health` | liveness |

Money-free, but the same house rules as Seamless apply: tenant-less single owner now, parameterised SQL, epoch seconds,
errors from a closed registry, `Page[T]` for lists, operation id `<tag>_<function>`.

## API-first and AI agents

Everything the panel shows comes from the same JSON API. A program (Claude, a script, another agent) authenticates with
`Authorization: Bearer dl_...`:

- `read` key = viewer: `GET /snapshot` and `GET /issues` give the fleet state and what is wrong, with evidence.
- `operate` key = admin: may also queue the read-only jobs (`ping`, `tcp_check`, `speedtest_*`).
- Keys can never queue `reboot` / `apt_upgrade_safe` / `self_update`, never manage users or keys; a signed-in human does that.
- `/llms.txt` describes the API for agents, `/api/openapi.json` is the schema, `docs/openapi.json` is the committed copy.

## Reports and the AI briefing (`master/app/features/reports/`)

Everything is computed on the master from data it already holds, so an assistant reads one document instead of gathering
facts itself. All endpoints are `GET`, viewer or `read` key, JSON by default and dense Markdown with `?format=md`; windows are
unix seconds (`since`/`until`, at most 366 days, error `window.invalid`). `/llms.txt` tells an assistant to start at the briefing.
The panel has no reports page: it shows only the health scores and the change log, as the «سلامت» and «تغییرات» tabs of the
Issues page (`/issues?tab=health|changes`; the old `/reports` address redirects there). Briefing and playbooks are for agents only.

| Path | What |
| --- | --- |
| `/reports/briefing?detail=brief\|full` | fleet status, open issues with evidence, recurring issues, path problems, health, traffic, quota (when quota fields exist), certificates, outdated agents, changes, ordered "check first" steps |
| `/reports/playbooks`, `/reports/playbooks/{code}` | curated fix guides (likely causes, read-only checks, safe fixes, never-do) per issue code or theme, flagged `detector: live\|planned`; unknown codes get a generic guide |
| `/reports/health` | 0-100 score per server (healthy 80+, degraded 50-79, failing below 50 or any hard gate) with penalties, gates and the signals not measured yet |
| `/reports/changes?since&until&server_id&kind` | the `events` table, newest first, at most 500 (jobs, agent updates, reboots, IP changes, server and settings changes, issue open/close), pruned after 180 days |
| `/reports/daily`, `/incidents`, `/traffic`, `/availability`, `/capacity`, `/relays` | digest of the last 24 h against the 24 h before; incident counts, MTTR and flapping; bytes and peaks; percent of time reporting; peak-hour load and sibling comparison; relay-by-exit loss, RTT, verdict and bytes |

Playbooks are hand-curated from the operator's vpnopsnyx knowledge base (`playbooks.py` names the source file of each entry);
`docs/DETECTION-CATALOG.md` is the plan for the detectors that are still `planned`.

## Roadmap (see ROADMAP.md)

v0.1 login + fleet + agent metrics + ping matrix + dashboard. Then: traffic quota and purchase alerts, Cloudflare tokens and
DNS failover (two probes + never remove the last record), panel connectors (PasarGuard first), relay-to-exit tunnel map,
speed tests, safe upgrade/reboot jobs, AI operator.
