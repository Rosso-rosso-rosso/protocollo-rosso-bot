"""R3 Fabric v2: per-node Ed25519 identity and signed envelopes."""
from __future__ import annotations
import base64, hashlib, json, secrets, time
from dataclasses import dataclass, field
from multiprocessing.queues import Queue
from typing import Any
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives import serialization
from bot.memory_router import MemoryFabricRouter

SCOPES = {"LOCAL", "PROJECT", "NETWORK", "EXTERNAL_SHARE"}
STATUSES = {"ACTIVE", "ROTATING", "REVOKED"}

def b64(data: bytes) -> str: return base64.urlsafe_b64encode(data).decode().rstrip("=")
def unb64(value: str) -> bytes: return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
def canon(value: dict[str, Any]) -> bytes: return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
def digest(value: Any) -> str: return hashlib.sha256(canon(value) if isinstance(value, dict) else value).hexdigest()

@dataclass
class KeyEntry:
    key_id: str
    public_key: str
    created_at: float
    status: str = "ACTIVE"

@dataclass
class NodeRecord:
    node_id: str
    keys: dict[str, KeyEntry]
    scopes: set[str]
    capabilities: set[str] = field(default_factory=set)

class NodeRegistry:
    def __init__(self): self.nodes: dict[str, NodeRecord] = {}
    def register(self, node_id: str, key_id: str, public_key: str, scopes: set[str], capabilities: set[str] | None = None, created_at: float | None = None) -> None:
        if not scopes <= SCOPES: raise ValueError("invalid scopes")
        self.nodes[node_id] = NodeRecord(node_id, {key_id: KeyEntry(key_id, public_key, created_at or time.time())}, set(scopes), set(capabilities or set()))
    def rotate(self, node_id: str, new_key_id: str, new_public_key: str) -> None:
        node = self.nodes[node_id]; current = self.active_key(node_id); current.status = "ROTATING"; node.keys[new_key_id] = KeyEntry(new_key_id, new_public_key, time.time(), "ACTIVE")
    def revoke(self, node_id: str, key_id: str) -> None: self.nodes[node_id].keys[key_id].status = "REVOKED"
    def active_key(self, node_id: str) -> KeyEntry:
        node = self.nodes[node_id]
        for key in node.keys.values():
            if key.status == "ACTIVE": return key
        raise ValueError("no active key")

class NodeIdentity:
    def __init__(self, node_id: str, *, key_id: str | None = None):
        self.node_id = node_id; self.key_id = key_id or f"{node_id}-{secrets.token_hex(4)}"; self.private = Ed25519PrivateKey.generate()
    @property
    def public_key(self) -> str: return b64(self.private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw))
    def public_record(self) -> dict[str, Any]: return {"node_id": self.node_id, "key_id": self.key_id, "public_key": self.public_key, "private_key_exported": False, "created_at": time.time(), "status": "ACTIVE"}
    def sign(self, body: dict[str, Any]) -> str: return b64(self.private.sign(canon(body)))

class FabricTransport:
    def send(self, envelope: dict[str, Any]) -> None: raise NotImplementedError
    def receive(self, timeout: float | None = None) -> dict[str, Any]: raise NotImplementedError
    def health(self) -> dict[str, Any]: raise NotImplementedError

class LoopbackTransport(FabricTransport):
    def __init__(self, queue: Queue): self.queue = queue
    def send(self, envelope): self.queue.put(envelope)
    def receive(self, timeout=None): return self.queue.get(timeout=timeout)
    def health(self): return {"transport": "loopback", "external": False}

class FabricNode:
    def __init__(self, identity: NodeIdentity, registry: NodeRegistry, *, fabric_id: str = "r3-interna-rossorosso", scopes: set[str] | None = None, capabilities: set[str] | None = None, router: MemoryFabricRouter | None = None):
        self.identity, self.registry, self.fabric_id = identity, registry, fabric_id
        self.scopes, self.capabilities, self.router = scopes or {"LOCAL"}, capabilities or set(), router
        self.used_messages: set[str] = set(); self.used_sequences: set[tuple[str, int]] = set()
        registry.register(identity.node_id, identity.key_id, identity.public_key, self.scopes, self.capabilities)
    def envelope(self, *, destination: str, message_type: str, payload: dict[str, Any], permission_scope: str, sequence: int, expires_in: int = 300) -> dict[str, Any]:
        now = time.time(); message_id = secrets.token_hex(16); payload_hash = digest(payload)
        body = {"fabric_id": self.fabric_id, "schema_version": "2", "message_id": message_id, "node_id": self.identity.node_id, "key_id": self.identity.key_id, "source_project": "protocollo-rosso-bot", "destination": destination, "message_type": message_type, "permission_scope": permission_scope, "created_at": now, "expires_at": now + expires_in, "sequence": sequence, "payload": payload, "payload_hash": payload_hash, "signature_algorithm": "Ed25519"}
        body["repository"] = "Rosso-rosso-rosso/protocollo-rosso-bot"; body["branch"] = "UNKNOWN"; body["commit_sha"] = "UNKNOWN"; body["signature"] = self.identity.sign(body); return body
    def receive(self, envelope: dict[str, Any]) -> tuple[str, Any]:
        required = {"fabric_id","schema_version","message_id","node_id","key_id","source_project","destination","message_type","permission_scope","created_at","expires_at","sequence","payload","payload_hash","signature_algorithm","signature"}
        if not required <= envelope.keys(): return "REJECT_SCHEMA", None
        if envelope["fabric_id"] != self.fabric_id or envelope["schema_version"] != "2": return "REJECT_FABRIC_OR_SCHEMA", None
        if envelope["message_id"] in self.used_messages or (envelope["node_id"], envelope["sequence"]) in self.used_sequences: return "REJECT_REPLAY", None
        if envelope["expires_at"] < time.time(): return "REJECT_EXPIRED", None
        if envelope["destination"] not in {self.identity.node_id, "BROADCAST"}: return "REJECT_DESTINATION", None
        sender = self.registry.nodes.get(envelope["node_id"])
        if not sender: return "REJECT_UNKNOWN_NODE", None
        key = sender.keys.get(envelope["key_id"])
        if not key: return "REJECT_KEY_ID", None
        if key.status == "REVOKED": return "REJECT_REVOKED_KEY", None
        if envelope["permission_scope"] not in sender.scopes: return "REJECT_SCOPE", None
        if envelope["destination"] == "BROADCAST" and "CAN_BROADCAST" not in sender.capabilities: return "REJECT_BROADCAST", None
        if envelope["signature_algorithm"] != "Ed25519" or digest(envelope["payload"]) != envelope["payload_hash"]: return "REJECT_PAYLOAD_HASH", None
        signed = {k:v for k,v in envelope.items() if k != "signature"}
        try: Ed25519PublicKey.from_public_bytes(unb64(key.public_key)).verify(unb64(envelope["signature"]), canon(signed))
        except Exception: return "REJECT_SIGNATURE", None
        self.used_messages.add(envelope["message_id"]); self.used_sequences.add((envelope["node_id"], envelope["sequence"]))
        if self.router and envelope["message_type"] == "memory_event":
            routed = self.router.route(envelope["payload"]["event"])
            return routed.decision, routed
        return "ACCEPT", envelope["payload"]
