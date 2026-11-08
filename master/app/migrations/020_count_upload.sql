-- Per server: 1 = the quota counts traffic by the workspace basis (today's behaviour), 0 = upload is free, only download counts.
ALTER TABLE servers ADD COLUMN count_upload INTEGER NOT NULL DEFAULT 1;
