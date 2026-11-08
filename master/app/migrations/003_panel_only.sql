-- a panel-only server is role 'panel' with this flag; the API shows it as role 'panel_only'
ALTER TABLE servers ADD COLUMN panel_only INTEGER NOT NULL DEFAULT 0;
