-- One row per stretch of time an issue was active, so the Issues page can show what happened, not only what is wrong now.
CREATE TABLE incidents (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  key TEXT NOT NULL,
  code TEXT,
  server_id INTEGER,
  server_name TEXT,
  severity TEXT,
  title TEXT,
  evidence TEXT,
  opened_at INTEGER,
  last_seen INTEGER,
  closed_at INTEGER
);
CREATE INDEX idx_incidents_key_opened ON incidents (key, opened_at);
CREATE INDEX idx_incidents_closed ON incidents (closed_at);
CREATE INDEX idx_incidents_opened ON incidents (opened_at);
