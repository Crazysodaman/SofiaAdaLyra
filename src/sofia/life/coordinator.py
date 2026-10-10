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
from sofia.run.work import (
    DurableWorkStore, TaskExecutionManager, WorkJob, WorkResult, WorkStatus,
)
from sofia.social.principals import local_sparks_principal

from .model import (
    PROJECT_TRANSITIONS, ArtifactEvaluation, ExperienceRecord, InterestRecord,
    InterestStatus, LifeProject, LifeSelection, MilestoneStatus,
    PersonalJudgment, ProjectBrief, ProjectEvent, ProjectIdea, ProjectMilestone,
    ProjectScope, ProjectStatus, ResourceBudget, SelectionKind,
    TechnicalOutcome, aware, identifier, text,
)
from .idea_agent import ProjectIdeaAgent
from .store import LifeStore


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

    def invent_project(
        self, idea: ProjectIdea, *, scope: ProjectScope = ProjectScope.PERSONAL_PRIVATE,
        budget: ResourceBudget | None = None,
    ) -> LifeProject:
        """Validate an open-ended structured idea; no project catalogue is consulted."""
        if not isinstance(idea, ProjectIdea):
            raise TypeError("ProjectIdea required")
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
        project = self._project(project_id)
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

    def complete(self, project_id: str, *, reason: str, now: datetime) -> LifeProject:
        project = self._project(project_id)
        if project.goal_id is None:
            raise ValueError("active project has no canonical goal")
        evaluations = self.store.evaluations(project_id)
        verified_result = any(
            item.technical_outcome is TechnicalOutcome.VALID
            and item.objective_results
            and all(result is True for result in item.objective_results.values())
            for item in evaluations
        )
        if not verified_result:
            raise ValueError("completion requires a verified successful artifact evaluation")
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

    def select_activity(
        self, *, now: datetime, busy: bool, resource_pressure: float,
    ) -> LifeSelection:
        if not 0 <= resource_pressure <= 1:
            raise ValueError("resource_pressure must be in 0..1")
        quiet = self.store.quiet_until(now=now)
        kind, project, reason = SelectionKind.INACTIVITY, None, "No optional activity is currently justified."
        if quiet is not None:
            reason = f"Sofía chose quiet time until {quiet[0].isoformat()}: {quiet[1]}"
        elif busy:
            reason = "Foreground user activity has priority over optional personal work."
        elif resource_pressure >= 0.75:
            reason = "Optional personal work paused for resource pressure."
        else:
            candidates = self.store.list_scope(
                owner_principal_id=SOFIA_PROJECT_OWNER, audience_id=LOCAL_AUDIENCE,
                statuses=(ProjectStatus.ACTIVE,),
            )
            for candidate in candidates:
                usage = self.store.usage(candidate.project_id, now.date())
                if (
                    float(usage["wall_seconds"]) >= candidate.brief.resource_budget.daily_seconds
                    or int(usage["storage_bytes"]) >= candidate.brief.resource_budget.storage_bytes
                ):
                    continue
                open_jobs = sum(
                    self.work_store.get(job_id).status in {
                        WorkStatus.QUEUED, WorkStatus.RUNNING, WorkStatus.BLOCKED,
                    }
                    for job_id in self.store.jobs(candidate.project_id)
                )
                if open_jobs >= candidate.brief.resource_budget.concurrent_jobs:
                    continue
                kind, project = SelectionKind.PROJECT, candidate
                reason = "Selected the highest-priority eligible personal project within current budgets."
                break
        selection = LifeSelection(
            f"life-selection:{uuid4()}", kind,
            None if project is None else project.project_id, reason,
            resource_pressure, busy, now,
        )
        self.store.record_selection(selection)
        return selection

    def consider_new_project(
        self, *, generate, now: datetime, busy: bool,
        resource_pressure: float,
    ) -> LifeProject | None:
        """Run at most one daily LLM suggestion through deterministic host policy."""
        if busy or resource_pressure >= 0.65 or self.store.quiet_until(now=now) is not None:
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
        interests = tuple(
            item for item in self.store.active_interests(audience_id=LOCAL_AUDIENCE)
            if item.confidence >= 0.6 and item.strength >= 0.5
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
            evidence_refs = tuple(dict.fromkeys(
                ref for interest in interests for ref in interest.evidence_refs
            ))[:32]
            deterministic_accept = (
                suggestion.pursue
                and suggestion.confidence >= 0.65
                and suggestion.curiosity >= 0.65
                and suggestion.artifact_kind in self._native_probe.supported_kinds
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
                interests[0].interest_id, suggestion.objectives,
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

    @staticmethod
    def _initial_specification(project: LifeProject, kind: ArtifactKind) -> dict[str, object]:
        if kind in {ArtifactKind.TEXT, ArtifactKind.STORY}:
            return {
                "content": f"# {project.name}\n\n{project.description}\n\n"
                + "\n".join(f"- {objective}" for objective in project.brief.objectives),
            }
        if kind is ArtifactKind.ART:
            digest = sha256(project.project_id.encode()).hexdigest()
            return {"color": "#" + digest[:6].upper()}
        if kind is ArtifactKind.MUSIC:
            return {"frequency_hz": 220 + int(sha256(project.project_id.encode()).hexdigest()[:2], 16) * 2}
        return {"concept": project.description, "objectives": list(project.brief.objectives)}

    def schedule_artifact(
        self, project_id: str, *, artifact_kind: ArtifactKind,
        title: str, specification: Mapping[str, object], evidence_ref: str,
        now: datetime, artifact_id: str | None = None,
    ) -> WorkJob:
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
        usage = self.store.usage(project.project_id, now.date())
        if int(usage["storage_bytes"]) >= project.brief.resource_budget.storage_bytes:
            raise RuntimeError("project storage budget is exhausted")
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
            now=now, deadline=now + timedelta(minutes=30),
        )
        self.store.authorize_artifact(
            request_id=str(parameters["request_id"]), project_id=project.project_id,
            artifact_id=artifact_key,
            request_digest=creative_request_digest(parameters), now=now,
        )
        self.store.link_job(project.project_id, job.job_id, now=now)
        return job

    def _create_artifact(self, job: WorkJob, cancel) -> WorkResult:
        if cancel.is_set():
            return WorkResult(WorkStatus.FAILED, {}, "cancelled_before_creative_execution")
        started = datetime.now(timezone.utc)
        project = self._project(str(job.payload["project_id"]))
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
        artifact_id, revision = str(output["artifact_id"]), int(output["revision"])
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
        if technical_outcome is TechnicalOutcome.VALID and (
            not objective_results or any(result is not True for result in objective_results.values())
        ):
            raise ValueError("technical validity requires every declared objective check to pass")
        value = ArtifactEvaluation(
            f"evaluation:{uuid4()}", project_id, artifact_id, revision.revision,
            technical_outcome, personal_judgment, objective_results, reason,
            evidence_refs, preserve_for_research, now,
        )
        self.store.record_evaluation(value)
        disposition = {
            PersonalJudgment.LIKE: PreferenceDisposition.LIKE,
            PersonalJudgment.DISLIKE: PreferenceDisposition.DISLIKE,
            PersonalJudgment.MIXED: PreferenceDisposition.UNKNOWN,
            PersonalJudgment.INDIFFERENT: PreferenceDisposition.INDIFFERENT,
            PersonalJudgment.UNKNOWN: PreferenceDisposition.UNKNOWN,
        }[personal_judgment]
        current = self.preferences.current(
            subject=PreferenceSubject.SOFIA, category="creation",
            target_id=artifact_id, context="project", audience_id=project.audience_id,
        )
        self.preferences.revise(
            subject=PreferenceSubject.SOFIA, category="creation",
            target_id=artifact_id, context="project", disposition=disposition,
            strength=0.75 if personal_judgment in {PersonalJudgment.LIKE, PersonalJudgment.DISLIKE} else 0.4,
            confidence=project.confidence, reason=reason,
            evidence_ref=evidence_refs[0], audience_id=project.audience_id,
            expected_revision=None if current is None else current.revision, now=now,
        )
        self._experience(
            project=project, kind="artifact_evaluated",
            summary=(
                f"Evaluated {artifact_id}: technically {technical_outcome.value}; "
                f"personal judgment {personal_judgment.value}."
            ), evidence_refs=evidence_refs, now=now,
            metadata={"preserve_for_research": preserve_for_research},
        )
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
        metadata: Mapping[str, object],
    ) -> ExperienceRecord:
        value = ExperienceRecord(
            f"experience:{uuid4()}", project.project_id, kind, summary,
            evidence_refs, project.audience_id,
            project.scope is ProjectScope.PERSONAL_PRIVATE,
            now, now, metadata,
        )
        self.store.record_experience(value)
        return value

    def tick(
        self, *, now: datetime, busy: bool = False,
        resource_pressure: float = 0.0,
    ) -> dict[str, object]:
        selection = self.select_activity(
            now=now, busy=busy, resource_pressure=resource_pressure,
        )
        scheduled = 0
        if selection.kind is SelectionKind.PROJECT and selection.project_id is not None:
            project = self._project(selection.project_id)
            if not self.store.artifacts(project.project_id) and not self.store.jobs(project.project_id):
                kind_tool = next((
                    tool for tool in project.brief.required_tools
                    if tool.startswith("artifact-kind:")
                ), "artifact-kind:text")
                kind = ArtifactKind(kind_tool.split(":")[-1])
                evidence_ref = self.record_observation(
                    kind="project-selection", source="life:selection",
                    assertion=f"{project.project_id} selected within resource budget",
                    now=now, payload={"selection_id": selection.selection_id},
                )
                self.schedule_artifact(
                    project.project_id, artifact_kind=kind,
                    title=project.name,
                    specification=self._initial_specification(project, kind),
                    evidence_ref=evidence_ref, now=now,
                )
                scheduled = 1
        started = self.manager.tick(
            now=now, busy=busy, resource_pressure=resource_pressure,
        )
        return {
            "selection": selection.kind.value,
            "project_id": selection.project_id,
            "scheduled": scheduled,
            "jobs_started": started,
        }

    def close(self) -> None:
        self.manager.close(wait=False)

    def has_pending(self) -> bool:
        return bool(self.work_store.ready(
            limit=1, kinds=tuple(self.manager.handlers),
        ))
