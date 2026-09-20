"""Persistent node registry contract and PostgreSQL adapter for CAP-R3-002."""
from __future__ import annotations
import json
from abc import ABC, abstractmethod
from typing import Any

VALID_SCOPES = {"LOCAL", "PROJECT", "NETWORK", "EXTERNAL_SHARE"}
VALID_STATUS = {"ACTIVE", "ROTATING", "REVOKED"}

class NodeRegistryStore(ABC):
    @abstractmethod
    def register(self, node_id: str, key_id: str, public_key: str, scopes: set[str], capabilities: set[str] = set()) -> None: ...
    @abstractmethod
    def get(self, node_id: str) -> dict[str, Any] | None: ...
    @abstractmethod
    def rotate(self, node_id: str, old_key_id: str, new_key_id: str, new_public_key: str) -> None: ...
    @abstractmethod
    def revoke(self, node_id: str, key_id: str) -> None: ...
    @abstractmethod
    def authorize(self, node_id: str, key_id: str, scope: str, capability: str | None = None) -> bool: ...
    @abstractmethod
    def health(self) -> dict[str, Any]: ...

class PostgreSQLNodeRegistry(NodeRegistryStore):
    """Uses caller-owned connection; never creates credentials or connections."""
    def __init__(self, connection): self.connection = connection
    def register(self, node_id, key_id, public_key, scopes, capabilities=set()):
        if not scopes <= VALID_SCOPES: raise ValueError("invalid scopes")
        with self.connection:
            with self.connection.cursor() as cur:
                cur.execute("INSERT INTO r3_nodes(node_id) VALUES(%s) ON CONFLICT(node_id) DO NOTHING", (node_id,))
                cur.execute("INSERT INTO r3_node_keys(node_id,key_id,public_key,status) VALUES(%s,%s,%s,'ACTIVE') ON CONFLICT(node_id,key_id) DO NOTHING", (node_id,key_id,public_key))
                for scope in scopes: cur.execute("INSERT INTO r3_node_scopes(node_id,scope) VALUES(%s,%s) ON CONFLICT DO NOTHING", (node_id,scope))
                for capability in capabilities: cur.execute("INSERT INTO r3_node_capabilities(node_id,capability) VALUES(%s,%s) ON CONFLICT DO NOTHING", (node_id,capability))
    def get(self, node_id):
        with self.connection.cursor() as cur:
            cur.execute("SELECT k.key_id,k.public_key,k.status,k.created_at FROM r3_node_keys k WHERE k.node_id=%s ORDER BY k.created_at", (node_id,)); keys=[dict(key_id=r[0],public_key=r[1],status=r[2],created_at=r[3]) for r in cur.fetchall()]
            cur.execute("SELECT scope FROM r3_node_scopes WHERE node_id=%s", (node_id,)); scopes={r[0] for r in cur.fetchall()}
            cur.execute("SELECT capability FROM r3_node_capabilities WHERE node_id=%s", (node_id,)); capabilities={r[0] for r in cur.fetchall()}
        return {"node_id":node_id,"keys":keys,"scopes":scopes,"capabilities":capabilities} if keys else None
    def rotate(self, node_id, old_key_id, new_key_id, new_public_key):
        with self.connection:
            with self.connection.cursor() as cur:
                cur.execute("SELECT status FROM r3_node_keys WHERE node_id=%s AND key_id=%s FOR UPDATE", (node_id,old_key_id))
                row = cur.fetchone()
                if row is None: raise KeyError("unknown old key")
                if row[0] != "ACTIVE": raise ValueError("old key is not ACTIVE")
                cur.execute("UPDATE r3_node_keys SET status='ROTATING' WHERE node_id=%s AND key_id=%s AND status='ACTIVE'", (node_id,old_key_id))
                if getattr(cur, "rowcount", 1) == 0: raise ValueError("old key is not ACTIVE")
                cur.execute("INSERT INTO r3_node_keys(node_id,key_id,public_key,status) VALUES(%s,%s,%s,'ACTIVE')", (node_id,new_key_id,new_public_key))
    def revoke(self, node_id, key_id):
        with self.connection:
            with self.connection.cursor() as cur: cur.execute("UPDATE r3_node_keys SET status='REVOKED',revoked_at=now() WHERE node_id=%s AND key_id=%s", (node_id,key_id))
    def authorize(self, node_id, key_id, scope, capability=None):
        if scope not in VALID_SCOPES: return False
        node=self.get(node_id)
        return bool(node and any(k["key_id"]==key_id and k["status"]=="ACTIVE" for k in node["keys"]) and scope in node["scopes"] and (capability is None or capability in node["capabilities"]))
    def health(self): return {"backend":"postgresql","registry":"configured_candidate"}
