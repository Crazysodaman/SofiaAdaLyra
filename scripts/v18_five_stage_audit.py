"""Evidence-conservative 780-task stage inventory; never equate file existence with completion."""
from __future__ import annotations
import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROWS = re.compile(r"^\|\s*((?:CA-\d+|ML-\d{3}|GA-\d{3}))\s*\|", re.M)
STAGES = ("NOT_WORKED_ON", "CODED_UNFINISHED", "PRODUCTION_CODED", "TESTED", "TESTED_CI")
EVIDENCE_FILE = Path("docs/development/v18-five-stage-task-evidence.json")
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
    "CA-111": ["src/sofia/core/life/coordinator.py", "test/test_life_structured_critique.py"],
    "CA-2203": ["src/sofia/core/life/validation.py", "test/test_life_structured_critique.py"],
    "CA-3502": ["docs/development/v18-ca3502-success-oracle-separation-2026-10-17.md",
                "test/test_life_structured_critique.py"],
}


def _audited_evidence(repo: Path) -> dict[str, dict]:
    """Load sparse, human-audited promotions without rewriting 780 defaults."""
    path = repo / EVIDENCE_FILE
    if not path.is_file():
        return {}
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("schema_version") != 1 or not isinstance(document.get("tasks"), list):
        raise ValueError("invalid five-stage task evidence document")
    output: dict[str, dict] = {}
    for item in document["tasks"]:
        if not isinstance(item, dict) or not isinstance(item.get("task_id"), str):
            raise ValueError("five-stage evidence task must be an object with task_id")
        task_id = item["task_id"]
        if task_id in output:
            raise ValueError(f"duplicate five-stage evidence for {task_id}")
        stage = item.get("stage")
        if stage not in STAGES or stage == "NOT_WORKED_ON":
            raise ValueError(f"invalid audited stage for {task_id}")
        source_sha = item.get("source_sha")
        if not isinstance(source_sha, str) or re.fullmatch(r"[0-9a-f]{40}", source_sha) is None:
            raise ValueError(f"invalid source_sha for {task_id}")
        paths = item.get("source_paths")
        if (
            not isinstance(paths, list) or not paths
            or any(not isinstance(value, str) or not (repo / value).is_file() for value in paths)
        ):
            raise ValueError(f"missing audited source path for {task_id}")
        tests = item.get("tests", [])
        ci_runs = item.get("ci_runs", [])
        if stage in {"PRODUCTION_CODED", "TESTED", "TESTED_CI"} and not item.get(
            "production_entrypoint"
        ):
            raise ValueError(f"production stage lacks entrypoint for {task_id}")
        if stage in {"TESTED", "TESTED_CI"} and not tests:
            raise ValueError(f"tested stage lacks executed tests for {task_id}")
        if stage == "TESTED_CI" and not ci_runs:
            raise ValueError(f"TESTED_CI lacks exact CI evidence for {task_id}")
        output[task_id] = item
    return output

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
    audited = _audited_evidence(repo)
    unknown_audited = set(audited) - set(ids)
    if unknown_audited:
        raise ValueError(f"five-stage evidence has unknown task IDs: {sorted(unknown_audited)}")
    tasks = []
    for id_ in ids:
        paths = TRACED.get(id_, [])
        found = [p for p in paths if (repo / p).is_file()]
        stage = ("CODED_UNFINISHED" if len(found) == len(paths) and bool(paths)
                 and any(path.startswith("src/") and path.endswith(".py") for path in found)
                 else "NOT_WORKED_ON")
        item = {
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
        }
        promoted = audited.get(id_)
        if promoted is not None:
            item.update({
                "stage": promoted["stage"],
                "source_sha": promoted["source_sha"],
                "source_paths": promoted["source_paths"],
                "production_entrypoint": promoted.get("production_entrypoint"),
                "tests": promoted.get("tests", []),
                "ci_runs": promoted.get("ci_runs", []),
                "open_clauses": promoted.get("open_clauses", []),
                "last_audited_at": promoted.get("last_audited_at"),
                "audit_depth": "task_clause_and_production_path_audit",
            })
        tasks.append(item)
    counts = {s: sum(t["stage"] == s for t in tasks) for s in STAGES}
    return {
        "schema_version": 1,
        "source_commit": source_sha,
        "as_of_utc": datetime.now(timezone.utc).isoformat(),
        "method": "inventory plus explicitly referenced inspected source/drafts; NOT a complete production/code audit",
        "counts": counts,
        "audited_targeted": sum(t["audit_depth"] != "inventory_only" for t in tasks),
        "audit_coverage_percent": round(100 * sum(t["audit_depth"] != "inventory_only" for t in tasks) / len(tasks), 2),
        "tasks": tasks,
    }

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", type=Path, default=Path("."))
    p.add_argument("--sha", required=True)
    p.add_argument("--verify-head", action="store_true", help="Require SHA to match checked-out Git HEAD")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--markdown-output", type=Path)
    args = p.parse_args()
    if args.verify_head:
        try:
            actual = subprocess.run(
                ["git", "-C", str(args.repo.resolve()), "rev-parse", "--verify", "HEAD"],
                capture_output=True, text=True, check=True, timeout=10,
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise ValueError("cannot independently resolve Git HEAD") from exc
        if actual != args.sha:
            raise ValueError("inventory source_sha differs from actual checked-out Git HEAD")
    result = build(args.repo.resolve(), args.sha)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if args.markdown_output:
        lines = ["# Sofía V18 five-stage development progress", "",
                 f"Source commit: `{args.sha}`", "",
                 "Conservative status from currently traced evidence, not 780 completed source audits.", "",
                 "| Stage | Tasks | Progress |", "| --- | ---: | --- |"]
        labels = {"NOT_WORKED_ON": "1. Not worked on / unverified",
                  "CODED_UNFINISHED": "2. Coded but unfinished",
                  "PRODUCTION_CODED": "3. Fully coded into production",
                  "TESTED": "4. Tested", "TESTED_CI": "5. Tested + CI"}
        for key in STAGES:
            count = result["counts"][key]
            filled = round(count * 30 / 780)
            lines.append(f"| {labels[key]} | {count}/780 | `{'█' * filled}{'░' * (30-filled)}` {100 * count / 780:.2f}% |")
        lines += ["", f"Targeted evidence traced: **{result['audited_targeted']}/780** ({result['audit_coverage_percent']}%).",
                  "", "Stage 5 counts require task-matched test and exact-revision CI evidence; green workflow alone is not enough.", ""]
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"counts": result["counts"], "audited_targeted": result["audited_targeted"]}))

if __name__ == "__main__":
    main()
