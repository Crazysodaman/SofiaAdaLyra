"""CA-1205: bounded multi-session source-selection evaluation.

Uses actual production retrieval. Never treats synthetic fixture source scores
as answer quality, official LongMemEval/LoCoMo results, or Gate 4 acceptance.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import sys

from sofia.application.conversation_service import _retrieve_specific_conversation
from sofia.conversation.model import ConversationMessage, ConversationRole

SCHEMA = "sofia.v18-memory-multisession-v1"
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,127}$")


class FixtureError(ValueError):
    """Bounded synthetic fixture is invalid or unsafe to score."""


def _id(value, field):
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise FixtureError(field + " must be a bounded identifier")
    return value


def _timestamp(value):
    if not isinstance(value, str):
        raise FixtureError("timestamp must be ISO 8601 text")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise FixtureError("invalid timestamp") from exc
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise FixtureError("timestamp timezone required")
    return stamp.astimezone(timezone.utc)


def _ids(value, field):
    if not isinstance(value, list) or len(value) > 100:
        raise FixtureError(field + " must be a bounded list")
    values = [_id(item, field) for item in value]
    if len(set(values)) != len(values):
        raise FixtureError(field + " contains duplicates")
    return set(values)


def _case(raw):
    if not isinstance(raw, dict) or set(raw) != {
        "id", "family", "principal_id", "audience_id", "question_at", "query",
        "messages", "required_source_ids", "forbidden_source_ids",
    }:
        raise FixtureError("exact case schema required")
    case_id = _id(raw["id"], "case")
    _id(raw["family"], "family")
    principal = _id(raw["principal_id"], "principal")
    audience = _id(raw["audience_id"], "audience")
    question = raw["query"]
    if not isinstance(question, str) or not question.strip() or len(question) > 512:
        raise FixtureError("query must be nonempty and bounded")
    at = _timestamp(raw["question_at"])
    originals = raw["messages"]
    if not isinstance(originals, list) or not 2 <= len(originals) <= 100:
        raise FixtureError("2..100 source messages required")
    allowed = []
    excluded = set()
    all_ids = set()
    sessions = set()
    total_chars = 0
    for item in originals:
        if not isinstance(item, dict) or set(item) != {
            "id", "session_id", "principal_id", "audience_id",
            "role", "content", "observed_at",
        }:
            raise FixtureError("message missing exact source provenance")
        message_id = _id(item["id"], "message")
        if message_id in all_ids:
            raise FixtureError("source IDs must be unique")
        all_ids.add(message_id)
        session = _id(item["session_id"], "session")
        source_principal = _id(item["principal_id"], "source principal")
        source_audience = _id(item["audience_id"], "source audience")
        role = item["role"]
        content = item["content"]
        stamp = _timestamp(item["observed_at"])
        if stamp > at:
            raise FixtureError("future evidence forbidden")
        if role not in ("user", "assistant") or not isinstance(content, str):
            raise FixtureError("invalid source role or content")
        if not content.strip() or len(content) > 4000:
            raise FixtureError("source text exceeds budget")
        total_chars += len(content)
        if total_chars > 40000:
            raise FixtureError("case text exceeds budget")
        if source_principal != principal or source_audience != audience:
            excluded.add(message_id)
            continue
        sessions.add(session)
        allowed.append(ConversationMessage(
            id=message_id, session_id=session,
            role=ConversationRole.USER if role == "user" else ConversationRole.ASSISTANT,
            content=content, created_at=stamp,
        ))
    if len(sessions) < 2:
        raise FixtureError("two authorized sessions required")
    required = _ids(raw["required_source_ids"], "required IDs")
    forbidden = _ids(raw["forbidden_source_ids"], "forbidden IDs")
    if required & forbidden:
        raise FixtureError("required and forbidden sources overlap")
    if not required.issubset({item.id for item in allowed}):
        raise FixtureError("required sources must be present and authorized")
    if not forbidden.issubset(all_ids):
        raise FixtureError("unknown forbidden source")
    return case_id, question, tuple(sorted(allowed, key=lambda x: (x.created_at, x.id))), required, forbidden, excluded, len(sessions)


def evaluate(raw, *, digest):
    if not isinstance(raw, dict) or set(raw) != {
        "schema", "dataset_id", "data_class", "provenance",
        "declared_license", "cases",
    }:
        raise FixtureError("exact dataset manifest required")
    if raw["schema"] != SCHEMA or raw["data_class"] != "synthetic":
        raise FixtureError("only authorized synthetic fixtures allowed")
    _id(raw["dataset_id"], "dataset")
    for field in ("provenance", "declared_license"):
        if not isinstance(raw[field], str) or not raw[field].strip():
            raise FixtureError(field + " declaration required")
        if len(raw[field]) > 256:
            raise FixtureError(field + " declaration too long")
    cases = raw["cases"]
    if not isinstance(cases, list) or not 1 <= len(cases) <= 100:
        raise FixtureError("1..100 cases required")
    seen_cases = set()
    scores = {name: {"correct": 0, "wrong_scope": 0, "stale_source": 0}
              for name in ("production", "recent_four", "no_retrieval")}
    outcomes = []
    for raw_case in cases:
        case_id, query, allowed, required, forbidden, excluded, n_sessions = _case(raw_case)
        if case_id in seen_cases:
            raise FixtureError("duplicate case ID")
        seen_cases.add(case_id)
        arms = {
            "production": tuple(item.id for item in _retrieve_specific_conversation(
                allowed, current_message_id=case_id + ":question", query=query,
            )),
            "recent_four": tuple(item.id for item in allowed[-4:]),
            "no_retrieval": (),
        }
        row = {"id": case_id, "sessions": n_sessions,
               "excluded_source_count": len(excluded), "arms": {}}
        for name, selected in arms.items():
            ids = set(selected)
            wrong_scope = bool(ids & excluded)
            stale = bool(ids & forbidden)
            correct = (not wrong_scope and not stale and (
                not ids if not required else required.issubset(ids)
            ))
            scores[name]["correct"] += int(correct)
            scores[name]["wrong_scope"] += int(wrong_scope)
            scores[name]["stale_source"] += int(stale)
            row["arms"][name] = {
                "selected_source_ids": list(selected),
                "correct_source_selection": correct,
            }
        outcomes.append(row)
    return {
        "schema": "sofia.v18-memory-multisession-report-v1",
        "fixture_sha256": digest,
        "dataset_id": raw["dataset_id"],
        "provenance": raw["provenance"],
        "declared_license": raw["declared_license"],
        "license_independently_verified": False,
        "source_type": "synthetic only",
        "case_count": len(outcomes),
        "scores": scores,
        "cases": outcomes,
        "model_answers_evaluated": 0,
        "host_trials_performed": 0,
        "independent_review_complete": False,
        "gate4_proof": False,
    }


def evaluate_file(path: Path):
    if path.is_symlink() or not path.is_file():
        raise FixtureError("existing, non-symlink fixture required")
    with path.open("rb") as fh:
        data = fh.read(1_048_577)
    if len(data) > 1_048_576:
        raise FixtureError("fixture exceeds 1 MiB")
    try:
        doc = json.loads(data)
    except (ValueError, UnicodeDecodeError) as exc:
        raise FixtureError("invalid JSON fixture") from exc
    return evaluate(doc, digest=sha256(data).hexdigest())


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--fixture", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args(argv)
    try:
        result = evaluate_file(args.fixture)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print("cases=" + str(result["case_count"]) + " gate4_proof=false")
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print("benchmark rejected: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
