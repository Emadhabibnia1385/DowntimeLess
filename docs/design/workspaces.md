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
- `sessions.active_workspace_id`, `users.last_workspace_id`, `users.last_login_at`; `users.role` is legacy (`none` for people
  who only exist because someone invited them).
- The migration runner turns foreign keys off around each script (SQLite's table-rebuild procedure) and refuses to commit
  a migration that leaves `PRAGMA foreign_key_check` rows.

## Auth context

- `Actor` carries `workspace_id` and the member role in that workspace. `require(role)` compares that role.
- A session's workspace: the stored one while the person is still a member; otherwise the last used, else the first
  workspace they were invited to, else their personal one. `POST /auth/workspace {workspace_id}` switches (unknown or foreign
  ids answer `workspace.not_found`), `GET /auth/workspaces` lists mine with my role and `is_personal`.
- An API key belongs to the workspace it was created in and acts only there (`full` = owner powers except members,
  `read` = viewer). An agent key resolves its workspace through its server row.
- Every data route takes `ws: int = Depends(current_workspace)`; a test walks `app.routes` and fails on a route without it
  (allowlist: auth, health, agent, llms.txt, OpenAPI). Every SQL statement on a workspace table must name `workspace_id`
  or carry a `# ws:` comment that says why it is safe; another test parses the code and enforces that.
- A row of another workspace is `*.not_found` (404), never 403.

## Roles

| Role | May |
| --- | --- |
| viewer | read everything in the workspace |
| operator | viewer + queue safe and diagnostic jobs (`SAFE_KINDS`, `DIAG_KINDS`) and re-check a domain |
| admin | everything except members and API keys |
| owner | everything, including members and keys |

## Members (`/members`, owner, signed-in session only)

`GET` lists members; `POST {tg_id, name?, role}` adds one (the user row is created when the Telegram id is unknown, with no
password); `PATCH /{user_id} {role}`; `DELETE /{user_id}` (never the owner or yourself; sessions of that person in this workspace
move to another workspace on their next request). `owner` is not assignable. Changes go to the change log
(`member_added`, `member_role_changed`, `member_removed`).

Login stays closed: a Telegram id gets in only when it is a member of some workspace. The first login creates the person's
own empty workspace (named after them) once.

## Monitor and alerts

The sweep runs once per workspace: thresholds, offline notices, certificate alerts, incidents, flapping and routes of that
workspace; private alerts go only to its owner and admins who have a Telegram id; channel alerts only to its channels. Agents get
ping targets and byte-counting peers from their own workspace only.
