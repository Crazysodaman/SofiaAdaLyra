"""Read-only reconciliation of the original 700 CA tasks with hybrid GO LIVE.

Source anchors and historical coding classifications are evidence leads, NOT
proof of production acceptance. This program never writes canonical state,
grants permission, or promotes a task to accepted.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import re
import sys

SOURCE = Path(__file__).resolve().parents[1] / "docs" / "sofia2" / (
    "V18_700_TASK_OWNER_CROSSWALK_2026-11-02.csv"
)
REQUIRED_FIELDS = frozenset({
    "task_id", "phase", "task_type", "task_summary",
    "primary_layer", "primary_owner", "coding_status", "disposition",
    "source_alignment",
})
ID_REGISTER = SOURCE.with_name("CA700_CANONICAL_IDS.txt")


def load_expected_ids(path: Path = ID_REGISTER) -> frozenset[str]:
    """Require 700 exact, nonduplicated audited identities in the manifest."""
    rows = [
        row.strip()
        for row in path.read_text(encoding="utf-8").splitlines()
        if row.strip() and not row.lstrip().startswith("#")
    ]
    unique = frozenset(rows)
    if len(rows) != 700 or len(unique) != 700 or any(
        re.fullmatch(r"CA-\d{3,4}", task_id) is None for task_id in rows
    ):
        raise ValueError("audited CA700 ID manifest must contain 700 unique phase IDs")
    return unique


EXPECTED_IDS = load_expected_ids()
CANDIDATE_LAYER = {
    "CORE": "PYTHON_COGNITION_CORE",
    "PLATFORM": "RUST_PLATFORM_OR_REVIEWED_PYTHON_BOUNDARY",
    "RELEASE_MODULE": "RUST_DESKTOP_OR_REVIEWED_PYTHON_MODULE",
    "OPTIONAL_MODULE": "OPTIONAL_MODULE_POST_GO_REVIEW",
}


def reconcile(source: Path = SOURCE) -> dict:
    """Validate original CA IDs, and emit a non-authoritative review projection.

    Raises ValueError for missing tasks, duplicates, incomplete ownership,
    malformed source evidence, or an unknown primary layer.
    """
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        # The column must exist even though 396 original source anchors are blank.
        required_columns = REQUIRED_FIELDS | {"source_anchor"}
        if reader.fieldnames is None or not required_columns <= set(reader.fieldnames):
            raise ValueError("CA source crosswalk is missing required columns")
        rows = list(reader)

    ids = [row["task_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate original CA task ID")
    missing = EXPECTED_IDS.difference(ids)
    extra = set(ids).difference(EXPECTED_IDS)
    if missing or extra:
        raise ValueError(
            f"CA task inventory mismatch: missing={len(missing)} "
            f"examples={sorted(missing)[:5]} extra={len(extra)} "
            f"examples={sorted(extra)[:5]}"
        )

    projected = []
    for row in rows:
        if any(not row.get(field, "").strip() for field in REQUIRED_FIELDS):
            raise ValueError(f"incomplete source evidence for {row['task_id']}")
        layer = row["primary_layer"]
        if layer not in CANDIDATE_LAYER:
            raise ValueError(f"unrecognized architecture layer for {row['task_id']}")
        if re.fullmatch(r"CA-\d{3,4}", row["task_id"]) is None:
            raise ValueError("malformed CA task ID")
        projected.append({
            "task_id": row["task_id"],
            "original_summary": row["task_summary"],
            "original_phase": row["phase"],
            "original_owner": row["primary_owner"],
            "original_layer": layer,
            "candidate_hybrid_owner": CANDIDATE_LAYER[layer],
            "historical_coding_status": row["coding_status"],
            "historical_disposition": row["disposition"],
            "source_anchor": row["source_anchor"],
            "source_anchor_present": bool(row["source_anchor"].strip()),
            "source_alignment": row["source_alignment"],
            "go_live_gate": None,
            "rust_gate": None,
            "release_critical": None,
            "production_entrypoint_verified": False,
            "installed_artifact_verified": False,
            "owner_acceptance_verified": False,
            "accepted": False,
            "review_status": "UNMAPPED_REQUIRES_INDEPENDENT_REVIEW",
        })

    return {
        "schema": "sofia.hybrid.ca700.review.v1",
        "count": len(projected),
        "source_anchors_missing": sum(not item["source_anchor_present"] for item in projected),
        "original_coding_status_counts": dict(
            sorted(Counter(item["historical_coding_status"] for item in projected).items())
        ),
        "original_owner_layer_counts": dict(
            sorted(Counter(item["original_layer"] for item in projected).items())
        ),
        "supplemental_ml_tasks": 40,
        "supplemental_ga_tasks": 40,
        "supplemental_status": "SEPARATE_NOT_INFERRED_FROM_CA700",
        "acceptance_state": "NOT_PROVEN_BY_SOURCE_CROSSWALK",
        "tasks": projected,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        result = reconcile(args.source)
    except (OSError, ValueError, KeyError) as exc:
        print(f"Hybrid CA700 reconciliation refused: {exc}", file=sys.stderr)
        return 2
    payload = json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
