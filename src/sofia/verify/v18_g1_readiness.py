"""Read-only G1 design-submission inventory, never a reviewer or award engine.

A task's original requirement remains unsatisfied until each clause has been
independently reviewed. This helper verifies submission provenance and exact
source requirement text, NOT whether a draft decision is correct or complete.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import sys

PACKET_PATHS = (
    "docs/development/v18-g1-review-batch-a-architecture-2026-10-17.md",
    "docs/development/v18-g1-review-batch-b-fleet-evidence-2026-10-17.md",
    "docs/development/v18-g1-review-batch-c-behavior-ci-research-2026-10-17.md",
    "docs/development/v18-g1-review-batch-d-operating-layer-2026-10-17.md",
)
MASTER = "docs/roadmaps/Sofia_Companion_Autonomy_Master_Roadmap_V18_Priority_Phases.md"
_SOURCE_ID = re.compile(r"^- \[ \] \*\*(CA-[0-9]+)\b.*$", re.MULTILINE)
_SECTION = re.compile(r"^## (CA-[0-9]+): [^\n]+\n(.*?)(?=^## CA-[0-9]+: |\Z)", re.MULTILINE | re.DOTALL)
_ORIGINAL = re.compile(r"^\*\*Original(?: requirement)?:\*\* (.+)$", re.MULTILINE)
_REQUIRED = (
    "Original", "Source", "G1",
)


class G1SubmissionError(ValueError):
    """Missing/ambiguous original requirement or candidate provenance."""


def _reviewed_source(root: Path, path: str) -> tuple[str, str]:
    if not isinstance(path, str) or not path or "\x00" in path:
        raise G1SubmissionError("invalid review-packet path")
    relative = Path(path)
    if relative.is_absolute() or ".." in relative.parts:
        raise G1SubmissionError("unsafe review-packet path")
    source = root / relative
    if any(part.is_symlink() for part in (source, *source.parents) if
           part == root or root in part.parents):
        raise G1SubmissionError("symlinked review-packet path")
    data = source.read_bytes()
    if len(data) > 2_000_000:
        raise G1SubmissionError("review-packet size limit exceeded")
    return data.decode("utf-8", "strict"), sha256(data).hexdigest()


def inspect_g1_submissions(
    root: Path, *, packet_paths: tuple[str, ...] = PACKET_PATHS,
) -> dict:
    """Check submitted exact task IDs against authoritative ORIGINAL lines.

    This function cannot approve G1, add gate proofs, mint reviewer identity or
    alter project state. Without external review, its accepted count is zero.
    """
    root = root.resolve(strict=True)
    master, _ = _reviewed_source(root, MASTER)
    original = {}
    for match in _SOURCE_ID.finditer(master):
        task_id = match.group(1)
        if task_id in original:
            raise G1SubmissionError("duplicate original requirement " + task_id)
        original[task_id] = match.group(0).replace("- [ ] ", "", 1)
    if len(original) != 700:
        raise G1SubmissionError("expected 700 canonical original tasks")
    if not packet_paths:
        raise G1SubmissionError("at least one review packet required")
    rows = []
    seen = set()
    for path in packet_paths:
        content, digest = _reviewed_source(root, path)
        found = False
        for match in _SECTION.finditer(content):
            found = True
            task_id, body = match.groups()
            if task_id in seen:
                raise G1SubmissionError("duplicate G1 review submission " + task_id)
            seen.add(task_id)
            if task_id not in original:
                raise G1SubmissionError("review submission for unknown " + task_id)
            source = _ORIGINAL.search(body)
            if source is None or source.group(1).strip() != original[task_id]:
                raise G1SubmissionError(task_id + ": original requirement drift")
            for field in _REQUIRED:
                if "**" + field not in body:
                    raise G1SubmissionError(task_id + ": missing review field " + field)
            if "OPEN" not in body and "UNDECIDED" not in body:
                raise G1SubmissionError(task_id + ": draft falsely omits pending review")
            rows.append({
                "id": task_id, "source_packet": path,
                "packet_sha256": digest, "original_requirement_sha256":
                sha256(original[task_id].encode("utf-8")).hexdigest(),
                "submission_status": "draft_for_independent_review",
                "gate1_accepted": False,
            })
        if not found:
            raise G1SubmissionError("review packet contains no original-task sections")
    return {
        "schema": "sofia.v18-g1-review-submissions-v1",
        "total_submissions": len(rows), "unique_submissions": len(seen),
        "independently_accepted_gate1": 0,
        "warning": "This inventory does NOT attest original requirements "
                   "were satisfied or reviewed. Only an independently "
                   "authenticated reviewer may accept a complete G1 task.",
        "tasks": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        data = inspect_g1_submissions(args.repo)
        if args.output:
            args.output.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print("submitted_for_independent_g1_review="
              + str(data["total_submissions"])
              + " accepted_gate1=0")
        return 0
    except (OSError, UnicodeError, TypeError, G1SubmissionError) as exc:
        print("G1 submission audit failed: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
