-- Bytes between a server and each peer server (relay <-> exit), counted by the agent's nftables counters.
ALTER TABLE servers ADD COLUMN acct_on INTEGER NOT NULL DEFAULT 0;
CREATE TABLE link_traffic (
  server_id INTEGER NOT NULL REFERENCES servers(id) ON DELETE CASCADE,
  peer_ip TEXT NOT NULL,
  hour INTEGER NOT NULL,
  in_bytes INTEGER NOT NULL DEFAULT 0,
  out_bytes INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (server_id, peer_ip, hour)
);
CREATE TABLE link_prev (
  server_id INTEGER NOT NULL REFERENCES servers(id) ON DELETE CASCADE,
  peer_ip TEXT NOT NULL,
  in_bytes INTEGER NOT NULL,
  out_bytes INTEGER NOT NULL,
  PRIMARY KEY (server_id, peer_ip)
);
CREATE INDEX link_traffic_hour ON link_traffic(hour);
