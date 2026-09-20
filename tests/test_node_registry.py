from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
from bot.node_registry import InMemoryNodeRegistry, KeyConflict, UnknownKey, InvalidRotation

class Cursor:
    rowcount=1
    def __init__(self, row=("ACTIVE",)): self.row=row; self.sql=[]
    def __enter__(self): return self
    def __exit__(self,*a): return False
    def execute(self,q,p=()): self.sql.append((q,p))
    def fetchone(self): return self.row
    def fetchall(self): return []
class Connection:
    def __init__(self,cursor=None): self.cursor_obj=cursor or Cursor(); self.commits=0
    def __enter__(self): self.commits+=1; return self
    def __exit__(self,*a): return False
    def cursor(self): return self.cursor_obj

def test_same_key_same_public_key_is_idempotent():
    r=InMemoryNodeRegistry(); r.register("n","k","pub",{"PROJECT"}); r.register("n","k","pub",{"PROJECT"}); assert len(r.get("n")["keys"])==1

def test_same_key_different_public_key_is_rejected():
    r=InMemoryNodeRegistry(); r.register("n","k","pub",{"PROJECT"})
    with pytest.raises(KeyConflict,match="REJECT_CONFLICT"): r.register("n","k","other",{"PROJECT"})

def test_two_active_keys_are_impossible():
    r=InMemoryNodeRegistry(); r.register("n","k1","pub1",{"PROJECT"})
    with pytest.raises(KeyConflict,match="ACTIVE_KEY_EXISTS"): r.register("n","k2","pub2",{"PROJECT"})

def test_rotation_requires_active_old_key_and_revocation_is_explicit():
    r=InMemoryNodeRegistry(); r.register("n","k1","pub1",{"PROJECT"}); r.rotate("n","k1","k2","pub2")
    with pytest.raises(InvalidRotation,match="OLD_KEY_NOT_ACTIVE"): r.rotate("n","k1","k3","pub3")
    r.revoke("n","k2")
    with pytest.raises(UnknownKey,match="UNKNOWN_KEY"): r.revoke("n","missing")

def test_double_rotation_has_one_active_key():
    r=InMemoryNodeRegistry(); r.register("n","k1","pub1",{"PROJECT"})
    def rotate(i):
        try: r.rotate("n","k1",f"k2-{i}",f"pub2-{i}"); return "ok"
        except Exception as exc: return type(exc).__name__
    with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(rotate,range(2)))
    assert results.count("ok")==1; assert sum(k["status"]=="ACTIVE" for k in r.get("n")["keys"])==1

def test_postgres_candidate_rejects_conflict_and_uses_lock():
    from bot.node_registry import PostgreSQLNodeRegistry
    cursor=Cursor(row=("existing-public",));
    with pytest.raises(KeyConflict,match="REJECT_CONFLICT"): PostgreSQLNodeRegistry(Connection(cursor)).register("n","k","different",{"PROJECT"})

def test_registry_register_rotate_revoke_uses_transactional_calls():
    from bot.node_registry import PostgreSQLNodeRegistry
    conn=Connection(); registry=PostgreSQLNodeRegistry(conn); registry.register("n","k1","pub1",{"PROJECT"},{"CAN_BROADCAST"}); registry.rotate("n","k1","k2","pub2"); registry.revoke("n","k1")
    assert conn.commits==3; statements=" ".join(sql for sql,_ in conn.cursor_obj.sql); assert "FOR UPDATE" in statements and "REVOKED" in statements

def test_schema_enforces_single_active_key_per_node():
    schema=Path("docs/r3_memory_postgres_schema.sql").read_text(); assert "r3_node_keys_one_active_per_node" in schema and "WHERE status='ACTIVE'" in schema

def test_provenance_commit_branch_not_hardcoded(monkeypatch):
    from tools.activate_protocollo import resolve_provenance, UNKNOWN
    monkeypatch.setenv("R3_BRANCH","observed-from-env"); monkeypatch.setenv("R3_COMMIT_SHA","deadbeef"); assert resolve_provenance()==("observed-from-env","deadbeef"); assert UNKNOWN=="UNKNOWN"
