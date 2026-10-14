"""Read-only, dependency-reviewed small-first work queue for the V18 780 tasks.

A missing dependency review is UNKNOWN, never equivalent to no dependencies.
The queue is scheduling advice, not authority to change code, grants, hosts or
the canonical database. Only Gate 4 proof can settle a prerequisite.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Iterable

from sofia.verify.v18_gate4 import gate4_snapshot
from sofia.verify.v18_roadmap import RoadmapIntegrityError, _within

REVIEW_RELATIVE = "docs/development/v18-dependency-reviews.json"
SCHEMA = "sofia.v18-dependency-review-v1"
ID_RE = re.compile(r"(?:CA-\d+|ML-\d{3}|GA-\d{3})\Z")
SHA_RE = re.compile(r"[a-f0-9]{40}\Z")
SIZES = {"small": 0, "medium": 1, "large": 2}


def build_work_queue(
    progress: dict, reviews: dict, *, reserved: Iterable[str] = (),
    limit: int = 5,
) -> dict:
    """Fail closed on malformed review graphs and never schedule unknown deps."""
    if type(limit) is not int or not 1 <= limit <= 10:
        raise RoadmapIntegrityError("queue limit must be an integer from 1 to 10")
    if not isinstance(progress, dict):
        raise RoadmapIntegrityError("missing canonical gate progress")
    rows = progress.get("tasks", []) + progress.get("supplemental_tasks", [])
    if (not isinstance(progress.get("tasks"), list)
            or not isinstance(progress.get("supplemental_tasks"), list)
            or len(rows) != 780):
        raise RoadmapIntegrityError("work queue requires all 780 canonical task IDs")
    by_id = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            raise RoadmapIntegrityError("invalid canonical task row")
        key = row["id"]
        gate = row.get("gate_with_recorded_proof")
        if (not ID_RE.fullmatch(key) or key in by_id
                or type(gate) is not int or not 0 <= gate <= 4):
            raise RoadmapIntegrityError("duplicate or invalid canonical task/gate")
        by_id[key] = row
    if (not isinstance(reviews, dict) or reviews.get("schema") != SCHEMA
            or not isinstance(reviews.get("tasks"), dict)):
        raise RoadmapIntegrityError("invalid dependency review schema")
    decisions = reviews["tasks"]
    if set(decisions) - set(by_id):
        raise RoadmapIntegrityError("dependency review contains unknown task ID")
    reserved_ids = tuple(reserved)
    if any(key not in by_id for key in reserved_ids):
        raise RoadmapIntegrityError("reservation references unknown task ID")
    for key, item in decisions.items():
        if not isinstance(item, dict) or item.get("complexity") not in SIZES:
            raise RoadmapIntegrityError("missing reviewed complexity for " + key)
        deps = item.get("depends_on")
        if (not isinstance(deps, list) or len(deps) != len(set(deps))
                or any(not isinstance(d, str) or d not in by_id or d == key
                       for d in deps)):
            raise RoadmapIntegrityError("invalid dependencies for " + key)
        if (not isinstance(item.get("reviewer"), str)
                or not item["reviewer"].strip()
                or not isinstance(item.get("rationale"), str)
                or len(item["rationale"].strip()) < 25
                or not isinstance(item.get("source_sha"), str)
                or not SHA_RE.fullmatch(item["source_sha"])):
            raise RoadmapIntegrityError("unsubstantiated dependency review for " + key)

    # Validate the entire declared graph, including tasks that are already done.
    visiting, visited = set(), set()
    def visit(key: str) -> None:
        if key in visiting:
            raise RoadmapIntegrityError("dependency cycle at " + key)
        if key in visited:
            return
        visiting.add(key)
        for dependency in decisions.get(key, {}).get("depends_on", ()):
            visit(dependency)
        visiting.remove(key)
        visited.add(key)
    for key in decisions:
        visit(key)

    reserved_set = set(reserved_ids)
    dependents = Counter(
        dependency
        for item in decisions.values()
        for dependency in item["depends_on"]
    )
    results = []
    for key, row in by_id.items():
        gate = row["gate_with_recorded_proof"]
        item = decisions.get(key)
        deps = [] if item is None else item["depends_on"]
        blocked = [d for d in deps
                   if by_id[d]["gate_with_recorded_proof"] < 4]
        if gate == 4:
            state = "complete"
        elif key in reserved_set:
            state = "reserved"
        elif item is None:
            state = "dependency_review_required"
        elif blocked:
            state = "blocked_on_prerequisite"
        else:
            state = "ready"
        results.append({
            "id": key, "phase": row["phase"], "gate": gate,
            "state": state,
            "complexity": None if item is None else item["complexity"],
            "depends_on": list(deps), "blocked_by": blocked,
            "unblocks_reviewed_tasks": dependents[key],
        })
    ready = sorted(
        (row for row in results if row["state"] == "ready"),
        key=lambda row: (
            SIZES[row["complexity"]], -row["unblocks_reviewed_tasks"],
            row["phase"], row["id"],
        ),
    )
    counts = Counter(row["state"] for row in results)
    return {
        "schema": "sofia.v18-work-queue-v1",
        "total": 780,
        "gate4_recorded": counts["complete"],
        "reviewed_dependencies": len(decisions),
        "states": {key: counts[key] for key in (
            "complete", "ready", "blocked_on_prerequisite", "reserved",
            "dependency_review_required",
        )},
        "target_per_run": limit,
        "selected": ready[:limit],
        "tasks": results,
        "warning": (
            "Dependency reviews are manually scoped. Unreviewed tasks are "
            "not assumed independent; queue selection is not gate acceptance."
        ),
    }


def _head(repo: Path) -> str:
    result = subprocess.run(
        ("git", "rev-parse", "--verify", "HEAD"),
        cwd=repo, capture_output=True, text=True, check=True, timeout=10,
    )
    value = result.stdout.strip()
    if not SHA_RE.fullmatch(value):
        raise RoadmapIntegrityError("work queue requires an exact Git revision")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m sofia.verify.v18_work_queue")
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--reserve", action="append", default=[])
    args = parser.parse_args(argv)
    try:
        root = args.repo.resolve(strict=True)
        before = _head(root)
        reviews = json.loads(_within(root, REVIEW_RELATIVE).read_text(encoding="utf-8"))
        report = build_work_queue(
            gate4_snapshot(root), reviews, reserved=args.reserve, limit=args.limit,
        )
        if _head(root) != before:
            raise RoadmapIntegrityError("checkout changed during queue calculation")
        report["revision"] = before
        report["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8",
        )
        print(
            f"ready={report['states']['ready']} "
            f"review_needed={report['states']['dependency_review_required']} "
            f"selected={len(report['selected'])}"
        )
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"V18 work queue rejected: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
