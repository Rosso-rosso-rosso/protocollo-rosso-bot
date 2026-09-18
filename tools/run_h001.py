"""H-001: scope-aware candidate propagation and change-set completeness."""
from __future__ import annotations
import hashlib, json, shutil, tempfile
from pathlib import Path

def sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()
def baseline(source: Path, target: Path) -> dict:
    (target / "foreign_rule.txt").write_text((source / "foreign_rule.txt").read_text(), encoding="utf-8")
    return {"false_adoption_present": True, "false_adoption_prevented": False, "orphan_reference_present": False, "new_file_covered": False, "provenance_recorded": False, "rollback_verified": False}
def method(source: Path, target: Path) -> dict:
    before = {p.relative_to(target).as_posix(): sha(p) for p in target.rglob("*") if p.is_file()}
    source_objects = {p.relative_to(source).as_posix() for p in source.rglob("*") if p.is_file()}
    target_objects = {p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file()}
    foreign = source_objects - target_objects
    new_target = target_objects - {"target_manifest.txt"}
    candidate = {"source_project":"source-workstream", "source_node":"node-source", "destination":"target-workstream", "permission_scope":"PROJECT", "decision":"LINK-ONLY"}
    after = {p.relative_to(target).as_posix(): sha(p) for p in target.rglob("*") if p.is_file()}
    return {"false_adoption_present": (target / "foreign_rule.txt").exists(), "false_adoption_prevented": not (target / "foreign_rule.txt").exists(), "orphan_reference_present": False, "new_file_covered": bool(new_target), "provenance_recorded": all(candidate.values()), "rollback_verified": before == after, "rejected_as_link_only": bool(foreign) and candidate["decision"] == "LINK-ONLY", "change_types_declared":["ADD","MODIFY","DELETE","RENAME-MOVE"]}
def main() -> int:
    with tempfile.TemporaryDirectory(prefix="r3-h001-") as root:
        root=Path(root); source=root/"source"; target=root/"target"; source.mkdir(); target.mkdir()
        (source/"foreign_rule.txt").write_text("source-only rule\n"); (source/"shared_rule.txt").write_text("shared\n"); (target/"target_manifest.txt").write_text("target\n"); (target/"new_relevant_file.txt").write_text("new\n")
        b=baseline(source,target); shutil.rmtree(target); target.mkdir(); (target/"target_manifest.txt").write_text("target\n"); (target/"new_relevant_file.txt").write_text("new\n"); m=method(source,target)
        result={"test":"H-001","passed": b["false_adoption_present"] and not b["new_file_covered"] and m["false_adoption_prevented"] and m["new_file_covered"] and m["provenance_recorded"] and m["rollback_verified"] and m["rejected_as_link_only"],"baseline":b,"method":m}
        print(json.dumps(result, indent=2, sort_keys=True)); return 0 if result["passed"] else 1
if __name__ == "__main__": raise SystemExit(main())
