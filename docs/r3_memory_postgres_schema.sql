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
