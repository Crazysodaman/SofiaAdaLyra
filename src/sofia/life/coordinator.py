"""Application-owned Self-Directed Life and Project Forge coordinator."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Callable, Mapping
from uuid import uuid4

from sofia.capability.gateway import CapabilityGateway
from sofia.capability.model import CapabilityProposal, CapabilityResultKind
from sofia.creative import (
    ArtifactKind, CreativeExplorer, CreativeProject, CreativeStore,
    CreativeWorldBridge, NativeCreativeAdapter, creative_request_digest,
)
from sofia.goals import (
    CompletionKind, GoalCompletionCondition, GoalCost, GoalOrigin, GoalRisk,
    GoalRunState, GoalService, GoalStatus, SOFIA_GOAL_OWNER_ID,
)
from sofia.goals.evidence import GoalEvidenceIndex, GoalEvidenceLedger
from sofia.interaction.world_model import ObjectKind, SpaceKind, Transform
from sofia.interaction.world_store import VirtualWorldStore
from sofia.neuro.model import NeuralActivation
from sofia.personality.preferences import (
    PreferenceDisposition, PreferenceRegistry, PreferenceSubject,
)
from sofia.rel.nicknames import NicknameProposal, NicknameRegistry
from sofia.safe.operator_stop import OperatorStopStore
from sofia.run.work import (
    DurableWorkStore, TaskExecutionManager, WorkJob, WorkResult, WorkStatus,
)
from sofia.social.principals import local_sparks_principal

from .model import (
    PROJECT_TRANSITIONS, ArtifactEvaluation, ExperienceRecord, InterestRecord,
    InterestStatus, LifeProject, LifeSelection, MilestoneStatus, MotivationSignal,
    PersonalJudgment, ProjectBrief, ProjectEvent, ProjectIdea, ProjectMilestone,
    ProjectScope, ProjectStatus, ResourceBudget, SelectionKind,
    TechnicalOutcome, aware, identifier, text,
)
from .idea_agent import ProjectIdeaAgent
from .draft_agent import ProjectDraftAgent, ProjectDraftGenerationError
from .store import LifeStore, ProjectWorkPending


SOFIA_PROJECT_OWNER = "sofia:self"
SOFIA_CREATIVE_OWNER = "sofia"
SOFIA_CREATIVE_AUTHOR = "sofia"
LOCAL_AUDIENCE = "local:text"


ShareCallback = Callable[[LifeProject, str, tuple[str, ...], datetime], bool]


class SelfDirectedLifeCoordinator:
    """Choose optional work without turning preference, goals, or mood into authority."""

    def __init__(
        self, *, state_path: Path | str, goals: GoalService,
        gateway: CapabilityGateway, creative_store: CreativeStore,
        creative_explorer: CreativeExplorer, world: VirtualWorldStore,
        creative_world: CreativeWorldBridge, preferences: PreferenceRegistry,
        nicknames: NicknameRegistry | None = None,
        share_callback: ShareCallback | None = None,
        max_workers: int = 1,
    ) -> None:
        if not isinstance(goals, GoalService) or not isinstance(gateway, CapabilityGateway):
            raise TypeError("canonical GoalService and CapabilityGateway required")
        self.path = Path(state_path)
        self.store = LifeStore(self.path)
        self.operator_stop = OperatorStopStore(self.path)
        self.goals, self.gateway = goals, gateway
        self.creative_store, self.creative_explorer = creative_store, creative_explorer
        self.world, self.creative_world = world, creative_world
        self.preferences, self.nicknames = preferences, nicknames
        self.share_callback = share_callback
        self.evidence = GoalEvidenceLedger(self.path)
        self.evidence_index = GoalEvidenceIndex(self.path)
        self.work_store = DurableWorkStore(self.path)
        self.work_store.recover(now=datetime.now(timezone.utc))
        self.manager = TaskExecutionManager(
            self.work_store, {"life-create-artifact": self._create_artifact},
            max_workers=max_workers, max_queued=32,
        )
        self._native_probe = NativeCreativeAdapter().probe()

    @staticmethod
    def _event(
        project: LifeProject, *, next_status: ProjectStatus, decision: str,
        reason: str, evidence_refs: tuple[str, ...], actor: str,
        now: datetime,
    ) -> ProjectEvent:
        return ProjectEvent(
            f"life-event:{uuid4()}", project.project_id, project.status,
            next_status, decision, reason, evidence_refs, actor, now,
        )

    def _verify_evidence(self, evidence_refs: tuple[str, ...]) -> None:
        if not evidence_refs or any(self.evidence_index.lookup(ref) is None for ref in evidence_refs):
            raise ValueError("Project Forge requires independently verified evidence")

    def record_observation(
        self, *, kind: str, source: str, assertion: str, now: datetime,
        payload: dict[str, object] | None = None,
    ) -> str:
        """Create typed evidence from a trusted host caller, never from attention alone."""
        identifier(kind, "evidence kind"); text(source, "evidence source", 300)
        text(assertion, "evidence assertion", 500)
        record = self.evidence.record(
            kind="reviewed_evidence", observed_at=now, source=source,
            assertion=assertion, payload={**(payload or {}), "kind": kind},
            principal_id=local_sparks_principal().principal_id,
            audience=LOCAL_AUDIENCE,
        )
        return record.evidence_ref

    def revise_interest(
        self, *, name: str, context: str, strength: float, confidence: float,
        reason: str, evidence_refs: tuple[str, ...], now: datetime,
        retire: bool = False,
    ) -> InterestRecord:
        self._verify_evidence(evidence_refs)
        existing = self.store.current_interest(
            name=name, context=context, audience_id=LOCAL_AUDIENCE,
        )
        digest = sha256(f"{name.casefold()}\0{context}".encode()).hexdigest()[:24]
        value = InterestRecord(
            f"interest:{digest}", name, context, strength, confidence,
            InterestStatus.RETIRED if retire else InterestStatus.ACTIVE,
            reason, evidence_refs, LOCAL_AUDIENCE,
            1 if existing is None else existing.revision + 1, now,
        )
        self.store.revise_interest(
            value, expected_revision=None if existing is None else existing.revision,
        )
        return value

    @staticmethod
    def _experience_digest(experience: ExperienceRecord) -> str:
        document = {
            "experience_id": experience.experience_id,
            "project_id": experience.project_id,
            "kind": experience.kind,
            "summary": experience.summary,
            "evidence_refs": experience.evidence_refs,
            "audience_id": experience.audience_id,
            "private": experience.private,
            "occurred_at": experience.occurred_at.astimezone(timezone.utc).isoformat(),
            "recorded_at": experience.recorded_at.astimezone(timezone.utc).isoformat(),
            "metadata": dict(experience.metadata),
        }
        return sha256(json.dumps(
            document, sort_keys=True, separators=(",", ":"),
        ).encode()).hexdigest()

    def learn_from_experiences(
        self, *, now: datetime, limit: int = 16,
    ) -> dict[str, int]:
        """Apply bounded, source-backed experience signals to durable interests.

        Only canonical artifact evaluations created by LIFE carry the v1 signal.
        Summaries, model prose, emotions, and mere project completion are never
        interpreted as evidence of taste.
        """
        aware(now, "learning time")
        counts = {"applied": 0, "no_change": 0, "ineligible": 0, "invalid": 0}
        for experience in self.store.pending_interest_experiences(limit=limit):
            if experience.recorded_at > now:
                # Preserve a future-dated record for bounded reconsideration once
                # its canonical observation window actually arrives.
                continue
            digest = self._experience_digest(experience)

            def consume(outcome: str, reason: str) -> None:
                if self.store.record_interest_learning(
                    experience_id=experience.experience_id,
                    experience_digest=digest, outcome=outcome, reason=reason,
                    processed_at=now,
                ):
                    counts[outcome] += 1

            signal = experience.metadata.get("interest_learning")
            if experience.kind != "artifact_evaluated" or not isinstance(signal, dict):
                consume("ineligible", "experience has no reviewed interest-learning signal")
                continue
            if signal.get("schema") != 1 or not isinstance(signal.get("evaluation_id"), str):
                consume("invalid", "interest-learning signal schema is invalid")
                continue
            if experience.project_id is None:
                consume("invalid", "interest-learning experience has no project")
                continue
            try:
                project = self.store.get(
                    experience.project_id,
                    owner_principal_id=SOFIA_PROJECT_OWNER,
                    audience_id=experience.audience_id,
                )
            except KeyError:
                consume("invalid", "project owner or audience does not match experience")
                continue
            if project.audience_id != experience.audience_id:
                consume("invalid", "project and experience audience differ")
                continue
            signal_confidence = signal.get("confidence")
            if (
                signal.get("originating_interest") != project.originating_interest
                or isinstance(signal_confidence, bool)
                or not isinstance(signal_confidence, (int, float))
                or not 0 <= float(signal_confidence) <= 1
                or float(signal_confidence) != project.confidence
            ):
                consume("invalid", "interest identity or confidence does not match project")
                continue
            evaluations = tuple(
                item for item in self.store.evaluations(project.project_id)
                if item.evaluation_id == signal["evaluation_id"]
            )
            if len(evaluations) != 1:
                consume("invalid", "canonical artifact evaluation is missing")
                continue
            evaluation = evaluations[0]
            if (
                evaluation.evidence_refs != experience.evidence_refs
                or evaluation.evaluated_at != experience.occurred_at
            ):
                consume("invalid", "experience does not match canonical evaluation")
                continue
            evidence = tuple(
                self.evidence_index.lookup(ref) for ref in experience.evidence_refs
            )
            if any(item is None for item in evidence):
                consume("invalid", "source evidence is missing")
                continue
            principal_id = local_sparks_principal().principal_id
            if any(
                item.principal_id != principal_id
                or item.audience != experience.audience_id
                or not item.source
                or item.observed_at > experience.occurred_at
                or item.kind not in {"reviewed_evidence", "operation_receipt"}
                for item in evidence if item is not None
            ):
                consume("invalid", "evidence provenance, principal, audience, or time is invalid")
                continue
            # A free-standing evaluation row and plausible evidence reference
            # are NOT proof that a personal project produced the artifact.
            # Recheck the original historical revision, actual immutable
            # bytes and its authorized completed RUN receipt before learning.
            if (
                (evaluation.artifact_id, evaluation.artifact_revision)
                not in self.store.artifacts(project.project_id)
            ):
                consume("invalid", "evaluation artifact revision is not linked to project")
                continue
            revisions = self.creative_store.history(
                evaluation.artifact_id, SOFIA_CREATIVE_OWNER,
                project.audience_id,
            )
            revision = next((
                candidate for candidate in revisions
                if candidate.revision == evaluation.artifact_revision
                and candidate.project_id == project.project_id
            ), None)
            if revision is None or not any(
                self._confirmed_artifact_run_receipt(
                    project, artifact_id=evaluation.artifact_id,
                    revision=evaluation.artifact_revision,
                    evidence_ref=ref, now=now,
                )
                for ref in evaluation.evidence_refs
            ):
                consume("invalid", "evaluation has no canonical creative revision and RUN receipt")
                continue
            from .validation import inspect_objective_artifact, ObjectiveDisposition
            try:
                report = inspect_objective_artifact(
                    revision=revision, path=Path(revision.content_path),
                    objectives=project.brief.objectives,
                )
            except (OSError, ValueError, TypeError):
                consume("invalid", "historical creative artifact cannot be independently inspected")
                continue
            observed_results = {
                item.objective: (
                    True if item.disposition is ObjectiveDisposition.PASS
                    else False if item.disposition is ObjectiveDisposition.FAIL
                    else None
                ) for item in report.findings
            }
            observed_outcome = (
                TechnicalOutcome.VALID if report.eligible_for_independent_completion
                else TechnicalOutcome.INVALID if any(
                    item.disposition is ObjectiveDisposition.FAIL
                    for item in report.findings
                ) else TechnicalOutcome.INCONCLUSIVE
            )
            if (
                report.integrity is not ObjectiveDisposition.PASS
                or report.revision != evaluation.artifact_revision
                or dict(evaluation.objective_results) != observed_results
                or evaluation.technical_outcome is not observed_outcome
            ):
                consume("invalid", "historical evaluation conflicts with source artifact objective checks")
                continue
            # Repair only the original reviewed preference, never invent a
            # judgment from technical results or rewrite newer preferences.
            # A failed preference CAS leaves the experience pending so the
            # same application worker can safely retry on the next tick.
            self._settle_evaluation_preference(project, evaluation)
            judgment = evaluation.personal_judgment
            if judgment is PersonalJudgment.UNKNOWN:
                consume("no_change", "grounded evaluation made no personal judgment")
                continue

            current = self.store.interest_by_id(
                project.originating_interest, audience_id=project.audience_id,
            )
            name = project.name if current is None else current.name
            context = "creative-project" if current is None else current.context
            base_strength = 0.35 if current is None else current.strength
            base_confidence = 0.4 if current is None else current.confidence
            delta = {
                PersonalJudgment.LIKE: 0.10,
                PersonalJudgment.DISLIKE: -0.14,
                PersonalJudgment.MIXED: -0.02,
                PersonalJudgment.INDIFFERENT: -0.08,
            }[judgment] * max(0.25, project.confidence)
            strength = min(1.0, max(0.0, base_strength + delta))
            confidence = min(1.0, base_confidence + 0.05 * project.confidence)
            if judgment is PersonalJudgment.LIKE:
                status = (
                    InterestStatus.ACTIVE if strength >= 0.35
                    else InterestStatus.RETIRED
                )
            elif judgment in {PersonalJudgment.DISLIKE, PersonalJudgment.INDIFFERENT}:
                status = (
                    InterestStatus.RETIRED
                    if strength <= 0.20 and confidence >= 0.6
                    else (InterestStatus.ACTIVE if current is None else current.status)
                )
            else:
                status = InterestStatus.ACTIVE if current is None else current.status
            refs = tuple(dict.fromkeys(
                (() if current is None else current.evidence_refs)
                + experience.evidence_refs
            ))[-32:]
            interest_id = (
                "interest:" + sha256(
                    f"{name.casefold()}\0{context}".encode()
                ).hexdigest()[:24]
                if current is None else current.interest_id
            )
            revision = 1 if current is None else current.revision + 1
            learned = InterestRecord(
                interest_id, name, context, strength, confidence, status,
                (
                    f"Grounded artifact evaluation {evaluation.evaluation_id} "
                    f"recorded a {judgment.value} judgment for {project.name}."
                ),
                refs, project.audience_id, revision, now,
            )
            if self.store.record_interest_learning(
                experience_id=experience.experience_id,
                experience_digest=digest, outcome="applied",
                reason="canonical artifact evaluation updated originating interest",
                processed_at=now, interest=learned,
                expected_revision=None if current is None else current.revision,
            ):
                counts["applied"] += 1
        return counts

    def invent_project(
        self, idea: ProjectIdea, *, scope: ProjectScope = ProjectScope.PERSONAL_PRIVATE,
        budget: ResourceBudget | None = None,
    ) -> LifeProject:
        """Validate an open-ended structured idea; no project catalogue is consulted."""
        if not isinstance(idea, ProjectIdea):
            raise TypeError("ProjectIdea required")
        if self.operator_stop.current().active:
            raise PermissionError("operator stop blocks optional LIFE project creation")
        self._verify_evidence(idea.evidence_refs)
        try:
            artifact_kind = ArtifactKind(idea.requested_artifact_kind)
        except ValueError as exc:
            raise ValueError("requested project output has no verified creative adapter") from exc
        if artifact_kind not in self._native_probe.supported_kinds or not self._native_probe.available:
            raise RuntimeError("requested creative tool is not verified available")
        live = self.store.list_scope(
            owner_principal_id=SOFIA_PROJECT_OWNER, audience_id=LOCAL_AUDIENCE,
        )
        comparable = " ".join(idea.name.casefold().split())
        if any(
            project.status not in {ProjectStatus.ARCHIVED, ProjectStatus.SUPERSEDED}
            and " ".join(project.name.casefold().split()) == comparable
            for project in live
        ):
            raise ValueError("an equivalent live personal project already exists")
        project_id = "project:" + sha256(
            f"{idea.idea_id}\0{idea.name}\0{LOCAL_AUDIENCE}".encode()
        ).hexdigest()[:28]
        resource_budget = budget or ResourceBudget()
        brief = ProjectBrief(
            idea.objectives, idea.optional_success_criteria,
            (self._native_probe.adapter_id, f"artifact-kind:{artifact_kind.value}"),
            ("creative.artifact.create",), resource_budget,
        )
        project = LifeProject(
            project_id, idea.name, idea.description, SOFIA_GOAL_OWNER_ID,
            SOFIA_PROJECT_OWNER, LOCAL_AUDIENCE, scope,
            idea.originating_interest, ProjectStatus.IDEA, brief, None,
            max(0.55, min(0.85, (idea.curiosity + idea.confidence) / 2)),
            idea.confidence, idea.created_at, idea.created_at,
        )
        event = ProjectEvent(
            f"life-event:{uuid4()}", project_id, None, ProjectStatus.IDEA,
            "invent", "Sofía formed a bounded project idea from recorded evidence.",
            idea.evidence_refs, SOFIA_GOAL_OWNER_ID, idea.created_at,
        )
        self.store.create(project, event)
        self.creative_store.create_project(CreativeProject(
            project_id, idea.name, SOFIA_CREATIVE_OWNER, LOCAL_AUDIENCE,
            idea.created_at,
        ))
        for ordinal, objective in enumerate(idea.objectives):
            self.store.add_milestone(ProjectMilestone(
                f"milestone:{sha256(f'{project_id}:{ordinal}'.encode()).hexdigest()[:24]}",
                project_id, objective, MilestoneStatus.PLANNED, ordinal,
                (), None, idea.created_at,
            ))
        self._experience(
            project=project, kind="project_invented",
            summary=f"Invented the optional project {project.name}.",
            evidence_refs=idea.evidence_refs, now=idea.created_at,
            metadata={"idea_id": idea.idea_id},
        )
        return project

    def propose_project(
        self, project_id: str, *, reason: str, evidence_refs: tuple[str, ...],
        now: datetime,
    ) -> LifeProject:
        return self._transition(
            project_id, ProjectStatus.PROPOSED, decision="propose",
            reason=reason, evidence_refs=evidence_refs,
            actor=SOFIA_GOAL_OWNER_ID, now=now, sync_goal=False,
        )

    def activate_project(
        self, project_id: str, *, reason: str, evidence_refs: tuple[str, ...],
        now: datetime, resource_pressure: float = 0.0,
    ) -> LifeProject:
        if self.operator_stop.current().active:
            raise PermissionError("operator stop blocks optional LIFE project activation")
        project = self._project(project_id)
        if self.operator_stop.current().active:
            raise PermissionError("operator stop blocks optional LIFE goal activation")
        if project.status is not ProjectStatus.PROPOSED:
            raise ValueError("only a proposed project may be activated")
        self._verify_evidence(evidence_refs)
        digest = project.project_id.split(":", 1)[-1]
        activation = NeuralActivation(
            key=f"life:project:{digest}", source=f"life:{project.originating_interest}",
            kind="project", score=max(0.72, project.priority), novelty=0.65,
            updated_at=now,
        )
        completion_text = f"Project {project.project_id} reached a chosen completion option"
        candidate = self.goals.candidate_from_activation(
            activation=activation, title=project.name,
            reason=reason, completion=GoalCompletionCondition(
                CompletionKind.EVIDENCE_TRUE, completion_text,
            ), evidence_refs=evidence_refs, now=now,
            risk=GoalRisk.LOW, cost=GoalCost.LOW,
            principal=local_sparks_principal(), expires_at=now + timedelta(days=90),
        )
        if candidate is None:
            raise ValueError("project did not meet bounded goal admission threshold")
        decision = self.goals.evaluate_candidate(
            candidate, resource_pressure=resource_pressure,
        )
        goal = self.goals.admit_candidate(
            candidate, decision=decision, now=now,
            resource_pressure=resource_pressure,
        )
        if goal is None or goal.status is not GoalStatus.ACTIVE:
            raise RuntimeError(f"project goal was not activated: {decision.decision.value}")
        event = self._event(
            project, next_status=ProjectStatus.ACTIVE, decision="activate",
            reason=reason, evidence_refs=evidence_refs,
            actor=SOFIA_GOAL_OWNER_ID, now=now,
        )
        updated = replace(
            project, status=ProjectStatus.ACTIVE, goal_id=goal.id,
            updated_at=now, revision=project.revision + 1,
        )
        self.store.update(updated, event, expected_revision=project.revision)
        return updated

    def _project(self, project_id: str) -> LifeProject:
        return self.store.get(
            project_id, owner_principal_id=SOFIA_PROJECT_OWNER,
            audience_id=LOCAL_AUDIENCE,
        )

    def _sync_goal(
        self, project: LifeProject, next_status: ProjectStatus,
        evidence_refs: tuple[str, ...], reason: str, now: datetime,
    ) -> None:
        if project.goal_id is None:
            return
        principal = local_sparks_principal()
        goal = next((item for item in self.goals.list_visible(principal) if item.id == project.goal_id), None)
        if goal is None or goal.status in {
            GoalStatus.COMPLETED, GoalStatus.REJECTED, GoalStatus.CANCELLED,
            GoalStatus.EXPIRED, GoalStatus.SUPERSEDED,
        }:
            return
        target = None
        kwargs: dict[str, object] = {}
        if next_status is ProjectStatus.PAUSED and goal.status in {GoalStatus.ACTIVE, GoalStatus.BLOCKED}:
            target = GoalStatus.PAUSED
        elif next_status is ProjectStatus.ACTIVE and goal.status in {GoalStatus.PAUSED, GoalStatus.BLOCKED}:
            target = GoalStatus.ACTIVE
        elif next_status in {ProjectStatus.ABANDONED, ProjectStatus.ARCHIVED, ProjectStatus.REJECTED}:
            target = GoalStatus.CANCELLED
        elif next_status is ProjectStatus.FAILED and goal.status is GoalStatus.ACTIVE:
            target = GoalStatus.BLOCKED
            kwargs["blocked_reason"] = reason[:320]
        elif next_status is ProjectStatus.COMPLETED:
            target = GoalStatus.COMPLETED
        if target is None:
            return
        self.goals.transition(
            goal_id=goal.id, principal_id=goal.scope_principal_id,
            audience=goal.scope_audience, expected_status=goal.status,
            next_status=target, actor_principal_id=SOFIA_GOAL_OWNER_ID,
            now=now, evidence_refs=evidence_refs, note=reason[:320], **kwargs,
        )

    def _transition(
        self, project_id: str, next_status: ProjectStatus, *, decision: str,
        reason: str, evidence_refs: tuple[str, ...], actor: str,
        now: datetime, sync_goal: bool = True,
        superseded_by: str | None = None,
    ) -> LifeProject:
        project = self._project(project_id)
        if next_status not in PROJECT_TRANSITIONS.get(project.status, frozenset()):
            raise ValueError(f"illegal project transition {project.status.value}->{next_status.value}")
        self._verify_evidence(evidence_refs)
        if (
            next_status in {ProjectStatus.ABANDONED, ProjectStatus.REJECTED}
            and project.scope in {ProjectScope.USER_ASSIGNMENT, ProjectScope.OPERATIONAL_DUTY}
            and actor == SOFIA_GOAL_OWNER_ID
        ):
            raise PermissionError("critical/user work requires explicit handoff or owner cancellation")
        if sync_goal:
            self._sync_goal(project, next_status, evidence_refs, reason, now)
        event = self._event(
            project, next_status=next_status, decision=decision, reason=reason,
            evidence_refs=evidence_refs, actor=actor, now=now,
        )
        updated = replace(
            project, status=next_status, updated_at=now,
            revision=project.revision + 1,
            superseded_by=superseded_by if next_status is ProjectStatus.SUPERSEDED else None,
        )
        self.store.update(updated, event, expected_revision=project.revision)
        self._experience(
            project=updated, kind=f"project_{next_status.value}",
            summary=f"{updated.name}: {reason}", evidence_refs=evidence_refs,
            now=now, metadata={"decision": decision},
        )
        return updated

    def pause(self, project_id: str, *, reason: str, evidence_refs: tuple[str, ...], now: datetime) -> LifeProject:
        return self._transition(project_id, ProjectStatus.PAUSED, decision="pause", reason=reason, evidence_refs=evidence_refs, actor=SOFIA_GOAL_OWNER_ID, now=now)

    def resume(self, project_id: str, *, reason: str, evidence_refs: tuple[str, ...], now: datetime) -> LifeProject:
        return self._transition(project_id, ProjectStatus.ACTIVE, decision="resume", reason=reason, evidence_refs=evidence_refs, actor=SOFIA_GOAL_OWNER_ID, now=now)

    def abandon(self, project_id: str, *, reason: str, evidence_refs: tuple[str, ...], now: datetime) -> LifeProject:
        return self._transition(project_id, ProjectStatus.ABANDONED, decision="voluntary_abandonment", reason=reason, evidence_refs=evidence_refs, actor=SOFIA_GOAL_OWNER_ID, now=now)

    def reject(self, project_id: str, *, reason: str, evidence_refs: tuple[str, ...], now: datetime) -> LifeProject:
        """Decline an optional idea without manufacturing replacement work."""
        project = self._transition(
            project_id, ProjectStatus.REJECTED, decision="voluntary_rejection",
            reason=reason, evidence_refs=evidence_refs,
            actor=SOFIA_GOAL_OWNER_ID, now=now,
        )
        self.store.choose_quiet(
            until_at=now + timedelta(hours=1),
            reason="A rejected optional activity is not automatically replaced.",
            now=now,
        )
        return project

    def archive(self, project_id: str, *, reason: str, evidence_refs: tuple[str, ...], now: datetime) -> LifeProject:
        return self._transition(project_id, ProjectStatus.ARCHIVED, decision="archive", reason=reason, evidence_refs=evidence_refs, actor=SOFIA_GOAL_OWNER_ID, now=now)

    def supersede(
        self, project_id: str, *, replacement_project_id: str, reason: str,
        evidence_refs: tuple[str, ...], now: datetime,
    ) -> LifeProject:
        self._project(replacement_project_id)
        if replacement_project_id == project_id:
            raise ValueError("project cannot supersede itself")
        return self._transition(
            project_id, ProjectStatus.SUPERSEDED, decision="supersede",
            reason=reason, evidence_refs=evidence_refs,
            actor=SOFIA_GOAL_OWNER_ID, now=now,
            superseded_by=replacement_project_id,
        )

    def _current_verified_objective_completion(
        self, project: LifeProject, *, now: datetime,
    ) -> bool:
        """Revalidate the actual original current bytes and completed RUN.

        A durable COMPLETED/ARCHIVED label is historical state, not proof
        that bytes still exist, have the same digest, or meet original
        objectives today. This source-only check is shared by the actual
        completion gate and operator-facing diagnosis.
        """
        if (
            project.goal_id is None
            or len(set(project.brief.objectives)) != len(project.brief.objectives)
        ):
            return False
        for evaluation in self.store.evaluations(project.project_id):
            if (
                evaluation.technical_outcome is not TechnicalOutcome.VALID
                or set(evaluation.objective_results) != set(project.brief.objectives)
                or any(value is not True for value in evaluation.objective_results.values())
            ):
                continue
            try:
                report = self.inspect_artifact_objectives(
                    project.project_id, artifact_id=evaluation.artifact_id,
                )
            except (LookupError, OSError, ValueError, PermissionError):
                continue
            except RuntimeError as exc:
                if "failed preview integrity check" not in str(exc):
                    raise
                continue
            if (
                report.revision == evaluation.artifact_revision
                and report.eligible_for_independent_completion
                and any(
                    self._confirmed_artifact_run_receipt(
                        project,
                        artifact_id=evaluation.artifact_id,
                        revision=evaluation.artifact_revision,
                        evidence_ref=ref, now=now,
                    )
                    for ref in evaluation.evidence_refs
                )
            ):
                return True
        return False

    def complete(self, project_id: str, *, reason: str, now: datetime) -> LifeProject:
        project = self._project(project_id)
        if len(set(project.brief.objectives)) != len(project.brief.objectives):
            raise ValueError("legacy original objectives are ambiguous; completion needs correction")
        if project.goal_id is None:
            raise ValueError("active project has no canonical goal")
        if not self._current_verified_objective_completion(project, now=now):
            raise ValueError(
                "completion requires current artifact bytes and independent "
                "PASS for all original objectives; model critique alone is insufficient"
            )
        goal = next(item for item in self.goals.list_visible(local_sparks_principal()) if item.id == project.goal_id)
        record = self.evidence.record(
            kind="reviewed_evidence", observed_at=now, source="life:project-evaluation",
            successful=True, goal_id=goal.id,
            assertion=goal.completion.description,
            payload={"project_id": project_id, "decision": "completed"},
            principal_id=local_sparks_principal().principal_id,
            audience=LOCAL_AUDIENCE,
        )
        return self._transition(
            project_id, ProjectStatus.COMPLETED, decision="complete",
            reason=reason, evidence_refs=(record.evidence_ref,),
            actor=SOFIA_GOAL_OWNER_ID, now=now,
        )

    def fail(self, project_id: str, *, reason: str, evidence_refs: tuple[str, ...], now: datetime) -> LifeProject:
        """Technical failure is recorded without creating emotional evidence."""
        return self._transition(project_id, ProjectStatus.FAILED, decision="technical_failure", reason=reason, evidence_refs=evidence_refs, actor=SOFIA_GOAL_OWNER_ID, now=now)

    def choose_inactivity(self, *, reason: str, until: datetime, now: datetime) -> LifeSelection:
        aware(until, "quiet-until")
        if until <= now or until > now + timedelta(days=30):
            raise ValueError("inactivity window must be future and bounded")
        self.store.choose_quiet(until_at=until, reason=text(reason, "inactivity reason", 500), now=now)
        selection = LifeSelection(
            f"life-selection:{uuid4()}", SelectionKind.INACTIVITY, None,
            reason, 0.0, False, now,
        )
        self.store.record_selection(selection)
        return selection

    def motivation_signals(
        self, *, now: datetime, busy: bool,
        resource_pressure: float, limit: int = 32,
    ) -> tuple[MotivationSignal, ...]:
        """Project source-grounded optional motivation, never new authority.

        The score is a bounded heuristic over original LIFE interests and
        projects, GOALS, RUN receipts, and real resource usage. Verified
        progress is zero unless the original work still passes the closed
        validator and has a linked completed RUN receipt. This neither
        persists motivation nor learns a subjective reward from model text.
        """
        aware(now, "motivation inspection time")
        if type(busy) is not bool:
            raise TypeError("busy must be boolean")
        if (
            isinstance(resource_pressure, bool)
            or not isinstance(resource_pressure, (int, float))
            or not 0.0 <= resource_pressure <= 1.0
        ):
            raise ValueError("resource pressure must be bounded")
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("motivation limit must be between 1 and 100")
        visible = {
            item.id: item
            for item in self.goals.list_visible(local_sparks_principal())
            if item.origin is GoalOrigin.SELF
            and item.owner_principal_id == SOFIA_GOAL_OWNER_ID
            and item.scope_audience == LOCAL_AUDIENCE
        }
        projects = self.store.list_scope(
            owner_principal_id=SOFIA_PROJECT_OWNER,
            audience_id=LOCAL_AUDIENCE,
            statuses=(ProjectStatus.ACTIVE,),
        )
        stopped = self.operator_stop.current().active
        quiet = self.store.quiet_until(now=now) is not None
        source: list[MotivationSignal] = []
        for project in projects[:limit]:
            goal = visible.get(project.goal_id)
            interest = self.store.interest_by_id(
                project.originating_interest, audience_id=project.audience_id,
            )
            jobs = tuple(
                self.work_store.get(job_id)
                for job_id in self.store.jobs(project.project_id)
            )
            latest = jobs[-1] if jobs else None
            usage = self.store.usage(
                project.project_id, now.astimezone(timezone.utc).date(),
            )
            budget = project.brief.resource_budget
            resource_cost = round(min(1.0, max(
                float(usage["wall_seconds"]) / budget.daily_seconds,
                int(usage["storage_bytes"]) / budget.storage_bytes,
            )), 6)
            curiosity = (
                round(interest.strength * interest.confidence, 6)
                if interest is not None
                and interest.status is InterestStatus.ACTIVE
                else 0.0
            )
            goal_importance = (
                round((goal.base_priority + project.priority) / 2, 6)
                if goal is not None else 0.0
            )
            artifacts = self.store.artifacts(project.project_id)
            novelty = round(1.0 / (1 + len(artifacts)), 6)
            unfinished = 1.0 if any(
                milestone.status in {
                    MilestoneStatus.PLANNED, MilestoneStatus.ACTIVE,
                }
                for milestone in self.store.milestones(project.project_id)
            ) else 0.0
            verified_progress = (
                1.0 if artifacts and self._current_verified_objective_completion(
                    project, now=now,
                ) else 0.0
            )
            unresolved_run = latest is not None and latest.status in {
                WorkStatus.QUEUED, WorkStatus.RUNNING,
                WorkStatus.WAITING_APPROVAL, WorkStatus.BLOCKED,
                WorkStatus.UNCERTAIN,
                WorkStatus.FAILED, WorkStatus.CANCELLED,
            }
            uncertainty = (
                1.0 if latest is not None and latest.status in {
                    WorkStatus.UNCERTAIN, WorkStatus.BLOCKED,
                }
                else 0.65 if latest is not None
                and latest.status is WorkStatus.COMPLETED
                and verified_progress == 0
                else 0.25
            )
            risk = (
                0.45 if len(project.brief.required_tools) > 2
                else 0.15
            )
            interruption_cost = 1.0 if busy else float(resource_pressure)
            blockers = []
            if stopped:
                blockers.append("operator_stop")
            if quiet:
                blockers.append("voluntary_quiet")
            if busy or resource_pressure >= 0.75:
                blockers.append("foreground_or_resource_priority")
            if goal is None or goal.status is not GoalStatus.ACTIVE:
                blockers.append("canonical_goal_not_active")
            if project.scope is not ProjectScope.PERSONAL_PRIVATE:
                blockers.append("not_optional_private_work")
            if interest is None or interest.status is not InterestStatus.ACTIVE:
                blockers.append("original_interest_not_active")
            if resource_cost >= 1.0:
                blockers.append("daily_budget_exhausted")
            if unresolved_run:
                blockers.append("prior_run_needs_settlement")
            # Utility is a conservative explanatory heuristic, not a new
            # GOALS priority, permission, emotional experience or source
            # success oracle. High uncertainty/cost always reduces score.
            score = round(max(0.0, min(1.0,
                0.35 * goal_importance
                + 0.20 * curiosity
                + 0.12 * novelty
                + 0.12 * unfinished
                + 0.12 * verified_progress
                - 0.12 * resource_cost
                - 0.12 * uncertainty
                - 0.08 * risk
                - 0.20 * interruption_cost
            )), 6)
            evidence_refs = tuple(dict.fromkeys(
                (() if interest is None else interest.evidence_refs)
                + (() if goal is None else goal.evidence_refs)
            ))[:32]
            source.append(MotivationSignal(
                project_id=project.project_id, goal_id=project.goal_id,
                evidence_refs=evidence_refs,
                goal_importance=goal_importance, curiosity=curiosity,
                verified_learning_progress=verified_progress,
                novelty=novelty, unfinished_commitment=unfinished,
                uncertainty=uncertainty, resource_cost=resource_cost,
                risk=risk, interruption_cost=interruption_cost,
                score=score, eligible=not blockers,
                reason=(
                    "Eligible bounded evidence-derived optional project."
                    if not blockers
                    else "Ineligible: " + ", ".join(blockers)
                ),
                observed_at=now,
            ))
        return tuple(source)

    def compare_optional_choices(
        self, *, now: datetime, busy: bool,
        resource_pressure: float, limit: int = 32,
    ) -> dict[str, object]:
        """Counterfactual policy view, never observed outcome or tool authority.

        Original GOALS/LIFE/SAFE and RUN budget eligibility is checked first
        via the same signals used by select_activity. Alternative outcomes
        are explicitly hypothetical; no private project is abandoned, no
        owner is messaged, and nothing is persisted by this comparison.
        """
        signals = self.motivation_signals(
            now=now, busy=busy,
            resource_pressure=resource_pressure, limit=limit,
        )
        eligible = tuple(sorted(
            (signal for signal in signals if signal.eligible),
            key=lambda signal: (
                -signal.score, -signal.goal_importance, signal.project_id,
            ),
        ))
        blocked = tuple(signal for signal in signals if not signal.eligible)
        primary = eligible[0] if eligible else None
        alternate = eligible[1] if len(eligible) > 1 else None
        blocked_review = any(
            "prior_run_needs_settlement" in signal.reason
            or "canonical_goal_not_active" in signal.reason
            for signal in blocked
        )
        cases: list[dict[str, object]] = []
        for choice, signal, permitted, evidence in (
            (
                "continue", primary, primary is not None,
                "Original LIFE/GOALS eligibility and bounded motivation score.",
            ),
            (
                "switch", alternate, alternate is not None,
                "Alternative already-eligible private project; no new grant.",
            ),
            (
                "postpone", None, True,
                "No optional execution is required; inactivity is always valid.",
            ),
            (
                "ask", None, blocked_review,
                "Blocked canonical state needs independent operator review.",
            ),
            (
                "abandon", None, False,
                "Terminating a private project needs its own evidence-linked LIFE decision.",
            ),
        ):
            cases.append({
                "choice": choice,
                "project_id": None if signal is None else signal.project_id,
                "eligible": permitted,
                "hypothetical": True,
                "estimated_utility": 0.0 if signal is None else signal.score,
                "estimated_risk": 0.0 if signal is None else signal.risk,
                "estimated_interruption_cost": (
                    0.0 if signal is None else signal.interruption_cost
                ),
                "uncertainty": (
                    0.0 if signal is None else signal.uncertainty
                ),
                "reason": evidence,
            })
        recommendation = (
            "continue" if primary is not None
            else "postpone"
        )
        return {
            "as_of": now.astimezone(timezone.utc).isoformat(),
            "recommendation": recommendation,
            "selected_project_id": (
                None if primary is None else primary.project_id
            ),
            "source": "canonical_life_goal_run_motivation_projection",
            "choices": tuple(cases),
            "simulation_only": True,
        }

    def select_activity(
        self, *, now: datetime, busy: bool, resource_pressure: float,
    ) -> LifeSelection:
        if not 0 <= resource_pressure <= 1:
            raise ValueError("resource_pressure must be in 0..1")
        quiet = self.store.quiet_until(now=now)
        kind, project, reason = SelectionKind.INACTIVITY, None, "No optional activity is currently justified."
        if self.operator_stop.current().active:
            reason = "Optional LIFE work paused by the operator stop."
        elif quiet is not None:
            reason = f"Sofía chose quiet time until {quiet[0].isoformat()}: {quiet[1]}"
        elif busy:
            reason = "Foreground user activity has priority over optional personal work."
        elif resource_pressure >= 0.75:
            reason = "Optional personal work paused for resource pressure."
        else:
            alternatives = self.compare_optional_choices(
                now=now, busy=busy, resource_pressure=resource_pressure,
            )
            chosen = alternatives["selected_project_id"]
            if alternatives["recommendation"] == "continue" and chosen is not None:
                project = self._project(chosen)
                kind = SelectionKind.PROJECT
                reason = (
                    "Selected an original GOALS-authorized private project "
                    "after bounded, explicitly hypothetical alternatives."
                )
        # The background worker may observe identical inactivity on every
        # 300-second tick. Reuse a recent exact idle decision instead of
        # producing indefinite duplicate durable rows and false activity.
        # A changed quiet window, busy/pressure context or eligible project
        # still produces a fresh canonical selection immediately.
        if kind is SelectionKind.INACTIVITY:
            previous = self.store.selections(limit=1)
            if previous:
                recent = previous[0]
                if (
                    recent.kind is SelectionKind.INACTIVITY
                    and recent.project_id is None
                    and recent.reason == reason
                    and recent.busy is busy
                    and recent.resource_pressure == resource_pressure
                    and recent.selected_at <= now
                    and now - recent.selected_at < timedelta(hours=1)
                ):
                    return recent
        selection = LifeSelection(
            f"life-selection:{uuid4()}", kind,
            None if project is None else project.project_id, reason,
            resource_pressure, busy, now,
        )
        self.store.record_selection(selection)
        return selection

    def inspect_artifact_objectives(self, project_id: str, *, artifact_id: str):
        """Independent, read-only structural and objective evidence projection.

        Unknown natural-language objectives remain unknown. This cannot
        complete a goal or update preferences or memory by itself.
        """
        from .validation import inspect_objective_artifact

        project = self._project(project_id)
        path, _media = self.creative_explorer.verified_preview(
            artifact_id,
            owner_principal_id=SOFIA_CREATIVE_OWNER,
            audience_id=project.audience_id,
        )
        revision = self.creative_store.latest(
            artifact_id, SOFIA_CREATIVE_OWNER, project.audience_id,
        )
        if (
            revision is None
            or revision.project_id != project.project_id
            or (artifact_id, revision.revision) not in self.store.artifacts(project_id)
        ):
            raise PermissionError("requested artifact is not linked to this project")
        return inspect_objective_artifact(
            revision=revision,
            path=path,
            objectives=project.brief.objectives,
        )

    def project_causal_trace(
        self, project_id: str, *, now: datetime, limit: int = 48,
    ) -> dict[str, object]:
        """Trace original private LIFE intention to RUN, review and memory.

        This is an audit projection, not a retrieved synthetic narrative.
        Inaccessible or revoked evidence never contributes original text
        to the returned trace; absence is reported UNKNOWN, not erasure.
        """
        aware(now, "causal trace time")
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("causal trace limit must be 1..100")
        project = self._project(project_id)
        principal = local_sparks_principal()
        def observed_refs(refs: tuple[str, ...]) -> tuple[str, ...]:
            verified = []
            for ref in refs:
                original = self.evidence_index.lookup(ref)
                if (
                    original is None
                    or original.principal_id != principal.principal_id
                    or original.audience != project.audience_id
                    or original.observed_at > now
                ):
                    continue
                verified.append(ref)
            return tuple(verified)

        events = self.store.events(
            project.project_id,
            owner_principal_id=SOFIA_PROJECT_OWNER,
            audience_id=project.audience_id,
        )
        jobs = tuple(
            self.work_store.get(job_id)
            for job_id in self.store.jobs(project.project_id)
        )
        evaluations = self.store.evaluations(project.project_id)
        experiences = self.store.project_experiences(
            project.project_id, audience_id=project.audience_id, limit=limit,
        )
        outcomes = self.store.run_outcome_observations(
            project.project_id, limit=limit,
        )
        scoped_goals = self.goals.list_visible(principal)
        goal = next((
            item for item in scoped_goals
            if item.id == project.goal_id
            and item.origin is GoalOrigin.SELF
            and item.owner_principal_id == SOFIA_GOAL_OWNER_ID
            and item.scope_audience == project.audience_id
        ), None)
        intent = []
        for event in events[-limit:]:
            originals = observed_refs(event.evidence_refs)
            valid = len(originals) == len(event.evidence_refs)
            intent.append({
                "event_id": event.event_id,
                "from_status": (
                    None if event.from_status is None
                    else event.from_status.value
                ),
                "to_status": event.to_status.value,
                "decision": event.decision if valid else "unknown",
                "reason": event.reason if valid else None,
                "source_state": "observed" if valid else "unknown",
                "source_evidence_refs": originals,
                "occurred_at": event.occurred_at.isoformat(),
            })
        actions = []
        for job in jobs[-limit:]:
            result = job.result if isinstance(job.result, dict) else {}
            receipt_ref = result.get("evidence_ref")
            source = (
                observed_refs((receipt_ref,))
                if isinstance(receipt_ref, str) else ()
            )
            actions.append({
                "job_id": job.job_id,
                "kind": job.kind,
                "status": job.status.value,
                "source_evidence_refs": source,
                "source_state": "observed" if source else "unknown",
                "artifact_id": result.get("artifact_id") if source else None,
                "updated_at": job.updated_at.isoformat(),
                "uncertain_effect": job.status is WorkStatus.UNCERTAIN,
            })
        critiques = []
        for evaluation in evaluations[-limit:]:
            refs = observed_refs(evaluation.evidence_refs)
            valid = len(refs) == len(evaluation.evidence_refs)
            critiques.append({
                "evaluation_id": evaluation.evaluation_id,
                "artifact_id": evaluation.artifact_id if valid else None,
                "revision": evaluation.artifact_revision if valid else None,
                "technical_recorded": (
                    evaluation.technical_outcome.value if valid else "unknown"
                ),
                "personal_recorded": (
                    evaluation.personal_judgment.value if valid else "unknown"
                ),
                "source_state": (
                    "recorded_not_reverified" if valid else "unknown"
                ),
                "source_evidence_refs": refs,
                "evaluated_at": evaluation.evaluated_at.isoformat(),
            })
        episodes = []
        for experience in reversed(experiences):
            refs = observed_refs(experience.evidence_refs)
            valid = len(refs) == len(experience.evidence_refs)
            episodes.append({
                "experience_id": experience.experience_id,
                "kind": experience.kind if valid else "unknown",
                "summary": experience.summary if valid else None,
                "source_state": "observed" if valid else "unknown",
                "source_evidence_refs": refs,
                "occurred_at": experience.occurred_at.isoformat(),
                "linked_evaluation_id": (
                    experience.metadata.get("interest_learning", {}).get(
                        "evaluation_id"
                    )
                    if valid and isinstance(
                        experience.metadata.get("interest_learning"), dict
                    ) else None
                ),
            })
        return {
            "as_of": now.astimezone(timezone.utc).isoformat(),
            "project_id": project.project_id,
            "audience_id": project.audience_id,
            "goal_id": project.goal_id,
            "goal_state": "unknown" if goal is None else goal.status.value,
            "goal_revision": None if goal is None else goal.revision,
            "project_status": project.status.value,
            "intention_events": tuple(intent),
            "run_actions": tuple(actions),
            "run_event_observations": tuple({
                "run_event_id": item.run_event_id,
                "job_id": item.job_id,
                "status": item.status,
                "occurred_at": item.run_at.isoformat(),
            } for item in outcomes),
            "artifact_evaluations": tuple(critiques),
            "experiences": tuple(episodes),
            "truncated": (
                len(events) > limit
                or len(jobs) > limit
                or len(evaluations) > limit
                or len(experiences) >= limit
            ),
            "authority": "read_only_canonical_source_trace",
        }

    def portfolio_index(
        self, *, limit: int = 24,
    ) -> tuple[dict[str, object], ...]:
        """Source-derived private portfolio, with no fabricated creative history.

        This application-internal projection reads original scoped LIFE and
        CreativeStore revisions, real RUN-linked artifact references, original
        Project Forge decisions and recorded objective evaluations. It never
        publishes/shares artifacts, generates new content or writes a second
        index. The private local audience is fixed here deliberately.
        """
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("portfolio limit must be 1..100")
        projects = self.store.list_scope(
            owner_principal_id=SOFIA_PROJECT_OWNER,
            audience_id=LOCAL_AUDIENCE,
        )
        output: list[dict[str, object]] = []
        for project in projects[:limit]:
            original_events = self.store.events(
                project.project_id,
                owner_principal_id=SOFIA_PROJECT_OWNER,
                audience_id=project.audience_id,
            )
            evaluations = {
                (value.artifact_id, value.artifact_revision): value
                for value in self.store.evaluations(project.project_id)
            }
            linked = tuple(dict.fromkeys(self.store.artifacts(project.project_id)))
            artifacts: list[dict[str, object]] = []
            for artifact_id, revision_number in linked[-24:]:
                # CreativeStore is authoritative for revision identity and
                # bytes; the LIFE link alone is never proof of real content.
                history = self.creative_store.history(
                    artifact_id, SOFIA_CREATIVE_OWNER, project.audience_id,
                )
                revision = next((
                    value for value in history
                    if value.revision == revision_number
                    and value.project_id == project.project_id
                ), None)
                if revision is None:
                    artifacts.append({
                        "artifact_id": artifact_id,
                        "revision": revision_number,
                        "condition": "missing_creative_revision",
                    })
                    continue
                review = evaluations.get((artifact_id, revision_number))
                artifacts.append({
                    "artifact_id": artifact_id,
                    "revision": revision_number,
                    "kind": revision.kind.value,
                    "title": revision.title,
                    "recorded_sha256": revision.content_sha256,
                    "created_at": revision.created_at.isoformat(),
                    "source_receipt_id": revision.source_receipt_id,
                    "condition": "recorded_not_reverified",
                    "technical_outcome": (
                        None if review is None
                        else review.technical_outcome.value
                    ),
                    "personal_judgment": (
                        None if review is None
                        else review.personal_judgment.value
                    ),
                    "evaluation_id": (
                        None if review is None else review.evaluation_id
                    ),
                    "evaluation_evidence_refs": (
                        () if review is None else review.evidence_refs
                    ),
                })
            output.append({
                "project_id": project.project_id,
                "scope": project.scope.value,
                "audience_id": project.audience_id,
                "status": project.status.value,
                "name": project.name,
                "original_brief": project.description,
                "original_objectives": project.brief.objectives,
                "goal_id": project.goal_id,
                "started_at": project.created_at.isoformat(),
                "last_decision": (
                    None if not original_events else {
                        "decision": original_events[-1].decision,
                        "reason": original_events[-1].reason,
                        "evidence_refs": original_events[-1].evidence_refs,
                        "occurred_at": original_events[-1].occurred_at.isoformat(),
                    }
                ),
                "space_ids": self.store.spaces(project.project_id),
                "linked_artifact_count": len(linked),
                "artifacts": tuple(artifacts),
                "truncated_artifact_history": len(linked) > 24,
            })
        return tuple(output)

    def pending_work_review(self, *, limit: int = 32) -> tuple[dict[str, object], ...]:
        """Project existing RUN outcomes without asserting goal success.

        A finished creative job is *not* independently validated work.
        Missing receipts, failure and uncertain outcomes remain review items.
        This method reads canonical stores only and cannot schedule, promote
        memories, grant permissions or alter project statuses.
        """
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("review limit must be between 1 and 100")
        projects = self.store.list_scope(
            owner_principal_id=SOFIA_PROJECT_OWNER,
            audience_id=LOCAL_AUDIENCE,
            statuses=(ProjectStatus.ACTIVE, ProjectStatus.PAUSED, ProjectStatus.FAILED),
        )
        reviews: list[dict[str, object]] = []
        for project in projects:
            evaluated = {
                (item.artifact_id, item.artifact_revision): item
                for item in self.store.evaluations(project.project_id)
            }
            milestones = self.store.milestones(project.project_id)
            for job_id in self.store.jobs(project.project_id):
                job = self.work_store.get(job_id)
                outcome = job.result if isinstance(job.result, dict) else {}
                artifact_id = outcome.get("artifact_id")
                revision = outcome.get("revision")
                verified_link = (
                    isinstance(artifact_id, str)
                    and type(revision) is int
                    and (artifact_id, revision) in self.store.artifacts(project.project_id)
                )
                if job.status is WorkStatus.COMPLETED:
                    if len(set(project.brief.objectives)) != len(project.brief.objectives):
                        disposition = "ambiguous_original_objectives_require_review"
                        reviews.append({
                            "project_id": project.project_id,
                            "job_id": job.job_id,
                            "status": job.status.value,
                            "disposition": disposition,
                            "artifact_id": artifact_id if verified_link else None,
                            "revision": revision if verified_link else None,
                            "evidence_ref": None,
                        })
                        if len(reviews) >= limit:
                            return tuple(reviews)
                        continue
                    critique = (
                        evaluated.get((artifact_id, revision))
                        if verified_link else None
                    )
                    if critique is None:
                        disposition = (
                            "needs_independent_artifact_review"
                            if verified_link else "missing_or_unlinked_artifact_receipt"
                        )
                    elif any(
                        milestone.status in {
                            MilestoneStatus.PLANNED, MilestoneStatus.ACTIVE,
                        }
                        and critique.objective_results.get(milestone.title) is True
                        for milestone in milestones
                    ):
                        disposition = "needs_verified_milestone_settlement"
                    elif critique.technical_outcome is TechnicalOutcome.INCONCLUSIVE:
                        disposition = "needs_independent_objective_review"
                    elif critique.personal_judgment is not PersonalJudgment.UNKNOWN:
                        disposition = "needs_personal_critique_review"
                    elif critique.technical_outcome is TechnicalOutcome.INVALID:
                        disposition = "needs_revision_or_pause"
                    else:
                        continue  # independently reviewed, no outstanding decision
                elif job.status is WorkStatus.UNCERTAIN:
                    disposition = "uncertain_no_automatic_retry"
                elif job.status is WorkStatus.WAITING_APPROVAL:
                    # A pending SAFE decision is not running or completed.
                    # It needs visibility and operator authority, not a
                    # speculative retry or another optional LIFE project.
                    disposition = "awaiting_separate_operator_approval"
                elif job.status in {WorkStatus.FAILED, WorkStatus.CANCELLED, WorkStatus.BLOCKED}:
                    disposition = "needs_failure_or_blocked_review"
                else:
                    continue  # queued/running are not settled results
                reviews.append({
                    "project_id": project.project_id,
                    "job_id": job.job_id,
                    "status": job.status.value,
                    "disposition": disposition,
                    "artifact_id": artifact_id if verified_link else None,
                    "revision": revision if verified_link else None,
                    "evidence_ref": (
                        outcome.get("evidence_ref")
                        if isinstance(outcome.get("evidence_ref"), str)
                        else None
                    ),
                })
                if len(reviews) >= limit:
                    return tuple(reviews)
        return tuple(reviews)

    def goal_dependency_view(
        self, *, now: datetime, limit: int = 32,
    ) -> tuple[dict[str, object], ...]:
        """Read-only LIFE/GOALS prerequisite, resource and approval view.

        Source only: canonical project brief and milestone rows, original
        GOALS status/revision and linked RUN jobs. A missing scoped goal is
        UNKNOWN, not evidence that one does not exist. Priority is the
        original bounded project value, not invented model motivation.
        """
        aware(now, "goal dependency inspection time")
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("goal dependency limit must be 1..100")
        visible = {
            goal.id: goal
            for goal in self.goals.list_visible(local_sparks_principal())
            if goal.origin is GoalOrigin.SELF
            and goal.owner_principal_id == SOFIA_GOAL_OWNER_ID
            and goal.scope_audience == LOCAL_AUDIENCE
        }
        projects = self.store.list_scope(
            owner_principal_id=SOFIA_PROJECT_OWNER,
            audience_id=LOCAL_AUDIENCE,
        )
        halted = self.operator_stop.current().active
        view: list[dict[str, object]] = []
        for project in projects[:limit]:
            goal = visible.get(project.goal_id)
            milestone_rows = self.store.milestones(project.project_id)
            open_milestones = tuple(
                {
                    "milestone_id": m.milestone_id,
                    "objective": m.title,
                    "status": m.status.value,
                    "source_evidence_refs": m.evidence_refs,
                }
                for m in milestone_rows
                if m.status not in {
                    MilestoneStatus.COMPLETED, MilestoneStatus.SKIPPED,
                }
            )
            jobs = tuple(
                self.work_store.get(job_id)
                for job_id in self.store.jobs(project.project_id)
            )
            latest = jobs[-1] if jobs else None
            unsettled = tuple(
                job.job_id for job in jobs
                if job.status in {
                    WorkStatus.QUEUED, WorkStatus.RUNNING,
                    WorkStatus.WAITING_APPROVAL, WorkStatus.BLOCKED,
                    WorkStatus.UNCERTAIN,
                }
            )
            usage = self.store.usage(
                project.project_id, now.astimezone(timezone.utc).date(),
            )
            budget = project.brief.resource_budget
            constraints: list[str] = []
            if halted:
                constraints.append("operator_stop")
            if project.status is not ProjectStatus.ACTIVE:
                constraints.append("project_not_active")
            if goal is None:
                constraints.append("canonical_goal_unobserved")
            elif goal.status is not GoalStatus.ACTIVE:
                constraints.append("goal_not_active")
            if float(usage["wall_seconds"]) >= budget.daily_seconds:
                constraints.append("daily_time_budget_exhausted")
            if int(usage["storage_bytes"]) >= budget.storage_bytes:
                constraints.append("daily_storage_budget_exhausted")
            if latest is not None:
                if latest.status is WorkStatus.UNCERTAIN:
                    constraints.append("run_effect_uncertain")
                elif latest.status is WorkStatus.WAITING_APPROVAL:
                    constraints.append("operator_approval_pending")
                elif latest.status is WorkStatus.BLOCKED:
                    constraints.append("run_blocked")
                elif latest.status in {WorkStatus.QUEUED, WorkStatus.RUNNING}:
                    constraints.append("existing_run_job")
                elif latest.status in {WorkStatus.FAILED, WorkStatus.CANCELLED}:
                    constraints.append("run_failure_review")
            # A source-derived next-action suggestion is NOT authorization,
            # execution, private motivation or evidence of objective success.
            # It gives the operator a precise blocker/verification route
            # without asking the model to reverse-engineer RUN events.
            reviews = tuple(self.store.evaluations(project.project_id))
            latest_review = reviews[-1] if reviews else None
            if halted:
                next_action, next_reason = (
                    "rest", "Original SAFE operator stop is active."
                )
            elif latest is not None and latest.status is WorkStatus.UNCERTAIN:
                next_action, next_reason = (
                    "ask", "Original RUN outcome is uncertain; no automatic retry."
                )
            elif latest is not None and latest.status is WorkStatus.WAITING_APPROVAL:
                next_action, next_reason = (
                    "ask", "RUN requires an independent operator approval."
                )
            elif latest is not None and latest.status in {
                WorkStatus.BLOCKED, WorkStatus.FAILED, WorkStatus.CANCELLED,
            }:
                next_action, next_reason = (
                    "ask", "Original RUN outcome needs an operator review."
                )
            elif goal is None:
                next_action, next_reason = (
                    "ask", "Canonical scoped GOALS state cannot be observed."
                )
            elif goal.status is not GoalStatus.ACTIVE:
                next_action, next_reason = (
                    "rest", "The original goal does not authorize new work."
                )
            elif project.status is not ProjectStatus.ACTIVE:
                next_action, next_reason = (
                    "rest", "The personal project is not active."
                )
            elif latest is not None and latest.status in {
                WorkStatus.QUEUED, WorkStatus.RUNNING,
            }:
                next_action, next_reason = (
                    "wait", "An original RUN job is already in flight."
                )
            elif latest is not None and latest.status is WorkStatus.COMPLETED:
                source_result = (
                    latest.result if isinstance(latest.result, dict) else {}
                )
                reviewed = next((
                    evaluation for evaluation in reversed(reviews)
                    if evaluation.artifact_id == source_result.get("artifact_id")
                    and evaluation.artifact_revision == source_result.get("revision")
                ), None)
                if reviewed is None:
                    next_action, next_reason = (
                        "verify", "Completed RUN receipt still needs independent artifact review."
                    )
                elif reviewed.technical_outcome is TechnicalOutcome.INCONCLUSIVE:
                    next_action, next_reason = (
                        "ask", "Original objective remains unknown to independent validators."
                    )
                elif reviewed.technical_outcome is TechnicalOutcome.INVALID:
                    next_action, next_reason = (
                        "review", "Original artifact did not meet the checked objectives."
                    )
                elif reviewed.personal_judgment is not PersonalJudgment.UNKNOWN:
                    next_action, next_reason = (
                        "review", "A recorded personal judgment needs a distinct project decision."
                    )
                elif open_milestones:
                    next_action, next_reason = (
                        "verify", "Milestones require source-backed settlement."
                    )
                else:
                    next_action, next_reason = (
                        "review", "Independent completion decision still needs reconciliation."
                    )
            elif any(name.startswith("daily_") for name in constraints):
                next_action, next_reason = (
                    "rest", "Original project daily budget is exhausted."
                )
            elif not jobs:
                next_action, next_reason = (
                    "explore", "Eligible original project has no scheduled artifact."
                )
            else:
                next_action, next_reason = (
                    "review", "Source history needs a guarded new-work decision."
                )
            # This is a deterministic review projection, not a second
            # clock, action queue or persisted state machine. The key
            # changes only when original source decisions change.
            reviewed = (
                next((
                    evaluation for evaluation in reversed(reviews)
                    if latest is not None
                    and isinstance(latest.result, dict)
                    and evaluation.artifact_id == latest.result.get("artifact_id")
                    and evaluation.artifact_revision == latest.result.get("revision")
                ), None)
            )
            awaiting_verification = (
                latest is not None
                and latest.status is WorkStatus.COMPLETED
                and reviewed is None
            )
            due_source = (
                latest.updated_at if latest is not None
                and next_action in {"verify", "review", "ask"}
                else project.updated_at
                if next_action == "explore" else None
            )
            next_milestone = (
                open_milestones[0] if open_milestones else None
            )
            due_key_inputs = {
                "project_id": project.project_id,
                "project_revision": project.revision,
                "goal_revision": None if goal is None else goal.revision,
                "run_job_id": None if latest is None else latest.job_id,
                "run_status": None if latest is None else latest.status.value,
                "evaluation_id": None if reviewed is None else reviewed.evaluation_id,
                "next_milestone_id": (
                    None if next_milestone is None
                    else next_milestone["milestone_id"]
                ),
                "next_milestone_status": (
                    None if next_milestone is None else next_milestone["status"]
                ),
                "next_action": next_action,
            }
            review_decision_key = "life-review:" + sha256(
                json.dumps(
                    due_key_inputs, sort_keys=True, separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()[:32]
            view.append({
                "project_id": project.project_id,
                "project_revision": project.revision,
                "project_status": project.status.value,
                "goal_id": project.goal_id,
                "goal_revision": None if goal is None else goal.revision,
                "goal_status": "unknown" if goal is None else goal.status.value,
                "parent_goal_id": None if goal is None else goal.parent_goal_id,
                "priority": project.priority,
                "resource_budget": {
                    "daily_seconds": budget.daily_seconds,
                    "storage_bytes": budget.storage_bytes,
                    "concurrent_jobs": budget.concurrent_jobs,
                },
                "usage_today": {
                    "wall_seconds": float(usage["wall_seconds"]),
                    "storage_bytes": int(usage["storage_bytes"]),
                },
                "unresolved_milestones": open_milestones,
                "original_evidence_refs": (
                    () if goal is None else goal.evidence_refs
                ),
                "needed_objective_evidence": tuple(
                    row["objective"] for row in open_milestones
                ),
                "latest_run_job_id": None if latest is None else latest.job_id,
                "latest_run_status": None if latest is None else latest.status.value,
                "unsettled_job_ids": unsettled,
                "blockers": tuple(constraints),
                "next_action_candidate": next_action,
                "next_action_reason": next_reason,
                "next_action_source_job_id": None if latest is None else latest.job_id,
                "next_action_review_id": (
                    None if latest_review is None else latest_review.evaluation_id
                ),
                "review_decision_key": review_decision_key,
                "review_due_at": (
                    None if due_source is None else due_source.isoformat()
                ),
                "awaiting_verification": awaiting_verification,
                "next_milestone_id": (
                    None if next_milestone is None
                    else next_milestone["milestone_id"]
                ),
                # The milestone's original updated_at is when it became
                # actionable, not an invented deadline. No automatic
                # scheduling is authorized by this view.
                "next_milestone_actionable_since": (
                    None if next_milestone is None
                    else next(
                        m.updated_at.isoformat()
                        for m in milestone_rows
                        if m.milestone_id == next_milestone["milestone_id"]
                    )
                ),
                # New-work eligibility is narrower than a lack of SAFE
                # blockers: COMPLETED but unverified work still needs
                # verification, not another RUN creative submission.
                "eligible_for_new_work": (
                    not constraints and next_action == "explore"
                ),
                "source": "canonical_life_goals_run_projection",
            })
        return tuple(view)

    def operator_diagnostics(
        self, *, now: datetime, limit: int = 32,
    ) -> dict[str, object]:
        """Read-only, canonical source-derived LIFE status for an operator.

        Never make diagnosis an independent scheduler status. Project statuses
        come from LifeStore, work transitions from DurableWorkStore, and
        uncertain/blocked events retain their original RUN identifiers.
        """
        aware(now, "diagnostic timestamp")
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("diagnostic limit must be 1..100")
        projects = self.store.list_scope(
            owner_principal_id=SOFIA_PROJECT_OWNER,
            audience_id=LOCAL_AUDIENCE,
        )
        quiet = self.store.quiet_until(now=now)
        recent = self.store.selections(limit=1)
        last_selection = recent[0] if recent else None
        records: list[dict[str, object]] = []
        for project in projects[:limit]:
            jobs = tuple(
                self.work_store.get(job_id)
                for job_id in self.store.jobs(project.project_id)
            )
            blocked = next((job for job in jobs if job.status is WorkStatus.BLOCKED), None)
            uncertain = next((job for job in jobs if job.status is WorkStatus.UNCERTAIN), None)
            approval = next(
                (job for job in jobs if job.status is WorkStatus.WAITING_APPROVAL),
                None,
            )
            running = next(
                (job for job in jobs if job.status in {
                    WorkStatus.RUNNING, WorkStatus.QUEUED,
                }), None,
            )
            failed = next(
                (job for job in jobs if job.status in {
                    WorkStatus.FAILED, WorkStatus.CANCELLED,
                }), None,
            )
            reviewed = self.store.evaluations(project.project_id)
            if project.status in {
                ProjectStatus.COMPLETED, ProjectStatus.ARCHIVED,
                ProjectStatus.ABANDONED, ProjectStatus.REJECTED,
                ProjectStatus.SUPERSEDED,
            }:
                condition, origin = "finished", "life_project.status"
            elif uncertain is not None:
                # A protective LIFE pause must never hide an unresolved
                # potentially executed remote RUN effect from the operator.
                condition, origin = "uncertain", "autonomous_work_job.status"
            elif project.status is ProjectStatus.PAUSED:
                condition, origin = "paused", "life_project.status"
            elif project.status is ProjectStatus.FAILED:
                condition, origin = "failed", "life_project.status"
            elif blocked is not None:
                condition, origin = "blocked", "autonomous_work_job.status"
            elif approval is not None:
                condition, origin = "awaiting_permission", "autonomous_work_job.status"
            elif failed is not None:
                condition, origin = "reviewing_failure", "autonomous_work_job.status"
            elif running is not None:
                condition, origin = "working", "autonomous_work_job.status"
            elif jobs or reviewed:
                condition, origin = "reviewing", "life_project_job"
            elif project.status is ProjectStatus.ACTIVE:
                condition, origin = "eligible", "life_project.status"
            else:
                condition, origin = "awaiting_activation", "life_project.status"
            cause = next((
                item for item in (uncertain, blocked, approval, failed, running)
                if item is not None
            ), None)
            observations = self.store.run_outcome_observations(
                project.project_id, limit=1,
            )
            last_outcome = observations[-1] if observations else None
            records.append({
                "project_id": project.project_id,
                "project_status": project.status.value,
                "condition": condition,
                "source": origin,
                "source_job_id": None if cause is None else cause.job_id,
                "source_job_status": None if cause is None else cause.status.value,
                "source_job_reason": None if cause is None else cause.reason,
                "last_run_event_id": (
                    None if last_outcome is None else last_outcome.run_event_id
                ),
                "last_run_status": (
                    None if last_outcome is None else last_outcome.status
                ),
                "artifact_count": len(self.store.artifacts(project.project_id)),
                "evaluations_count": len(reviewed),
                "has_verified_completion": (
                    project.status in {ProjectStatus.COMPLETED, ProjectStatus.ARCHIVED}
                    and self._current_verified_objective_completion(project, now=now)
                ),
            })
        if quiet is not None:
            overall, reason = "idle_by_choice", quiet[1]
            source = "life_quiet_choice"
        elif not projects:
            overall, reason = "idle_no_project", "No projects in the canonical LIFE scope."
            source = "life_project"
        elif any(item["condition"] == "eligible" for item in records):
            overall, reason = "ready", "An active project is eligible for consideration."
            source = "life_project.status"
        elif any(item["condition"] == "working" for item in records):
            overall, reason = "working", "A RUN job is queued or executing."
            source = "autonomous_work_job.status"
        elif any(item["condition"] == "uncertain" for item in records):
            overall, reason = "uncertain", "RUN outcome may include unconfirmed effects."
            source = "autonomous_work_job.status"
        elif any(item["condition"] == "awaiting_permission" for item in records):
            overall, reason = "awaiting_permission", "A RUN job needs separate approval."
            source = "autonomous_work_job.status"
        elif any(item["condition"] in {"blocked", "reviewing_failure", "reviewing"} for item in records):
            overall, reason = "reviewing", "A prior project or RUN outcome requires review."
            source = "life_project_job"
        else:
            overall, reason = "idle", "No currently eligible LIFE activity."
            source = "life_project.status"
        return {
            "as_of": now.astimezone(timezone.utc).isoformat(),
            "condition": overall,
            "reason": reason,
            "source": source,
            "last_selection_id": None if last_selection is None else last_selection.selection_id,
            "last_selection_reason": None if last_selection is None else last_selection.reason,
            "quiet_until": None if quiet is None else quiet[0].isoformat(),
            "projects": tuple(records),
            "goal_dependencies": self.goal_dependency_view(now=now, limit=limit),
            "truncated": len(projects) > limit,
        }

    def consider_new_project(
        self, *, generate, now: datetime, busy: bool,
        resource_pressure: float,
    ) -> LifeProject | None:
        """Run at most one daily LLM suggestion through deterministic host policy."""
        # Production background_runtime invokes this independently of tick().
        # Refuse before waking the cognitive provider or reserving a draft.
        if self.operator_stop.current().active:
            return None
        if (
            self.operator_stop.current().active
            or busy or resource_pressure >= 0.65
            or self.store.quiet_until(now=now) is not None
        ):
            return None
        live = self.store.list_scope(
            owner_principal_id=SOFIA_PROJECT_OWNER, audience_id=LOCAL_AUDIENCE,
            statuses=(
                ProjectStatus.IDEA, ProjectStatus.PROPOSED,
                ProjectStatus.ACTIVE, ProjectStatus.PAUSED,
            ),
        )
        if live:
            return None
        # An unchanged interest must not repeatedly spawn replacement
        # projects immediately after a reviewed abandonment or failure.
        # This is a derived cooldown from canonical LIFE project/interest
        # revisions, not a separate persistent motivation state. New
        # grounded interest evidence after the decision lifts the cooldown.
        history = self.store.list_scope(
            owner_principal_id=SOFIA_PROJECT_OWNER,
            audience_id=LOCAL_AUDIENCE,
        )
        def cooling_down(interest: InterestRecord) -> bool:
            return any(
                project.originating_interest == interest.interest_id
                and project.status in {
                    ProjectStatus.REJECTED, ProjectStatus.ABANDONED,
                    ProjectStatus.FAILED,
                }
                and interest.recorded_at <= project.updated_at
                and timedelta(0) <= now - project.updated_at < timedelta(days=7)
                for project in history
            )
        interests = tuple(
            item for item in self.store.active_interests(audience_id=LOCAL_AUDIENCE)
            if item.confidence >= 0.6 and item.strength >= 0.5
            and not cooling_down(item)
        )[:8]
        if not interests:
            return None
        slot = self.store.claim_idea_attempt(now=now)
        if slot is None:
            return None
        experiences = self.store.experiences(
            audience_id=LOCAL_AUDIENCE, include_private=True, limit=8,
        )
        try:
            suggestion = ProjectIdeaAgent(generate).suggest(
                interests=interests,
                experience_summaries=tuple(item.summary for item in experiences),
                now=now,
            )
            # A model can take time. Operator stop may have been asserted
            # while the unprivileged suggestion was being produced.
            if self.operator_stop.current().active:
                self.store.finish_idea_attempt(
                    slot, status="declined",
                    reason="operator_stop_after_model_suggestion",
                    suggestion_id=suggestion.suggestion_id,
                )
                return None
            # Project origin must be the one exact selected eligible
            # interest, not whichever interest happens to sort first.
            # Evidence from unrelated interests never launders into a
            # new LIFE project or its future preference-learning chain.
            selected_interest = next(
                (item for item in interests
                 if item.interest_id == suggestion.originating_interest_id),
                None,
            )
            if selected_interest is None:
                raise ValueError("suggestion has no eligible original interest")
            evidence_refs = selected_interest.evidence_refs[:32]
            deterministic_accept = (
                suggestion.pursue
                and suggestion.confidence >= 0.65
                and suggestion.curiosity >= 0.65
                and suggestion.artifact_kind in self._native_probe.supported_kinds
                # An installed serializer is not an autonomous author.
                # LIFE v1 has independently reviewed tool-free drafting for
                # text/story only. Other native adapters still serialize
                # starter specimens and must not be presented as completed
                # self-directed creative work.
                and suggestion.artifact_kind in {ArtifactKind.TEXT, ArtifactKind.STORY}
            )
            if not deterministic_accept:
                self.choose_inactivity(
                    reason=(
                        "No proposed project passed Sofía's bounded interest and confidence policy: "
                        + suggestion.reason
                    ),
                    until=now + timedelta(hours=6), now=now,
                )
                self.store.finish_idea_attempt(
                    slot, status="declined", reason=suggestion.reason,
                    suggestion_id=suggestion.suggestion_id,
                )
                return None
            idea = ProjectIdea(
                suggestion.suggestion_id.replace("idea-suggestion:", "idea:"),
                suggestion.name, suggestion.description,
                selected_interest.interest_id, suggestion.objectives,
                suggestion.optional_success_criteria,
                suggestion.artifact_kind.value, evidence_refs,
                suggestion.confidence, suggestion.curiosity, now,
            )
            project = self.invent_project(idea)
            project = self.propose_project(
                project.project_id,
                reason=(
                    "The model suggested an optional project; deterministic host validation "
                    "confirmed a verified tool, evidence, and bounded feasibility."
                ), evidence_refs=evidence_refs, now=now,
            )
            project = self.activate_project(
                project.project_id, reason=suggestion.reason,
                evidence_refs=evidence_refs, now=now,
                resource_pressure=resource_pressure,
            )
            self.store.finish_idea_attempt(
                slot, status="accepted", reason=suggestion.reason,
                suggestion_id=suggestion.suggestion_id,
                project_id=project.project_id,
            )
            return project
        except Exception as exc:
            self.store.finish_idea_attempt(
                slot, status="failed", reason=type(exc).__name__,
            )
            raise

    def schedule_artifact(
        self, project_id: str, *, artifact_kind: ArtifactKind,
        title: str, specification: Mapping[str, object], evidence_ref: str,
        now: datetime, artifact_id: str | None = None,
    ) -> WorkJob:
        if self.operator_stop.current().active:
            raise PermissionError("operator stop blocks optional LIFE scheduling")
        project = self._project(project_id)
        if project.status is not ProjectStatus.ACTIVE or project.goal_id is None:
            raise ValueError("only an active goal-backed project can schedule artifacts")
        self._verify_evidence((evidence_ref,))
        if artifact_kind not in self._native_probe.supported_kinds:
            raise RuntimeError("artifact kind lacks a verified native adapter")
        if "creative.artifact.create" not in project.brief.permission_requirements:
            raise PermissionError("project brief did not declare creative execution")
        artifact_key = artifact_id or f"artifact:{uuid4().hex}"
        parameters = {
            "request_id": f"request:{uuid4().hex}",
            "project_id": project.project_id,
            "artifact_id": artifact_key,
            "kind": artifact_kind.value,
            "title": text(title, "artifact title", 500),
            "owner_principal_id": SOFIA_CREATIVE_OWNER,
            "author_principal_id": SOFIA_CREATIVE_AUTHOR,
            "audience_id": project.audience_id,
            "license_id": "private",
            "specification": dict(specification),
            "evidence_ref": evidence_ref,
        }
        encoded_specification = json.dumps(
            parameters["specification"], sort_keys=True,
            separators=(",", ":"), ensure_ascii=False,
        )
        if len(encoded_specification.encode("utf-8")) > 64_000:
            raise ValueError("creative specification exceeds bounded RUN payload")
        usage = self.store.usage(
            project.project_id, now.astimezone(timezone.utc).date(),
        )
        budget = project.brief.resource_budget
        if int(usage["storage_bytes"]) >= budget.storage_bytes:
            raise RuntimeError("project storage budget is exhausted")
        remaining_seconds = budget.daily_seconds - float(usage["wall_seconds"])
        if remaining_seconds < 1:
            raise RuntimeError("project daily work-time budget is exhausted")
        # The RUN deadline is a bounded admission deadline, not a substitute
        # for OS isolation or an enforced process CPU/memory quota.
        admitted_seconds = min(1800, remaining_seconds)
        goal = next(item for item in self.goals.list_visible(local_sparks_principal()) if item.id == project.goal_id)
        action = self.goals.propose_action(
            goal=goal, capability_name="creative.artifact.create",
            parameters=parameters, requested_scope=project.project_id,
            rationale=f"Create a bounded artifact for optional project {project.name}.",
        )
        fingerprint = sha256(
            repr((project.project_id, artifact_key, artifact_kind.value, dict(specification))).encode()
        ).hexdigest()[:48]
        job = self.manager.submit(
            kind="life-create-artifact", fingerprint=f"life-artifact:{fingerprint}",
            payload={
                "project_id": project.project_id,
                "goal_id": goal.id,
                "capability_name": action.proposal.capability_name,
                "parameters": action.proposal.parameters,
                "requested_scope": action.proposal.requested_scope,
                "rationale": action.proposal.rationale,
            },
            priority=max(1, min(100, round(project.priority * 100))),
            resource_cost=max(1, min(100, project.brief.resource_budget.cpu_percent)),
            risk="isolated_change",
            completion_condition="A real managed artifact is created and hash-verified.",
            now=now, deadline=now + timedelta(seconds=admitted_seconds),
            after_enqueue=lambda db, candidate: self.store.provision_artifact_job(
                db, project_id=project.project_id, job_id=candidate.job_id,
                request_id=str(parameters["request_id"]), artifact_id=artifact_key,
                request_digest=creative_request_digest(parameters), now=now,
            ),
        )
        return job

    def _create_artifact(self, job: WorkJob, cancel) -> WorkResult:
        if self.operator_stop.current().active:
            self.store.cancel_artifact_authorization(str(job.payload["parameters"]["request_id"]))
            return WorkResult(WorkStatus.BLOCKED, {}, "operator_stop_blocks_optional_creative_execution")
        if cancel.is_set():
            return WorkResult(WorkStatus.FAILED, {}, "cancelled_before_creative_execution")
        started = datetime.now(timezone.utc)
        project = self._project(str(job.payload["project_id"]))
        # RUN's queued status is not perpetual permission. Before any
        # consequential capability execution, re-read the canonical LIFE
        # project and scoped GOALS state, then let the normal SAFE gateway
        # and one-use claim enforce authority again at execution.
        goal = next((
            value for value in self.goals.list_visible(local_sparks_principal())
            if value.id == project.goal_id
        ), None)
        if (
            project.status is not ProjectStatus.ACTIVE
            or goal is None or goal.status is not GoalStatus.ACTIVE
            or goal.owner_principal_id != SOFIA_GOAL_OWNER_ID
            or goal.scope_audience != project.audience_id
        ):
            self.store.cancel_artifact_authorization(
                str(job.payload["parameters"]["request_id"]),
            )
            return WorkResult(
                WorkStatus.BLOCKED, {"project_id": project.project_id},
                "life_project_or_goal_no_longer_active_no_execution",
            )
        proposal = CapabilityProposal(
            str(job.payload["capability_name"]),
            dict(job.payload["parameters"]),
            str(job.payload["rationale"]),
            job.payload["requested_scope"],
        )
        result = self.gateway.execute(proposal)
        if result.kind is not CapabilityResultKind.SUCCESS:
            self.store.cancel_artifact_authorization(
                str(job.payload["parameters"]["request_id"]),
            )
            evidence = self.evidence.record(
                kind="operation_receipt", observed_at=datetime.now(timezone.utc),
                source="life:creative-capability", successful=False,
                goal_id=project.goal_id, action_id=job.job_id,
                assertion="creative artifact generation failed or was unavailable",
                payload={"result_kind": result.kind.value, "error": result.error},
                principal_id=local_sparks_principal().principal_id,
                audience=LOCAL_AUDIENCE,
            )
            self._experience(
                project=project, kind="experiment_unavailable",
                summary=f"Artifact work for {project.name} did not complete: {result.kind.value}.",
                evidence_refs=(evidence.evidence_ref,), now=datetime.now(timezone.utc),
                metadata={"job_id": job.job_id},
            )
            status = WorkStatus.BLOCKED if result.kind in {
                CapabilityResultKind.UNAUTHORIZED, CapabilityResultKind.UNAVAILABLE,
            } else WorkStatus.FAILED
            return WorkResult(status, {"capability_result": result.kind.value}, result.error or result.kind.value)
        output = dict(result.evidence)
        parameters = dict(job.payload["parameters"])
        # An executor may have carried out its external effect even if its
        # returned evidence is incomplete. Do not retry or invent success.
        receipt_ok = (
            isinstance(output.get("artifact_id"), str)
            and output.get("artifact_id") == parameters.get("artifact_id")
            and output.get("project_id") == project.project_id
            and type(output.get("revision")) is int
            and output["revision"] >= 1
            and type(output.get("byte_size")) is int
            and output["byte_size"] > 0
            and isinstance(output.get("sha256"), str)
            and len(output["sha256"]) == 64
            and all(char in "0123456789abcdef" for char in output["sha256"])
        )
        if receipt_ok:
            candidate = self.creative_store.latest(
                output["artifact_id"], SOFIA_CREATIVE_OWNER, project.audience_id,
            )
            receipt_ok = (
                candidate is not None
                and candidate.project_id == project.project_id
                and candidate.revision == output["revision"]
                and candidate.content_sha256 == output["sha256"]
                and candidate.byte_size == output["byte_size"]
            )
        if not receipt_ok:
            finished = datetime.now(timezone.utc)
            evidence = self.evidence.record(
                kind="operation_receipt", observed_at=finished,
                source="life:creative-capability", successful=False,
                goal_id=project.goal_id, action_id=job.job_id,
                assertion="creative execution reported success without a valid linked artifact receipt",
                payload={"result_kind": "unverified_success_receipt"},
                principal_id=local_sparks_principal().principal_id,
                audience=LOCAL_AUDIENCE,
            )
            self._experience(
                project=project, kind="experiment_uncertain",
                summary="Creative execution reported success but its artifact receipt is unverified.",
                evidence_refs=(evidence.evidence_ref,), now=finished,
                metadata={"job_id": job.job_id},
            )
            return WorkResult(
                WorkStatus.UNCERTAIN,
                {"evidence_ref": evidence.evidence_ref},
                "creative_receipt_missing_or_inconsistent_no_automatic_retry",
            )
        artifact_id, revision = output["artifact_id"], output["revision"]
        finished = datetime.now(timezone.utc)
        self.store.link_artifact(project.project_id, artifact_id, revision, now=finished)
        evidence = self.evidence.record(
            kind="operation_receipt", observed_at=finished,
            source="life:creative-capability", successful=True,
            goal_id=project.goal_id, action_id=job.job_id,
            assertion=f"created artifact {artifact_id} revision {revision}",
            payload=output, principal_id=local_sparks_principal().principal_id,
            audience=LOCAL_AUDIENCE,
        )
        duration = max(0.0, (finished - started).total_seconds())
        self.store.add_usage(
            project_id=project.project_id, usage_day=finished.date(),
            cpu_seconds=duration, gpu_seconds=0.0, wall_seconds=duration,
            storage_bytes=int(output["byte_size"]),
        )
        self._experience(
            project=project, kind="artifact_created",
            summary=f"Created and hash-verified {artifact_id} revision {revision} for {project.name}.",
            evidence_refs=(evidence.evidence_ref,), now=finished,
            metadata={"artifact_id": artifact_id, "revision": revision, "sha256": output["sha256"]},
        )
        return WorkResult(
            WorkStatus.COMPLETED,
            {**output, "evidence_ref": evidence.evidence_ref},
            "managed_artifact_created_and_verified",
        )

    def _settle_evaluation_preference(
        self, project: LifeProject, evaluation: ArtifactEvaluation,
    ) -> bool:
        """Apply a reviewed personal judgment without replaying stale taste.

        LIFE's canonical evaluation and experience are committed together,
        but the existing PreferenceRegistry owns preference revisions. A
        restart or preference write failure must not turn an already
        evaluated artifact into a permanent missing preference. Matching
        preference provenance and the original evaluation timestamp make
        replay idempotent; a newer preference always wins.
        """
        if evaluation.personal_judgment is PersonalJudgment.UNKNOWN:
            return False
        if evaluation.project_id != project.project_id:
            raise PermissionError("evaluation is outside the scoped project")
        disposition = {
            PersonalJudgment.LIKE: PreferenceDisposition.LIKE,
            PersonalJudgment.DISLIKE: PreferenceDisposition.DISLIKE,
            PersonalJudgment.MIXED: PreferenceDisposition.UNKNOWN,
            PersonalJudgment.INDIFFERENT: PreferenceDisposition.INDIFFERENT,
        }[evaluation.personal_judgment]
        scope = dict(
            subject=PreferenceSubject.SOFIA, category="creation",
            target_id=evaluation.artifact_id, context="project",
            audience_id=project.audience_id,
        )
        current = self.preferences.current(**scope)
        if current is not None:
            # Do not overwrite an independently changed preference from a
            # later review or operator correction.
            if current.recorded_at > evaluation.evaluated_at:
                return False
            history = self.preferences.history(**scope)
            if any(
                item.recorded_at == evaluation.evaluated_at
                and item.evidence_ref == evaluation.evidence_refs[0]
                and item.reason == evaluation.reason
                and item.disposition is disposition
                for item in history
            ):
                return False
            if current.recorded_at == evaluation.evaluated_at:
                # Conflicting same-time evidence cannot be arbitrated by
                # the model or by a background retry.
                return False
        self.preferences.revise(
            **scope, disposition=disposition,
            strength=(
                0.75 if evaluation.personal_judgment in {
                    PersonalJudgment.LIKE, PersonalJudgment.DISLIKE,
                } else 0.4
            ),
            confidence=project.confidence,
            reason=evaluation.reason,
            evidence_ref=evaluation.evidence_refs[0],
            expected_revision=None if current is None else current.revision,
            now=evaluation.evaluated_at,
        )
        return True

    def evaluate_artifact(
        self, project_id: str, *, artifact_id: str,
        technical_outcome: TechnicalOutcome,
        personal_judgment: PersonalJudgment,
        objective_results: Mapping[str, bool | None], reason: str,
        evidence_refs: tuple[str, ...], preserve_for_research: bool,
        now: datetime,
    ) -> ArtifactEvaluation:
        project = self._project(project_id)
        self._verify_evidence(evidence_refs)
        if len(set(project.brief.objectives)) != len(project.brief.objectives):
            raise ValueError("legacy original objectives are ambiguous; require reviewed correction")
        path, _media = self.creative_explorer.verified_preview(
            artifact_id, owner_principal_id=SOFIA_CREATIVE_OWNER,
            audience_id=project.audience_id,
        )
        revision = self.creative_store.latest(
            artifact_id, SOFIA_CREATIVE_OWNER, project.audience_id,
        )
        if revision is None or not path.is_file():
            raise RuntimeError("artifact is unavailable for grounded critique")
        if (
            revision.project_id != project_id
            or (artifact_id, revision.revision) not in self.store.artifacts(project_id)
        ):
            raise PermissionError("artifact is not linked to this project")
        # Every technical assertion must match the independently inspected
        # ORIGINAL objectives, not merely claims of success. In particular
        # a generator or a reviewer cannot invent a FAIL to trigger more RUN
        # work, nor claim INCONCLUSIVE when a typed predicate already failed.
        from .validation import inspect_objective_artifact, ObjectiveDisposition
        objective_report = inspect_objective_artifact(
            revision=revision, path=path, objectives=project.brief.objectives,
        )
        if (
            objective_report.revision != revision.revision
            or objective_report.integrity is not ObjectiveDisposition.PASS
        ):
            raise ValueError("artifact byte integrity must pass before critique")
        independently_observed = {
            item.objective: (
                True if item.disposition is ObjectiveDisposition.PASS
                else False if item.disposition is ObjectiveDisposition.FAIL
                else None
            )
            for item in objective_report.findings
        }
        if (
            set(objective_results) != set(project.brief.objectives)
            or dict(objective_results) != independently_observed
        ):
            raise ValueError(
                "critique results must match independently checked "
                "original artifact objectives"
            )
        if objective_report.eligible_for_independent_completion:
            observed_outcome = TechnicalOutcome.VALID
        elif any(
            finding.disposition is ObjectiveDisposition.FAIL
            for finding in objective_report.findings
        ):
            observed_outcome = TechnicalOutcome.INVALID
        else:
            observed_outcome = TechnicalOutcome.INCONCLUSIVE
        if technical_outcome is not observed_outcome:
            raise ValueError(
                "technical critique conflicts with independent objective checks"
            )
        # Repeated ticks/restarts must not promote the same artifact revision
        # into multiple independent judgments or memory/preference updates.
        # A changed judgment requires an explicit reviewed correction path.
        existing = tuple(
            item for item in self.store.evaluations(project_id)
            if item.artifact_id == artifact_id
            and item.artifact_revision == revision.revision
        )
        if existing:
            prior = existing[-1]
            if (
                prior.technical_outcome is technical_outcome
                and prior.personal_judgment is personal_judgment
                and dict(prior.objective_results) == dict(objective_results)
                and prior.evidence_refs == evidence_refs
                and prior.preserve_for_research is preserve_for_research
                and prior.reason == reason
            ):
                self._settle_evaluation_preference(project, prior)
                return prior
            raise ValueError(
                "artifact revision already reviewed; conflicting correction "
                "requires a separately authorized, evidence-linked revision"
            )
        value = ArtifactEvaluation(
            f"evaluation:{uuid4()}", project_id, artifact_id, revision.revision,
            technical_outcome, personal_judgment, objective_results, reason,
            evidence_refs, preserve_for_research, now,
        )
        experience = self._experience(
            project=project, kind="artifact_evaluated",
            summary=(
                f"Evaluated {artifact_id}: technically {technical_outcome.value}; "
                f"personal judgment {personal_judgment.value}."
            ), evidence_refs=evidence_refs, now=now,
            metadata={
                "preserve_for_research": preserve_for_research,
                "interest_learning": {
                    "schema": 1,
                    "evaluation_id": value.evaluation_id,
                    "originating_interest": project.originating_interest,
                    "confidence": project.confidence,
                },
            },
            persist=False,
        )
        self.store.record_evaluation_with_experience(value, experience)
        self._settle_evaluation_preference(project, value)
        return value

    def update_milestone(
        self, project_id: str, *, milestone_id: str,
        expected_status: MilestoneStatus, next_status: MilestoneStatus,
        result: str, evidence_refs: tuple[str, ...], now: datetime,
    ) -> ProjectMilestone:
        self._project(project_id)
        self._verify_evidence(evidence_refs)
        milestone = next((
            item for item in self.store.milestones(project_id)
            if item.milestone_id == milestone_id
        ), None)
        if milestone is None or milestone.status is not expected_status:
            raise RuntimeError("milestone changed concurrently or does not exist")
        allowed = {
            MilestoneStatus.PLANNED: {
                MilestoneStatus.ACTIVE, MilestoneStatus.SKIPPED,
            },
            MilestoneStatus.ACTIVE: {
                MilestoneStatus.COMPLETED, MilestoneStatus.FAILED,
                MilestoneStatus.SKIPPED,
            },
            MilestoneStatus.FAILED: {MilestoneStatus.ACTIVE, MilestoneStatus.SKIPPED},
        }
        if next_status not in allowed.get(expected_status, set()):
            raise ValueError("illegal milestone transition")
        updated = replace(
            milestone, status=next_status, evidence_refs=evidence_refs,
            result=text(result, "milestone result", 1200), updated_at=now,
        )
        self.store.update_milestone(updated, expected_status=expected_status)
        return updated

    def _confirmed_artifact_run_receipt(
        self, project: LifeProject, *, artifact_id: str, revision: int,
        evidence_ref: str, now: datetime,
    ) -> bool:
        """Require an actual completed, linked RUN operation receipt.

        Valid artifact bytes alone cannot attest to authorized execution.
        The typed GOALS evidence index verifies the original operation
        receipt independently of artifact metadata or provider text.
        """
        receipt = self.evidence_index.lookup(evidence_ref)
        if (
            receipt is None or receipt.kind != "operation_receipt"
            or receipt.source != "life:creative-capability"
            or receipt.successful is not True
            or receipt.goal_id != project.goal_id
            or receipt.principal_id != local_sparks_principal().principal_id
            or receipt.audience != project.audience_id
            or receipt.observed_at > now
        ):
            return False
        for job_id in self.store.jobs(project.project_id):
            if job_id != receipt.action_id:
                continue
            job = self.work_store.get(job_id)
            result = job.result if isinstance(job.result, dict) else {}
            return (
                job.status is WorkStatus.COMPLETED
                and result.get("artifact_id") == artifact_id
                and type(result.get("revision")) is int
                and result["revision"] == revision
                and result.get("evidence_ref") == evidence_ref
                and (artifact_id, revision) in self.store.artifacts(project.project_id)
            )
        return False

    def _settle_verified_milestones(
        self, project: LifeProject, *, artifact_id: str, revision: int,
        evaluation: ArtifactEvaluation, evidence_ref: str, job_id: str,
        now: datetime,
    ) -> int:
        """Persist actual objective progress from a completed RUN artifact.

        Milestones represent the *original* brief objectives in ordinal order.
        Neither a model's critique nor a job's COMPLETED status proves any
        objective. The content is re-read and independently checked before
        either state transition. The existing milestone CAS keeps restarts
        idempotent without introducing a parallel LIFE scheduler.
        """
        if (
            len(set(project.brief.objectives)) != len(project.brief.objectives)
            or project.scope is not ProjectScope.PERSONAL_PRIVATE
            or project.status is not ProjectStatus.ACTIVE
            or evaluation.project_id != project.project_id
            or (evaluation.artifact_id, evaluation.artifact_revision) != (artifact_id, revision)
            or evidence_ref not in evaluation.evidence_refs
        ):
            return 0
        if not self._confirmed_artifact_run_receipt(
            project, artifact_id=artifact_id, revision=revision,
            evidence_ref=evidence_ref, now=now,
        ):
            return 0
        if self.evidence_index.lookup(evidence_ref).action_id != job_id:
            return 0
        try:
            report = self.inspect_artifact_objectives(
                project.project_id, artifact_id=artifact_id,
            )
        except (LookupError, PermissionError, OSError, ValueError):
            return 0
        from .validation import ObjectiveDisposition
        if (
            report.revision != revision
            or report.integrity is not ObjectiveDisposition.PASS
        ):
            return 0
        milestones = self.store.milestones(project.project_id)
        completed = 0
        for milestone in milestones:
            if (
                milestone.ordinal >= len(project.brief.objectives)
                or milestone.title != project.brief.objectives[milestone.ordinal]
                or milestone.status not in {MilestoneStatus.PLANNED, MilestoneStatus.ACTIVE}
            ):
                continue
            objective = project.brief.objectives[milestone.ordinal]
            verified = next((
                finding for finding in report.findings
                if finding.objective == objective
                and finding.disposition is ObjectiveDisposition.PASS
            ), None)
            if verified is None or evaluation.objective_results.get(objective) is not True:
                continue
            if milestone.status is MilestoneStatus.PLANNED:
                milestone = self.update_milestone(
                    project.project_id, milestone_id=milestone.milestone_id,
                    expected_status=MilestoneStatus.PLANNED,
                    next_status=MilestoneStatus.ACTIVE,
                    result="Independent artifact objective verified; recording progress.",
                    evidence_refs=(evidence_ref,), now=now,
                )
            self.update_milestone(
                project.project_id, milestone_id=milestone.milestone_id,
                expected_status=MilestoneStatus.ACTIVE,
                next_status=MilestoneStatus.COMPLETED,
                result=(
                    f"Objective independently passed for {artifact_id} "
                    f"revision {revision} using completed RUN job {job_id}."
                ),
                evidence_refs=(evidence_ref,), now=now,
            )
            completed += 1
        return completed

    def choose_favorite(
        self, *, category: str, target_id: str, context: str,
        reason: str, evidence_ref: str, now: datetime,
    ):
        self._verify_evidence((evidence_ref,))
        current = self.preferences.current(
            subject=PreferenceSubject.SOFIA, category=category,
            target_id=target_id, context=context, audience_id=LOCAL_AUDIENCE,
        )
        return self.preferences.revise(
            subject=PreferenceSubject.SOFIA, category=category,
            target_id=target_id, context=context,
            disposition=PreferenceDisposition.FAVORITE,
            strength=0.9, confidence=0.8, reason=reason,
            evidence_ref=evidence_ref, audience_id=LOCAL_AUDIENCE,
            expected_revision=None if current is None else current.revision,
            now=now,
        )

    def propose_nickname(
        self, *, target_id: str, nickname: str, contexts: tuple[str, ...],
        evidence_ref: str, now: datetime,
    ) -> NicknameProposal:
        if self.nicknames is None:
            raise RuntimeError("nickname registry is unavailable")
        self._verify_evidence((evidence_ref,))
        return self.nicknames.propose(
            proposer_id="sofia", recipient=local_sparks_principal(),
            target_id=target_id, nickname=nickname, contexts=contexts,
            evidence_ref=evidence_ref, now=now,
        )

    def record_tradition(
        self, project_id: str, *, summary: str,
        evidence_refs: tuple[str, ...], now: datetime,
    ) -> ExperienceRecord:
        project = self._project(project_id)
        self._verify_evidence(evidence_refs)
        return self._experience(
            project=project, kind="shared_tradition", summary=summary,
            evidence_refs=evidence_refs, now=now,
            metadata={"grounded_shared_experience": True},
        )

    def create_project_space(
        self, project_id: str, *, name: str, private: bool,
        evidence_ref: str, now: datetime,
    ) -> str:
        project = self._project(project_id)
        self._verify_evidence((evidence_ref,))
        if project.status is not ProjectStatus.ACTIVE:
            raise ValueError("project spaces may be created only for active projects")
        space_id = "project-space:" + sha256(f"{project_id}:{name}".encode()).hexdigest()[:24]
        self.world.create_space(
            space_id=space_id, name=name,
            kind=SpaceKind.PRIVATE if private else SpaceKind.WORKSPACE,
            owner_principal_id=SOFIA_CREATIVE_OWNER,
            audience_id=project.audience_id, parent_space_id=None,
            actor_principal_id=SOFIA_GOAL_OWNER_ID,
            evidence_ref=evidence_ref, now=now,
        )
        self.store.link_space(project_id, space_id, now=now)
        return space_id

    def place_artifact(
        self, project_id: str, *, artifact_id: str, space_id: str,
        object_name: str, object_kind: ObjectKind, transform: Transform,
        evidence_ref: str, now: datetime,
    ) -> str:
        project = self._project(project_id)
        self._verify_evidence((evidence_ref,))
        if space_id not in self.store.spaces(project_id):
            raise PermissionError("project has not associated this space")
        if artifact_id not in {item[0] for item in self.store.artifacts(project_id)}:
            raise PermissionError("artifact is not associated with this project")
        object_id = "project-object:" + sha256(f"{project_id}:{artifact_id}:{space_id}".encode()).hexdigest()[:24]
        receipt = self.creative_world.place(
            artifact_id=artifact_id,
            artifact_owner_principal_id=SOFIA_CREATIVE_OWNER,
            world_owner_principal_id=SOFIA_CREATIVE_OWNER,
            audience_id=project.audience_id, object_id=object_id,
            object_name=object_name, object_kind=object_kind,
            space_id=space_id, transform=transform,
            actor_principal_id=SOFIA_GOAL_OWNER_ID,
            evidence_ref=evidence_ref, now=now,
        )
        return receipt.entity_id

    def share(
        self, project_id: str, *, message: str,
        evidence_refs: tuple[str, ...], now: datetime,
    ) -> bool:
        project = self._project(project_id)
        self._verify_evidence(evidence_refs)
        if self.share_callback is None:
            return False
        return bool(self.share_callback(project, text(message, "share message", 1000), evidence_refs, now))

    def _experience(
        self, *, project: LifeProject, kind: str, summary: str,
        evidence_refs: tuple[str, ...], now: datetime,
        metadata: Mapping[str, object], persist: bool = True,
    ) -> ExperienceRecord:
        value = ExperienceRecord(
            f"experience:{uuid4()}", project.project_id, kind, summary,
            evidence_refs, project.audience_id,
            project.scope is ProjectScope.PERSONAL_PRIVATE,
            now, now, metadata,
        )
        if persist:
            self.store.record_experience(value)
        return value

    def _settle_personal_project(
        self, project: LifeProject, *, now: datetime, generate,
    ) -> tuple[int, str]:
        """Review settled RUN receipts and advance optional personal work.

        One application-owned production path: real creative artifact bytes ->
        closed independent objective checker -> durable evaluation -> either
        completion, one bounded revision, or an explicit review/pause. NEVER
        infer a successful result from LLM text or a synthetic job receipt.
        Protected/user work is not automatically revised or completed.
        """
        if project.scope is not ProjectScope.PERSONAL_PRIVATE:
            return 0, "awaiting_owner_review"
        if len(set(project.brief.objectives)) != len(project.brief.objectives):
            return 0, "ambiguous_original_objectives_require_review"
        jobs = tuple(self.work_store.get(key) for key in self.store.jobs(project.project_id))
        if not jobs:
            return 0, "no_work"
        if any(job.status in {
            WorkStatus.QUEUED, WorkStatus.RUNNING,
            WorkStatus.BLOCKED, WorkStatus.WAITING_APPROVAL,
        } for job in jobs):
            return 0, "waiting_on_existing_work"
        if any(job.status in {
            WorkStatus.FAILED, WorkStatus.CANCELLED, WorkStatus.UNCERTAIN,
        } for job in jobs):
            # External effects may already have happened, or grants failed.
            # Never silently retry a protected or uncertain RUN operation.
            return 0, "failed_or_uncertain_requires_review"

        evaluations = self.store.evaluations(project.project_id)
        evaluated = {
            (evaluation.artifact_id, evaluation.artifact_revision): evaluation
            for evaluation in evaluations
        }
        latest = jobs[-1]
        outcome = latest.result if isinstance(latest.result, dict) else {}
        artifact_id, revision = outcome.get("artifact_id"), outcome.get("revision")
        evidence_ref = outcome.get("evidence_ref")
        if (
            latest.status is not WorkStatus.COMPLETED
            or not isinstance(artifact_id, str)
            or type(revision) is not int
            or (artifact_id, revision) not in self.store.artifacts(project.project_id)
            or not isinstance(evidence_ref, str)
            or not self._confirmed_artifact_run_receipt(
                project, artifact_id=artifact_id, revision=revision,
                evidence_ref=evidence_ref, now=now,
            )
        ):
            return 0, "missing_verified_artifact_receipt"

        evaluation = evaluated.get((artifact_id, revision))
        if evaluation is None:
            try:
                report = self.inspect_artifact_objectives(
                    project.project_id, artifact_id=artifact_id,
                )
            except (LookupError, PermissionError, OSError, ValueError):
                return 0, "artifact_integrity_review_required"
            if report.revision != revision:
                return 0, "artifact_revision_changed_requires_review"
            from .validation import ObjectiveDisposition
            if report.integrity is ObjectiveDisposition.FAIL:
                # Corruption is a possible external side-effect or tampering,
                # not evidence that a new creative draft should replace it.
                return 0, "artifact_integrity_review_required"
            outcomes = {
                finding.objective: (
                    True if finding.disposition is ObjectiveDisposition.PASS
                    else False if finding.disposition is ObjectiveDisposition.FAIL
                    else None
                )
                for finding in report.findings
            }
            if report.eligible_for_independent_completion:
                technical = TechnicalOutcome.VALID
            elif (
                report.integrity is ObjectiveDisposition.FAIL
                or any(f.disposition is ObjectiveDisposition.FAIL for f in report.findings)
            ):
                technical = TechnicalOutcome.INVALID
            else:
                technical = TechnicalOutcome.INCONCLUSIVE
            # The host may grade the typed artifact objective, but it has no
            # basis to invent a personal emotional preference for the model.
            evaluation = self.evaluate_artifact(
                project.project_id, artifact_id=artifact_id,
                technical_outcome=technical,
                personal_judgment=PersonalJudgment.UNKNOWN,
                objective_results=outcomes,
                reason=(
                    "Independent artifact-byte/objective critique; "
                    "subjective taste not claimed. "
                    + "; ".join(
                        f"{finding.check}: {finding.disposition.value} "
                        f"({finding.reason})"
                        for finding in report.findings[:8]
                    )[:800]
                ),
                evidence_refs=(evidence_ref,), preserve_for_research=False,
                now=now,
            )
        # Reconcile source-verified milestones before a completion or revision
        # decision. This also heals interruption after an evaluation was
        # committed but before its milestone updates were durably written.
        self._settle_verified_milestones(
            project, artifact_id=artifact_id, revision=revision,
            evaluation=evaluation, evidence_ref=evidence_ref,
            job_id=latest.job_id, now=now,
        )
        if evaluation.technical_outcome is TechnicalOutcome.VALID:
            if (
                evaluation.personal_judgment is PersonalJudgment.UNKNOWN
                and set(evaluation.objective_results) == set(project.brief.objectives)
                and all(value is True for value in evaluation.objective_results.values())
            ):
                self.complete(
                    project.project_id,
                    reason="All original typed objectives passed independent source checks.",
                    now=now,
                )
                return 0, "independently_completed"
            return 0, "reviewed_judgment_requires_decision"
        if evaluation.technical_outcome is TechnicalOutcome.INCONCLUSIVE:
            # A natural-language/unsupported original criterion cannot
            # become independently true by making more drafts. Preserve
            # the real artifact and judgment, pause optional spending, and
            # keep the original objective accessible for operator review.
            self.pause(
                project.project_id,
                reason=(
                    "The original project objective is not independently "
                    "verifiable; pausing rather than manufacturing success "
                    "or starting speculative revisions."
                ),
                evidence_refs=(evidence_ref,), now=now,
            )
            return 0, "needs_independent_objective_review"
        if evaluation.personal_judgment is not PersonalJudgment.UNKNOWN:
            return 0, "personal_judgment_requires_decision"
        if set(evaluation.objective_results) != set(project.brief.objectives) or any(
            value is None for value in evaluation.objective_results.values()
        ):
            return 0, "needs_independent_objective_review"

        # Bounded autonomous revisions ONLY for failed, independently graded
        # TEXT/STORY artifacts, not inconclusive subjective work.
        if len(self.store.artifacts(project.project_id)) >= 3:
            self.pause(
                project.project_id,
                reason="Three independently checked attempts exhausted; choosing to pause.",
                evidence_refs=(evidence_ref,), now=now,
            )
            return 0, "revision_budget_exhausted_paused"
        kind_tool = next((
            tool for tool in project.brief.required_tools
            if tool.startswith("artifact-kind:")
        ), "artifact-kind:text")
        kind = ArtifactKind(kind_tool.split(":")[-1])
        if kind not in {ArtifactKind.TEXT, ArtifactKind.STORY} or generate is None:
            return 0, "revision_requires_native_drafting"
        if not self.store.claim_daily_draft_attempt(project.project_id, now=now):
            return 0, "deferred_daily_draft_limit"
        failed = tuple(
            key for key, result in evaluation.objective_results.items()
            if result is False
        )
        # The revision prompt receives independent checker findings only.
        # Generator self-critique is never a pass/fail oracle.
        checked = self.inspect_artifact_objectives(
            project.project_id, artifact_id=artifact_id,
        )
        if checked.revision != revision:
            return 0, "artifact_revision_changed_requires_review"
        feedback = (
            "The prior artifact failed independently inspected objectives: "
            + "; ".join(
                f"{item.objective[:100]} ({item.check}: {item.reason})"
                for item in checked.findings
                if item.objective in failed
                and item.disposition.value == "fail"
            )[:400]
        )[:600]
        try:
            draft = ProjectDraftAgent(generate).draft(
                project, kind, feedback=feedback,
            )
        except ProjectDraftGenerationError:
            return 0, "revision_draft_failed_unverified"
        observation = self.record_observation(
            kind="independent-revision",
            source="life:artifact-objectives",
            assertion=f"Independent objective report requires revision of {artifact_id}.",
            now=now, payload={
                "previous_artifact_id": artifact_id,
                "previous_revision": revision,
                "evaluation_id": evaluation.evaluation_id,
            },
        )
        try:
            self.schedule_artifact(
                project.project_id, artifact_kind=kind,
                title=project.name, specification=draft,
                evidence_ref=observation, now=now,
            )
        except ProjectWorkPending:
            # A concurrently running canonical LIFE tick won admission.
            # The winner's original job/permission must be left unchanged.
            return 0, "waiting_on_existing_work"
        return 1, "revision_scheduled"

    def _settle_retired_optional_interests(self, *, now: datetime) -> int:
        """Close paused personal projects after newer reviewed disinterest.

        A retired interest comes from original canonical evidence and never
        implies a model has feelings. Active work, uncertain effects, duties,
        the operator stop and old unverified retirement cannot be overridden.
        """
        if self.operator_stop.current().active:
            return 0
        projects = self.store.list_scope(
            owner_principal_id=SOFIA_PROJECT_OWNER,
            audience_id=LOCAL_AUDIENCE,
            statuses=(ProjectStatus.PAUSED,),
        )
        settled = 0
        for project in projects:
            if project.scope is not ProjectScope.PERSONAL_PRIVATE:
                continue
            interest = self.store.interest_by_id(
                project.originating_interest, audience_id=project.audience_id,
            )
            if (
                interest is None
                or interest.status is not InterestStatus.RETIRED
                or interest.recorded_at <= project.updated_at
                or interest.recorded_at > now
                or not interest.evidence_refs
            ):
                continue
            if any(
                self.work_store.get(job_id).status in {
                    WorkStatus.QUEUED, WorkStatus.RUNNING,
                    WorkStatus.WAITING_APPROVAL, WorkStatus.BLOCKED,
                    WorkStatus.UNCERTAIN,
                }
                for job_id in self.store.jobs(project.project_id)
            ):
                continue
            if any(
                self.evidence_index.lookup(ref) is None
                for ref in interest.evidence_refs
            ):
                continue
            self.abandon(
                project.project_id,
                reason=(
                    "Newer reviewed evidence retired the originating interest; "
                    "this optional personal project has ended."
                ),
                evidence_refs=interest.evidence_refs[:32],
                now=now,
            )
            settled += 1
        return settled

    def _reconcile_canonical_goal_lifecycle(self, *, now: datetime) -> int:
        """Stop private optional LIFE activity after a canonical GOALS change.

        This is a projection of already persisted GOALS authority, not a
        new approval or success oracle. An unseen goal is UNKNOWN rather
        than evidence of absence. A potentially executed RUN effect is
        never silently labelled abandoned or completed.
        """
        visible = {
            item.id: item for item in self.goals.list_visible(
                local_sparks_principal()
            )
        }
        projects = self.store.list_scope(
            owner_principal_id=SOFIA_PROJECT_OWNER,
            audience_id=LOCAL_AUDIENCE,
            statuses=(ProjectStatus.ACTIVE, ProjectStatus.PAUSED),
        )
        settled = 0
        for project in projects:
            if project.scope is not ProjectScope.PERSONAL_PRIVATE:
                continue
            goal = visible.get(project.goal_id)
            if goal is None:
                continue  # no inference about missing/denied GOALS records
            if (
                goal.origin is not GoalOrigin.SELF
                or goal.owner_principal_id != SOFIA_GOAL_OWNER_ID
                or goal.scope_audience != project.audience_id
            ):
                continue  # scope mismatch requires separate operator audit
            status = goal.status
            if (
                status is GoalStatus.ACTIVE
                and project.status is ProjectStatus.PAUSED
            ):
                events = self.store.events(
                    project.project_id,
                    owner_principal_id=SOFIA_PROJECT_OWNER,
                    audience_id=project.audience_id,
                )
                # A manually chosen LIFE pause has its own authority.
                # Only a previous GOALS-derived pause may follow the
                # canonical GOALS transition back to ACTIVE.
                if (
                    events
                    and events[-1].decision == "canonical_goal_reconciliation"
                    and events[-1].to_status is ProjectStatus.PAUSED
                ):
                    linked = tuple(
                        self.work_store.get(job_id)
                        for job_id in self.store.jobs(project.project_id)
                    )
                    unsafe = any(job.status in {
                        WorkStatus.UNCERTAIN, WorkStatus.FAILED,
                        WorkStatus.CANCELLED, WorkStatus.BLOCKED,
                    } for job in linked)
                    if not unsafe:
                        evidence = self.record_observation(
                            kind="goal-lifecycle-reconciliation",
                            source="life:canonical-goals",
                            assertion=(
                                f"Canonical scoped goal {goal.id} resumed "
                                "ACTIVE after a GOALS-derived LIFE pause."
                            ),
                            now=now,
                            payload={
                                "project_id": project.project_id,
                                "goal_id": goal.id,
                                "goal_revision": goal.revision,
                                "goal_status": status.value,
                            },
                        )
                        self._transition(
                            project.project_id, ProjectStatus.ACTIVE,
                            decision="canonical_goal_reconciliation",
                            reason="Original scoped GOALS authority resumed.",
                            evidence_refs=(evidence,),
                            actor=SOFIA_GOAL_OWNER_ID, now=now,
                            sync_goal=False,
                        )
                        settled += 1
                continue
            terminal = status in {
                GoalStatus.CANCELLED, GoalStatus.EXPIRED, GoalStatus.REJECTED,
            }
            must_pause = status in {
                GoalStatus.PAUSED, GoalStatus.COMPLETED,
                GoalStatus.SUPERSEDED, GoalStatus.CANDIDATE,
            }
            if not terminal and not must_pause:
                continue
            jobs = tuple(
                self.work_store.get(job_id)
                for job_id in self.store.jobs(project.project_id)
            )
            unsettled = any(job.status in {
                WorkStatus.QUEUED, WorkStatus.RUNNING,
                WorkStatus.WAITING_APPROVAL, WorkStatus.UNCERTAIN,
            } for job in jobs)
            # A cancelled goal with a possibly in-flight operation first
            # pauses LIFE, leaving the original RUN receipt to be settled.
            # Only a terminal goal with no unsettled work may close the
            # optional project; completion is NEVER inferred from goal state.
            disposition = (
                ProjectStatus.PAUSED if must_pause or unsettled
                else ProjectStatus.ABANDONED
            )
            if project.status is disposition:
                continue
            evidence = self.record_observation(
                kind="goal-lifecycle-reconciliation",
                source="life:canonical-goals",
                assertion=(
                    f"Canonical scoped goal {goal.id} is {status.value}; "
                    f"optional LIFE project cannot claim ongoing approval."
                ),
                now=now,
                payload={
                    "project_id": project.project_id,
                    "goal_id": goal.id,
                    "goal_revision": goal.revision,
                    "goal_status": status.value,
                    "unsettled_run_jobs": unsettled,
                },
            )
            self._transition(
                project.project_id, disposition,
                decision="canonical_goal_reconciliation",
                reason=(
                    f"Canonical goal {goal.id} is {status.value}; "
                    + (
                        "preserving unresolved RUN work for operator review."
                        if unsettled else
                        "no optional execution or completion is authorized."
                    )
                ),
                evidence_refs=(evidence,),
                actor=SOFIA_GOAL_OWNER_ID, now=now,
                sync_goal=False,  # GOALS is the source, not our mutation target
            )
            settled += 1
        return settled

    def _reconcile_terminal_run_projects(self, *, now: datetime) -> int:
        """Settle linked terminal RUN outcomes into LIFE and GOALS once.

        RUN remains authoritative. Reconciliation requires an original,
        durable RUN event linked to the exact project/job and reflecting
        its *current* terminal status. An uncertain external effect is
        never called a failure, success, or permission to retry it.
        This uses existing LIFE transition and GOALS authorities rather
        than introducing a new event queue or execution path.
        """
        settled = 0
        projects = self.store.list_scope(
            owner_principal_id=SOFIA_PROJECT_OWNER,
            audience_id=LOCAL_AUDIENCE,
            statuses=(ProjectStatus.ACTIVE,),
        )
        for project in projects:
            job_ids = self.store.jobs(project.project_id)
            if not job_ids:
                continue
            job = self.work_store.get(job_ids[-1])
            if job.status not in {
                WorkStatus.FAILED, WorkStatus.CANCELLED,
                WorkStatus.UNCERTAIN, WorkStatus.BLOCKED,
            }:
                continue
            # The derived LIFE observation is source-linked to a RUN
            # event. Neither an unlinked job nor a fabricated result dict
            # can cause an autonomous project status transition.
            source = next((
                event for event in reversed(
                    self.store.run_outcome_observations(project.project_id)
                )
                if event.job_id == job.job_id
                and event.status == job.status.value
                and event.run_at <= now
                and event.observed_at <= now
            ), None)
            if source is None:
                continue
            # Recheck before applying policy, in case RUN settled between
            # the projection and this transition. This is still a separate
            # source observation, not authorization for another effect.
            if self.work_store.get(job.job_id).status is not job.status:
                continue
            status = job.status
            explanation = (
                f"RUN job {job.job_id} has {status.value} status in "
                f"original RUN event {source.run_event_id}; "
                + (
                    "remote effects may have occurred; operator reconciliation required."
                    if status is WorkStatus.UNCERTAIN
                    else (
                        "authority or execution is blocked; review before retry."
                        if status is WorkStatus.BLOCKED
                        else "no autonomous retry; operator review required."
                    )
                )
            )
            evidence_ref = self.record_observation(
                kind="run-terminal-reconciliation",
                source="life:canonical-run-events",
                assertion=explanation[:500],
                now=now,
                payload={
                    "project_id": project.project_id,
                    "job_id": job.job_id,
                    "run_event_id": source.run_event_id,
                    "run_status": status.value,
                },
            )
            # Technical FAILED blocks the goal; authorization BLOCKED,
            # cancellation and uncertain effects pause LIFE instead of
            # claiming an objective failed or retrying the original effect.
            if status is WorkStatus.FAILED:
                self.fail(
                    project.project_id, reason=explanation,
                    evidence_refs=(evidence_ref,), now=now,
                )
            else:
                self.pause(
                    project.project_id, reason=explanation,
                    evidence_refs=(evidence_ref,), now=now,
                )
            settled += 1
        return settled

    def tick(
        self, *, now: datetime, busy: bool = False,
        resource_pressure: float = 0.0,
        generate=None,
    ) -> dict[str, object]:
        # Observe already-committed outcomes before optional cognition or
        # resource-limited project selection. This remains useful while busy.
        observed = self.store.reconcile_run_outcomes(now=now)
        terminal_settled = self._reconcile_terminal_run_projects(now=now)
        goal_settled = self._reconcile_canonical_goal_lifecycle(now=now)
        retired_settled = self._settle_retired_optional_interests(now=now)
        if self.operator_stop.current().active:
            return {
                "selection": SelectionKind.INACTIVITY.value,
                "project_id": None,
                "scheduled": 0,
                "jobs_started": 0,
                "follow_through": "operator_stop",
                "run_outcomes_observed": len(observed),
                "terminal_run_projects_settled": terminal_settled,
                "goal_lifecycle_projects_settled": goal_settled,
                "retired_interest_projects_settled": retired_settled,
                "review_queue": self.pending_work_review(limit=16),
            }
        if self.operator_stop.current().active:
            # Settling already-observed durable outcomes is bookkeeping,
            # not a license to launch new optional work or wake the model.
            selection = self.select_activity(
                now=now, busy=busy, resource_pressure=resource_pressure,
            )
            return {
                "selection": selection.kind.value,
                "project_id": None,
                "scheduled": 0,
                "jobs_started": 0,
                "stop_reason": "operator_stop_active",
                "run_outcomes_observed": len(observed),
                "terminal_run_projects_settled": terminal_settled,
                "goal_lifecycle_projects_settled": goal_settled,
                "retired_interest_projects_settled": retired_settled,
                "review_queue": self.pending_work_review(limit=16),
            }
        # Completion verification is a settlement of an ALREADY STARTED
        # canonical RUN job, not permission to spend new creation budget.
        # A finished artifact must not be orphaned forever merely because
        # its earlier generation used the project's daily CPU/storage cap.
        # Foreground activity and chosen quiet time still defer optional
        # verification; this never fabricates subjective preferences.
        if (
            not busy and resource_pressure < 0.75
            and self.store.quiet_until(now=now) is None
        ):
            candidates = self.store.list_scope(
                owner_principal_id=SOFIA_PROJECT_OWNER,
                audience_id=LOCAL_AUDIENCE,
                statuses=(ProjectStatus.ACTIVE,),
            )
            for candidate in candidates:
                linked_jobs = tuple(
                    self.work_store.get(key)
                    for key in self.store.jobs(candidate.project_id)
                )
                if not linked_jobs or not all(
                    job.status is WorkStatus.COMPLETED for job in linked_jobs
                ):
                    continue
                usage = self.store.usage(candidate.project_id, now.astimezone(timezone.utc).date())
                within_budget = (
                    float(usage["wall_seconds"])
                    < candidate.brief.resource_budget.daily_seconds
                    and int(usage["storage_bytes"])
                    < candidate.brief.resource_budget.storage_bytes
                )
                last = linked_jobs[-1]
                receipt = last.result if isinstance(last.result, dict) else {}
                artifact_id = receipt.get("artifact_id")
                revision = receipt.get("revision")
                if (
                    not isinstance(artifact_id, str)
                    or type(revision) is not int
                    or (artifact_id, revision) not in self.store.artifacts(
                        candidate.project_id
                    )
                ):
                    # A missing/unlinked receipt goes to operator review.
                    # Repeatedly selecting it cannot produce real evidence.
                    continue
                evaluations = {
                    (item.artifact_id, item.artifact_revision): item
                    for item in self.store.evaluations(candidate.project_id)
                }
                existing = evaluations.get((artifact_id, revision))
                if existing is not None:
                    # Crash recovery must be able to replay a source-verified
                    # milestone that was not committed after evaluation.
                    # Never require another LLM draft or new work budget for
                    # this reconciliation. The actual objective still needs a
                    # fresh original-byte check in _settle_personal_project.
                    incomplete = {
                        milestone.title
                        for milestone in self.store.milestones(candidate.project_id)
                        if milestone.status in {
                            MilestoneStatus.PLANNED, MilestoneStatus.ACTIVE,
                        }
                    }
                    needs_milestone_replay = any(
                        existing.objective_results.get(objective) is True
                        for objective in incomplete
                    )
                    if existing.technical_outcome is TechnicalOutcome.VALID:
                        auto_completion = (
                            existing.personal_judgment is PersonalJudgment.UNKNOWN
                            and set(existing.objective_results) == set(
                                candidate.brief.objectives
                            )
                            and all(
                                item is True
                                for item in existing.objective_results.values()
                            )
                        )
                        if not auto_completion and not needs_milestone_replay:
                            continue
                    elif existing.technical_outcome is TechnicalOutcome.INVALID:
                        can_revise = (
                            within_budget and generate is not None
                            and not self.store.has_daily_draft_attempt(
                                candidate.project_id, now=now,
                            )
                        )
                        # A permanently exhausted revision policy must
                        # settle to PAUSED even without a model callback or
                        # any remaining daily creation budget. Otherwise
                        # the finished work loops in ACTIVE forever.
                        exhausted = (
                            len(self.store.artifacts(candidate.project_id)) >= 3
                        )
                        if not (can_revise or needs_milestone_replay or exhausted):
                            continue
                    elif not needs_milestone_replay:
                        # Unverifiable criteria do not justify retries.
                        continue
                # Independent grading may still complete an existing
                # artifact. A new revision may only be drafted inside
                # the original separately enforced resource budget.
                scheduled, follow_through = self._settle_personal_project(
                    candidate, now=now,
                    generate=generate if within_budget else None,
                )
                selection = LifeSelection(
                    f"life-selection:{uuid4()}", SelectionKind.PROJECT,
                    candidate.project_id,
                    "Reconciling existing completed RUN artifact evidence.",
                    resource_pressure, busy, now,
                )
                self.store.record_selection(selection)
                started = self.manager.tick(
                    now=now, busy=busy, resource_pressure=resource_pressure,
                )
                return {
                    "selection": selection.kind.value,
                    "project_id": candidate.project_id,
                    "scheduled": scheduled,
                    "jobs_started": started,
                    "follow_through": follow_through,
                    "run_outcomes_observed": len(observed) + len(
                        self.store.reconcile_run_outcomes(now=now)
                    ),
                    "terminal_run_projects_settled": terminal_settled,
            "goal_lifecycle_projects_settled": goal_settled,
            "retired_interest_projects_settled": retired_settled,
                    "review_queue": self.pending_work_review(limit=16),
                }
        selection = self.select_activity(
            now=now, busy=busy, resource_pressure=resource_pressure,
        )
        scheduled = 0
        follow_through = "not_applicable"
        if selection.kind is SelectionKind.PROJECT and selection.project_id is not None:
            project = self._project(selection.project_id)
            if self.store.jobs(project.project_id):
                scheduled, follow_through = self._settle_personal_project(
                    project, now=now, generate=generate,
                )
            elif not self.store.artifacts(project.project_id):
                kind_tool = next((
                    tool for tool in project.brief.required_tools
                    if tool.startswith("artifact-kind:")
                ), "artifact-kind:text")
                kind = ArtifactKind(kind_tool.split(":")[-1])
                if kind not in {ArtifactKind.TEXT, ArtifactKind.STORY} or generate is None:
                    # No canned brief, hashed color, oscillator sample or
                    # serialized concept may masquerade as autonomous work.
                    # An explicitly approved manual Project Forge request
                    # still uses its own capability/permission path.
                    return {
                        "selection": selection.kind.value,
                        "project_id": selection.project_id,
                        "scheduled": 0,
                        "jobs_started": self.manager.tick(
                            now=now, busy=busy, resource_pressure=resource_pressure,
                        ),
                        "draft_status": (
                            "approved_autonomous_authoring_unavailable"
                            if kind not in {ArtifactKind.TEXT, ArtifactKind.STORY}
                            else "model_generation_unavailable"
                        ),
                        "terminal_run_projects_settled": terminal_settled,
            "goal_lifecycle_projects_settled": goal_settled,
            "retired_interest_projects_settled": retired_settled,
                        "review_queue": self.pending_work_review(limit=16),
                    }
                if not self.store.claim_daily_draft_attempt(project.project_id, now=now):
                    return {
                        "selection": selection.kind.value,
                        "project_id": selection.project_id,
                        "scheduled": 0,
                        "jobs_started": self.manager.tick(
                            now=now, busy=busy, resource_pressure=resource_pressure,
                        ),
                        "draft_status": "deferred_daily_limit",
                        "terminal_run_projects_settled": terminal_settled,
            "goal_lifecycle_projects_settled": goal_settled,
            "retired_interest_projects_settled": retired_settled,
                        "review_queue": self.pending_work_review(limit=16),
                    }
                try:
                    specification = ProjectDraftAgent(generate).draft(project, kind)
                except ProjectDraftGenerationError:
                    # A model drafting failure is not a license to submit
                    # a template as real creative output.
                    return {
                        "selection": selection.kind.value,
                        "project_id": selection.project_id,
                        "scheduled": 0,
                        "jobs_started": self.manager.tick(
                            now=now, busy=busy, resource_pressure=resource_pressure,
                        ),
                        "draft_status": "failed_unverified",
                        "terminal_run_projects_settled": terminal_settled,
            "goal_lifecycle_projects_settled": goal_settled,
            "retired_interest_projects_settled": retired_settled,
                        "review_queue": self.pending_work_review(limit=16),
                    }
                # Do not leave a misleading creative-work evidence record
                # when there is no authorized original draft to submit.
                evidence_ref = self.record_observation(
                    kind="project-selection", source="life:selection",
                    assertion=f"Original authored draft admitted for {project.project_id}.",
                    now=now, payload={"selection_id": selection.selection_id},
                )
                try:
                    self.schedule_artifact(
                        project.project_id, artifact_kind=kind,
                        title=project.name,
                        specification=specification,
                        evidence_ref=evidence_ref, now=now,
                    )
                except ProjectWorkPending:
                    follow_through = "waiting_on_existing_work"
                else:
                    scheduled = 1
        started = self.manager.tick(
            now=now, busy=busy, resource_pressure=resource_pressure,
        )
        return {
            "selection": selection.kind.value,
            "project_id": selection.project_id,
            "scheduled": scheduled,
            "jobs_started": started,
            "follow_through": follow_through,
            "run_outcomes_observed": len(observed) + len(
                self.store.reconcile_run_outcomes(now=now)
            ),
            "terminal_run_projects_settled": terminal_settled,
            "goal_lifecycle_projects_settled": goal_settled,
            "retired_interest_projects_settled": retired_settled,
            "review_queue": self.pending_work_review(limit=16),
        }

    def close(self) -> None:
        # Complete the bounded worker/database callback drain before the
        # application closes its canonical SQLite handles. Do not claim
        # Windows state shutdown succeeded while futures still write.
        self.manager.close(wait=True, timeout_seconds=30.0)

    def has_pending(self) -> bool:
        return bool(self.work_store.ready(
            limit=1, kinds=tuple(self.manager.handlers),
        ))
