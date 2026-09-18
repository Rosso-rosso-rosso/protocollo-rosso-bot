"""Memoria append-only, scoped e atomica per il filo tra nodi."""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from pathlib import Path
from typing import Any
from bot.config import BASE_DIR

MEMORY_PATH = Path(os.getenv("R3_MEMORY_PATH", str(BASE_DIR / "r3-memory.jsonl")))
NODE_ID = os.getenv("R3_NODE_ID", "protocollo-rosso-bot")
REPOSITORY = os.getenv("R3_REPOSITORY", "Rosso-rosso-rosso/protocollo-rosso-bot")
BRANCH = os.getenv("R3_BRANCH", "UNKNOWN")
COMMIT_SHA = os.getenv("R3_COMMIT_SHA", "UNKNOWN")
_LOCK = threading.Lock()


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _last_hash_unlocked() -> str:
    if not MEMORY_PATH.exists():
        return "GENESIS"
    last = "GENESIS"
    with MEMORY_PATH.open("r", encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                try:
                    last = json.loads(line)["event_hash"]
                except (KeyError, json.JSONDecodeError):
                    return "BROKEN_CHAIN"
    return last


def append_event(kind: str, payload: dict[str, Any], *, source_project: str, permission_scope: str = "PROJECT") -> dict[str, Any]:
    if permission_scope not in {"LOCAL", "PROJECT", "NETWORK", "EXTERNAL_SHARE"}:
        raise ValueError("invalid permission scope")
    with _LOCK:
        # Lock covers read head -> event construction -> hash -> append -> flush.
        event = {
            "ts": time.time_ns(), "node": NODE_ID, "repository": REPOSITORY,
            "branch": BRANCH, "commit_sha": COMMIT_SHA, "kind": kind,
            "source_project": source_project, "permission_scope": permission_scope,
            "payload": payload, "prev_hash": _last_hash_unlocked(),
        }
        event["event_hash"] = hashlib.sha256(_canonical(event).encode("utf-8")).hexdigest()
        MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        with MEMORY_PATH.open("a", encoding="utf-8") as stream:
            stream.write(_canonical(event) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
    return event


def memory_health() -> dict[str, Any]:
    with _LOCK:
        return {"node": NODE_ID, "repository": REPOSITORY, "branch": BRANCH, "commit_sha": COMMIT_SHA, "path": str(MEMORY_PATH), "exists": MEMORY_PATH.exists(), "chain_head": _last_hash_unlocked()}


def remember_classification(run_id: str, text: str, layer: str) -> dict[str, Any]:
    return append_event("classification", {"run_id": run_id, "input_sha256": hashlib.sha256(text.encode()).hexdigest(), "layer": layer}, source_project="protocollo-rosso-bot")


def plan_key(intent: str, source_project: str, permission_scope: str, version: str) -> str:
    return hashlib.sha256(_canonical({"intent": " ".join(intent.lower().split()), "source_project": source_project, "permission_scope": permission_scope, "version": version}).encode()).hexdigest()


def store_plan(intent: str, plan: dict[str, Any], *, source_project: str, permission_scope: str = "PROJECT", version: str = "1") -> dict[str, Any]:
    return append_event("candidate_plan", {"key": plan_key(intent, source_project, permission_scope, version), "intent": intent, "plan": plan, "decision": "LINK-ONLY", "version": version}, source_project=source_project, permission_scope=permission_scope)


def load_linked_plan(intent: str, *, source_project: str, permission_scope: str = "PROJECT", version: str = "1") -> dict[str, Any] | None:
    key = plan_key(intent, source_project, permission_scope, version)
    if not MEMORY_PATH.exists(): return None
    found = None
    with MEMORY_PATH.open(encoding="utf-8") as stream:
        for line in stream:
            try: event = json.loads(line)
            except json.JSONDecodeError: continue
            payload = event.get("payload", {})
            if event.get("kind") == "candidate_plan" and payload.get("key") == key and payload.get("decision") == "LINK-ONLY": found = payload
    return found
