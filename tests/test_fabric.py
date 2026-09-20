from __future__ import annotations


def test_fabric_envelope_verifies_and_preserves_provenance():
    from bot.fabric import create_envelope, verify_envelope

    envelope = create_envelope(node_id="node-a", source_project="protocollo-rosso-bot", destination="node-b", message_type="memory_event", payload={"event_hash": "abc"}, permission_scope="NETWORK", secret="test-secret")
    assert verify_envelope(envelope, secret="test-secret", expected_destination="node-b") == (True, "verified")
    assert envelope["source_project"] == "protocollo-rosso-bot"
    assert verify_envelope(envelope, secret="wrong")[0] is False
    assert verify_envelope(envelope, secret="test-secret", expected_fabric_id="other")[1] == "fabric_id_mismatch"
    assert verify_envelope(envelope, secret="test-secret", expected_destination="node-c")[1] == "destination_mismatch"
