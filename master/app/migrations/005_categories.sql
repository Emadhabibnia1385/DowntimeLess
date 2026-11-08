-- free categories for servers; a server may have none
CREATE TABLE categories (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  created_at INTEGER NOT NULL
);
ALTER TABLE servers ADD COLUMN category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL;
-- an old install carried a fixed fleet label: keep it as a category only where servers used it;
-- a fresh install starts with no categories at all
INSERT INTO categories (name, created_at) SELECT 'عماد', strftime('%s','now') WHERE EXISTS (SELECT 1 FROM servers WHERE fleet NOT IN ('mobin','shared'));
INSERT INTO categories (name, created_at) SELECT 'مبین', strftime('%s','now') WHERE EXISTS (SELECT 1 FROM servers WHERE fleet = 'mobin');
INSERT INTO categories (name, created_at) SELECT 'مشترک', strftime('%s','now') WHERE EXISTS (SELECT 1 FROM servers WHERE fleet = 'shared');
UPDATE servers SET category_id = (SELECT id FROM categories WHERE name = CASE servers.fleet WHEN 'mobin' THEN 'مبین' WHEN 'shared' THEN 'مشترک' ELSE 'عماد' END);
