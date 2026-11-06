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

## Roles

- `owner`: the first person who opens the one-time claim link printed by the installer.
- `admin`: invited by the owner; everything except managing admins and tokens.
- `viewer`: read-only.

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
- Jobs are a closed whitelist: `ping`, `tcp_check`, `speedtest_down`, `speedtest_up`, `apt_upgrade_safe`, `reboot`, `self_update`.
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
| `GET/POST/DELETE /keys` | API keys (owner, session only). Token shown once, only a SHA-256 is stored |
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

## Roadmap (see ROADMAP.md)

v0.1 login + fleet + agent metrics + ping matrix + dashboard. Then: traffic quota and purchase alerts, Cloudflare tokens and
DNS failover (two probes + never remove the last record), panel connectors (PasarGuard first), relay-to-exit tunnel map,
speed tests, safe upgrade/reboot jobs, AI operator.
