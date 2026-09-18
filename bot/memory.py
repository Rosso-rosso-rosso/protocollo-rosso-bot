"""Memoria minima, append-only e scoped per il filo tra nodi.

La memoria non rende il sistema cosciente: conserva eventi verificabili,
provenienza e piani candidati con hash-chain e decisione esplicita.
"""

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
_LOCK = threading.Lock()


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _last_hash() -> str:
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
    event = {
        "ts": time.time_ns(),
        "node": NODE_ID,
        "kind": kind,
        "source_project": source_project,
        "permission_scope": permission_scope,
        "payload": payload,
        "prev_hash": _last_hash(),
    }
    event["event_hash"] = hashlib.sha256(_canonical(event).encode("utf-8")).hexdigest()
    with _LOCK:
        MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        with MEMORY_PATH.open("a", encoding="utf-8") as stream:
            stream.write(_canonical(event) + "\n")
    return event


def remember_classification(run_id: str, text: str, layer: str) -> dict[str, Any]:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return append_event(
        "classification",
        {"run_id": run_id, "input_sha256": digest, "layer": layer},
        source_project="protocollo-rosso-bot",
        permission_scope="PROJECT",
    )


def memory_health() -> dict[str, Any]:
    return {
        "node": NODE_ID,
        "path": str(MEMORY_PATH),
        "exists": MEMORY_PATH.exists(),
        "chain_head": _last_hash(),
    }


def plan_key(intent: str, source_project: str, permission_scope: str, version: str) -> str:
    material = {"intent": " ".join(intent.lower().split()), "source_project": source_project, "permission_scope": permission_scope, "version": version}
    return hashlib.sha256(_canonical(material).encode("utf-8")).hexdigest()


def store_plan(intent: str, plan: dict[str, Any], *, source_project: str, permission_scope: str = "PROJECT", version: str = "1") -> dict[str, Any]:
    key = plan_key(intent, source_project, permission_scope, version)
    return append_event(
        "candidate_plan",
        {"key": key, "intent": intent, "plan": plan, "decision": "LINK-ONLY", "version": version},
        source_project=source_project,
        permission_scope=permission_scope,
    )


def load_linked_plan(intent: str, *, source_project: str, permission_scope: str = "PROJECT", version: str = "1") -> dict[str, Any] | None:
    """Restituisce solo un piano già registrato come LINK-ONLY nello stesso scope."""
    key = plan_key(intent, source_project, permission_scope, version)
    if not MEMORY_PATH.exists():
        return None
    found: dict[str, Any] | None = None
    with MEMORY_PATH.open("r", encoding="utf-8") as stream:
        for line in stream:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            payload = event.get("payload", {})
            if event.get("kind") == "candidate_plan" and payload.get("key") == key and payload.get("decision") == "LINK-ONLY":
                found = payload
    return found
