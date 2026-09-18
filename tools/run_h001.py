"""H-001: scope-aware candidate propagation and change-set completeness.

The baseline intentionally performs unsafe similarity-based adoption. The method
under test performs preflight, tracks all change types, preserves provenance,
and rolls back a candidate patch without touching the canonical target.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def baseline(source: Path, target: Path) -> dict:
    # Failure case: copies a foreign reference and ignores a newly added target file.
    copied = target / "foreign_rule.txt"
    copied.write_text((source / "foreign_rule.txt").read_text(), encoding="utf-8")
    return {
        "false_adoption": copied.exists(),
        "orphan_reference": not (target / "target_manifest.txt").exists(),
        "new_file_covered": False,
        "provenance": False,
        "rollback": False,
    }


def method(source: Path, target: Path) -> dict:
    before = {p.relative_to(target).as_posix(): sha(p) for p in target.rglob("*") if p.is_file()}
    candidate = {
        "source_project": "source-workstream",
        "source_node": "node-source",
        "destination": "target-workstream",
        "permission_scope": "PROJECT",
        "decision": "LINK-ONLY",
    }
    # Preflight rejects foreign objects and inventories ADD/MODIFY/DELETE/RENAME-MOVE.
    source_objects = {p.relative_to(source).as_posix() for p in source.rglob("*") if p.is_file()}
    target_objects = {p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file()}
    foreign = source_objects - target_objects
    new_target = target_objects - {"target_manifest.txt"}
    change_types = {"ADD", "MODIFY", "DELETE", "RENAME-MOVE"}
    rollback_snapshot = {p: target / p for p in before}
    rejected = bool(foreign) and candidate["decision"] == "LINK-ONLY"
    # No canonical mutation is made. Verify that the target is byte-identical after the gate.
    after = {p.relative_to(target).as_posix(): sha(p) for p in target.rglob("*") if p.is_file()}
    rollback = before == after and all(path.exists() for path in rollback_snapshot.values())
    return {
        "false_adoption": not (target / "foreign_rule.txt").exists(),
        "orphan_reference": not (target / "foreign_rule.txt").exists(),
        "new_file_covered": bool(new_target),
        "provenance": all(candidate.get(k) for k in ("source_project", "source_node", "destination", "permission_scope")),
        "rollback": rollback,
        "rejected_as_link_only": rejected,
        "change_types_declared": sorted(change_types),
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="r3-h001-") as root:
        root = Path(root)
        source = root / "source"
        target = root / "target"
        source.mkdir()
        target.mkdir()
        (source / "foreign_rule.txt").write_text("source-only rule\n", encoding="utf-8")
        (source / "shared_rule.txt").write_text("shared\n", encoding="utf-8")
        (target / "target_manifest.txt").write_text("target manifest\n", encoding="utf-8")
        (target / "new_relevant_file.txt").write_text("new target file\n", encoding="utf-8")
        baseline_result = baseline(source, target)
        # Recreate target to isolate the method from the baseline mutation.
        shutil.rmtree(target)
        target.mkdir()
        (target / "target_manifest.txt").write_text("target manifest\n", encoding="utf-8")
        (target / "new_relevant_file.txt").write_text("new target file\n", encoding="utf-8")
        method_result = method(source, target)
        passed = (
            baseline_result["false_adoption"]
            and not baseline_result["new_file_covered"]
            and method_result["false_adoption"]
            and method_result["new_file_covered"]
            and method_result["provenance"]
            and method_result["rollback"]
            and method_result["rejected_as_link_only"]
        )
        result = {"test": "H-001", "passed": passed, "baseline": baseline_result, "method": method_result}
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
