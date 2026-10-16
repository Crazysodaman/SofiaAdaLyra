"""First 200 V18 tasks in canonical phase order, not numeric-ID order.

This is an evidence-only, read-only *work sequence* and never a promotion
engine. It cannot infer acceptance from source files, test existence,
historical receipts or developer activity.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

from sofia.verify.v18_gate4 import gate4_snapshot
from sofia.verify.v18_roadmap import RoadmapIntegrityError

BATCH_SIZE = 200
FIRST = "CA-001"
LAST = "CA-6811"
PHASES = {"00": 65, "01": 66, "02": 30, "03": 39}


def ordered_first200(progress: dict) -> dict:
    """Fail closed if canonical order or acceptance evidence is incomplete."""
    tasks = progress.get("tasks") if isinstance(progress, dict) else None
    if not isinstance(tasks, list) or len(tasks) != 700:
        raise RoadmapIntegrityError("ordered batch requires 700 canonical tasks")
    first = tasks[:BATCH_SIZE]
    if first[0].get("id") != FIRST or first[-1].get("id") != LAST:
        raise RoadmapIntegrityError("roadmap first-200 task order changed")
    observed = Counter(row.get("phase") for row in first)
    if dict(observed) != PHASES:
        raise RoadmapIntegrityError("first-200 phase boundaries changed")
    seen = set()
    ordered = []
    for index, row in enumerate(first, 1):
        task_id = row.get("id")
        if (
            not isinstance(task_id, str) or task_id in seen
            or not isinstance(row.get("original_requirement"), str)
            or not row["original_requirement"].strip()
            or type(row.get("gate4")) is not bool
        ):
            raise RoadmapIntegrityError("incomplete, repeated or ungrounded task")
        seen.add(task_id)
        ordered.append({
            "position": index,
            "id": task_id,
            "phase": row["phase"],
            "requirement": row["original_requirement"],
            "gate4_verified": row["gate4"],
            "source_triage": row["source_status"],
            "known_missing": row.get("known_missing"),
            "next_action": row["next_action"],
            "independent_review_pending": row.get("independent_review_pending", False),
        })
    total = sum(row["gate4_verified"] for row in ordered)
    unfinished = [row for row in ordered if not row["gate4_verified"]]
    return {
        "schema": "sofia.v18-ordered-first200-evidence-only-v1",
        "order": "exact canonical V18 priority order",
        "total": BATCH_SIZE,
        "phase_counts": PHASES.copy(),
        "verified_gate4": total,
        "remaining_unverified": BATCH_SIZE - total,
        "first_unverified": None if not unfinished else unfinished[0]["id"],
        "next_ten_unverified": [row["id"] for row in unfinished[:10]],
        "status": "evidence-only: no self-certification",
        "task_rows": ordered,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        report = ordered_first200(gate4_snapshot(args.repo.resolve(strict=True)))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(
            f"first200_gate4_verified={report['verified_gate4']}/{BATCH_SIZE} "
            f"next={report['first_unverified']}"
        )
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print("ordered 200-task report rejected: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
