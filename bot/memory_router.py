"""CAP-R3-001 Memory Fabric Router.

The default store is deterministic in-memory for tests. The PostgreSQL adapter
is a candidate H1 and is never activated without an authorized DSN.
"""
from __future__ import annotations
import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Iterable

SCOPES = {"LOCAL", "PROJECT", "NETWORK", "EXTERNAL_SHARE"}

def canonical_event(event: dict[str, Any]) -> str:
    return json.dumps({k: v for k, v in event.items() if k != "event_hash"}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def verify_hash(event: dict[str, Any]) -> bool:
    return event.get("event_hash") == hashlib.sha256(canonical_event(event).encode()).hexdigest()

class MemoryStore(ABC):
    @abstractmethod
    def append_if_head_matches(self, event: dict[str, Any], expected_head: str) -> bool: ...
    @abstractmethod
    def get_head(self, node: str) -> str: ...
    @abstractmethod
    def contains_hash(self, event_hash: str) -> bool: ...
    @abstractmethod
    def get_event(self, event_hash: str) -> dict[str, Any] | None: ...
    @abstractmethod
    def iterate_events(self) -> Iterable[dict[str, Any]]: ...
    @abstractmethod
    def health(self) -> dict[str, Any]: ...

class InMemoryStore(MemoryStore):
    def __init__(self, events: Iterable[dict[str, Any]] = ()):
        self.events: dict[str, dict[str, Any]] = {}
        self.heads: dict[str, str] = {}
        for event in events:
            self._replay(event)

    def _replay(self, event: dict[str, Any]) -> None:
        h, node, prev = event.get("event_hash"), event.get("node"), event.get("prev_hash")
        if not h or not node or not verify_hash(event) or prev != self.get_head(node):
            raise ValueError("invalid ledger replay")
        self.events[h] = dict(event)
        self.heads[node] = h

    def append_if_head_matches(self, event: dict[str, Any], expected_head: str) -> bool:
        node, h = event["node"], event["event_hash"]
        if self.get_head(node) != expected_head or h in self.events: return False
        self._replay(event)
        return True

    def get_head(self, node: str) -> str: return self.heads.get(node, "GENESIS")
    def contains_hash(self, event_hash: str) -> bool: return event_hash in self.events
    def get_event(self, event_hash: str) -> dict[str, Any] | None: return self.events.get(event_hash)
    def iterate_events(self) -> Iterable[dict[str, Any]]: return tuple(self.events.values())
    def health(self) -> dict[str, Any]: return {"events": len(self.events), "nodes": sorted(self.heads)}

class PostgreSQLMemoryStore(MemoryStore):
    """Candidate H1 adapter. Requires external psycopg and an authorized DSN."""
    def __init__(self, connection): self.connection = connection
    def append_if_head_matches(self, event, expected_head):
        with self.connection:
            with self.connection.cursor() as cur:
                cur.execute("INSERT INTO r3_events(event_hash,node,prev_hash,payload) SELECT %s,%s,%s,%s WHERE COALESCE((SELECT head FROM r3_heads WHERE node=%s FOR UPDATE),'GENESIS')=%s ON CONFLICT (event_hash) DO NOTHING RETURNING event_hash", (event["event_hash"], event["node"], event["prev_hash"], json.dumps(event), event["node"], expected_head))
                ok = cur.fetchone() is not None
                if ok: cur.execute("INSERT INTO r3_heads(node,head) VALUES(%s,%s) ON CONFLICT(node) DO UPDATE SET head=EXCLUDED.head", (event["node"], event["event_hash"]))
                return ok
    def get_head(self, node):
        with self.connection.cursor() as cur:
            cur.execute("SELECT head FROM r3_heads WHERE node=%s", (node,)); row = cur.fetchone()
        return row[0] if row else "GENESIS"
    def contains_hash(self, event_hash):
        with self.connection.cursor() as cur:
            cur.execute("SELECT 1 FROM r3_events WHERE event_hash=%s", (event_hash,)); return cur.fetchone() is not None
    def get_event(self, event_hash):
        with self.connection.cursor() as cur:
            cur.execute("SELECT payload FROM r3_events WHERE event_hash=%s", (event_hash,)); row = cur.fetchone()
        return json.loads(row[0]) if row else None
    def iterate_events(self):
        with self.connection.cursor() as cur:
            cur.execute("SELECT payload FROM r3_events ORDER BY event_hash"); return tuple(json.loads(row[0]) for row in cur.fetchall())
    def health(self): return {"backend": "postgresql", "status": "configured_candidate"}

@dataclass(frozen=True)
class RouteResult:
    decision: str
    reason: str
    event_hash: str
    destination: str

class MemoryFabricRouter:
    def __init__(self, *, destination_project: str, store: MemoryStore | None = None):
        self.destination_project = destination_project
        self.store = store or InMemoryStore()
        self.links: list[dict[str, Any]] = []
        self.rejections: list[dict[str, Any]] = []

    def route(self, event: dict[str, Any]) -> RouteResult:
        h, node, source, scope = (str(event.get(k, "")) for k in ("event_hash", "node", "source_project", "permission_scope"))
        if not h or not node or not source or scope not in SCOPES: return self._reject(h, "invalid_required_fields")
        if self.store.contains_hash(h): return RouteResult("DUPLICATE", "event_hash_already_seen", h, self.destination_project)
        if not verify_hash(event): return self._reject(h, "hash_mismatch")
        expected = self.store.get_head(node)
        if event.get("prev_hash") != expected: return self._reject(h, "chain_gap_or_replay")
        cross = source != self.destination_project
        if cross and scope in {"LOCAL", "PROJECT"}: return self._reject(h, "cross_project_scope_forbids_adoption")
        if not self.store.append_if_head_matches(event, expected): return self._reject(h, "concurrent_head_conflict")
        if cross:
            self.links.append({"event_hash": h, "source_project": source, "destination": self.destination_project, "transformation": "LINK-ONLY", "original_scope": scope})
            return RouteResult("LINK-ONLY", "cross_project_event_linked_without_adoption", h, self.destination_project)
        return RouteResult("ACCEPT", "same_project_event_appended", h, self.destination_project)

    def bootstrap(self, *, node_id: str, known_head: str, provenance: dict[str, Any], schema_version: str = "1") -> dict[str, Any]:
        current = self.store.get_head(node_id)
        return {"node_id": node_id, "known_head": known_head, "current_head": current, "provenance": provenance, "schema_version": schema_version, "decision": "READY" if known_head == current else "REPLAY_REQUIRED"}

    def _reject(self, h: str, reason: str) -> RouteResult:
        self.rejections.append({"event_hash": h, "reason": reason}); return RouteResult("REJECT", reason, h, self.destination_project)
    def health(self) -> dict[str, Any]:
        out = dict(self.store.health()); out.update({"links": len(self.links), "rejections": len(self.rejections)}); return out
