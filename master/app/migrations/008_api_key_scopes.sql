CREATE TABLE api_keys_new (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  prefix TEXT NOT NULL,
  token_hash TEXT NOT NULL UNIQUE,
  scope TEXT NOT NULL CHECK (scope IN ('read','full')),
  created_by INTEGER REFERENCES users(id),
  created_at INTEGER NOT NULL,
  last_used INTEGER
);
INSERT INTO api_keys_new SELECT id, name, prefix, token_hash, CASE scope WHEN 'read' THEN 'read' ELSE 'full' END, created_by, created_at, last_used FROM api_keys;
DROP TABLE api_keys;
ALTER TABLE api_keys_new RENAME TO api_keys;
