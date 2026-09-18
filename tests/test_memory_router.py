from __future__ import annotations
import hashlib, json

def event(node, source, scope, payload, prev="GENESIS", ts=1):
    value={"ts":ts,"node":node,"kind":"test","source_project":source,"permission_scope":scope,"payload":payload,"prev_hash":prev}
    value["event_hash"]=hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest(); return value

def test_router_accepts_deduplicates_and_links():
    from bot.memory_router import MemoryFabricRouter
    r=MemoryFabricRouter(destination_project="target"); local=event("a","target","PROJECT",{"n":1}); remote=event("b","source","NETWORK",{"n":2})
    assert r.route(local).decision=="ACCEPT"; assert r.route(local).decision=="DUPLICATE"; assert r.route(remote).decision=="LINK-ONLY"; assert r.health()=={"events":2,"nodes":["a","b"],"links":1,"rejections":0}

def test_router_rejects_scope_hash_and_chain():
    from bot.memory_router import MemoryFabricRouter
    r=MemoryFabricRouter(destination_project="target"); forbidden=event("x","source","PROJECT",{"n":1}); assert r.route(forbidden).reason=="cross_project_scope_forbids_adoption"
    bad=event("y","target","PROJECT",{"n":2}); bad["payload"]={"n":999}; assert r.route(bad).reason=="hash_mismatch"; assert r.route(event("z","target","PROJECT",{"n":3},prev="wrong")).reason=="chain_gap_or_replay"

def test_restart_replay_and_duplicate_after_restart():
    from bot.memory_router import InMemoryStore, MemoryFabricRouter
    first=event("a","target","PROJECT",{"n":1}); store=InMemoryStore([first]); r=MemoryFabricRouter(destination_project="target",store=store); assert r.route(first).decision=="DUPLICATE"; assert store.get_head("a")==first["event_hash"]

def test_fork_and_out_of_order_are_rejected():
    from bot.memory_router import InMemoryStore, MemoryFabricRouter
    first=event("a","target","PROJECT",{"n":1}); child=event("a","target","PROJECT",{"n":2},first["event_hash"],2); fork=event("a","target","PROJECT",{"n":3},first["event_hash"],3); r=MemoryFabricRouter(destination_project="target",store=InMemoryStore([first])); assert r.route(child).decision=="ACCEPT"; assert r.route(fork).reason=="chain_gap_or_replay"; assert r.route(event("a","target","PROJECT",{"n":4},prev="GENESIS",ts=4)).reason=="chain_gap_or_replay"

def test_chain_bootstrap():
    from bot.memory_router import MemoryFabricRouter
    r=MemoryFabricRouter(destination_project="target"); result=r.bootstrap(node_id="remote",known_head="abc",provenance={"repository":"repo"},schema_version="1"); assert result["decision"]=="REPLAY_REQUIRED"; assert result["schema_version"]=="1"
