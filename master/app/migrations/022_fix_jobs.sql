-- One-click fixes: at most one identical fix waiting per server, enforced by the database (two clicks at once).
CREATE UNIQUE INDEX jobs_fix_pending ON jobs (server_id, kind, args)
  WHERE status IN ('queued','sent') AND kind IN ('nft_reload','sysctl_apply','ipset_sync','tunnel_restart');
