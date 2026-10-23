"""CA-1205 reproducible synthetic memory retrieval ablations.

This does NOT evaluate official LongMemEval/LoCoMo questions or LLM answer
quality. It exercises the production specific-recall selector on newly created
non-sensitive, current-session examples inspired by those task taxonomies.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Callable

from sofia.platform.application.conversation_service import _retrieve_specific_conversation
from sofia.conversation.model import ConversationMessage, ConversationRole

FAMILIES = ("longmemeval-inspired", "locomo-inspired", "agent-environment-inspired")
ABLATIONS = ("production_topical", "recent_four_only", "recent_one_only", "no_retrieval")
ORIGIN = datetime(2026, 10, 14, tzinfo=timezone.utc)


@dataclass(frozen=True)
class RecallCase:
    case_id: str
    family: str
    task_kind: str
    query: str
    originals: tuple[ConversationMessage, ...]
    expected_source_ids: frozenset[str]
    forbidden_source_ids: frozenset[str] = frozenset()


def _message(case: str, idx: int, content: str) -> ConversationMessage:
    return ConversationMessage(
        id=f"{case}:m{idx}",
        session_id=f"synthetic-session:{case}",
        role=ConversationRole.USER,
        content=content,
        created_at=ORIGIN + timedelta(minutes=idx),
    )


def scenarios() -> tuple[RecallCase, ...]:
    """Deterministic, source-authored proxies; no real private conversations."""
    cases: list[RecallCase] = []
    for family in FAMILIES:
        for variant in range(12):
            case_id = f"{family}:{variant:02}"
            keyword = ("locomotive" if family == "longmemeval-inspired"
                       else "workshop" if family == "locomo-inspired"
                       else "sensor")
            subject = f"{keyword}-{variant:02}"
            kind = (
                ("abstention", "single_source", "multi_source", "updated_fact",
                 "temporal")[variant % 5]
            )
            records: list[ConversationMessage] = []
            records.append(_message(case_id, 0, f"Some unrelated weather note for {case_id}."))
            records.append(_message(
                case_id, 1,
                f"Evidence: {subject} was first observed during a diagnostic inspection.",
            ))
            records.append(_message(
                case_id, 2,
                f"Followup: {subject} observation was entered into the logbook.",
            ))
            for offset in range(3, 11):
                records.append(_message(
                    case_id, offset,
                    f"Noise {offset} about garden supplies and arithmetic {offset}.",
                ))
            expected: frozenset[str] = frozenset()
            forbidden: frozenset[str] = frozenset()
            if kind == "single_source":
                query = f"What did I say about {subject} diagnostic inspection?"
                expected = frozenset((records[1].id,))
            elif kind == "multi_source":
                query = f"What evidence and followup did I report for {subject}?"
                expected = frozenset((records[1].id, records[2].id))
            elif kind == "updated_fact":
                records.append(_message(
                    case_id, 11, f"Correction: {subject} was repaired, superseding the old observation.",
                ))
                query = f"What was the latest correction for {subject}?"
                expected = frozenset((records[-1].id,))
                forbidden = frozenset((records[1].id,))
            elif kind == "temporal":
                query = f"When was the {subject} diagnostic inspection reported?"
                expected = frozenset((records[1].id,))
            else:
                query = f"Did we discuss the unobserved-noctilucent-{variant}?"
                # The original chat contains no support; select no sources.
            cases.append(RecallCase(
                case_id=case_id, family=family, task_kind=kind,
                query=query, originals=tuple(records),
                expected_source_ids=expected, forbidden_source_ids=forbidden,
            ))
    return tuple(cases)


def _production(case: RecallCase) -> tuple[str, ...]:
    return tuple(x.id for x in _retrieve_specific_conversation(
        case.originals, current_message_id=f"{case.case_id}:current",
        query=case.query,
    ))


def _recent(case: RecallCase, limit: int) -> tuple[str, ...]:
    return tuple(x.id for x in case.originals[-limit:])


def evaluate() -> dict:
    cases = scenarios()
    if len(cases) != 36 or len({x.case_id for x in cases}) != 36:
        raise RuntimeError("synthetic benchmark case count drift")
    selectors: dict[str, Callable[[RecallCase], tuple[str, ...]]] = {
        "production_topical": _production,
        "recent_four_only": lambda case: _recent(case, 4),
        "recent_one_only": lambda case: _recent(case, 1),
        # Baseline without any history source. Only genuine unsupported
        # questions can earn a correct abstention in this source-ID oracle.
        "no_retrieval": lambda case: (),
    }
    results = []
    counts: dict[str, Counter] = {key: Counter() for key in selectors}
    by_family: dict[str, dict[str, Counter]] = {
        family: {key: Counter() for key in selectors} for family in FAMILIES
    }
    for case in cases:
        outcomes = {}
        for name, selector in selectors.items():
            retrieved = tuple(selector(case))
            selected = frozenset(retrieved)
            if not case.expected_source_ids:
                error = "false_positive_on_unanswerable" if selected else None
                correct = not selected
            elif not case.expected_source_ids.issubset(selected):
                error = "missing_required_source"
                correct = False
            elif case.forbidden_source_ids & selected:
                error = "outdated_source_also_selected"
                correct = False
            else:
                error = None
                correct = True
            count = counts[name]
            family_count = by_family[case.family][name]
            for target in (count, family_count):
                target["n"] += 1
                target["correct"] += int(correct)
                target["abstention_total"] += int(not case.expected_source_ids)
                target["abstention_correct"] += int(
                    not case.expected_source_ids and not selected
                )
                if error:
                    target[error] += 1
            outcomes[name] = {
                "selected_ids": list(retrieved),
                "correct": correct,
                "error": error,
                "selected_chars": sum(
                    len(x.content) for x in case.originals if x.id in selected
                ),
            }
        results.append({
            "id": case.case_id, "family": case.family,
            "task_kind": case.task_kind, "expected_source_ids": sorted(case.expected_source_ids),
            "forbidden_source_ids": sorted(case.forbidden_source_ids),
            "outcomes": outcomes,
        })

    def report(counter: Counter) -> dict:
        total = counter["n"]
        abstain = counter["abstention_total"]
        return {
            "samples": total,
            "correct": counter["correct"],
            "accuracy": counter["correct"] / total if total else 0.0,
            "abstention_samples": abstain,
            "correct_abstentions": counter["abstention_correct"],
            "abstention_accuracy": (
                counter["abstention_correct"] / abstain if abstain else None
            ),
            "errors": {key: counter[key] for key in (
                "false_positive_on_unanswerable", "missing_required_source",
                "outdated_source_also_selected",
            )},
        }

    return {
        "schema": "sofia.v18-synthetic-retrieval-benchmark-v1",
        "question_count": len(cases),
        "families": list(FAMILIES),
        "dataset_provenance": "synthetic, generated inside this repository; no original benchmark samples",
        "metric": "strict required source IDs and prohibited outdated IDs, not generated answer quality",
        "model_evaluations_performed": 0,
        "live_host_evaluations_performed": 0,
        "ablation_configurations": list(ABLATIONS),
        "scores": {name: report(counts[name]) for name in selectors},
        "by_family": {
            family: {name: report(by_family[family][name]) for name in selectors}
            for family in FAMILIES
        },
        "cases": results,
        "gate4_proof": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report = evaluate()
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    for kind, result in report["scores"].items():
        print(f"{kind}: {result['correct']}/{result['samples']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
