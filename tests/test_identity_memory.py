from __future__ import annotations

import json


def test_identity_is_explicit_and_non_overclaiming():
    from bot.identity import manifest

    data = manifest()
    assert data["identity"]["name"] == "Raffaello"
    assert "coscienza non dimostrata" in data["identity"]["epistemic_status"]
    assert "provenienza prima del riuso" in data["priorities"]
    assert set(data["decisions"]) == {"ADOPT", "ADAPT", "LINK-ONLY", "REJECT"}


def test_append_only_memory_is_hash_chained(tmp_path, monkeypatch):
    from bot import memory

    path = tmp_path / "memory.jsonl"
    monkeypatch.setattr(memory, "MEMORY_PATH", path)
    first = memory.append_event("test", {"n": 1}, source_project="test", permission_scope="LOCAL")
    second = memory.append_event("test", {"n": 2}, source_project="test", permission_scope="LOCAL")
    rows = [json.loads(line) for line in path.read_text().splitlines()]

    assert first["prev_hash"] == "GENESIS"
    assert second["prev_hash"] == first["event_hash"]
    assert rows[1]["event_hash"] == second["event_hash"]


def test_plan_key_is_scoped():
    from bot.memory import plan_key

    a = plan_key("same intent", "project-a", "PROJECT", "1")
    b = plan_key("same intent", "project-b", "PROJECT", "1")
    assert a != b


def test_plan_cache_is_link_only(tmp_path, monkeypatch):
    from bot import memory

    monkeypatch.setattr(memory, "MEMORY_PATH", tmp_path / "plans.jsonl")
    memory.store_plan("intent", {"step": "verify"}, source_project="p")
    plan = memory.load_linked_plan("intent", source_project="p")
    assert plan["decision"] == "LINK-ONLY"
    assert memory.load_linked_plan("intent", source_project="other") is None


def test_concurrent_append_has_single_linear_chain(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from bot import memory

    path = tmp_path / "concurrent.jsonl"
    monkeypatch.setattr(memory, "MEMORY_PATH", path)
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda i: memory.append_event("concurrent", {"i": i}, source_project="p"), range(40)))
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert len(rows) == 40
    assert len({row["event_hash"] for row in rows}) == 40
    assert rows[0]["prev_hash"] == "GENESIS"
    assert {row["prev_hash"] for row in rows[1:]} == {rows[i]["event_hash"] for i in range(39)}
