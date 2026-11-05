"""Read-only hybrid migration register over the original 700-task crosswalk.

Never upgrades historical source-evidence status into implemented, tested,
merged, authorized or GO LIVE status. The extra 80 ML/GA tasks are separate.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/sofia2/V18_700_TASK_OWNER_CROSSWALK_2026-11-02.csv"

HISTORICAL_STATUSES = {
    "CODED_SOURCE_EVIDENCE",
    "PARTIAL_SOURCE_EVIDENCE",
    "UNVERIFIED",
    "SUPERSEDED",
}
LAYERS = {
    "CORE": "PYTHON_CORE",
    "PLATFORM": "RUST_PLATFORM_CANDIDATE",
    "RELEASE_MODULE": "RUST_CLIENT_OR_APPROVED_MODULE_CANDIDATE",
    "OPTIONAL_MODULE": "LANGUAGE_NOT_DECIDED",
}
EXPECTED_HISTORICAL_COUNTS = {
    "CODED_SOURCE_EVIDENCE": 118,
    "PARTIAL_SOURCE_EVIDENCE": 189,
    "UNVERIFIED": 390,
    "SUPERSEDED": 3,
}
EXPECTED_LAYER_COUNTS = {
    "CORE": 222,
    "PLATFORM": 350,
    "RELEASE_MODULE": 33,
    "OPTIONAL_MODULE": 95,
}


def build_register(source: Path = SOURCE) -> dict[str, object]:
    """Validate every original CA ID and project conservative hybrid metadata."""
    data = source.read_bytes()
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 700:
        raise ValueError(f"expected exactly 700 CA records, got {len(rows)}")

    seen: set[str] = set()
    items = []
    status_counts: Counter[str] = Counter()
    layer_counts: Counter[str] = Counter()
    for row in rows:
        task_id = row["task_id"]
        layer = row["primary_layer"]
        status = row["coding_status"]
        if not task_id.startswith("CA-") or not task_id[3:].isdigit():
            raise ValueError(f"invalid task ID: {task_id!r}")
        if task_id in seen:
            raise ValueError(f"duplicate task ID: {task_id}")
        seen.add(task_id)
        if layer not in LAYERS or status not in HISTORICAL_STATUSES:
            raise ValueError(f"unrecognized source classification for {task_id}")
        if not row["task_summary"] or not row["primary_owner"]:
            raise ValueError(f"missing task or owner for {task_id}")
        status_counts[status] += 1
        layer_counts[layer] += 1
        items.append({
            "task_id": task_id,
            "task_summary": row["task_summary"],
            "phase": row["phase"],
            "primary_owner": row["primary_owner"],
            "primary_layer": layer,
            "proposed_hybrid_destination": LAYERS[layer],
            "historical_coding_status": status,
            "source_anchor": row["source_anchor"],
            "source_alignment": row["source_alignment"],
            "go_live_gate": "NOT_YET_MAPPED",
            "rust_gate": "NOT_YET_MAPPED",
            "acceptance": "NOT_VERIFIED",
            "implementation_sha": None,
        })
    if dict(status_counts) != EXPECTED_HISTORICAL_COUNTS:
        raise ValueError("source-evidence classifications differ from accepted 700-task audit")
    if dict(layer_counts) != EXPECTED_LAYER_COUNTS:
        raise ValueError("architectural ownership differs from reviewed 700-task crosswalk")
    return {
        "schema": "sofia.hybrid-task-register.v1",
        "source_sha256": hashlib.sha256(data).hexdigest(),
        "original_task_count": len(items),
        "supplemental_ml_ga_task_count": 80,
        "supplements_reconciled_here": False,
        "historical_status_counts": dict(status_counts),
        "owner_counts": dict(layer_counts),
        "tasks": items,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", action="store_true", help="summary without task bodies")
    args = parser.parse_args()
    register = build_register()
    if args.audit:
        register.pop("tasks")
    print(json.dumps(register, sort_keys=True, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
