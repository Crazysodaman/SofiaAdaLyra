"""Read-only, source-and-revision-bound status for *all 65* V18 Phase 00 items.

A successfully generated report verifies task inventory and source pointers.
It does not perform the per-task integration, unit, CI, hardware or acceptance
gates. In particular a documentation-only source path never becomes
production-wiring proof.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys

from sofia.platform.verify.v18_phase00_audit import _git_head
from sofia.platform.verify.v18_gate4 import gate4_snapshot
from sofia.platform.verify.v18_roadmap import (
    LEDGER_RELATIVE, MASTER_RELATIVE, RoadmapIntegrityError,
    _within, validate_repository,
)

_SHA = re.compile(r"[a-f0-9]{40}\Z")


_DESIGN_CANDIDATES = {
    "CA-1205": "docs/development/v18-phase00-ca1205-memory-benchmark-protocol.md",
    "CA-1206": "docs/development/v18-phase00-ca1206-acceptance-matrix-2026-10-14.md",
    **{f"CA-{n}": "docs/development/v18-batch50-science-safety.md"
       for n in range(3304, 3313)},
    **{f"CA-{n}": "docs/development/v18-batch50-references-os.md"
       for n in (*range(4001, 4007), 4501, 4503, 4505, 4506)},
    **{f"CA-{n}": "docs/development/v18-batch50-experience-hosting.md"
       for n in (*range(4701, 4707), 5401, 5402, 5404, 5405, 5407, 5408)},
}


def all_phase00_snapshot(root: Path, *, expected_revision: str | None = None) -> dict:
    root = root.resolve(strict=True)
    if expected_revision is not None and (
        not isinstance(expected_revision, str) or not _SHA.fullmatch(expected_revision)
    ):
        raise RoadmapIntegrityError("invalid expected Phase 00 revision")
    revision = _git_head(root)
    if expected_revision is not None and revision != expected_revision:
        raise RoadmapIntegrityError("Phase 00 source revision does not match")
    validate_repository(root)
    source = _within(root, MASTER_RELATIVE.as_posix()).read_text(
        encoding="utf-8").splitlines()
    ledger = json.loads(_within(root, LEDGER_RELATIVE.as_posix()).read_text(
        encoding="utf-8"))
    progress = gate4_snapshot(root)
    candidates = [task for task in ledger["tasks"] if task["phase"] == "00"]
    if len(candidates) != 65 or len({task["id"] for task in candidates}) != 65:
        raise RoadmapIntegrityError("Phase 00 must enumerate exactly 65 unique tasks")
    expected = [task for task in progress["tasks"] if task["phase"] == "00"]
    if [item["id"] for item in candidates] != [item["id"] for item in expected]:
        raise RoadmapIntegrityError("Phase 00 task ordering disagrees with source")
    counters = Counter()
    categories = Counter()
    rows = []
    candidate_docs = 0
    for task, proof in zip(candidates, expected, strict=True):
        requirement = source[task["master_line"] - 1]
        if not requirement.startswith("- [") or "**" + task["id"] + " " not in requirement:
            raise RoadmapIntegrityError("Phase 00 requirement source mismatch")
        category = (
            "design_research" if "[DESIGN/RESEARCH]" in requirement
            else "verify" if "[VERIFY]" in requirement else "implementation_gap"
        )
        source_paths = task["code_paths"]
        for path in source_paths:
            _within(root, path)
        candidate_path = None
        if task["status"] == "unassessed":
            candidate_path = _DESIGN_CANDIDATES.get(task["id"])
            if candidate_path is None:
                raise RoadmapIntegrityError("unreviewed design task has no candidate evidence")
            contents = _within(root, candidate_path).read_text(encoding="utf-8")
            if task["id"] not in contents:
                raise RoadmapIntegrityError("design candidate lacks original task anchor")
            candidate_docs += 1
        gate = proof["gate_with_recorded_proof"]
        if type(gate) is not int or not 0 <= gate <= 4:
            raise RoadmapIntegrityError("invalid exact Phase 00 proof state")
        if bool(task["accepted"]) != (task["status"] == "accepted"):
            raise RoadmapIntegrityError("Phase 00 status/acceptance mismatch")
        gap = (
            (task.get("phase00_batch30_review") or {}).get("unresolved_requirement")
            or (task.get("audit_observation") or {}).get("missing")
            or (task.get("production_wiring") or {}).get("remaining")
            or "Task-specific evidence and original acceptance criteria need independent review."
        )
        if not isinstance(gap, str) or not gap.strip():
            raise RoadmapIntegrityError("missing task-specific next evidence")
        rows.append({
            "id": task["id"], "requirement": requirement,
            "category": category, "ledger_status": task["status"],
            "gate_with_recorded_proof": gate,
            "gate4_verified": proof["gate4"],
            "canonical_source_paths": list(source_paths),
            "unassessed_design_review_candidate": candidate_path,
            "candidate_not_independently_reviewed": candidate_path is not None,
            "static_paths_exist": True,
            "code_present_claimed": task["status"] in {
                "code_present_unverified", "accepted",
            },
            "production_accepted_in_canonical_ledger": task["accepted"],
            "open_evidence": gap,
        })
        categories[category] += 1
        counters[task["status"]] += 1
        counters["gate4"] += int(proof["gate4"] is True)
    if _git_head(root) != revision:
        raise RoadmapIntegrityError("Git revision changed during Phase 00 audit")
    return {
        "schema": "sofia.v18-phase00-all-source-audit-v1",
        "exact_revision": revision,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "task_count": 65,
        "category_counts": dict(categories),
        "ledger_status_counts": {
            name: counters[name] for name in (
                "unassessed", "partial_wiring", "code_present_unverified",
                "accepted",
            )
        },
        "candidate_unassessed_documents_verified": candidate_docs,
        "gate4_verified": counters["gate4"],
        "tasks_without_gate4": 65 - counters["gate4"],
        "source_audit_executed": True,
        "focused_tests_attested_by_source_report": False,
        "ci_result_attested_by_source_report": False,
        "venus_or_multi_host_acceptance_attested": False,
        "warning": "A source audit is not code completion, functional CI, owner review, "
                   "actual GPU/voice/avatar measurement, or host acceptance.",
        "tasks": rows,
    }


def markdown_summary(report: dict) -> str:
    lines = [
        "# V18 Phase 00: exact source review for 65 original tasks", "",
        f"Revision: `{report['exact_revision']}`", "",
        f"Original items: {report['task_count']}; independently verified Gate 4: "
        f"{report['gate4_verified']}; still unverified: "
        f"{report['tasks_without_gate4']}.", "",
        "**This report does not award a task, CI result, live-host test, "
        "or production acceptance.**", "",
        "| Task | Category | Ledger state | Archived receipt count (not acceptance) | Source paths |",
        "| --- | --- | --- | ---: | ---: |",
    ]
    for row in report["tasks"]:
        lines.append(
            f"| {row['id']} | {row['category']} | {row['ledger_status']} | "
            f"{row['gate_with_recorded_proof']} | "
            f"{len(row['canonical_source_paths'])} |"
        )
    lines += ["", "## Required remaining task-by-task evidence", ""]
    for row in report["tasks"]:
        lines.append(f"- **{row['id']}**: {row['open_evidence']}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path)
    args = parser.parse_args(argv)
    try:
        report = all_phase00_snapshot(args.repo, expected_revision=args.expected_revision)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        if args.markdown_output is not None:
            args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
            args.markdown_output.write_text(markdown_summary(report), encoding="utf-8")
        print(f"Phase00 source audit: {report['task_count']} items, "
              f"verified_gate4={report['gate4_verified']}, live=NOT_ATTESTED")
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Phase00 audit rejected: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
