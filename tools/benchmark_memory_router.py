from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bot.memory_router import MemoryFabricRouter


def event(node, source, scope, n, prev="GENESIS"):
    value = {"ts": n, "node": node, "kind": "benchmark", "source_project": source, "permission_scope": scope, "payload": {"n": n}, "prev_hash": prev}
    value["event_hash"] = hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return value


router = MemoryFabricRouter(destination_project="target")
start = time.perf_counter()
accepted = linked = rejected = duplicate = 0
heads = {"node-a": "GENESIS", "node-b": "GENESIS"}
for n in range(1000):
    node, source, scope = ("node-a", "target", "PROJECT") if n % 2 == 0 else ("node-b", "source", "NETWORK")
    item = event(node, source, scope, n, heads[node])
    heads[node] = item["event_hash"]
    decision = router.route(item).decision
    if decision == "ACCEPT": accepted += 1
    elif decision == "LINK-ONLY": linked += 1
    elif decision == "REJECT": rejected += 1
    duplicate += router.route(item).decision == "DUPLICATE"
elapsed = time.perf_counter() - start
result = {"benchmark": "IN_MEMORY_ROUTER_MICROBENCHMARK", "events": 1000, "accepted": accepted, "linked": linked, "rejected": rejected, "duplicates": duplicate, "elapsed_ms": round(elapsed * 1000, 3), "events_per_second": round(1000 / elapsed, 2), "note": "in-memory only; not a distributed durability or network capacity claim", "health": router.health()}
print(json.dumps(result, indent=2, sort_keys=True))
