-- Workspaces: one account's whole fleet. Everything that exists today becomes workspace 1, owned by the current owner.
-- The runner turns foreign keys off around this script, so tables can be rebuilt without cascading deletes.
CREATE TABLE workspaces (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  owner_user_id INTEGER REFERENCES users(id),
  created_at INTEGER NOT NULL
);
-- a person owns one workspace: their own (workspace 1 is the original owner's); NULL while unclaimed
CREATE UNIQUE INDEX workspaces_owner ON workspaces(owner_user_id);
CREATE TABLE workspace_members (
  workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK (role IN ('viewer','operator','admin','owner')),
  added_by INTEGER REFERENCES users(id),
  created_at INTEGER NOT NULL,
  PRIMARY KEY (workspace_id, user_id)
);
CREATE INDEX workspace_members_user ON workspace_members(user_id);

INSERT INTO workspaces (id, name, owner_user_id, created_at)
VALUES (1, 'فضای کار اصلی', (SELECT id FROM users WHERE role='owner' ORDER BY id LIMIT 1), CAST(strftime('%s','now') AS INTEGER));
INSERT INTO workspace_members (workspace_id, user_id, role, added_by, created_at)
SELECT 1, u.id,
       CASE WHEN u.id = (SELECT owner_user_id FROM workspaces WHERE id=1) THEN 'owner' WHEN u.role='owner' THEN 'admin' ELSE u.role END,
       NULL, u.created_at
FROM users u;

-- users.role is legacy now; 'none' is someone who exists only because a workspace invited them
CREATE TABLE users_new (
  id INTEGER PRIMARY KEY,
  tg_id INTEGER UNIQUE,
  tg_username TEXT,
  name TEXT NOT NULL DEFAULT '',
  role TEXT NOT NULL CHECK (role IN ('owner','admin','viewer','none')),
  username TEXT UNIQUE,
  password_hash TEXT,
  created_at INTEGER NOT NULL,
  last_workspace_id INTEGER,
  last_login_at INTEGER
);
INSERT INTO users_new (id, tg_id, tg_username, name, role, username, password_hash, created_at, last_workspace_id, last_login_at)
SELECT id, tg_id, tg_username, name, role, username, password_hash, created_at, NULL,
       (SELECT MAX(s.created_at) FROM sessions s WHERE s.user_id=users.id)
FROM users;
DROP TABLE users;
ALTER TABLE users_new RENAME TO users;

ALTER TABLE sessions ADD COLUMN active_workspace_id INTEGER;

-- tables reached directly; jobs, metrics, pings, link_traffic and link_prev reach theirs through server_id
ALTER TABLE servers ADD COLUMN workspace_id INTEGER NOT NULL DEFAULT 1;
CREATE INDEX servers_workspace ON servers(workspace_id);
ALTER TABLE api_keys ADD COLUMN workspace_id INTEGER NOT NULL DEFAULT 1;
CREATE INDEX api_keys_workspace ON api_keys(workspace_id);
ALTER TABLE incidents ADD COLUMN workspace_id INTEGER NOT NULL DEFAULT 1;
CREATE INDEX idx_incidents_ws_key ON incidents (workspace_id, key, opened_at);
CREATE INDEX idx_incidents_ws_opened ON incidents (workspace_id, opened_at);
ALTER TABLE events ADD COLUMN workspace_id INTEGER NOT NULL DEFAULT 1;
CREATE INDEX idx_events_ws_ts ON events (workspace_id, ts);

CREATE TABLE categories_new (
  id INTEGER PRIMARY KEY,
  workspace_id INTEGER NOT NULL DEFAULT 1,
  name TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  UNIQUE (workspace_id, name)
);
INSERT INTO categories_new (id, workspace_id, name, created_at) SELECT id, 1, name, created_at FROM categories;
DROP TABLE categories;
ALTER TABLE categories_new RENAME TO categories;

CREATE TABLE domains_new (
  id INTEGER PRIMARY KEY,
  workspace_id INTEGER NOT NULL DEFAULT 1,
  host TEXT NOT NULL,
  port INTEGER NOT NULL DEFAULT 443,
  note TEXT NOT NULL DEFAULT '',
  not_after INTEGER,
  issuer TEXT,
  error TEXT,
  last_checked INTEGER,
  created_at INTEGER NOT NULL,
  source TEXT NOT NULL DEFAULT 'manual',
  server_id INTEGER REFERENCES servers(id) ON DELETE CASCADE,
  seen_at INTEGER,
  ignored INTEGER NOT NULL DEFAULT 0,
  UNIQUE (workspace_id, host, port)
);
INSERT INTO domains_new (id, workspace_id, host, port, note, not_after, issuer, error, last_checked, created_at, source, server_id, seen_at, ignored)
SELECT id, 1, host, port, note, not_after, issuer, error, last_checked, created_at, source, server_id, seen_at, ignored FROM domains;
DROP TABLE domains;
ALTER TABLE domains_new RENAME TO domains;

CREATE TABLE settings_new (
  workspace_id INTEGER NOT NULL DEFAULT 1,
  key TEXT NOT NULL,
  value TEXT NOT NULL,
  PRIMARY KEY (workspace_id, key)
);
INSERT INTO settings_new (workspace_id, key, value) SELECT 1, key, value FROM settings;
DROP TABLE settings;
ALTER TABLE settings_new RENAME TO settings;

CREATE TABLE telegram_channels_new (
  id INTEGER PRIMARY KEY,
  workspace_id INTEGER NOT NULL DEFAULT 1,
  name TEXT NOT NULL,
  chat_id TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  UNIQUE (workspace_id, chat_id)
);
INSERT INTO telegram_channels_new (id, workspace_id, name, chat_id, created_at) SELECT id, 1, name, chat_id, created_at FROM telegram_channels;
DROP TABLE telegram_channels;
ALTER TABLE telegram_channels_new RENAME TO telegram_channels;

CREATE TABLE rule_routes_new (
  workspace_id INTEGER NOT NULL DEFAULT 1,
  rule TEXT NOT NULL,
  route TEXT NOT NULL,
  PRIMARY KEY (workspace_id, rule)
);
INSERT INTO rule_routes_new (workspace_id, rule, route) SELECT 1, rule, route FROM rule_routes;
DROP TABLE rule_routes;
ALTER TABLE rule_routes_new RENAME TO rule_routes;

CREATE TABLE alert_state_new (
  workspace_id INTEGER NOT NULL DEFAULT 1,
  key TEXT NOT NULL,
  level TEXT NOT NULL,
  PRIMARY KEY (workspace_id, key)
);
INSERT INTO alert_state_new (workspace_id, key, level) SELECT 1, key, level FROM alert_state;
DROP TABLE alert_state;
ALTER TABLE alert_state_new RENAME TO alert_state;

CREATE TABLE flapping_new (
  workspace_id INTEGER NOT NULL DEFAULT 1,
  key TEXT NOT NULL,
  since INTEGER NOT NULL,
  PRIMARY KEY (workspace_id, key)
);
INSERT INTO flapping_new (workspace_id, key, since) SELECT 1, key, since FROM flapping;
DROP TABLE flapping;
ALTER TABLE flapping_new RENAME TO flapping;
