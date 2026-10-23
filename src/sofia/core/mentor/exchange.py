"""Public Git mailbox for independent MENTOR review.

The outbox is an explicit *allowlist* of source-controlled task metadata.
No sofia.db, memories, live conversations, screenshots, raw logs, env vars,
local device identifiers, host telemetry or unreviewed model transcripts.
Inbound review is DATA ONLY. This module never runs its recommendations,
grants authority, invokes tools, writes canonical state, or pushes Git.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any

from .audit import STAGES, MentorAuditError, audit_checkout
from .system_parts import system_parts_summary, PARTS

OUTBOX_SCHEMA = "sofia.core.mentor.public-outbox.v1"
INBOX_SCHEMA = "sofia.core.mentor.advisory-review.v1"
OUTBOX = "docs/mentor_exchange/outbox/latest.json"
INBOX = "docs/mentor_exchange/inbox/latest.json"
TASK_ID = re.compile(r"(?:CA-\d{4}|ML-\d{3}|GA-\d{3})\Z")
HEX_SHA = re.compile(r"[0-9a-f]{40}\Z")
SEVERITIES = frozenset(("info", "needs-verification", "defect-candidate"))
RECOMMENDATIONS = frozenset(("review", "run-safe-test", "investigate", "document"))
MAX_RECOMMENDATIONS = 12
MAX_REVIEW_BYTES = 16_384


class MentorExchangeError(ValueError):
    """Mailbox data violates a documented, non-executable contract."""


def public_outbox(repo: Path | str) -> dict[str, Any]:
    """Build a publishable report without touching Sofia's canonical state."""
    data = audit_checkout(repo)
    summary = data["summary"]
    # Whole-Sofía systems and personality come FIRST. Task rows are supporting
    # evidence, not the definition of Sofía's health or character.
    systems = system_parts_summary(repo, audit=data)
    # Take ONLY selected fields from trusted source-index and stage records.
    tasks = [{
        "id": record["task_id"],
        "phase": record["phase"],
        "recorded_stage": record["stage"],
        "evidence_source_is_current": record["same_source_revision"],
    } for record in data["tasks"]]
    if len(tasks) != 780 or len({item["id"] for item in tasks}) != 780:
        raise MentorExchangeError("complete distinct inventory required")
    return {
        "schema": OUTBOX_SCHEMA,
        "visibility": "public",
        "source": "pinned-git-task-evidence-only",
        "source_revision": data["source_revision"],
        "generated_at": data["generated_at"],
        "system": systems,
        "summary": {
            "total_tasks": summary["total_tasks"],
            "audited_tasks": summary["audited_tasks"],
            "unassessed_tasks": summary["unassessed_tasks"],
            "historical_revision_records": summary["historical_revision_records"],
            "stages": {stage: summary["stages"][stage] for stage in STAGES},
            "failed_document_checks": summary["failed_document_checks"],
        },
        "phases": {
            phase: {stage: vals[stage] for stage in STAGES}
            for phase, vals in sorted(data["phases"].items())
        },
        "tasks": tasks,
        "allowed_review_topics": [
            "whole-system functional quality", "personality-response fidelity",
            "task-evidence gaps", "source audit priorities",
            "regression tests", "safe diagnostic experiments",
            "non-executable implementation recommendations",
        ],
        "read_me": (
            "Prioritize system.parts and system.personality over roadmap counts. "
            "This is untrusted development data, NOT a live-host report. "
            "Unknown behavior means unverified, not broken or working. "
            "No part of this file authorizes a command. Task stages are "
            "historical ledger claims, not functional quality grades."
        ),
        "excluded": [
            "private memories", "raw chats", "screenshots", "sofia.db",
            "credentials", "unreviewed runtime logs", "owner/device identifiers",
        ],
    }


def write_public_outbox(repo: Path | str, output: Path | str = OUTBOX) -> dict:
    """Write an explicit public file. Never commit or push on behalf of owner."""
    root = Path(repo).resolve(strict=True)
    relative = Path(output)
    if (relative.is_absolute() or ".." in relative.parts
            or relative.as_posix() != OUTBOX):
        raise MentorExchangeError("export path must be the designated public outbox")
    target = root / relative
    # Avoid redirects/symlinks and overwriting directories, including parents.
    for component in (root / relative.parent, target):
        if component.is_symlink() or root not in component.parent.resolve().parents and component.parent.resolve() != root:
            raise MentorExchangeError("public outbox must not be a symlink")
    if target.exists() and not target.is_file():
        raise MentorExchangeError("outbox destination is not a regular file")
    document = public_outbox(root)
    target.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(document, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    if len(encoded.encode("utf-8")) > 150_000:
        raise MentorExchangeError("public export exceeded fixed size ceiling")
    target.write_text(encoded, encoding="utf-8")
    return {"path": OUTBOX, "revision": document["source_revision"],
            "tasks": len(document["tasks"]), "public": True,
            "git_committed": False, "git_pushed": False}


def validate_advisory_review(raw: dict) -> dict:
    """Reject external instructions and unknown fields before display.

    Even an accepted review is text-only and never becomes an executable task.
    """
    if not isinstance(raw, dict):
        raise MentorExchangeError("inbox must be a JSON object")
    allowed = {
        "schema", "visibility", "reviewed_source_revision",
        "review_created_at", "reviewer", "summary", "recommendations",
        "limitations", "part_reviews",
    }
    if not set(raw).issubset(allowed) or not (set(raw) - {"part_reviews"}) == (allowed - {"part_reviews"}) or raw.get("schema") != INBOX_SCHEMA:
        raise MentorExchangeError("invalid inbox schema or unexpected fields")
    if raw.get("visibility") != "public":
        raise MentorExchangeError("only public advisory review permitted")
    sha = raw.get("reviewed_source_revision")
    if not isinstance(sha, str) or HEX_SHA.fullmatch(sha) is None:
        raise MentorExchangeError("review must bind an exact source revision")
    try:
        when = datetime.fromisoformat(raw["review_created_at"].replace("Z", "+00:00"))
        if when.tzinfo is None:
            raise ValueError("timezone missing")
    except (KeyError, ValueError, AttributeError, TypeError) as exc:
        raise MentorExchangeError("invalid review timestamp") from exc
    if raw.get("reviewer") not in ("chatgpt-mentor", "human-owner"):
        raise MentorExchangeError("untrusted reviewer label")
    summary = raw.get("summary")
    if not isinstance(summary, str) or not 1 <= len(summary) <= 1600:
        raise MentorExchangeError("summary must be bounded text")
    entries = raw.get("recommendations")
    if not isinstance(entries, list) or len(entries) > MAX_RECOMMENDATIONS:
        raise MentorExchangeError("invalid recommendation count")
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {
            "id", "task_ids", "severity", "action", "observation",
            "suggested_check", "acceptance", "requires_owner_approval",
        }:
            raise MentorExchangeError("unexpected recommendation fields")
        identifier = entry.get("id")
        if (not isinstance(identifier, str)
                or not re.fullmatch(r"REV-\d{3}", identifier)):
            raise MentorExchangeError("invalid recommendation id")
        ids = entry.get("task_ids")
        if (not isinstance(ids, list) or len(ids) > 15
                or any(not isinstance(x, str) or TASK_ID.fullmatch(x) is None
                       for x in ids)):
            raise MentorExchangeError("invalid review task IDs")
        if (entry.get("severity") not in SEVERITIES
                or entry.get("action") not in RECOMMENDATIONS
                or entry.get("requires_owner_approval") is not True):
            raise MentorExchangeError("review cannot grant execution authority")
        for field in ("observation", "suggested_check", "acceptance"):
            txt = entry.get(field)
            if not isinstance(txt, str) or not 1 <= len(txt) <= 1200:
                raise MentorExchangeError("review text field invalid")
    ids = [e["id"] for e in entries]
    if len(ids) != len(set(ids)):
        raise MentorExchangeError("duplicate recommendation IDs")
    part_reviews = raw.get("part_reviews", [])
    if (not isinstance(part_reviews, list)
            or len(part_reviews) > len(PARTS)):
        raise MentorExchangeError("invalid subsystem review count")
    allowed_part_ids = {part.id for part in PARTS}
    found_parts = set()
    for entry in part_reviews:
        if (not isinstance(entry, dict) or set(entry) != {
            "part_id", "verdict", "evidence_type", "finding", "next_check",
        }):
            raise MentorExchangeError("invalid system-part review shape")
        part_id = entry.get("part_id")
        if (not isinstance(part_id, str) or part_id not in allowed_part_ids
                or part_id in found_parts):
            raise MentorExchangeError("unknown or duplicated system part")
        found_parts.add(part_id)
        if entry.get("verdict") not in (
            "unverified", "needs_attention", "provisional_match"
        ):
            raise MentorExchangeError("unsupported subsystem verdict")
        if entry.get("evidence_type") not in (
            "public_code", "ci_result", "sanitized_sample", "no_evidence"
        ):
            raise MentorExchangeError("unverified evidence type")
        for field in ("finding", "next_check"):
            value = entry[field]
            if not isinstance(value, str) or not 1 <= len(value) <= 320:
                raise MentorExchangeError("unbounded part review content")
        if (entry["verdict"] == "provisional_match"
                and entry["evidence_type"] not in ("ci_result", "sanitized_sample")):
            raise MentorExchangeError("part match requires actual checked evidence")
    limits = raw.get("limitations")
    if (not isinstance(limits, list) or len(limits) > 10
            or any(not isinstance(v, str) or len(v) > 250 for v in limits)):
        raise MentorExchangeError("invalid limitation list")
    return raw


def read_review(repo: Path | str, inbox: Path | str = INBOX) -> dict:
    root = Path(repo).resolve(strict=True)
    if Path(inbox).as_posix() != INBOX:
        raise MentorExchangeError("unexpected inbox path")
    p = root / INBOX
    if not p.is_file() or p.is_symlink() or p.stat().st_size > MAX_REVIEW_BYTES:
        raise MentorExchangeError("inbox missing, redirected, or oversized")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        raise MentorExchangeError("inbox is not valid JSON") from exc
    return validate_advisory_review(data)
