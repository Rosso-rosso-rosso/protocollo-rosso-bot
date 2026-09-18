"""R³∞ Fabric seed: authenticated envelopes for a future private node network.

This module does not open ports or contact external services. It defines the
minimal wire contract so nodes can be connected later without losing origin.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from typing import Any

FABRIC_ID = os.getenv("R3_FABRIC_ID", "r3-interna-rossorosso")
SCHEMA_VERSION = "1"


def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def create_envelope(*, node_id: str, source_project: str, destination: str, message_type: str, payload: dict[str, Any], permission_scope: str, secret: str, fabric_id: str = FABRIC_ID) -> dict[str, Any]:
    envelope = {
        "fabric_id": fabric_id,
        "schema_version": SCHEMA_VERSION,
        "node_id": node_id,
        "source_project": source_project,
        "destination": destination,
        "message_type": message_type,
        "permission_scope": permission_scope,
        "payload": payload,
    }
    envelope["signature"] = hmac.new(secret.encode(), _canonical(envelope), hashlib.sha256).hexdigest()
    return envelope


def verify_envelope(envelope: dict[str, Any], *, secret: str, expected_fabric_id: str = FABRIC_ID, expected_destination: str | None = None) -> tuple[bool, str]:
    required = {"fabric_id", "schema_version", "node_id", "source_project", "destination", "message_type", "permission_scope", "payload", "signature"}
    if not required.issubset(envelope): return False, "invalid_envelope_fields"
    if envelope["fabric_id"] != expected_fabric_id: return False, "fabric_id_mismatch"
    if expected_destination is not None and envelope["destination"] not in {expected_destination, "BROADCAST"}: return False, "destination_mismatch"
    signed = {k: v for k, v in envelope.items() if k != "signature"}
    expected = hmac.new(secret.encode(), _canonical(signed), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(envelope["signature"], expected): return False, "signature_mismatch"
    return True, "verified"
