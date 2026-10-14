"""Source-bound review of exact original V18 tasks 31–80, not production acceptance."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys

from sofia.verify.v18_roadmap import (
    LEDGER_RELATIVE, RoadmapIntegrityError, _within, validate_repository,
)

BATCH_RELATIVE = Path("docs/development/v18-next50-audit.json")
SCHEMA = "sofia.v18-next50-source-review-v1"
REVISION = re.compile(r"^[a-f0-9]{40}$")


def _head(root: Path) -> str:
    result = subprocess.run(
        ("git", "rev-parse", "--verify", "HEAD"), cwd=root,
        capture_output=True, text=True, timeout=10, check=True,
    )
    value = result.stdout.strip()
    if not REVISION.fullmatch(value):
        raise RoadmapIntegrityError("invalid Git revision")
    return value


def audit_next50(
    root: Path, *, manifest: dict | None = None,
    expected_revision: str | None = None,
) -> dict[str, object]:
    root = root.resolve(strict=True)
    if expected_revision is not None and not REVISION.fullmatch(expected_revision):
        raise RoadmapIntegrityError("invalid expected revision")
    head = _head(root)
    if expected_revision is not None and head != expected_revision:
        raise RoadmapIntegrityError("review checkout does not match requested revision")
    validate_repository(root)
    ledger = json.loads(_within(root, LEDGER_RELATIVE.as_posix()).read_text(
        encoding="utf-8",
    ))
    original = ledger["tasks"]
    start = next((i for i, row in enumerate(original) if row["id"] == "CA-3304"), -1)
    expected = original[start:start + 50] if start >= 0 else ()
    if len(expected) != 50 or expected[0]["id"] != "CA-3304" or expected[-1]["id"] != "CA-2201":
        raise RoadmapIntegrityError("next 50 original task boundaries changed")
    review = (
        json.loads(_within(root, BATCH_RELATIVE.as_posix()).read_text(
            encoding="utf-8",
        )) if manifest is None else manifest
    )
    if (
        not isinstance(review, dict)
        or review.get("schema") != SCHEMA
        or review.get("canonical_ledger") != LEDGER_RELATIVE.as_posix()
        or review.get("task_count") != 50
        or review.get("tests_attested") is not False
        or review.get("host_acceptance_attested") is not False
        or review.get("accepted_task_count") != 0
        or not isinstance(review.get("tasks"), list)
        or len(review["tasks"]) != 50
    ):
        raise RoadmapIntegrityError("invalid next-fifty evidence manifest")
    results = []
    for index, (candidate, task) in enumerate(zip(review["tasks"], expected, strict=True)):
        if not isinstance(candidate, dict) or (
            candidate.get("id") != task["id"]
            or candidate.get("phase") != task["phase"]
            or candidate.get("source_topic") != task["source_topic"]
            or candidate.get("original_status") != task["status"]
        ):
            raise RoadmapIntegrityError(f"task ID/order/status mismatch at index {index}")
        if (
            candidate.get("review_state") != "reviewed_not_accepted"
            or candidate.get("manifest_claims_tests_executed") is not False
            or candidate.get("manifest_claims_host_verified") is not False
            or candidate.get("accepted") is not False
        ):
            raise RoadmapIntegrityError(f"false success claim: {task['id']}")
        blocker = candidate.get("acceptance_blocker")
        if not isinstance(blocker, str) or len(blocker.strip()) < 30:
            raise RoadmapIntegrityError(f"missing independent acceptance barrier: {task['id']}")
        src = _within(root, candidate.get("source"))
        doc = _within(root, candidate.get("review_document"))
        if not src.read_bytes():
            raise RoadmapIntegrityError(f"empty source evidence: {task['id']}")
        review_text = doc.read_text(encoding="utf-8")
        key = task["id"]
        if f"## {key} " not in review_text and f"| {key} |" not in review_text:
            raise RoadmapIntegrityError(f"unreviewed task in design document: {key}")
        results.append({
            "id": key,
            "ledger_status": task["status"],
            "source_path_exists": True,
            "review_present": True,
            "production_accepted": False,
        })
    if _head(root) != head:
        raise RoadmapIntegrityError("checkout changed during review")
    return {
        "schema": "sofia.v18-next50-review-result-v1",
        "revision": head,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "reviewed_task_count": 50,
        "source_files_found": 50,
        "review_documents_bound": 50,
        "tests_executed_by_this_command": False,
        "live_host_verified": False,
        "production_accepted_task_count": 0,
        "tasks": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m sofia.verify.v18_next50_audit",
    )
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--expected-revision")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        result = audit_next50(args.repo, expected_revision=args.expected_revision)
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(
            f"reviewed={result['reviewed_task_count']} "
            f"accepted={result['production_accepted_task_count']} "
            f"revision={result['revision']}"
        )
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"V18 review failed closed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
