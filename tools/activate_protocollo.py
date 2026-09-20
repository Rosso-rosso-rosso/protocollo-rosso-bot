from __future__ import annotations
import json
import os
import subprocess
import tempfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

UNKNOWN = "UNKNOWN"


def _from_git(*args: str) -> str:
    try:
        value = subprocess.check_output(
            ["git", *args],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        return value or UNKNOWN
    except Exception:
        return UNKNOWN


def resolve_provenance() -> tuple[str, str]:
    """Branch and commit from environment or current checkout. Fallback: UNKNOWN."""
    branch = os.environ.get("R3_BRANCH") or os.environ.get("GITHUB_REF_NAME") or _from_git("rev-parse", "--abbrev-ref", "HEAD")
    sha = os.environ.get("R3_COMMIT_SHA") or os.environ.get("GITHUB_SHA") or _from_git("rev-parse", "HEAD")
    if not branch or branch == "HEAD":
        branch = UNKNOWN
    if not sha:
        sha = UNKNOWN
    return branch, sha


def main() -> None:
    branch, sha = resolve_provenance()
    with tempfile.TemporaryDirectory(prefix="r3-activation-") as tmp:
        os.environ["R3_MEMORY_PATH"] = str(Path(tmp) / "r3-memory.jsonl")
        os.environ["R3_MEMORY_ENABLED"] = "1"
        os.environ.setdefault("R3_REPOSITORY", "Rosso-rosso-rosso/protocollo-rosso-bot")
        os.environ["R3_BRANCH"] = branch
        os.environ["R3_COMMIT_SHA"] = sha
        from bot import sdq1
        from bot.identity import manifest
        from bot.memory import memory_health
        from bot.memory_router import MemoryFabricRouter
        out = sdq1.ask("attivazione protocollo rosso")
        router = MemoryFabricRouter(destination_project="protocollo-rosso-bot")
        result = {
            "activated": True,
            "mode": "local-verified",
            "identity": manifest()["identity"],
            "ask_provider": out.get("provider"),
            "agents": out.get("agenti"),
            "memory": memory_health(),
            "router": router.health(),
            "external_backend": False,
            "main_merge": False,
            "branch": branch,
            "commit_sha": sha,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
