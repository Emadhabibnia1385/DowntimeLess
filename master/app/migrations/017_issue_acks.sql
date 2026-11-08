-- Issues the team acknowledged: still listed, but quiet (no Telegram, not counted) until the ack ends.
CREATE TABLE issue_acks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  key TEXT NOT NULL,
  mode TEXT NOT NULL CHECK (mode IN ('until_resolved','24h','7d','always')),
  until INTEGER,
  severity TEXT NOT NULL,
  note TEXT NOT NULL DEFAULT '',
  created_by INTEGER,
  created_at INTEGER NOT NULL,
  UNIQUE (workspace_id, key)
);
