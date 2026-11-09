-- TCP (and TLS) probes from Iran relays to the real listening ports of the foreign servers of their workspace.
-- Path verdicts (blacklisted, relay_egress, relay_filtered) come from these; ICMP alone is only a note.

-- one row per probe result; reached through server_id (the relay that probed), kept two days
CREATE TABLE probes (
  server_id INTEGER NOT NULL REFERENCES servers(id) ON DELETE CASCADE,
  ts INTEGER NOT NULL,
  target TEXT NOT NULL,
  port INTEGER NOT NULL,
  ok INTEGER NOT NULL,          -- 1: the TCP connection was accepted
  rtt REAL,                     -- connect time in ms when ok
  error TEXT,                   -- timeout | refused | unreachable | error, when not ok
  tls INTEGER                   -- NULL not tried, 1 handshake done, 0 handshake failed
);
CREATE INDEX probes_server_ts ON probes(server_id, ts);
CREATE INDEX probes_ts ON probes(ts);

-- ports that answered at least once: only these decide a verdict, so a firewalled or local-only port never does
CREATE TABLE probe_ports (
  workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  target TEXT NOT NULL,
  port INTEGER NOT NULL,
  last_ok INTEGER NOT NULL,
  PRIMARY KEY (workspace_id, target, port)
);
