"""Fail-closed pre-commit review of a V18 roadmap coding batch.

Use against a checked-out main workspace:
 python scripts/v18_change_guard.py --manifest docs/development/v18-batch-review.json --base <sha>
The guard checks the actual Git diff, never infers completed task stages.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

TASK_ID = re.compile(r"^(?:CA-\d+|ML-\d{3}|GA-\d{3})$")
SHA = re.compile(r"^[0-9a-f]{40}$")


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True, capture_output=True, text=True, timeout=30,
    )
    return result.stdout


def verify(repo: Path, manifest: dict, *, base: str, head: str = "HEAD") -> dict:
    """Require review of every touched existing production file.

    A manifest is intent and review evidence, never a replacement for CI.
    """
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise ValueError("review manifest schema_version must be 1")
    if not SHA.fullmatch(base):
        raise ValueError("base must be an exact full commit SHA")
    if _git(repo, "merge-base", base, head).strip() != base:
        raise ValueError("base is not an ancestor of head")
    tasks = manifest.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("batch requires roadmap task reviews")
    ids = set()
    for task in tasks:
        if not isinstance(task, dict) or not TASK_ID.fullmatch(str(task.get("task_id", ""))):
            raise ValueError("each task must have a real roadmap task ID")
        if task["task_id"] in ids:
            raise ValueError("duplicate task review")
        ids.add(task["task_id"])
        for field in ("original_requirement", "existing_behavior", "missing_requirement",
                      "production_caller", "regression_tests"):
            if not isinstance(task.get(field), str) or not task[field].strip():
                raise ValueError(f"{task['task_id']} missing {field}")
    statuses = _git(repo, "diff", "--name-status", "--find-renames", base, head)
    changes = []
    for line in statuses.splitlines():
        parts = line.split("\t")
        status = parts[0]
        path = parts[-1]
        changes.append((status, path))
    reviewed = manifest.get("reviewed_existing_paths")
    if not isinstance(reviewed, dict):
        raise ValueError("reviewed_existing_paths must be a mapping")
    for status, path in changes:
        if status.startswith(("D", "R")) and path not in manifest.get("approved_removals", []):
            raise ValueError(f"deletion/rename lacks explicit approval: {path}")
        if path.startswith("src/") and not status.startswith("A"):
            evidence = reviewed.get(path)
            if not isinstance(evidence, dict) or any(
                not isinstance(evidence.get(k), str) or not evidence[k].strip()
                for k in ("before", "preserved", "reason")
            ):
                raise ValueError(f"existing production code changed without review: {path}")
            # A written assertion of prior behavior is not sufficient.
            # Verify the claimed source actually existed at the pinned base.
            previous_path = path
            if status.startswith("R"):
                previous_path = next(
                    (line.split("\\t")[1] for line in statuses.splitlines()
                     if line.startswith(status + "\\t") and
                     line.split("\\t")[-1] == path), path,
                )
            original = _git(repo, "show", f"{base}:{previous_path}")
            if evidence["before"] not in original:
                raise ValueError(f"pre-change source evidence not found at base: {path}")
    unknown = set(reviewed) - {p for _, p in changes}
    if unknown:
        raise ValueError(f"review claims untouched paths: {sorted(unknown)}")
    return {"tasks_reviewed": sorted(ids), "changes": len(changes),
            "reviewed_existing_production": sorted(reviewed),
            "status": "change_review_only_not_stage_promotion"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", default="HEAD")
    args = parser.parse_args()
    repo = args.repo.resolve()
    manifest_path = args.manifest if args.manifest.is_absolute() else repo / args.manifest
    output = verify(repo, json.loads(manifest_path.read_text(encoding="utf-8")),
                    base=args.base, head=args.head)
    print(json.dumps(output, sort_keys=True))


if __name__ == "__main__":
    main()
