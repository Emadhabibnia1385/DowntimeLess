-- free categories for servers; a server may have none
CREATE TABLE categories (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  created_at INTEGER NOT NULL
);
ALTER TABLE servers ADD COLUMN category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL;
INSERT INTO categories (name, created_at) VALUES ('عماد', strftime('%s','now')), ('مبین', strftime('%s','now')), ('مشترک', strftime('%s','now'));
UPDATE servers SET category_id = (SELECT id FROM categories WHERE name = CASE servers.fleet WHEN 'mobin' THEN 'مبین' WHEN 'shared' THEN 'مشترک' ELSE 'عماد' END);
