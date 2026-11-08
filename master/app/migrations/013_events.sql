-- Change log: what happened to the fleet and the panel, newest first in reports. No foreign key: a removed server keeps its history.
CREATE TABLE events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts INTEGER NOT NULL,
  server_id INTEGER,
  kind TEXT NOT NULL,
  title TEXT NOT NULL,
  detail TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX idx_events_ts ON events (ts);
CREATE INDEX idx_events_server_ts ON events (server_id, ts);
