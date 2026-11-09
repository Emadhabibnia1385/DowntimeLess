-- Self-registration, linking a Telegram account to a signed-in account (with a one-way merge), invites by Telegram
-- username. Forward only: nothing here drops or rewrites a row.

-- A merge can leave one person owning several workspaces, so "one owned workspace" is kept by the single-statement insert
-- in app/workspaces.py (ensure_personal) instead of a unique index. Dropping an index never touches a row.
DROP INDEX IF EXISTS workspaces_owner;
CREATE INDEX workspaces_owner_user ON workspaces(owner_user_id);

-- caps per workspace; NULL is the panel default (200 servers, 300 domains). Self-registered workspaces get 20 and 30.
ALTER TABLE workspaces ADD COLUMN server_cap INTEGER;
ALTER TABLE workspaces ADD COLUMN domain_cap INTEGER;

-- a key moved by an account merge never acts above the role its creator had in that workspace at the time
ALTER TABLE api_keys ADD COLUMN role_cap TEXT CHECK (role_cap IS NULL OR role_cap IN ('viewer','operator','admin','owner'));

-- panel-wide switches (registration_open); only the panel owner changes them
CREATE TABLE app_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
-- an existing panel does not silently start accepting sign-ups from the internet: closed there, the owner opens it;
-- a fresh install (no people yet) keeps the default, open
INSERT INTO app_settings (key, value) SELECT 'registration_open', '0' WHERE EXISTS (SELECT 1 FROM users);

-- linking a Telegram account to the account signed in on one browser session: bot deep link, then two confirmations
CREATE TABLE link_tokens (
  id INTEGER PRIMARY KEY,
  token_hash TEXT NOT NULL UNIQUE,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  -- pending: link shown; seen: the bot got /start from a Telegram account; confirmed: it said yes in Telegram;
  -- done: the panel confirmed and the link (or merge) happened; denied: refused or cancelled
  status TEXT NOT NULL CHECK (status IN ('pending','seen','confirmed','done','denied')),
  tg_id INTEGER,
  tg_username TEXT,
  tg_name TEXT NOT NULL DEFAULT '',
  -- the one-time code the bot shows after a yes; the panel must send it back (hash only), a few tries
  code_hash TEXT,
  code_tries INTEGER NOT NULL DEFAULT 0,
  created_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL,
  done_at INTEGER
);
CREATE INDEX link_tokens_user ON link_tokens(user_id);

-- someone invited by Telegram username; becomes a membership when an account with that username links or starts the bot
CREATE TABLE workspace_invites (
  id INTEGER PRIMARY KEY,
  workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  tg_username TEXT NOT NULL,  -- lower case, without @
  role TEXT NOT NULL CHECK (role IN ('viewer','operator')),
  display_name TEXT NOT NULL DEFAULT '',
  invited_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
  created_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL,
  claimed_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
  claimed_tg_id INTEGER,
  claimed_at INTEGER
);
CREATE UNIQUE INDEX workspace_invites_open ON workspace_invites(workspace_id, tg_username) WHERE claimed_at IS NULL;
CREATE INDEX workspace_invites_username ON workspace_invites(tg_username);
CREATE INDEX workspace_invites_ws ON workspace_invites(workspace_id);
