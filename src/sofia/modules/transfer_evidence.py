"""Pure, effect-free review of bounded task-transfer trial evidence.

Shared by the legacy Generalization capability and the ML evaluation domain.
This module does not import a Core, mutate state, or grant any capability.
Every input is caller-supplied evidence, never independently verified here.
"""
from __future__ import annotations

import re
from collections.abc import Mapping

_TRIAL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$")
_FIELDS = frozenset({
    "id", "baseline_successes", "candidate_successes", "trial_count",
    "novel_task", "independent_holdout",
})


def review_transfer_trial(item: Mapping[str, object]) -> dict[str, object]:
    """Return an advisory result, preserving the v1 Generalization row contract.

    Success-rate deltas and test novelty are reported, but cannot establish
    general intelligence or authorize model updates, deployments, or learning.
    """
    if not isinstance(item, Mapping) or set(item) != _FIELDS:
        raise ValueError("unexpected fields in supplied projection")
    key = item["id"]
    if not isinstance(key, str) or _TRIAL_ID.fullmatch(key) is None:
        raise ValueError("invalid id")
    n = item["trial_count"]
    if type(n) is not int or not 1 <= n <= 100_000:
        raise ValueError("invalid trial_count")
    baseline = item["baseline_successes"]
    candidate = item["candidate_successes"]
    if type(baseline) is not int or not 0 <= baseline <= n:
        raise ValueError("invalid baseline_successes")
    if type(candidate) is not int or not 0 <= candidate <= n:
        raise ValueError("invalid candidate_successes")
    novel = item["novel_task"]
    holdout = item["independent_holdout"]
    if type(novel) is not bool or type(holdout) is not bool:
        raise ValueError("invalid flag")
    return {
        "id": key,
        "delta_success_rate": (candidate - baseline) / n,
        "finding": "candidate_transfer_evidence" if novel and holdout else "not_independent_transfer",
        "generalized_intelligence_verified": False,
    }
