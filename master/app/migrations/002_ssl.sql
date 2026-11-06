CREATE TABLE domains (
  id INTEGER PRIMARY KEY,
  host TEXT NOT NULL,
  port INTEGER NOT NULL DEFAULT 443,
  note TEXT NOT NULL DEFAULT '',
  not_after INTEGER,
  issuer TEXT,
  error TEXT,
  last_checked INTEGER,
  created_at INTEGER NOT NULL,
  UNIQUE (host, port)
);
CREATE TABLE alert_state (key TEXT PRIMARY KEY, level TEXT NOT NULL);
