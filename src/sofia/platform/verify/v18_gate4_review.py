"""Read-only Gate 4 review readiness audit. Never awards or mutates task gates.

A successful pinned CI run is not equivalent to independent assessment of the
original task. This audit makes explicitly pending reviews visible without
discarding historical, content-bound evidence.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

_PENDING_REVIEW_PHRASES = (
    "independent human review pending",
    "independent review pending",
    "awaiting independent review",
    "independent review not completed",
)


def review_readiness(task: dict) -> dict:
    """Separate four recorded proofs from their outstanding independent review."""
    task_id = task.get("id")
    proofs = task.get("gate4_proofs", [])
    if not isinstance(task_id, str) or not task_id:
        raise ValueError("missing task identifier")
    if not isinstance(proofs, list) or len(proofs) > 4:
        raise ValueError(f"{task_id}: malformed gate proofs")
    state = "not_recorded"
    reasons: list[str] = []
    if len(proofs) == 4:
        state = "review_claimed_not_independently_authenticated"
        for proof in proofs:
            if not isinstance(proof, dict):
                raise ValueError(f"{task_id}: malformed proof entry")
            reviewer = proof.get("reviewer", "")
            if not isinstance(reviewer, str):
                raise ValueError(f"{task_id}: malformed reviewer")
            if any(phrase in reviewer.casefold() for phrase in _PENDING_REVIEW_PHRASES):
                state = "independent_review_pending"
                reasons.append("proof explicitly records pending independent review")
                break
        if not reasons:
            reasons.append(
                "reviewer declaration exists, but independent identity and "
                "task-specific test relevance require external corroboration"
            )
        historical = task.get("phase00_batch30_review") or {}
        unresolved = historical.get("unresolved_requirement") if isinstance(historical, dict) else None
        if isinstance(unresolved, str) and unresolved.strip():
            reasons.append("historical unresolved requirement needs superseding acceptance evidence")
    return {
        "id": task_id,
        "phase": task.get("phase"),
        "recorded_gate4": len(proofs) == 4,
        "review_readiness": state,
        "reasons": reasons,
    }


def review_report(ledger: dict, supplemental: dict) -> dict:
    """Return conservative claims inventory, never an acceptance certificate."""
    tasks = ledger.get("tasks")
    extra = supplemental.get("tasks")
    if not isinstance(tasks, list) or len(tasks) != 700:
        raise ValueError("expected 700 canonical tasks")
    if not isinstance(extra, dict):
        raise ValueError("invalid supplemental proof overlay")
    rows = [review_readiness(t) for t in tasks]
    for task_id, proofs in extra.items():
        rows.append(review_readiness({"id": task_id, "phase": "ML/GA", "gate4_proofs": proofs}))
    if len({r["id"] for r in rows}) != len(rows):
        raise ValueError("duplicate task identifier")
    recorded = [r for r in rows if r["recorded_gate4"]]
    pending = [r for r in recorded if r["review_readiness"] == "independent_review_pending"]
    return {
        "schema": "sofia.v18-gate4-review-readiness-v1",
        "recorded_gate4": len(recorded),
        "explicitly_pending_independent_review": len(pending),
        "review_declared_external_authentication_needed": len(recorded) - len(pending),
        "certified_by_this_audit": 0,
        "warning": "This audit cannot certify task satisfaction, test relevance or reviewer independence.",
        "recorded_tasks": recorded,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        root = args.repo.resolve(strict=True)
        ledger = json.loads((root / "docs/development/v18-task-evidence.json").read_text(encoding="utf-8"))
        supplemental = json.loads(
            (root / "docs/development/v18-supplemental-gate4-proofs.json").read_text(encoding="utf-8")
        )
        result = review_report(ledger, supplemental)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(
            f"recorded_gate4={result['recorded_gate4']} "
            f"pending_independent_review={result['explicitly_pending_independent_review']}"
        )
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print("Gate 4 review readiness audit failed: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
