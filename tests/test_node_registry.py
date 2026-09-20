from __future__ import annotations

import pytest


class Cursor:
    def __init__(self): self.sql=[]; self.rows=[]
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def execute(self, query, params=()): self.sql.append((query, params))
    def fetchone(self): return ("ACTIVE",)
    def fetchall(self): return []

class Connection:
    def __init__(self): self.cursor_obj=Cursor(); self.commits=0
    def __enter__(self): self.commits += 1; return self
    def __exit__(self,*args): return False
    def cursor(self): return self.cursor_obj


def test_registry_rejects_invalid_scope():
    from bot.node_registry import PostgreSQLNodeRegistry
    with pytest.raises(ValueError): PostgreSQLNodeRegistry(Connection()).register("n", "k", "pub", {"INVALID"})


def test_registry_register_rotate_revoke_uses_transactional_calls():
    from bot.node_registry import PostgreSQLNodeRegistry
    conn=Connection(); registry=PostgreSQLNodeRegistry(conn)
    registry.register("n", "k1", "pub1", {"PROJECT"}, {"CAN_BROADCAST"})
    registry.rotate("n", "k1", "k2", "pub2")
    registry.revoke("n", "k1")
    assert conn.commits == 3
    statements=" ".join(sql for sql,_ in conn.cursor_obj.sql)
    assert "FOR UPDATE" in statements
    assert "ON CONFLICT" in statements
    assert "REVOKED" in statements


def test_registry_health_declares_candidate_only():
    from bot.node_registry import PostgreSQLNodeRegistry
    assert PostgreSQLNodeRegistry(Connection()).health()["registry"] == "configured_candidate"


def test_schema_enforces_single_active_key_per_node():
    from pathlib import Path

    schema = Path("docs/r3_memory_postgres_schema.sql").read_text()
    assert "UNIQUE" in schema
    assert "WHERE status='ACTIVE'" in schema
    assert "r3_node_keys_one_active_per_node" in schema


class RevokedCursor(Cursor):
    def fetchone(self):
        return ("REVOKED",)


class RevokedConnection(Connection):
    def __init__(self):
        super().__init__()
        self.cursor_obj = RevokedCursor()


def test_rotate_from_revoked_is_rejected():
    from bot.node_registry import PostgreSQLNodeRegistry

    registry = PostgreSQLNodeRegistry(RevokedConnection())
    with pytest.raises(ValueError, match="not ACTIVE"):
        registry.rotate("n", "k1", "k2", "pub2")
    statements = " ".join(sql for sql, _ in registry.connection.cursor_obj.sql)
    assert "ROTATING" not in statements


def test_provenance_commit_branch_not_hardcoded(monkeypatch):
    from pathlib import Path
    from tools.activate_protocollo import resolve_provenance, UNKNOWN

    source = Path("tools/activate_protocollo.py").read_text()
    assert "06bcb6fc6eed46ff6a24f98523c6a73b3548c257" not in source
    assert 'os.environ["R3_BRANCH"] = "feat/efficient-routing-cache"' not in source
    assert "resolve_provenance" in source
    assert UNKNOWN == "UNKNOWN"

    monkeypatch.setenv("R3_BRANCH", "observed-from-env")
    monkeypatch.setenv("R3_COMMIT_SHA", "deadbeef")
    branch, sha = resolve_provenance()
    assert branch == "observed-from-env"
    assert sha == "deadbeef"
