from __future__ import annotations

import hashlib
import json
import time


def event(node, source, scope, payload, prev="GENESIS"):
    value = {"ts": 1, "node": node, "kind": "test", "source_project": source, "permission_scope": scope, "payload": payload, "prev_hash": prev}
    value["event_hash"] = hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return value


def test_router_accepts_deduplicates_and_links():
    from bot.memory_router import MemoryFabricRouter

    router = MemoryFabricRouter(destination_project="target")
    local = event("node-a", "target", "PROJECT", {"n": 1})
    remote = event("node-b", "source", "NETWORK", {"n": 2})
    assert router.route(local).decision == "ACCEPT"
    assert router.route(local).decision == "DUPLICATE"
    assert router.route(remote).decision == "LINK-ONLY"
    assert len(router.canonical) == 1
    assert len(router.links) == 1


def test_router_rejects_scope_hash_and_chain():
    from bot.memory_router import MemoryFabricRouter

    router = MemoryFabricRouter(destination_project="target")
    forbidden = event("node-x", "source", "PROJECT", {"n": 1})
    assert router.route(forbidden).reason == "cross_project_scope_forbids_adoption"
    bad = dict(event("node-y", "target", "PROJECT", {"n": 2}))
    bad["payload"] = {"n": 999}
    assert router.route(bad).reason == "hash_mismatch"
    gap = event("node-y", "target", "PROJECT", {"n": 3}, prev="wrong")
    assert router.route(gap).reason == "chain_gap_or_replay"


def test_router_health_counts():
    from bot.memory_router import MemoryFabricRouter

    router = MemoryFabricRouter(destination_project="target")
    router.route(event("node-a", "target", "PROJECT", {"n": 1}))
    assert router.health() == {"canonical": 1, "links": 0, "rejections": 0, "seen": 1, "nodes": ["node-a"]}
