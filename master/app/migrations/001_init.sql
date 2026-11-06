CREATE TABLE users (
  id INTEGER PRIMARY KEY,
  tg_id INTEGER UNIQUE,
  tg_username TEXT,
  name TEXT NOT NULL DEFAULT '',
  role TEXT NOT NULL CHECK (role IN ('owner','admin','viewer')),
  username TEXT UNIQUE,
  password_hash TEXT,
  created_at INTEGER NOT NULL
);
CREATE TABLE sessions (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash TEXT NOT NULL UNIQUE,
  ip TEXT, ua TEXT,
  created_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL
);
CREATE TABLE login_challenges (
  id INTEGER PRIMARY KEY,
  token_hash TEXT NOT NULL UNIQUE,
  poll_hash TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('pending','linked','approved','denied')),
  user_id INTEGER REFERENCES users(id),
  ip TEXT, ua TEXT,
  created_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL,
  consumed_at INTEGER
);
CREATE TABLE claims (
  token_hash TEXT PRIMARY KEY,
  created_at INTEGER NOT NULL,
  used_at INTEGER
);
CREATE TABLE servers (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  alias TEXT NOT NULL DEFAULT '',
  role TEXT NOT NULL DEFAULT 'other' CHECK (role IN ('relay','exit','panel','other')),
  permission TEXT NOT NULL DEFAULT 'read' CHECK (permission IN ('read','safe','full')),
  enroll_hash TEXT,
  agent_hash TEXT UNIQUE,
  hostname TEXT, public_ip TEXT, country TEXT, city TEXT, org TEXT,
  agent_version TEXT,
  last_seen INTEGER,
  last_report TEXT,
  prev_rx INTEGER, prev_tx INTEGER,
  offline_notified INTEGER NOT NULL DEFAULT 0,
  created_at INTEGER NOT NULL
);
CREATE TABLE metrics (
  server_id INTEGER NOT NULL REFERENCES servers(id) ON DELETE CASCADE,
  ts INTEGER NOT NULL,
  cpu REAL, steal REAL, ram_pct REAL, disk_pct REAL,
  rx_bps REAL, tx_bps REAL, rx_delta INTEGER NOT NULL DEFAULT 0, tx_delta INTEGER NOT NULL DEFAULT 0,
  retrans REAL, conntrack REAL
);
CREATE INDEX metrics_server_ts ON metrics(server_id, ts);
CREATE TABLE pings (
  server_id INTEGER NOT NULL REFERENCES servers(id) ON DELETE CASCADE,
  ts INTEGER NOT NULL,
  target TEXT NOT NULL,
  loss REAL, rtt REAL
);
CREATE INDEX pings_server_ts ON pings(server_id, ts);
CREATE TABLE jobs (
  id INTEGER PRIMARY KEY,
  server_id INTEGER NOT NULL REFERENCES servers(id) ON DELETE CASCADE,
  kind TEXT NOT NULL,
  args TEXT NOT NULL DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','sent','ok','error','rejected')),
  result TEXT, error TEXT,
  created_by INTEGER REFERENCES users(id),
  created_at INTEGER NOT NULL,
  done_at INTEGER
);
CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE api_keys (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  prefix TEXT NOT NULL,
  token_hash TEXT NOT NULL UNIQUE,
  scope TEXT NOT NULL CHECK (scope IN ('read','operate')),
  created_by INTEGER REFERENCES users(id),
  created_at INTEGER NOT NULL,
  last_used INTEGER
);
