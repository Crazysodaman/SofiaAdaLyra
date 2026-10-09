"""Validated cognitive workload scheduling with bounded NEURO advice."""
from __future__ import annotations

from dataclasses import replace

from .contracts import (
    CognitiveBudget,
    CognitiveSchedule,
    CognitiveTask,
    CognitiveTaskKind,
    EvidenceNeed,
    ModelWorkerRole,
    ReasoningRequirement,
)


_BASE_BUDGETS = {
    ReasoningRequirement.DETERMINISTIC: CognitiveBudget(
        256, 500, 2, False, reason="host deterministic response"
    ),
    ReasoningRequirement.FAST: CognitiveBudget(
        1024, 4000, 3, False, reason="bounded fast reasoning"
    ),
    ReasoningRequirement.STANDARD: CognitiveBudget(
        3072, 12000, 6, False, reason="standard primary reasoning"
    ),
    ReasoningRequirement.DEEP: CognitiveBudget(
        6144, 30000, 8, True, reason="deep multi-stage reasoning"
    ),
    ReasoningRequirement.VERIFY: CognitiveBudget(
        8192, 60000, 10, True, reason="high-stakes verified reasoning"
    ),
}


class ValidatedCognitiveScheduler:
    """Build a dependency graph without acquiring evidence or running work."""

    def budget(
        self,
        requirement: ReasoningRequirement,
        *,
        neuro_snapshot=None,
    ) -> tuple[ReasoningRequirement, CognitiveBudget]:
        if not isinstance(requirement, ReasoningRequirement):
            raise TypeError("requirement must be ReasoningRequirement")
        effective = requirement
        reason_parts = [_BASE_BUDGETS[requirement].reason]
        load = 0.0
        pressure = 0.0
        if neuro_snapshot is not None:
            homeostasis = getattr(neuro_snapshot, "homeostasis", None)
            load = float(getattr(homeostasis, "cognitive_load", 0.0))
            pressure = float(getattr(homeostasis, "competition_pressure", 0.0))
            focus = getattr(neuro_snapshot, "focus", None)
            if (
                requirement in {
                    ReasoningRequirement.FAST,
                    ReasoningRequirement.STANDARD,
                }
                and getattr(focus, "kind", None)
                in {"ops", "fleet", "run", "goal"}
                and float(getattr(focus, "score", 0.0)) >= 0.72
            ):
                effective = ReasoningRequirement.DEEP
                reason_parts.append("NEURO promoted high operational salience")
        base = _BASE_BUDGETS[effective]
        scale = 0.75 if max(load, pressure) >= 0.85 else 1.0
        if scale < 1.0:
            reason_parts.append("bounded for high observed cognitive pressure")
        budget = replace(
            base,
            token_budget=max(256, int(base.token_budget * scale)),
            time_budget_ms=max(500, int(base.time_budget_ms * scale)),
            retrieval_limit=max(1, int(base.retrieval_limit * scale)),
            allow_parallelism=(base.allow_parallelism and pressure < 0.75),
            background_priority=min(
                1.0,
                max(
                    float(getattr(getattr(neuro_snapshot, "focus", None), "score", 0.0)),
                    0.0,
                ),
            ),
            reason="; ".join(reason_parts),
        )
        return effective, budget

    def schedule(
        self,
        *,
        turn_id: str,
        evidence_needs: tuple[EvidenceNeed, ...],
        reasoning_requirement: ReasoningRequirement,
        response_strategy: str,
        budget: CognitiveBudget,
    ) -> CognitiveSchedule:
        if not isinstance(evidence_needs, tuple):
            raise TypeError("evidence_needs must be tuple")
        if response_strategy not in {
            "clarify", "deterministic", "generative", "tool-assisted",
        }:
            raise ValueError("unsupported response_strategy")
        tasks = []
        evidence_ids = []
        for index, need in enumerate(evidence_needs, start=1):
            if not isinstance(need, EvidenceNeed):
                raise TypeError("evidence_needs must contain EvidenceNeed values")
            task_id = f"evidence:{index}"
            evidence_ids.append(task_id)
            tasks.append(CognitiveTask(
                task_id=task_id,
                kind=CognitiveTaskKind.EVIDENCE_ACQUISITION,
                time_budget_ms=max(250, budget.time_budget_ms // 3),
            ))

        dependencies = tuple(evidence_ids)
        if reasoning_requirement is not ReasoningRequirement.DETERMINISTIC:
            roles = (
                (ModelWorkerRole.PRIMARY, ModelWorkerRole.SECONDARY)
                if reasoning_requirement is ReasoningRequirement.VERIFY
                else (ModelWorkerRole.PRIMARY,)
            )
            tasks.append(CognitiveTask(
                task_id="reason:answer",
                kind=CognitiveTaskKind.REASONING,
                depends_on=dependencies,
                preferred_roles=roles,
                token_budget=budget.token_budget,
                time_budget_ms=budget.time_budget_ms,
            ))
            dependencies = ("reason:answer",)
        tasks.append(CognitiveTask(
            task_id="validate:claims",
            kind=CognitiveTaskKind.CLAIM_VALIDATION,
            depends_on=dependencies,
            time_budget_ms=max(250, budget.time_budget_ms // 4),
        ))
        tasks.append(CognitiveTask(
            task_id="render:response",
            kind=CognitiveTaskKind.RENDERING,
            depends_on=("validate:claims",),
            token_budget=max(128, budget.token_budget // 3),
            time_budget_ms=max(250, budget.time_budget_ms // 4),
        ))
        parallel = (
            (tuple(evidence_ids),)
            if budget.allow_parallelism and len(evidence_ids) >= 2
            else ()
        )
        return CognitiveSchedule(
            schedule_id=f"schedule:{turn_id}",
            tasks=tuple(tasks),
            parallel_groups=parallel,
        )
