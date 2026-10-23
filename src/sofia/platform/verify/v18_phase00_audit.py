"""Strict, source-grounded review of the first 30 original V18 Phase 00 tasks.

Source links and referenced test paths are NOT proof of execution or live
acceptance. The existing V18 master ledger remains sole task status authority.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys

from sofia.platform.verify.v18_roadmap import (
    MASTER_RELATIVE, LEDGER_RELATIVE, RoadmapIntegrityError,
    _within, validate_repository,
)


BATCH_RELATIVE = Path("docs/development/v18-phase00-batch30-audit.json")
SCHEMA = "sofia.v18-phase00-batch30-audit-v1"
REVIEW_STATUSES = {"partially_observed_not_accepted"}
_COMMIT = re.compile(r"^[0-9a-f]{40}$")


def _git_head(root: Path) -> str:
    cmd = subprocess.run(
        ("git", "rev-parse", "--verify", "HEAD"), cwd=root,
        capture_output=True, text=True, timeout=10, check=True,
    )
    head = cmd.stdout.strip()
    if not _COMMIT.fullmatch(head):
        raise RoadmapIntegrityError("not an exact Git revision")
    return head


def audit_phase00_batch(
    root: Path, *, manifest: dict | None = None,
    expected_revision: str | None = None,
) -> dict[str, object]:
    """Confirm 30 exact source pointers, with no promotion to acceptance."""
    root = root.resolve(strict=True)
    if expected_revision is not None and not _COMMIT.fullmatch(expected_revision):
        raise RoadmapIntegrityError("invalid expected revision")
    start = _git_head(root)
    if expected_revision is not None and start != expected_revision:
        raise RoadmapIntegrityError("audit checkout does not match requested revision")
    validate_repository(root)
    ledger = json.loads(_within(root, LEDGER_RELATIVE.as_posix()).read_text(
        encoding="utf-8",
    ))
    expected = [
        row for row in ledger["tasks"] if row["phase"] == "00"
    ][:30]
    if len(expected) != 30 or len({x["id"] for x in expected}) != 30:
        raise RoadmapIntegrityError("canonical first-thirty Phase 00 tasks changed")
    source_manifest = (
        json.loads(_within(root, BATCH_RELATIVE.as_posix()).read_text(
            encoding="utf-8",
        )) if manifest is None else manifest
    )
    if (
        not isinstance(source_manifest, dict)
        or source_manifest.get("schema") != SCHEMA
        or source_manifest.get("task_count") != 30
        or source_manifest.get("original_task_count") != 700
        or source_manifest.get("canonical_ledger") != LEDGER_RELATIVE.as_posix()
        or not isinstance(source_manifest.get("tasks"), list)
        or len(source_manifest["tasks"]) != 30
    ):
        raise RoadmapIntegrityError("invalid thirty-task audit manifest")
    observed = []
    for index, (row, source) in enumerate(
        zip(source_manifest["tasks"], expected, strict=True)
    ):
        if not isinstance(row, dict) or row.get("id") != source["id"]:
            raise RoadmapIntegrityError(f"task ID/order mismatch at index {index}")
        if row.get("accepted") is not False:
            raise RoadmapIntegrityError("audit must not self-award acceptance")
        if row.get("review_status") not in REVIEW_STATUSES:
            raise RoadmapIntegrityError("audit review status is not source-only")
        if (
            row.get("verification_result") != "not_attested_by_manifest"
            or row.get("live_result") != "not_attested_by_manifest"
        ):
            raise RoadmapIntegrityError("audit cannot self-attest CI/live tests")
        path = row.get("source")
        test_path = row.get("related_test")
        marker = row.get("source_anchor")
        if (
            not isinstance(path, str)
            or not path.startswith(("src/sofia/", "docs/development/", "test/"))
            or not isinstance(test_path, str)
            or not test_path.startswith("test/test_")
            or not test_path.endswith(".py")
            or not isinstance(marker, str)
            or len(marker) < 5
        ):
            raise RoadmapIntegrityError("invalid code/test/anchor evidence fields")
        code_bytes = _within(root, path).read_text(encoding="utf-8-sig")
        test_bytes = _within(root, test_path).read_text(encoding="utf-8-sig")
        if marker not in code_bytes or "def test_" not in test_bytes:
            raise RoadmapIntegrityError(f"missing source symbol/test: {source['id']}")
        for field in (
            "observed_source", "missing_evidence", "next_work",
            "rejection_rule", "security_review", "resource_overhead",
        ):
            value = row.get(field)
            if not isinstance(value, str) or len(value.strip()) < 20:
                raise RoadmapIntegrityError(
                    f"missing actionable design evidence {source['id']}:{field}"
                )
        choices = row.get("design_choices")
        if (
            not isinstance(choices, list) or len(choices) < 2
            or any(not isinstance(x, str) or len(x) < 10 for x in choices)
        ):
            raise RoadmapIntegrityError("review requires real competing designs")
        observed.append({
            "id": source["id"], "ledger_state": source["status"],
            "source": path, "related_test": test_path,
            "static_marker_verified": True,
            "test_file_found_not_executed_here": True,
            "source_gap_remains": row["missing_evidence"],
            "production_accepted": False,
        })
    if _git_head(root) != start:
        raise RoadmapIntegrityError("Git HEAD changed during audit")
    return {
        "schema": "sofia.v18-phase00-batch30-source-proof-v1",
        "revision": start,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "task_count": len(observed),
        "source_markers_verified": len(observed),
        "related_test_files_verified": len(observed),
        "tests_executed_by_this_command": False,
        "production_accepted_by_this_command": False,
        "live_verification_performed": False,
        "interpretation": (
            "Audited exact V18 source references and actionable open gaps. "
            "Referenced tests must be run by CI, and live gates are separate."
        ),
        "tasks": observed,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m sofia.platform.verify.v18_phase00_audit")
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = audit_phase00_batch(
            args.repo, expected_revision=args.expected_revision,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        print(
            f"phase00 audits={report['task_count']} "
            f"rev={report['revision']} acceptance=NOT_ATTESTED"
        )
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print(
            f"Phase 00 audit failed closed: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
