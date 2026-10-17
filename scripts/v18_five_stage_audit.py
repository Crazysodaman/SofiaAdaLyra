"""Evidence-conservative 780-task stage inventory; never equate file existence with completion."""
from __future__ import annotations
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROWS = re.compile(r"^\|\s*((?:CA-\d+|ML-\d{3}|GA-\d{3}))\s*\|", re.M)
STAGES = ("NOT_WORKED_ON", "CODED_UNFINISHED", "PRODUCTION_CODED", "TESTED", "TESTED_CI")
# Hand-inspected draft/source references only. These do not certify completed clauses.
TRACED = {
    **{f"CA-{i}": [
        "docs/development/v18-g1-review-batch-a-architecture-2026-10-17.md",
        "docs/development/v18-g1-batch01-ten-task-acceptance-2026-10-17.md",
    ] for i in range(3101, 3106)},
    **{f"CA-{i}": [
        "docs/development/v18-g1-review-batch-b-fleet-evidence-2026-10-17.md",
        "docs/development/v18-g1-batch01-ten-task-acceptance-2026-10-17.md",
    ] for i in range(3106, 3111)},
    "CA-111": ["src/sofia/life/coordinator.py", "test/test_life_structured_critique.py"],
    "CA-2203": ["src/sofia/life/validation.py", "test/test_life_structured_critique.py"],
    "CA-3502": ["docs/development/v18-ca3502-success-oracle-separation-2026-10-17.md",
                "test/test_life_structured_critique.py"],
}

def build(repo: Path, source_sha: str) -> dict:
    doc = repo / "docs/development/v18-full-780-task-design-code-gate-status-2026-10-17.md"
    original = doc.read_text(encoding="utf-8")
    rows = [line for line in original.splitlines() if ROWS.match(line)]
    ids = [ROWS.match(line).group(1) for line in rows]
    row_details = {}
    phase = None
    for line in original.splitlines():
        if line.startswith("### Phase ") or line.startswith("### Machine Learning addendum:") or line.startswith("### Generalization / lifelong-learning addendum:"):
            phase = line[4:].split("|", 1)[0].strip()
        if not ROWS.match(line):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 10 or not cells[8]:
            raise ValueError(f"malformed or missing original requirement for {cells[0]}")
        row_details[cells[0]] = {"task_type": cells[2], "original_requirement": cells[8], "phase": phase}
    expected = {f"ML-{i:03d}" for i in range(1, 41)} | {f"GA-{i:03d}" for i in range(1, 41)}
    if set(ids).intersection(expected) != expected:
        raise ValueError("missing ML/GA identifier in full task register")
    if len(ids) != 780 or len(set(ids)) != 780:
        raise ValueError(f"expected 780 unique task rows, got {len(ids)} rows / {len(set(ids))} unique")
    parts = {prefix: sum(x.startswith(prefix) for x in ids) for prefix in ("CA-", "ML-", "GA-")}
    if parts != {"CA-": 700, "ML-": 40, "GA-": 40}:
        raise ValueError(f"wrong CA/ML/GA partition: {parts}")
    if not source_sha or not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        raise ValueError("source_sha must be an exact 40-character Git commit SHA")
    tasks = []
    for id_ in ids:
        paths = TRACED.get(id_, [])
        found = [p for p in paths if (repo / p).is_file()]
        stage = "CODED_UNFINISHED" if len(found) == len(paths) and bool(paths) else "NOT_WORKED_ON"
        tasks.append({
            "task_id": id_,
            **row_details[id_],
            "stage": stage,
            "original_requirement_ref": f"{doc.relative_to(repo)}#{id_.lower()}",
            "source_paths": found,
            "expected_source_paths": paths,
            "production_entrypoint": None,
            "tests": [],
            "ci_runs": [],
            "open_clauses": ["Full original-clause production audit and/or required proof not established"]
            if found else ["Task-specific source/design evidence not yet inspected for this status ladder"],
            "audit_depth": "targeted_source_or_draft_check" if found else "inventory_only",
        })
    counts = {s: sum(t["stage"] == s for t in tasks) for s in STAGES}
    return {
        "schema_version": 1,
        "source_commit": source_sha,
        "as_of_utc": datetime.now(timezone.utc).isoformat(),
        "method": "inventory plus explicitly referenced inspected source/drafts; NOT a complete production/code audit",
        "counts": counts,
        "audited_targeted": sum(t["audit_depth"] != "inventory_only" for t in tasks),
        "tasks": tasks,
    }

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", type=Path, default=Path("."))
    p.add_argument("--sha", required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    result = build(args.repo.resolve(), args.sha)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"counts": result["counts"], "audited_targeted": result["audited_targeted"]}))

if __name__ == "__main__":
    main()
