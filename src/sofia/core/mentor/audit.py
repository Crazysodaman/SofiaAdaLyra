"""Read-only, revision-bound MENTOR QA over Sofía's 780 tasks.

No LLM calls, background workers, independent state database, authority grants,
repairs or host actions. Source existence is not proof of a working capability.
"""
from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess

SCHEMA = "sofia.core.mentor.audit.v1"
INDEX = "docs/Sofia_V18_700_Tasks_Brief_Table.md"
LEDGER = "docs/development/v18-five-stage-task-evidence.json"
DOCUMENTS = (
    "docs/atlas/Sofia_Owner_Handbook.md",
    "docs/atlas/Sofia_Technical_MENTOR_Reference.md",
    "docs/atlas/Sofia_Complete_System_Atlas.md",
)
STAGES = ("NOT_WORKED_ON", "CODED_UNFINISHED", "PRODUCTION_CODED", "TESTED", "TESTED_CI")
EXPECTED = {"CA": 700, "ML": 40, "GA": 40}
TASK_ROW = re.compile(r"^\|\s*((?:CA-\d+|ML-\d{3}|GA-\d{3}))\s*\|\s*(\d{1,2})\s*\|\s*(.*?)\s*\|")
ATLAS_ENTRY = re.compile(r"^### ((?:CA-\d+|ML-\d{3}|GA-\d{3}))\s*$", re.M)
REVISION = re.compile(r"[0-9a-f]{40}\Z")


class MentorAuditError(ValueError):
    """Input is missing, ambiguous or unsafe to classify."""


def _source(root: Path, relative: str) -> Path:
    path = Path(relative)
    if not relative or path.is_absolute() or ".." in path.parts or "\\" in relative:
        raise MentorAuditError("unsafe relative path")
    result = root / path
    if not result.is_file() or result.is_symlink() or root not in result.resolve().parents:
        raise MentorAuditError("source missing or redirected: " + relative)
    return result


def _head(root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=root, capture_output=True, check=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise MentorAuditError("Git HEAD unavailable; no source claim possible") from exc
    head = result.stdout.strip()
    if REVISION.fullmatch(head) is None:
        raise MentorAuditError("invalid Git HEAD")
    return head


def _inventory(root: Path) -> dict:
    data = _source(root, INDEX).read_text(encoding="utf-8-sig")
    tasks = {}
    for line in data.splitlines():
        row = TASK_ROW.match(line)
        if row is None:
            continue
        key, phase, brief = row.groups()
        if key in tasks or int(phase) not in range(17) or not brief.strip():
            raise MentorAuditError("bad task row: " + key)
        tasks[key] = {"phase": int(phase), "brief": brief.strip()}
    counts = Counter(k.split("-")[0] for k in tasks)
    if len(tasks) != 780 or dict(counts) != EXPECTED:
        raise MentorAuditError("expected exactly 700 CA + 40 ML + 40 GA unique tasks")
    return tasks


def _evidence(root: Path, ids: set[str]) -> dict:
    data = json.loads(_source(root, LEDGER).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise MentorAuditError("invalid evidence document")
    records = data.get("tasks")
    if not isinstance(records, list):
        raise MentorAuditError("missing evidence list")
    result = {}
    for record in records:
        if not isinstance(record, dict):
            raise MentorAuditError("invalid evidence row")
        key, stage = record.get("task_id"), record.get("stage")
        if (key not in ids or key in result or stage not in STAGES
                or stage == "NOT_WORKED_ON"):
            raise MentorAuditError("unexpected, duplicate or invalid evidence task")
        rev = record.get("source_sha")
        paths = record.get("source_paths")
        if not isinstance(rev, str) or REVISION.fullmatch(rev) is None:
            raise MentorAuditError("unversioned evidence: " + key)
        if (not isinstance(paths, list) or not paths
                or any(not isinstance(x, str) for x in paths)
                or len(paths) != len(set(paths))):
            raise MentorAuditError("invalid source paths: " + key)
        if stage in STAGES[2:] and not record.get("production_entrypoint"):
            raise MentorAuditError("missing production caller: " + key)
        if stage in STAGES[3:] and not record.get("tests"):
            raise MentorAuditError("missing executed tests: " + key)
        if stage == "TESTED_CI" and not record.get("ci_runs"):
            raise MentorAuditError("missing CI run reference: " + key)
        for relative in paths:
            _source(root, relative)
        result[key] = record
    return result


def audit_checkout(root: Path | str, *, revision: str | None = None) -> dict:
    """Generate advisory classifications; never promote an actual task."""
    root = Path(root).resolve(strict=True)
    revision = _head(root) if revision is None else revision
    if not isinstance(revision, str) or REVISION.fullmatch(revision) is None:
        raise MentorAuditError("source Git revision must be exact")
    tasks = _inventory(root)
    evidence = _evidence(root, set(tasks))
    findings, documents = [], {}
    for filename in DOCUMENTS:
        try:
            text = _source(root, filename).read_text(encoding="utf-8")
        except MentorAuditError:
            documents[filename] = "missing"
            findings.append({"kind": "missing_document", "subject": filename,
                             "severity": "fail"})
            continue
        documents[filename] = "present"
        if filename.endswith("Sofia_Complete_System_Atlas.md"):
            entries = ATLAS_ENTRY.findall(text)
            if len(entries) != 780 or set(entries) != set(tasks):
                findings.append({"kind": "atlas_mismatch", "subject": filename,
                                 "severity": "fail"})
    stage_counts = Counter()
    phase_counts = {}
    rows = []
    for key, meta in tasks.items():
        record = evidence.get(key)
        stage = record["stage"] if record else "NOT_WORKED_ON"
        stage_counts[stage] += 1
        phase = f"{meta['phase']:02d}"
        phase_counts.setdefault(phase, Counter())[stage] += 1
        rows.append({
            "task_id": key, "phase": phase, "brief": meta["brief"],
            "stage": stage, "audited": record is not None,
            "evidence_revision": None if record is None else record["source_sha"],
            "same_source_revision": record is not None and record["source_sha"] == revision,
            "ci_independently_checked": False,
            "open_clauses": [] if record is None else record.get("open_clauses", []),
        })
    return {
        "schema": SCHEMA, "source_revision": revision,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_tasks": len(rows), "audited_tasks": len(evidence),
            "unassessed_tasks": len(rows) - len(evidence),
            "family_counts": dict(EXPECTED),
            "stages": {name: stage_counts[name] for name in STAGES},
            "historical_revision_records": sum(
                x["audited"] and not x["same_source_revision"] for x in rows
            ),
            "failed_document_checks": len(findings),
        },
        "phases": {phase: {s: count[s] for s in STAGES}
                   for phase, count in sorted(phase_counts.items())},
        "documents": documents, "findings": findings, "tasks": rows,
        "limitations": [
            "Historical task-stage records do not prove current operational status.",
            "No model, real host, CI, authorization or external result was tested.",
            "No evidence is not proof of missing code.",
            "MENTOR cannot grant capabilities or execute repairs.",
        ],
    }


def compare_reports(previous: dict, current: dict) -> dict:
    """Compare recorded stages, never self-certify a promotion or fix."""
    if (previous.get("schema") != SCHEMA or current.get("schema") != SCHEMA):
        raise MentorAuditError("wrong report schema")
    before = {t["task_id"]: t["stage"] for t in previous["tasks"]}
    after = {t["task_id"]: t["stage"] for t in current["tasks"]}
    if len(before) != 780 or len(after) != 780 or set(before) != set(after):
        raise MentorAuditError("incompatible task inventories")
    changes = []
    for task_id in sorted(before):
        a, b = before[task_id], after[task_id]
        if a not in STAGES or b not in STAGES:
            raise MentorAuditError("invalid stage")
        if a != b:
            changes.append({
                "task_id": task_id, "from": a, "to": b,
                "direction": "up" if STAGES.index(b) > STAGES.index(a) else "down",
                "requires_independent_proof": True,
            })
    return {
        "schema": "sofia.core.mentor.diff.v1",
        "previous_revision": previous["source_revision"],
        "current_revision": current["source_revision"],
        "changes": changes,
        "reported_promotions": sum(c["direction"] == "up" for c in changes),
        "reported_downgrades": sum(c["direction"] == "down" for c in changes),
        "note": "Stage deltas are recorded observations, not certified results.",
    }
