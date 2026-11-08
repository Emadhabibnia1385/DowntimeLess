# Workspaces and members

A **workspace** is one account's whole fleet: servers (and through them jobs, metrics, pings, link traffic), categories,
domains and certificates, settings and alert switches, API keys, Telegram channels and routes, incidents, flapping and alert
state, and the change log. A person can belong to several workspaces and switches between them in the header.

## Model (migration `014_workspaces.sql`)

- `workspaces(id, name, owner_user_id, created_at)`; `workspace_members(workspace_id, user_id, role, added_by, created_at)`,
  primary key `(workspace_id, user_id)`, roles `viewer < operator < admin < owner`, exactly one owner per workspace.
- Workspace 1 `فضای کار اصلی` holds every existing row and is owned by the existing owner; every existing user becomes a
  member with their old `users.role`. On a fresh install workspace 1 has no owner until the claim link is used.
- `workspace_id INTEGER NOT NULL DEFAULT 1` (indexed) on `servers, categories, domains, settings, api_keys,
  telegram_channels, rule_routes, incidents, events, alert_state, flapping`. Unique keys become per workspace
  (`settings(workspace_id,key)`, `rule_routes(workspace_id,rule)`, `alert_state`/`flapping(workspace_id,key)`,
  `categories(workspace_id,name)`, `domains(workspace_id,host,port)`, `telegram_channels(workspace_id,chat_id)`).
- `jobs, metrics, pings, link_traffic, link_prev` reach their workspace through `server_id`: queries join `servers`.
- `sessions.active_workspace_id`, `users.last_workspace_id` (set to 1 for everyone existing), `users.last_login_at`;
  `users.role` is legacy (`none` for people who only exist because someone invited them).
- `workspace_members.display_name`: what the inviter called a person, kept on the membership only; the person's own Telegram
  name wins once they have signed in. An invite never writes `users.name` or `users.tg_username`.
- `telegram_channels.chat_id` is unique across all workspaces; `verified_at` says the bot confirmed it may post there
  (existing channels of workspace 1 count as verified).
- The migration runner turns foreign keys off around each script (SQLite's table-rebuild procedure) and refuses to commit
  a migration that leaves `PRAGMA foreign_key_check` rows.

## Auth context

- `Actor` carries `workspace_id` and the member role in that workspace. `require(role)` compares that role.
- Every request of the web panel names its workspace in `X-Workspace-Id`, from the browser tab's own state (sessionStorage).
  The master checks the membership on each request; an unknown, foreign or removed id answers `workspace.not_found` (404),
  never a silent fallback. Without the header (scripts on the cookie) the session's workspace applies: the one it signed in
  to. So two tabs on two workspaces never write into each other's.
- Landing at sign-in: `users.last_workspace_id` (remembered at every sign-in and every switch) while still a member, else the
  workspace the person owns, else their first membership. A workspace someone joins them to never takes over by itself.
- `POST /auth/workspace {workspace_id}` checks membership and remembers it for the next sign-in; the tab then sends the
  header. `GET /auth/workspaces` lists mine with my role, `is_personal` and `invited_by` (who added me), and both ignore the
  header so a stale tab can recover.
- An API key belongs to the workspace it was created in and acts only there, with its scope (`full` = owner, `read` =
  viewer) capped by its creator's current role there; a creator who left takes the key with them. Keys are made and
  deleted only by a signed-in owner. An agent key resolves its workspace through its server row.
- Every data route takes `ws: int = Depends(current_workspace)`; a test walks `app.routes` and fails on a route without it
  (allowlist: auth, health, agent, llms.txt, OpenAPI). `tests/test_workspace_guard.py` parses every `execute` call in
  `app/`: SQL must be literal (no run-time concatenation, `%` only for `SET %s=?`, `SUM(%s)`, `PRAGMA table_info(%s)`),
  each alias of a fleet table needs `alias.workspace_id = ?` (or equal to another scoped alias), per-server tables need a
  scoped join to `servers`, no `OR` next to the filter, no `executescript` outside the migration runner, no `execute` passed
  around. The only escapes are `# ws: <reason>` with one of `server_row`, `agent_server`, `token_lookup`, `retention`,
  `probe_queue`, `caller_row`, `unique_check`.
- A row of another workspace is `*.not_found` (404), never 403.

## Roles

| Role | May |
| --- | --- |
| viewer | read everything in the workspace |
| operator | viewer + queue safe and diagnostic jobs (`SAFE_KINDS`, `DIAG_KINDS`) and re-check a domain |
| admin | everything except members and API keys |
| owner | everything, including members and keys |

## Members (`/members`, workspace owner, signed-in session only)

`GET` lists members; `PATCH /{user_id} {role}`; `DELETE /{user_id}` (never the owner or yourself; that person's tabs on this
workspace get `workspace.not_found` and move on). `POST {tg_id, name?, role}` is the panel's registration door, so only the
**panel owner** (owner of workspace 1) may call it (`members.panel_owner_only` otherwise); it creates a bare user row for an
unknown id and answers with the membership only, never anyone's profile. At most 50 members per workspace (`members.limit`),
one owned workspace per person (unique index). `owner` is not assignable. Changes go to the change log.

Login stays closed: a Telegram id gets in only when it is a member of some workspace. The first login creates the person's
own empty workspace once, named after their Telegram name.

## Telegram channels

The bot is shared by every workspace, so a channel is saved only when it is this workspace's to use: a positive chat id
(a private chat) must be the Telegram id of one of its owner or admins; a group or channel must list the bot as an
administrator that may post and at least one of the workspace's owner or admins as an administrator
(`getChatAdministrators`). A chat already registered anywhere answers the generic `channel.invalid`. Only verified channels
receive alerts or the test message.

## Limits and probing

200 servers and 300 domains per workspace (`server.limit`, `domain.limit`; agent-found domains stop silently at the cap).
The certificate probe takes due domains in turns across workspaces (the oldest of each, then the next of each) within the
per-sweep limit and stops after a 20 s budget. It resolves a name once, refuses any internal address, and connects to that
same address with the name only for SNI and verification. Residual risk: the address was public when checked; the TLS
handshake itself still goes to whatever answers there, which is the point of the probe.

## Monitor and alerts

The sweep runs once per workspace: thresholds, offline notices, certificate alerts, incidents, flapping and routes of that
workspace; private alerts go only to its owner and admins who have a Telegram id; channel alerts only to its channels. Agents get
ping targets and byte-counting peers from their own workspace only.

## Rollout and rollback

1. Back up first, on the server: stop nothing, copy `data/downtimeless.db` with `sqlite3 data/downtimeless.db ".backup
   /root/downtimeless-before-014.db"` (the backup API includes the WAL). Keep it until the new version has run for a week.
2. Dry run on a copy: `venv/bin/python scripts/check_migration.py /path/to/copy.db` prints row counts before and after,
   `integrity_check`, `foreign_key_check` and rows per workspace, and ends with `RESULT: OK`. Do not deploy on `PROBLEM`.
3. Deploy (`downtimeless update`). Migration 014 runs once at start inside one transaction; if it fails, nothing is
   recorded and the old schema stays, so the service does not start and the updater rolls back the code.
4. Migration 014 is one-way. The old binary cannot run on the new schema: its queries ignore `workspace_id`, `settings`,
   `rule_routes`, `alert_state` and `flapping` changed their keys (the old `ON CONFLICT(key)` upserts fail), and channels,
   categories and domains have new unique keys. Rollback = stop the service, restore the backup file (and remove the
   `-wal`/`-shm` files next to it), deploy the previous version. Anything recorded after the upgrade (metrics, incidents,
   members, keys) is lost with the rollback.
5. After the upgrade every existing person lands in workspace 1 as before; open tabs from the old panel keep working
   without the header (the session's workspace is 1) until they reload.
