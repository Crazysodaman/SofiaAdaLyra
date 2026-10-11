"""Versioned, fail-closed traceability for the original V18 autonomy roadmap.

This is a source/ledger integrity gate, not a claim that an individual task
is implemented, tested or production accepted. Both files are kept in the
canonical Git repository; no additional state database or runtime is created.
"""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re
import sys


MASTER_RELATIVE = Path(
    "docs/roadmaps/Sofia_Companion_Autonomy_Master_Roadmap_V18_Priority_Phases.md"
)
LEDGER_RELATIVE = Path("docs/development/v18-task-evidence.json")
MASTER_SHA256 = "08c773e5d8080c2d5606e0a31459e11f78339cbfee069b00ce912b63c59128dc"
PHASE_RE = re.compile(r"^## Priority phase (\d{2}):")
TOPIC_RE = re.compile(r"^### Source topic (\d+):")
TASK_RE = re.compile(r"^- \[[ xX]\] \*\*(CA-\d+) (.*?)\*\*\s*(.*)$")
SOURCE_STATES = frozenset((
    "unassessed", "partial_wiring", "code_present_unverified", "accepted",
))
REVISION_RE = re.compile(r"^[0-9a-f]{40}$")


class RoadmapIntegrityError(ValueError):
    """The checked-in audit has lost or misrepresented canonical task IDs."""


def _within(repo: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative:
        raise RoadmapIntegrityError("invalid or missing source path")
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise RoadmapIntegrityError("source path must stay within the repository")
    result = repo.joinpath(path)
    # Resolve before examining the file to prevent a ledger symlink to data
    # outside the immutable checkout from masquerading as production source.
    canonical = result.resolve()
    if repo != canonical and repo not in canonical.parents:
        raise RoadmapIntegrityError("source path escapes repository root")
    if not result.is_file() or result.is_symlink():
        raise RoadmapIntegrityError(f"missing or symlinked source path: {relative}")
    return result


def original_tasks(master: Path) -> dict[str, tuple[str, str, int]]:
    """Return each original CA ID with its exact phase/topic/line ownership."""
    source = master.read_bytes()
    if sha256(source).hexdigest() != MASTER_SHA256:
        raise RoadmapIntegrityError("V18 source bytes changed; update via reviewed new version")
    current_phase = current_topic = None
    task_map: dict[str, tuple[str, str, int]] = {}
    for lineno, line in enumerate(source.decode("utf-8").splitlines(), 1):
        phase = PHASE_RE.match(line)
        topic = TOPIC_RE.match(line)
        task = TASK_RE.match(line)
        if phase is not None:
            current_phase = phase.group(1)
            current_topic = None
        if topic is not None:
            current_topic = topic.group(1)
        if task is None:
            continue
        key = task.group(1)
        if key in task_map:
            raise RoadmapIntegrityError(f"duplicated original task {key}")
        if current_phase is None or current_topic is None:
            raise RoadmapIntegrityError(f"orphan original task {key}")
        task_map[key] = (current_phase, current_topic, lineno)
    if (
        len(task_map) != 700
        or len({task[0] for task in task_map.values()}) != 17
        or len({task[1] for task in task_map.values()}) != 69
        or set(range(17)) != {int(task[0]) for task in task_map.values()}
    ):
        raise RoadmapIntegrityError("V18 original 700 / 17 / 69 coverage changed")
    return task_map


def validate_repository(repo_root: Path) -> dict[str, object]:
    """Reject an incomplete, inflated or source-free review ledger."""
    repo = repo_root.resolve(strict=True)
    master = _within(repo, MASTER_RELATIVE.as_posix())
    ledger_path = _within(repo, LEDGER_RELATIVE.as_posix())
    source = original_tasks(master)
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    if not isinstance(ledger, dict) or ledger.get("schema") != "sofia.v18-task-evidence-v1":
        raise RoadmapIntegrityError("unsupported task ledger schema")
    if (
        ledger.get("master_path") != MASTER_RELATIVE.as_posix()
        or ledger.get("master_sha256") != MASTER_SHA256
        or ledger.get("master_git_blob") != "9ea103b551b1e22ce7230202fdcc762eac63f050"
        or not isinstance(ledger.get("reviewed_main_sha"), str)
        or REVISION_RE.fullmatch(ledger["reviewed_main_sha"]) is None
    ):
        raise RoadmapIntegrityError("unbound or unversioned V18 audit source")
    items = ledger.get("tasks")
    if not isinstance(items, list) or len(items) != len(source):
        raise RoadmapIntegrityError("ledger does not enumerate all 700 original tasks")
    seen: set[str] = set()
    counts: Counter[str] = Counter()
    by_phase: Counter[str] = Counter()
    for record in items:
        if not isinstance(record, dict):
            raise RoadmapIntegrityError("ledger task must be a typed object")
        key = record.get("id")
        if not isinstance(key, str) or key not in source or key in seen:
            raise RoadmapIntegrityError(f"unexpected or duplicate task {key!r}")
        seen.add(key)
        expected_phase, expected_topic, expected_line = source[key]
        if (
            record.get("phase") != expected_phase
            or record.get("source_topic") != expected_topic
            or type(record.get("master_line")) is not int
            or record["master_line"] != expected_line
        ):
            raise RoadmapIntegrityError(f"task location changed: {key}")
        status = record.get("status")
        if status not in SOURCE_STATES:
            raise RoadmapIntegrityError(f"unrecognized task state for {key}")
        paths = record.get("code_paths")
        refs = record.get("evidence_commits")
        if not isinstance(paths, list) or not isinstance(refs, list):
            raise RoadmapIntegrityError(f"invalid source-evidence structure: {key}")
        if len(paths) != len(set(paths)) or len(refs) != len(set(refs)):
            raise RoadmapIntegrityError(f"duplicate evidence entries: {key}")
        if any(
            not isinstance(revision, str)
            or REVISION_RE.fullmatch(revision) is None
            for revision in refs
        ):
            raise RoadmapIntegrityError(f"invalid commit reference: {key}")
        for path in paths:
            _within(repo, path)
        if status in {"partial_wiring", "code_present_unverified", "accepted"} and not paths:
            raise RoadmapIntegrityError(f"task claims code without source paths: {key}")
        if status == "code_present_unverified":
            # A source file, a unit test or an unused class is not a
            # production implementation. Only reachable, composed code with
            # an identified actual effect may be counted as tests-only.
            wiring = record.get("production_wiring")
            if not isinstance(wiring, dict):
                raise RoadmapIntegrityError(
                    f"production-wired claim lacks real path evidence: {key}"
                )
            entrypoint = wiring.get("entrypoint")
            if not isinstance(entrypoint, str) or not entrypoint.strip():
                raise RoadmapIntegrityError(
                    f"production-wired claim lacks entrypoint: {key}"
                )
            if wiring.get("remaining") != "tests_only":
                raise RoadmapIntegrityError(
                    f"production-wired claim cannot conceal missing coding: {key}"
                )
            explanation = wiring.get("explanation")
            if not isinstance(explanation, str) or len(explanation.strip()) < 30:
                raise RoadmapIntegrityError(
                    f"production-wired claim lacks source explanation: {key}"
                )
            source_review = wiring.get("source_review_sha")
            if not isinstance(source_review, str) or REVISION_RE.fullmatch(source_review) is None:
                raise RoadmapIntegrityError(
                    f"production-wired claim lacks exact source review: {key}"
                )
            for role in ("composition_path", "caller_path", "implementation_path", "effect_path"):
                part = wiring.get(role)
                if not isinstance(part, str) or part not in paths:
                    raise RoadmapIntegrityError(
                        f"production-wired {role} lacks declared source: {key}"
                    )
                _within(repo, part)
                if part.startswith(("test/", "docs/")):
                    raise RoadmapIntegrityError(
                        f"production-wired {role} points only at tests/docs: {key}"
                    )
        accepted = record.get("accepted")
        if type(accepted) is not bool:
            raise RoadmapIntegrityError(f"missing explicit acceptance state: {key}")
        if accepted != (status == "accepted"):
            raise RoadmapIntegrityError(f"ambiguous accepted state: {key}")
        if status == "accepted":
            receipt = record.get("acceptance_receipt")
            if (
                not isinstance(receipt, dict)
                or not isinstance(receipt.get("revision"), str)
                or REVISION_RE.fullmatch(receipt["revision"]) is None
                or receipt.get("test_result") != "passed"
                or receipt.get("live_status") not in {"not_required", "passed"}
                or not isinstance(receipt.get("evidence_path"), str)
            ):
                raise RoadmapIntegrityError(f"task lacks exact acceptance receipt: {key}")
            _within(repo, receipt["evidence_path"])
        counts[status] += 1
        by_phase[expected_phase] += 1
    if seen != set(source):
        raise RoadmapIntegrityError("ledger silently omitted original CA IDs")
    return {
        "schema": "sofia.v18-validation-v1",
        "master_sha256": MASTER_SHA256,
        "reviewed_main_sha": ledger["reviewed_main_sha"],
        "total_original_tasks": len(source),
        "source_topic_groups": 69,
        "priority_phases": 17,
        "task_status_counts": dict(sorted(counts.items())),
        "phase_task_counts": dict(sorted(by_phase.items())),
        "accepted": counts["accepted"],
        "note": "Source integrity only: no tests, CI, or live host acceptance performed.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m sofia.verify.v18_roadmap")
    parser.add_argument(
        "--repo", type=Path, default=Path.cwd(),
        help="canonical Git checkout containing ROADMAP and source evidence",
    )
    args = parser.parse_args(argv)
    try:
        report = validate_repository(args.repo)
    except (OSError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"V18 task traceability rejected: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
