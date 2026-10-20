"""Single-pass, read-only triage for all V18 tasks lacking individual evidence.

Existing evidence is never promoted. Filename matches are leads, not a code,
test, CI, host, or Gate 4 proof. No inference, external access or state writes.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import re
import subprocess

from .audit import MentorAuditError, _source, audit_checkout

SCHEMA = "sofia.mentor.bulk-reconciliation.v1"
MASTER = "docs/development/v18-full-780-task-design-code-gate-status-2026-10-17.md"
PERSONALITY = "docs/development/v18-phase08-personality-status-evidence.json"
HISTORICAL = "docs/development/v18-unassessed-421-requirements-audit-2026-10-17.json"
PATH_RE = re.compile(r"(?:src/sofia|test)/[A-Za-z0-9_./-]+\.py")
WORDS = re.compile(r"[a-z][a-z0-9]{4,}")
IGNORED = frozenset(
    "before after there where their these those which would could should verified "
    "source exact task code tests design system existing production evidence "
    "original requirement owner authorizes current future actual report check "
    "without using model based record state against failed status verify build "
    "review support separate return preserve never produce result available".split()
)


def _git_files(root: Path) -> set[str]:
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z", "--", "src/sofia", "test"],
            cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=True, timeout=20,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise MentorAuditError("tracked source inventory unavailable") from exc
    names = result.stdout.decode("utf-8").split("\x00")
    return {name for name in names if name.endswith(".py") and
            name.startswith(("src/sofia/", "test/")) and
            (root / name).is_file() and not (root / name).is_symlink()}


def _master(root: Path) -> dict[str, dict]:
    result = {}
    for line in _source(root, MASTER).read_text(encoding="utf-8-sig").splitlines():
        if not re.match(r"^\|\s*(?:CA-\d+|ML-\d{3}|GA-\d{3})\s*\|", line):
            continue
        columns = [v.strip() for v in line.strip().strip("|").split("|")]
        if len(columns) < 10 or columns[0] in result or not columns[8]:
            raise MentorAuditError("invalid complete-roadmap task row")
        result[columns[0]] = {
            "task_type": columns[2], "original_requirement": columns[8],
            "historical_code_status": columns[3],
            "historical_next_proof": columns[9],
        }
    if len(result) != 780:
        raise MentorAuditError("full original requirements must cover 780 IDs")
    return result


def _personality(root: Path, allowed: set[str]) -> dict[str, dict]:
    data = json.loads(_source(root, PERSONALITY).read_text(encoding="utf-8"))
    rows = data.get("tasks")
    if not isinstance(rows, list) or len(rows) != 15:
        raise MentorAuditError("unexpected personality evidence register")
    result = {}
    for item in rows:
        if not isinstance(item, dict):
            raise MentorAuditError("invalid personality evidence")
        key, stage = item.get("id"), item.get("level")
        if key not in allowed or key in result or stage not in (2, 3):
            raise MentorAuditError("invalid or duplicate personality task")
        result[key] = item
    return result


def _historical(root: Path, allowed: set[str]) -> dict[str, dict]:
    data = json.loads(_source(root, HISTORICAL).read_text(encoding="utf-8"))
    items = data.get("tasks")
    if not isinstance(items, list):
        raise MentorAuditError("invalid historical source-lead inventory")
    result = {}
    for item in items:
        if not isinstance(item, dict) or item.get("id") not in allowed:
            raise MentorAuditError("historical source-lead ID unknown")
        key = item["id"]
        if key in result:
            raise MentorAuditError("duplicate historical source-lead ID")
        result[key] = item
    return result


def _lexical_leads(requirement: str, files: set[str], prefix: str) -> list[str]:
    words = set(WORDS.findall(requirement.lower())) - IGNORED
    scored = []
    for path in files:
        if not path.startswith(prefix):
            continue
        parts = set(re.findall(r"[a-z][a-z0-9]{3,}", path.lower()))
        # Filename/path co-occurrence is very weak evidence. Require >=2
        # distinctive shared tokens, not a ubiquitous word such as "tests".
        common = words & parts
        if len(common) >= 2:
            scored.append((len(common), path))
    return [name for _, name in sorted(scored, key=lambda row: (-row[0], row[1]))[:3]]


def _leads(key: str, requirement: str, historical: dict,
           files: set[str]) -> tuple[list[str], list[str], str]:
    direct = sorted(set(PATH_RE.findall(requirement)) & files)
    legacy = [
        p for p in historical.get(key, {}).get(
            "candidate_tracked_source_paths_unverified", []
        ) if isinstance(p, str) and p in files
    ]
    code = list(dict.fromkeys(
        p for p in direct + legacy if p.startswith("src/sofia/")
    ))[:5]
    tests = [p for p in direct if p.startswith("test/")][:5]
    if code or tests:
        basis = "requirement_path_or_historical_unverified_pointer"
    else:
        basis = "filename_topics_only"
    if not code:
        code = _lexical_leads(requirement, files, "src/sofia/")
    if not tests:
        tests = _lexical_leads(requirement, files, "test/")
    if not code and not tests:
        basis = "no_candidate_identified"
    return code, tests, basis


def reconcile_checkout(root: Path | str) -> dict:
    """Visit all 780 original requirements; emit rows for unclassified IDs."""
    root = Path(root).resolve(strict=True)
    snapshot = audit_checkout(root)
    ids = {item["task_id"] for item in snapshot["tasks"]}
    master = _master(root)
    if ids != set(master):
        raise MentorAuditError("full requirements disagree with live inventory")
    personality = _personality(root, ids)
    classified = {
        item["task_id"]: item["stage"]
        for item in snapshot["tasks"] if item["audited"]
    }
    overlap = set(classified) & set(personality)
    if overlap:
        raise MentorAuditError("competing personality evidence: " + sorted(overlap)[0])
    classified.update(
        {key: "PERSONALITY_LEVEL_" + str(item["level"])
         for key, item in personality.items()}
    )
    historical = _historical(root, ids)
    files = _git_files(root)
    rows = []
    for item in snapshot["tasks"]:
        key = item["task_id"]
        if key in classified:
            continue
        requirement = master[key]
        code, tests, basis = _leads(
            key, requirement["original_requirement"], historical, files
        )
        kind = requirement["task_type"]
        needed = (
            "independent design deliverable review" if kind == "Design"
            else "production caller and requirement-by-requirement code audit"
            if kind == "Build" else
            "exact-revision executed verification and required host witnesses"
        )
        rows.append({
            "task_id": key, "phase": item["phase"],
            "task_type": kind,
            "original_requirement": requirement["original_requirement"],
            "historical_code_status": requirement["historical_code_status"],
            "historical_next_proof": requirement["historical_next_proof"],
            "code_leads": code, "test_leads": tests, "lead_basis": basis,
            "remaining_proof": needed,
            "recorded_stage": "NOT_WORKED_ON",
            "code_implemented": None, "tests_executed": False,
            "gate4_accepted": False,
            "status_note": "Unclassified means evidence missing, not code absent.",
        })
    if len(rows) + len(classified) != 780 or len(set(x["task_id"] for x in rows)) != len(rows):
        raise MentorAuditError("bulk task coverage is incomplete")
    return {
        "schema": SCHEMA, "source_revision": snapshot["source_revision"],
        "summary": {
            "total": 780, "classified": len(classified),
            "unverified_reconciled": len(rows),
            "by_task_type": dict(Counter(x["task_type"] for x in rows)),
            "by_phase": dict(sorted(Counter(x["phase"] for x in rows).items())),
            "lead_basis": dict(Counter(x["lead_basis"] for x in rows)),
            "tasks_promoted": 0,
        },
        "classified_ids_excluded": sorted(classified),
        "unverified_tasks": rows,
        "limitations": [
            "One source and requirement inventory scan, not 651 manual code reviews.",
            "Candidate files are leads only: imports, callers, behavior and tests are unverified.",
            "No tests, live hosts, CI, permission, scientific outcomes or external effects executed.",
            "No canonical task stages, permissions, state databases or production code mutated.",
        ],
    }


def _destination(path: Path) -> Path:
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise MentorAuditError("unsafe output destination")
    if not path.parent.is_dir() or path.parent.is_symlink():
        raise MentorAuditError("missing or unsafe output directory")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only V18 bulk task reconciliation")
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--csv", type=Path)
    args = parser.parse_args(argv)
    report = reconcile_checkout(args.repo)
    _destination(args.output).write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if args.csv:
        with _destination(args.csv).open("w", newline="", encoding="utf-8") as fp:
            columns = (
                "task_id", "phase", "task_type", "original_requirement",
                "historical_code_status", "remaining_proof", "lead_basis",
                "code_leads", "test_leads", "recorded_stage", "gate4_accepted"
            )
            writer = csv.DictWriter(fp, fieldnames=columns)
            writer.writeheader()
            for row in report["unverified_tasks"]:
                writer.writerow({
                    name: "; ".join(row[name]) if isinstance(row[name], list)
                    else row[name] for name in columns
                })
    print(json.dumps({
        "revision": report["source_revision"],
        "summary": report["summary"],
        "output": str(args.output), "csv": str(args.csv) if args.csv else None,
        "note": "Evidence leads only. No task stage promoted.",
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
