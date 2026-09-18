"""Memory Fabric Router — CAP-R3-001.

Read/write logic is deliberately explicit and deterministic. Cross-project
packets are never adopted canonically: they are linked only when the declared
scope permits reuse.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

SCOPES = {"LOCAL", "PROJECT", "NETWORK", "EXTERNAL_SHARE"}


def canonical_event(event: dict[str, Any]) -> str:
    body = {k: v for k, v in event.items() if k != "event_hash"}
    return json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def verify_hash(event: dict[str, Any]) -> bool:
    expected = hashlib.sha256(canonical_event(event).encode("utf-8")).hexdigest()
    return event.get("event_hash") == expected


@dataclass(frozen=True)
class RouteResult:
    decision: str
    reason: str
    event_hash: str
    destination: str


class MemoryFabricRouter:
    def __init__(self, *, destination_project: str):
        self.destination_project = destination_project
        self.seen: set[str] = set()
        self.heads: dict[str, str] = {}
        self.canonical: list[dict[str, Any]] = []
        self.links: list[dict[str, Any]] = []
        self.rejections: list[dict[str, Any]] = []

    def route(self, event: dict[str, Any]) -> RouteResult:
        event_hash = str(event.get("event_hash", ""))
        node = str(event.get("node", ""))
        source = str(event.get("source_project", ""))
        scope = str(event.get("permission_scope", ""))
        if not event_hash or not node or not source or scope not in SCOPES:
            return self._reject(event_hash, "invalid_required_fields")
        if not verify_hash(event):
            return self._reject(event_hash, "hash_mismatch")
        if event_hash in self.seen:
            return RouteResult("DUPLICATE", "event_hash_already_seen", event_hash, self.destination_project)
        previous = str(event.get("prev_hash", ""))
        expected_previous = self.heads.get(node, "GENESIS")
        if previous != expected_previous:
            return self._reject(event_hash, "chain_gap_or_replay")
        cross_project = source != self.destination_project
        if cross_project and scope in {"LOCAL", "PROJECT"}:
            return self._reject(event_hash, "cross_project_scope_forbids_adoption")
        self.seen.add(event_hash)
        self.heads[node] = event_hash
        if cross_project:
            self.links.append({"event_hash": event_hash, "source_project": source, "destination": self.destination_project, "transformation": "LINK-ONLY", "original_scope": scope})
            return RouteResult("LINK-ONLY", "cross_project_event_linked_without_adoption", event_hash, self.destination_project)
        self.canonical.append(dict(event))
        return RouteResult("ACCEPT", "same_project_event_appended", event_hash, self.destination_project)

    def _reject(self, event_hash: str, reason: str) -> RouteResult:
        self.rejections.append({"event_hash": event_hash, "reason": reason})
        return RouteResult("REJECT", reason, event_hash, self.destination_project)

    def health(self) -> dict[str, Any]:
        return {"canonical": len(self.canonical), "links": len(self.links), "rejections": len(self.rejections), "seen": len(self.seen), "nodes": sorted(self.heads)}
