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
