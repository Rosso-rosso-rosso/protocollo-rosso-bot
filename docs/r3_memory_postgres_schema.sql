-- Candidate H1 adapter only. Never run without an authorized PostgreSQL destination.
CREATE TABLE IF NOT EXISTS r3_events (
  event_hash TEXT PRIMARY KEY,
  node TEXT NOT NULL,
  prev_hash TEXT NOT NULL,
  source_project TEXT NOT NULL,
  permission_scope TEXT NOT NULL CHECK (permission_scope IN ('LOCAL','PROJECT','NETWORK','EXTERNAL_SHARE')),
  repository TEXT NOT NULL,
  branch TEXT NOT NULL,
  commit_sha TEXT NOT NULL,
  schema_version TEXT NOT NULL DEFAULT '1',
  payload JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS r3_heads (
  node TEXT PRIMARY KEY,
  head TEXT NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS r3_events_node_prev_idx ON r3_events(node, prev_hash);

CREATE TABLE IF NOT EXISTS r3_nodes (
  node_id TEXT PRIMARY KEY,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS r3_node_keys (
  node_id TEXT NOT NULL REFERENCES r3_nodes(node_id) ON DELETE CASCADE,
  key_id TEXT NOT NULL,
  public_key TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('ACTIVE','ROTATING','REVOKED')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  revoked_at TIMESTAMPTZ,
  PRIMARY KEY (node_id, key_id)
);

CREATE TABLE IF NOT EXISTS r3_node_scopes (
  node_id TEXT NOT NULL REFERENCES r3_nodes(node_id) ON DELETE CASCADE,
  scope TEXT NOT NULL CHECK (scope IN ('LOCAL','PROJECT','NETWORK','EXTERNAL_SHARE')),
  PRIMARY KEY (node_id, scope)
);

CREATE TABLE IF NOT EXISTS r3_node_capabilities (
  node_id TEXT NOT NULL REFERENCES r3_nodes(node_id) ON DELETE CASCADE,
  capability TEXT NOT NULL,
  PRIMARY KEY (node_id, capability)
);
CREATE INDEX IF NOT EXISTS r3_node_keys_status_idx ON r3_node_keys(node_id, status);
