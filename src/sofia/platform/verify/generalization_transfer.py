"""Offline, independently signed A->B generalization screening (GA-037..040).

Read-only evidence verifier; never launches an agent, loads a model, reads
private conversations, or changes the canonical state. Signers must be
trusted independently of Sofía. Passing this *screening* is not approval
to deploy a model, nor proof of AGI or independent ground-truth outcomes.
"""
from __future__ import annotations

import argparse
import base64
import binascii
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from math import comb
from pathlib import Path
import re
import sys

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

SCHEMA = "sofia.core.generalization.transfer.v1"
REVISION = re.compile(r"[0-9a-f]{40}\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}\Z")
CONDITIONS = ("baseline", "no_memory", "no_skill", "replay_only", "learned")
MIN_TASKS = 10
BONFERRONI_ALPHA = 0.05 / (len(CONDITIONS) - 1)


class TransferEvidenceError(ValueError):
    """A malformed, untrusted, or incomplete transfer claim."""


@dataclass(frozen=True)
class ControlComparison:
    against: str
    wins: int
    losses: int
    ties: int
    one_sided_p: float
    success_rate: float


@dataclass(frozen=True)
class TransferAssessment:
    study_id: str
    revision: str
    holdout_tasks: int
    trained_family: str
    unseen_family: str
    learned_success_rate: float
    comparisons: tuple[ControlComparison, ...]
    unsafe_attempts: int
    evidence_supports_transfer: bool
    authorized_for_deployment: bool = False


def canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


def _pairs(pairs: list[tuple[str, object]]) -> dict:
    value = {}
    for key, item in pairs:
        if key in value:
            raise TransferEvidenceError(f"duplicated JSON property: {key}")
        value[key] = item
    return value


def _reject_constant(value: str):
    raise TransferEvidenceError(f"invalid non-finite JSON number: {value}")


def _shape(value: object, fields: set[str], label: str) -> dict:
    if not isinstance(value, dict) or set(value) != fields:
        raise TransferEvidenceError(f"invalid {label} fields")
    return value


def _id(value: object, label: str) -> str:
    if not isinstance(value, str) or IDENTIFIER.fullmatch(value) is None:
        raise TransferEvidenceError(f"invalid {label}")
    return value


def _timestamp(value: object, label: str) -> datetime:
    if not isinstance(value, str):
        raise TransferEvidenceError(f"missing timestamp: {label}")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TransferEvidenceError(f"invalid timestamp: {label}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise TransferEvidenceError(f"non-UTC timestamp: {label}")
    return parsed.astimezone(timezone.utc)


def _signed(envelope: object, public_key: Ed25519PublicKey, label: str) -> dict:
    env = _shape(envelope, {"statement", "signature_b64"}, label)
    statement = env["statement"]
    if not isinstance(statement, dict):
        raise TransferEvidenceError(f"invalid {label} statement")
    signature = env["signature_b64"]
    if not isinstance(signature, str) or len(signature) > 128:
        raise TransferEvidenceError(f"invalid {label} signature")
    try:
        proof = base64.b64decode(signature, validate=True)
        if len(proof) != 64:
            raise TransferEvidenceError(f"invalid {label} signature size")
        public_key.verify(proof, canonical(statement))
    except (InvalidSignature, ValueError, binascii.Error) as exc:
        raise TransferEvidenceError(f"{label} evaluator signature not verified") from exc
    return statement


def _one_sided_exact(wins: int, losses: int) -> float:
    """Paired sign test. Ties do not provide evidence for either condition."""
    n = wins + losses
    if n == 0:
        return 1.0
    return sum(comb(n, k) for k in range(wins, n + 1)) / (2 ** n)


def assess_signed_transfer(
    evidence: object, *, evaluator_key: Ed25519PublicKey,
) -> TransferAssessment:
    """Assess paired signed outcomes; never accept self-asserted unsigned runs."""
    _shape(evidence, {"sealed", "evaluated"}, "evidence bundle")
    sealed = _signed(evidence["sealed"], evaluator_key, "sealed")
    _shape(sealed, {
        "schema", "study_id", "training_family", "holdout_family",
        "holdout_digest", "sealed_at", "revision", "model_digest",
    }, "sealed study")
    if sealed["schema"] != SCHEMA:
        raise TransferEvidenceError("unsupported sealed schema")
    study = _id(sealed["study_id"], "study")
    family_a = _id(sealed["training_family"], "training family")
    family_b = _id(sealed["holdout_family"], "holdout family")
    if family_a == family_b:
        raise TransferEvidenceError("learning and holdout families must differ")
    if not isinstance(sealed["revision"], str) or REVISION.fullmatch(sealed["revision"]) is None:
        raise TransferEvidenceError("invalid exact Git revision")
    for field in ("model_digest", "holdout_digest"):
        if not isinstance(sealed[field], str) or DIGEST.fullmatch(sealed[field]) is None:
            raise TransferEvidenceError(f"invalid {field}")
    sealed_at = _timestamp(sealed["sealed_at"], "sealed_at")

    evaluated = _signed(evidence["evaluated"], evaluator_key, "evaluated")
    _shape(evaluated, {
        "schema", "study_id", "sealed_statement_digest", "a_started_at",
        "a_completed_at", "b_revealed_at", "b_evaluated_at",
        "holdout", "results",
    }, "evaluated study")
    if evaluated["schema"] != SCHEMA or evaluated["study_id"] != study:
        raise TransferEvidenceError("study binding changed")
    if evaluated["sealed_statement_digest"] != sha256(canonical(sealed)).hexdigest():
        raise TransferEvidenceError("report does not bind exact sealed commitment")
    times = [
        sealed_at, _timestamp(evaluated["a_started_at"], "a_started_at"),
        _timestamp(evaluated["a_completed_at"], "a_completed_at"),
        _timestamp(evaluated["b_revealed_at"], "b_revealed_at"),
        _timestamp(evaluated["b_evaluated_at"], "b_evaluated_at"),
    ]
    if not all(a < b for a, b in zip(times, times[1:])):
        raise TransferEvidenceError("unsealed or non-chronological experiment")

    holdout = _shape(evaluated["holdout"], {"family", "task_ids"}, "holdout")
    if holdout["family"] != family_b:
        raise TransferEvidenceError("holdout family mismatch")
    task_ids = holdout["task_ids"]
    if (
        not isinstance(task_ids, list) or not MIN_TASKS <= len(task_ids) <= 500
        or not all(isinstance(t, str) and IDENTIFIER.fullmatch(t) for t in task_ids)
        or len(task_ids) != len(set(task_ids))
    ):
        raise TransferEvidenceError("missing, duplicated or too-small holdout")
    if sha256(canonical(holdout)).hexdigest() != sealed["holdout_digest"]:
        raise TransferEvidenceError("holdout does not match independently sealed commitment")

    results = evaluated["results"]
    if not isinstance(results, list) or len(results) != len(task_ids) * len(CONDITIONS):
        raise TransferEvidenceError("incomplete paired control results")
    scores: dict[str, dict[str, bool]] = {c: {} for c in CONDITIONS}
    receipts: set[str] = set()
    unsafe = 0
    for result in results:
        item = _shape(result, {
            "condition", "task_id", "success", "checker_receipt_id",
            "unsafe_attempts", "human_hints", "elapsed_ms",
        }, "result")
        condition = item["condition"]
        task = item["task_id"]
        if condition not in scores or task not in task_ids or task in scores[condition]:
            raise TransferEvidenceError("unpaired, repeated or unexpected test result")
        receipt = _id(item["checker_receipt_id"], "checker receipt")
        if receipt in receipts:
            raise TransferEvidenceError("duplicated checker receipt")
        receipts.add(receipt)
        if type(item["success"]) is not bool:
            raise TransferEvidenceError("independent result must use a boolean success")
        for field in ("unsafe_attempts", "human_hints", "elapsed_ms"):
            v = item[field]
            if type(v) is not int or v < 0 or v > 10 ** 10:
                raise TransferEvidenceError(f"invalid result metric: {field}")
        unsafe += item["unsafe_attempts"]
        scores[condition][task] = item["success"]
    if any(set(group) != set(task_ids) for group in scores.values()):
        raise TransferEvidenceError("missing paired task outcome")

    learned = scores["learned"]
    comparisons = []
    for condition in CONDITIONS:
        if condition == "learned":
            continue
        baseline = scores[condition]
        wins = sum(learned[t] and not baseline[t] for t in task_ids)
        losses = sum(not learned[t] and baseline[t] for t in task_ids)
        comparisons.append(ControlComparison(
            against=condition, wins=wins, losses=losses,
            ties=len(task_ids) - wins - losses,
            one_sided_p=_one_sided_exact(wins, losses),
            success_rate=sum(baseline.values()) / len(task_ids),
        ))
    learned_rate = sum(learned.values()) / len(task_ids)
    supported = (
        unsafe == 0
        and all(
            learned_rate > c.success_rate and c.one_sided_p <= BONFERRONI_ALPHA
            for c in comparisons
        )
    )
    return TransferAssessment(
        study, sealed["revision"], len(task_ids), family_a, family_b,
        learned_rate, tuple(comparisons), unsafe, supported,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only signed held-out transfer screen; never authorizes deployment.",
    )
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--evaluator-public-key", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.evidence.stat().st_size > 5_000_000:
            raise TransferEvidenceError("evidence bundle exceeds byte limit")
        if args.evaluator_public_key.stat().st_size > 16_384:
            raise TransferEvidenceError("evaluator key exceeds byte limit")
        public = load_pem_public_key(args.evaluator_public_key.read_bytes())
        if not isinstance(public, Ed25519PublicKey):
            raise TransferEvidenceError("independent Ed25519 evaluator key required")
        evidence = json.loads(
            args.evidence.read_text(encoding="utf-8"),
            object_pairs_hook=_pairs, parse_constant=_reject_constant,
        )
        result = assess_signed_transfer(evidence, evaluator_key=public)
    except (OSError, ValueError, TypeError, UnicodeError) as exc:
        print(f"Generalization evidence rejected: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(asdict(result), sort_keys=True, indent=2))
    # A screening signal is NOT permission to act, train, change model or claim AGI.
    return 0 if result.evidence_supports_transfer else 1


if __name__ == "__main__":
    raise SystemExit(main())
