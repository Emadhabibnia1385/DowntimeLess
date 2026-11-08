ALTER TABLE metrics ADD COLUMN load1 REAL;
ALTER TABLE metrics ADD COLUMN swap_pct REAL;
ALTER TABLE metrics ADD COLUMN conns INTEGER;
UPDATE servers SET permission='full';
