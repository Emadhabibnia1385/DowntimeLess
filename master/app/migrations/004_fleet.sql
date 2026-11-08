-- which brand a server serves: emad, mobin or shared
ALTER TABLE servers ADD COLUMN fleet TEXT NOT NULL DEFAULT 'emad';
