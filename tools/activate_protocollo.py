from __future__ import annotations
import json
import os
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

with tempfile.TemporaryDirectory(prefix="r3-activation-") as tmp:
    os.environ["R3_MEMORY_PATH"] = str(Path(tmp) / "r3-memory.jsonl")
    os.environ["R3_MEMORY_ENABLED"] = "1"
    os.environ["R3_REPOSITORY"] = "Rosso-rosso-rosso/protocollo-rosso-bot"
    os.environ["R3_BRANCH"] = "feat/efficient-routing-cache"
    os.environ["R3_COMMIT_SHA"] = "06bcb6fc6eed46ff6a24f98523c6a73b3548c257"
    from bot import sdq1
    from bot.identity import manifest
    from bot.memory import memory_health
    from bot.memory_router import MemoryFabricRouter
    out = sdq1.ask("attivazione protocollo rosso")
    router = MemoryFabricRouter(destination_project="protocollo-rosso-bot")
    result = {"activated": True, "mode": "local-verified", "identity": manifest()["identity"], "ask_provider": out.get("provider"), "agents": out.get("agenti"), "memory": memory_health(), "router": router.health(), "external_backend": False, "main_merge": False}
    print(json.dumps(result, ensure_ascii=False, indent=2))
