-- Telegram destinations the owner adds by hand, and which destination each kind of alert uses.
CREATE TABLE telegram_channels (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  chat_id TEXT NOT NULL UNIQUE,
  created_at INTEGER NOT NULL
);
-- route is 'panel' (listed only), 'admins' (private message to every admin) or 'channel:<id>'
CREATE TABLE rule_routes (rule TEXT PRIMARY KEY, route TEXT NOT NULL);
-- one Telegram message per incident: when its opening message went out; and keys that flap
ALTER TABLE incidents ADD COLUMN notified_at INTEGER;
CREATE TABLE flapping (key TEXT PRIMARY KEY, since INTEGER NOT NULL);
-- event state kept from the agent reports: reboot, public IP change, resize
ALTER TABLE servers ADD COLUMN rebooted_at INTEGER;
ALTER TABLE servers ADD COLUMN prev_ip TEXT;
ALTER TABLE servers ADD COLUMN ip_changed_at INTEGER;
ALTER TABLE servers ADD COLUMN resized_at INTEGER;
ALTER TABLE servers ADD COLUMN resized_from TEXT;
-- optional traffic quota: size in GiB and the day of the month it resets
ALTER TABLE servers ADD COLUMN quota_gb REAL;
ALTER TABLE servers ADD COLUMN quota_reset_day INTEGER;
