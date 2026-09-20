from __future__ import annotations
import hashlib, json, multiprocessing


def ledger_event(node="node-a", source="protocollo-rosso-bot", scope="PROJECT", n=1, prev="GENESIS"):
    e={"ts":n,"node":node,"kind":"fabric-test","source_project":source,"permission_scope":scope,"payload":{"n":n},"prev_hash":prev}
    e["event_hash"]=hashlib.sha256(json.dumps(e, sort_keys=True, separators=(",", ":")).encode()).hexdigest(); return e


def test_ed25519_valid_replay_and_tamper():
    from bot.fabric_v2 import FabricNode, NodeIdentity, NodeRegistry
    reg=NodeRegistry(); sender=FabricNode(NodeIdentity("a"),reg,scopes={"PROJECT"}); receiver=FabricNode(NodeIdentity("b"),reg,scopes={"PROJECT"})
    env=sender.envelope(destination="b",message_type="test",payload={"x":1},permission_scope="PROJECT",sequence=1)
    assert receiver.receive(env)[0]=="ACCEPT"; assert receiver.receive(env)[0]=="REJECT_REPLAY"
    env["payload"]["x"]=2; assert receiver.receive(env)[0]=="REJECT_REPLAY"

def test_registry_scope_destination_and_broadcast():
    from bot.fabric_v2 import FabricNode, NodeIdentity, NodeRegistry
    reg=NodeRegistry(); sender=FabricNode(NodeIdentity("a"),reg,scopes={"PROJECT"}); receiver=FabricNode(NodeIdentity("b"),reg,scopes={"PROJECT"})
    assert receiver.receive(sender.envelope(destination="b",message_type="test",payload={},permission_scope="NETWORK",sequence=1))[0]=="REJECT_SCOPE"
    assert receiver.receive(sender.envelope(destination="c",message_type="test",payload={},permission_scope="PROJECT",sequence=2))[0]=="REJECT_DESTINATION"
    assert receiver.receive(sender.envelope(destination="BROADCAST",message_type="test",payload={},permission_scope="PROJECT",sequence=3))[0]=="REJECT_BROADCAST"

def test_rotation_revocation_preserves_history():
    from bot.fabric_v2 import FabricNode, NodeIdentity, NodeRegistry
    reg=NodeRegistry(); old=NodeIdentity("a",key_id="key1"); sender=FabricNode(old,reg,scopes={"PROJECT"}); receiver=FabricNode(NodeIdentity("b"),reg,scopes={"PROJECT"})
    historical=sender.envelope(destination="b",message_type="test",payload={},permission_scope="PROJECT",sequence=1)
    assert receiver.receive(historical)[0]=="ACCEPT"
    new=NodeIdentity("a",key_id="key2"); reg.rotate("a","key1","key2",new.public_key); sender.identity=new
    current=sender.envelope(destination="b",message_type="test",payload={},permission_scope="PROJECT",sequence=2); assert receiver.receive(current)[0]=="ACCEPT"
    reg.revoke("a","key1"); assert receiver.receive(historical)[0]=="REJECT_REPLAY"
    old_env=old.sign
    forged={**sender.envelope(destination="b",message_type="test",payload={},permission_scope="PROJECT",sequence=3),"key_id":"key1","signature":old_env({k:v for k,v in sender.envelope(destination="b",message_type="test",payload={},permission_scope="PROJECT",sequence=4).items() if k!="signature"})}
    assert receiver.receive(forged)[0]=="REJECT_REVOKED_KEY"

def test_unknown_node_and_unknown_key():
    from bot.fabric_v2 import FabricNode, NodeIdentity, NodeRegistry
    sender_reg=NodeRegistry(); sender=FabricNode(NodeIdentity("a"),sender_reg,scopes={"PROJECT"}); receiver=FabricNode(NodeIdentity("b"),NodeRegistry(),scopes={"PROJECT"})
    assert receiver.receive(sender.envelope(destination="b",message_type="test",payload={},permission_scope="PROJECT",sequence=1))[0]=="REJECT_UNKNOWN_NODE"

def _child(queue, envelope, public_key):
    from bot.fabric_v2 import FabricNode, NodeIdentity, NodeRegistry
    reg=NodeRegistry(); reg.register("a","a-key",public_key,{"PROJECT"}); receiver=FabricNode(NodeIdentity("b"),reg,scopes={"PROJECT"}); queue.put(receiver.receive(envelope)[0])

def test_two_process_transport():
    from bot.fabric_v2 import FabricNode, NodeIdentity, NodeRegistry, LoopbackTransport
    reg=NodeRegistry(); sender=FabricNode(NodeIdentity("a",key_id="a-key"),reg,scopes={"PROJECT"}); env=sender.envelope(destination="b",message_type="test",payload={"x":1},permission_scope="PROJECT",sequence=1)
    q=multiprocessing.Queue(); p=multiprocessing.Process(target=_child,args=(q,env,sender.identity.public_key)); p.start(); result=q.get(timeout=5); p.join(5); assert result=="ACCEPT"; assert p.exitcode==0
    assert LoopbackTransport(q).health()["external"] is False


def test_signed_envelope_reaches_router_once():
    from bot.fabric_v2 import FabricNode, NodeIdentity, NodeRegistry
    from bot.memory_router import MemoryFabricRouter

    reg = NodeRegistry()
    router = MemoryFabricRouter(destination_project="target")
    sender = FabricNode(NodeIdentity("a"), reg, scopes={"NETWORK"})
    receiver = FabricNode(NodeIdentity("b"), reg, scopes={"NETWORK"}, router=router)
    event = ledger_event(scope="NETWORK")
    envelope = sender.envelope(destination="b", message_type="memory_event", payload={"event": event}, permission_scope="NETWORK", sequence=1)
    assert receiver.receive(envelope)[0] == "LINK-ONLY"
    assert router.health()["events"] == 1
    assert receiver.receive(envelope)[0] == "REJECT_REPLAY"


def test_fabric_and_signature_rejections():
    from bot.fabric_v2 import FabricNode, NodeIdentity, NodeRegistry

    reg = NodeRegistry(); sender = FabricNode(NodeIdentity("a"), reg, scopes={"PROJECT"}); receiver = FabricNode(NodeIdentity("b"), reg, scopes={"PROJECT"})
    bad_fabric = sender.envelope(destination="b", message_type="test", payload={}, permission_scope="PROJECT", sequence=1); bad_fabric["fabric_id"] = "other"
    assert receiver.receive(bad_fabric)[0] == "REJECT_FABRIC_OR_SCHEMA"
    bad_schema = sender.envelope(destination="b", message_type="test", payload={}, permission_scope="PROJECT", sequence=2); bad_schema["schema_version"] = "999"
    assert receiver.receive(bad_schema)[0] == "REJECT_FABRIC_OR_SCHEMA"
    bad_sig = sender.envelope(destination="b", message_type="test", payload={}, permission_scope="PROJECT", sequence=3); bad_sig["signature"] = "invalid"
    assert receiver.receive(bad_sig)[0] == "REJECT_SIGNATURE"


def test_sender_scoped_sequence_replay():
    from bot.fabric_v2 import FabricNode, NodeIdentity, NodeRegistry

    reg = NodeRegistry()
    node_a = FabricNode(NodeIdentity("A"), reg, scopes={"PROJECT"})
    node_c = FabricNode(NodeIdentity("C"), reg, scopes={"PROJECT"})
    receiver = FabricNode(NodeIdentity("b"), reg, scopes={"PROJECT"})
    env_a = node_a.envelope(destination="b", message_type="test", payload={"from": "A"}, permission_scope="PROJECT", sequence=1)
    env_c = node_c.envelope(destination="b", message_type="test", payload={"from": "C"}, permission_scope="PROJECT", sequence=1)
    assert receiver.receive(env_a)[0] == "ACCEPT"
    assert receiver.receive(env_c)[0] == "ACCEPT"
    assert receiver.receive(env_a)[0] == "REJECT_REPLAY"
