-- Phase 2 and 3 detectors: what the master remembers between agent reports, per workspace and server.

-- listening (proto, port) per server; a row joins the baseline once it was seen without a gap for 24 hours
CREATE TABLE listener_baseline (
  workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  server_id INTEGER NOT NULL REFERENCES servers(id) ON DELETE CASCADE,
  proto TEXT NOT NULL,
  port INTEGER NOT NULL,
  proc TEXT,
  first_seen INTEGER NOT NULL,
  last_seen INTEGER NOT NULL,
  missing INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (server_id, proto, port)
);
CREATE INDEX listener_baseline_ws ON listener_baseline(workspace_id);

-- per-server memory of earlier reports (counters, previous states, first-seen times) as one JSON object
CREATE TABLE check_state (
  workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  server_id INTEGER PRIMARY KEY REFERENCES servers(id) ON DELETE CASCADE,
  data TEXT NOT NULL DEFAULT '{}',
  updated_at INTEGER NOT NULL
);
CREATE INDEX check_state_ws ON check_state(workspace_id);

-- what an admin marked deliberate: a retired container or panel node, an inbound with no group on purpose
CREATE TABLE check_ignores (
  workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  server_id INTEGER NOT NULL REFERENCES servers(id) ON DELETE CASCADE,
  kind TEXT NOT NULL CHECK (kind IN ('container', 'node', 'inbound')),
  name TEXT NOT NULL,
  created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
  created_at INTEGER NOT NULL,
  PRIMARY KEY (server_id, kind, name)
);
CREATE INDEX check_ignores_ws ON check_ignores(workspace_id);

-- users and bytes of each PasarGuard node per full hour, as the panel host's agent read them
CREATE TABLE node_usage (
  workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  server_id INTEGER NOT NULL REFERENCES servers(id) ON DELETE CASCADE,
  node_id INTEGER NOT NULL,
  hour INTEGER NOT NULL,
  users INTEGER NOT NULL,
  bytes INTEGER NOT NULL,
  PRIMARY KEY (server_id, node_id, hour)
);
CREATE INDEX node_usage_ws ON node_usage(workspace_id, server_id, hour);
