"""Application bootstrap and controlled lifecycle for Sofía."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import RLock

from sofia.avatar.clothing_action import ClothingActionService
from sofia.avatar.generated_decision import GeneratedGarmentDecisionService
from sofia.avatar.generated_proposal import (
    GarmentGenerationBrief,
    GeneratedGarmentProposalService,
)
from sofia.avatar.generation_conversation import (
    WardrobeGenerationConversationService,
)
from sofia.avatar.authoring import GarmentDesignRequest, WardrobeStudio
from sofia.avatar.wardrobe_generated_store import (
    GarmentAcceptanceResult,
    GeneratedWardrobeStore,
    SofiaGarmentAcceptance,
)
from sofia.avatar.wardrobe_prebuild import GarmentBlueprint
from sofia.avatar.wardrobe_pending_store import (
    PendingGeneratedGarment,
    PendingGeneratedWardrobeStore,
)
from sofia.avatar.wardrobe_autonomy import WardrobeAutonomyContext
from sofia.avatar.presentation_routine import HeadlessPresentationRoutine
from sofia.avatar.presentation_store import PresentationStoreError
from sofia.avatar.wardrobe_planner import (
    Activity,
    OutfitPlanner,
    WardrobeContext,
    wardrobe_emotion_influences,
)
from sofia.avatar.presentation_runtime import (
    PresentationRuntimeBundle,
    load_or_bootstrap_presentation,
)
from sofia.application.emotional_conversation import (
    ConversationActivityGroup,
    EmotionalConversationService,
)
from sofia.application.conversation_service import ConversationService
from sofia.application.idle_reflection import IdleReflectionWorker
from sofia.application.background import ApplicationBackgroundCoordinator
from sofia.application.background_runtime import create_background_coordinator
from sofia.application.act_service import (
    SofiaActService, configure_act_delivery_from_environment,
    notification_route_from_environment,
)
from sofia.capability.gateway import CapabilityGateway
from sofia.application.evolution import SofiaEvolutionService
from sofia.application.fleet_runtime import (
    configure_fleet_enrollment_notices,
)
from sofia.application.memory_review import MemoryReviewService
from sofia.application.conversation_learning import ConversationLearningCoordinator
from sofia.application.release_runtime import create_release_manager
from sofia.cognition.matrix import (
    ContextualInfluenceMatrix,
    InfluenceSurface,
)
from sofia.composition.root import compose
from sofia.config.defaults import create_production_configuration
from sofia.config.model import SofiaConfiguration
from sofia.config.reviewed_projection import apply_reviewed_configuration
from sofia.config.user_settings import (
    RuntimeUserSettings,
    RuntimeUserSettingsStore,
)
from sofia.environment.factory import create_environment_service
from sofia.conversation.store import ConversationStore
from sofia.cognition.engine import CognitiveEngineError
from sofia.cognition.model import CognitiveResponse
from sofia.cognition.model_lifecycle import ModelLifecycleWorker
from sofia.cognition.v2 import (
    CognitiveEvidenceLedger,
    EntityCandidate,
    EvidenceAcquisitionCoordinator,
    EvidenceGraph,
    FleetMachineAnswerCoordinator,
    PersonalityAfterTruthRenderer,
    ProjectionAnswerCoordinator,
    ProductionTurnKernel,
    SQLiteConversationFocusStore,
)
from sofia.knowledge.evidence import KnowledgeEvidenceCoordinator
from sofia.interaction.opt_in_service import OptInInteractionConversationService
from sofia.runtime.internal_workspace import normalize_runtime_workspace_awareness
from sofia.run.heartbeat import ApplicationHeartbeatStore
from sofia.ops.backup_topology import backup_topology_enabled
from sofia.neuro import NeuralSignal, NeuroRuntime
from sofia.neuro import BodyReflexObservation, VoiceSensoryObservation
from sofia.neuro.coordinator import NeuroInputCoordinator
from sofia.neuro.store import NeuroObservabilityStore
from sofia.ops.local_telemetry import collect_local_telemetry
from sofia.habits.pattern_store import HabitPatternStore
from sofia.rel.store import RelationshipStore
from sofia.goals import (
    GoalEvidenceIndex,
    GoalService,
    GoalStatus,
    GoalStore,
    effective_priority,
)
from sofia.goals.conversation import GoalConversationResolver
from sofia.goals.coordinator import GoalProductionCoordinator
from sofia.ops.agent_discovery import (
    create_configured_fleet_discovery_source,
)
from sofia.distributed.state_paths import migrate_legacy_fleet_sidecars
from sofia.personality.influence import ContinuityInfluence
from sofia.habits.continuity import HabitContinuityCoordinator
from sofia.runtime.runtime import SofiaRuntime, SofiaRuntimeError
from sofia.social.principals import local_sparks_principal, SPARKS_PRINCIPAL_ID
from sofia.state.component_schema import verify_production_component_schemas
from sofia.ui.drafts import UIDraftStore
from sofia.ui.text import UITextClient
from sofia.voice import (
    TTSPlaybackReceipt,
    TTSStatus,
    TextToSpeechService,
    VoiceProsodyMatrix,
    VoiceProsodyProfile,
    VoiceUrgency,
    create_tts_service_from_environment,
)


class SofiaApplicationError(RuntimeError):
    """Raised when application bootstrap or lifecycle fails."""


def _habit_learning_enabled() -> bool:
    setting = os.environ.get("SOFIA_HABIT_LEARNING", "1").strip().lower()
    if setting in ("0", "false", "off"):
        return False
    if setting in ("1", "true", "on"):
        return True
    raise ValueError("SOFIA_HABIT_LEARNING must be 1 or 0 (also accepts true/false).")


def _idle_reflections_enabled() -> bool:
    """Enable reflection by default while preserving an explicit host opt-out."""
    setting = os.environ.get("SOFIA_IDLE_REFLECTIONS", "").strip().lower()
    if setting in ("0", "false", "off"):
        return False
    if setting in ("", "1", "true", "on"):
        return True
    raise ValueError("SOFIA_IDLE_REFLECTIONS must be 1 or 0 (also accepts true/false).")


class SofiaApplication:
    """Canonical application boundary for Sofía.

    Owns application-level orchestration only.
    Runtime remains responsible for Sofía's runtime lifecycle.
    """

    def __init__(self, configuration: SofiaConfiguration) -> None:
        self._configuration = configuration
        self._environment_settings_store = RuntimeUserSettingsStore(
            configuration.state_path
        )
        self._environment_settings_fingerprint = (
            self._environment_fingerprint(
                self._environment_settings_store.load()
            )
        )
        verify_production_component_schemas(configuration.state_path)
        migrate_legacy_fleet_sidecars(configuration.state_path)
        self._runtime: SofiaRuntime = compose(configuration)
        # Composition applies reviewed State Plane configuration. From this
        # point forward the application must use that same canonical object,
        # not the pre-review constructor input.
        self._configuration = self._runtime.configuration
        configuration = self._configuration
        self._evolution = SofiaEvolutionService(
            configuration=configuration,
            state_plane=self._runtime.state_plane,
        )
        self._release_manager = create_release_manager(
            configuration=configuration,
            state_plane=self._runtime.state_plane,
        )
        self._model_lock = RLock()
        # Background state mutation keeps one application lock. Each
        # conversation receives its own turn lock below, while routed Primary
        # and Secondary workers synchronize independently inside cognition.
        self._conversation_activity = ConversationActivityGroup()
        self._tts: TextToSpeechService = (
            create_tts_service_from_environment()
        )
        self._channel_conversations: list[ConversationService] = []
        self._neuro = NeuroRuntime(
            observability=NeuroObservabilityStore(configuration.state_path)
        )
        self._neuro_inputs = NeuroInputCoordinator(
            self._neuro,
            configuration.state_path,
            state_plane=self._runtime.state_plane,
        )
        self._neuro_telemetry = None
        self._neuro_telemetry_at: datetime | None = None
        self._last_neuro_input_error: str | None = None
        self._goals = GoalService(
            GoalStore(self._runtime.state_plane),
            evidence_verifier=GoalEvidenceIndex(configuration.state_path),
        )
        self._cognitive_evidence = CognitiveEvidenceLedger(
            configuration.state_path
        )
        self._cognitive_evidence_graph = EvidenceGraph(
            self._cognitive_evidence
        )
        self._cognitive_evidence_acquisition = EvidenceAcquisitionCoordinator(
            self._cognitive_evidence
        )
        dispatcher = self._runtime.cognitive_system.tool_dispatcher
        if dispatcher is None:
            raise SofiaApplicationError("production cognitive tool dispatcher is required")
        self._fleet_machine_answers = FleetMachineAnswerCoordinator(
            dispatcher, self._cognitive_evidence_acquisition
        )
        self._knowledge_answers = KnowledgeEvidenceCoordinator(
            dispatcher, self._cognitive_evidence_acquisition
        )
        self._projection_answers = ProjectionAnswerCoordinator(
            self._runtime, self._cognitive_evidence
        )
        self._personality_answer_renderer = PersonalityAfterTruthRenderer()
        self._turn_kernel = ProductionTurnKernel(
            SQLiteConversationFocusStore(configuration.state_path),
            entity_provider=self._cognition_entity_candidates,
        )
        conversation_store = ConversationStore(configuration.state_path)
        if conversation_store.database_path.resolve() != Path(
            configuration.state_path
        ).resolve():
            raise SofiaApplicationError(
                "canonical conversation store does not match configuration.state_path"
            )
        self._conversation_service: ConversationService = OptInInteractionConversationService(
            runtime=self._runtime,
            conversation_store=conversation_store,
            activity_group=self._conversation_activity,
        )
        self._conversation_service.set_evolution_service(self._evolution)
        candidate_store = self._runtime.memory_system.candidate_store
        if candidate_store is None:
            raise SofiaApplicationError(
                "production reviewed-memory candidate store is required"
            )
        self._memory_review = MemoryReviewService(
            conversation_store=conversation_store,
            candidate_store=candidate_store,
            state_path=configuration.state_path,
        )
        self._conversation_learning = ConversationLearningCoordinator(
            self._memory_review
        )
        self._conversation_service.set_learning_coordinator(
            self._conversation_learning
        )
        self._habit_continuity = HabitContinuityCoordinator(
            self._runtime.state_plane
        )
        self._habit_pattern_store = HabitPatternStore(
            self._runtime.state_plane
        )
        self._relationship_store = RelationshipStore(
            configuration.state_path,
            state_plane=self._runtime.state_plane,
        )
        self._conversation_service.set_habit_continuity(
            self._habit_continuity
        )
        self._conversation_service.set_pre_response_hook(
            self._refresh_trusted_live_state_before_response
        )
        self._conversation_service.set_voice_runtime_provider(
            self.voice_runtime_status
        )
        self._conversation_service.set_neuro_runtime(
            self._neuro
        )
        self._conversation_service.set_turn_kernel(self._turn_kernel)
        self._conversation_service.set_v2_answer_handler(self._answer_v2)
        self._conversation_service.set_goal_context_provider(
            self._goal_context_for_principal
        )
        goal_conversation = GoalConversationResolver(self._goals)
        self._conversation_service.set_goal_command_handler(
            goal_conversation.resolve
        )
        self._act_service = SofiaActService(
            Path(configuration.state_path)
        )
        configure_act_delivery_from_environment(
            self._act_service
        )
        self._goal_production = GoalProductionCoordinator(
            goals=self._goals,
            state_path=configuration.state_path,
            gateway=CapabilityGateway(self._runtime.capability_system),
            principal_provider=lambda: self._conversation_service._principal_context(),
            neuro_provider=lambda: self._neuro.last_snapshot,
            notify_review=self._notify_goal_review,
            wake_recorder=self._neuro.record_wake_outcome,
        )
        configure_fleet_enrollment_notices(
            ops_service=self._runtime.ops_service,
            act_service=self._act_service,
        )
        self._background: ApplicationBackgroundCoordinator | None = None
        self._startup_awareness_error: CognitiveEngineError | None = None
        self._heartbeat_store = ApplicationHeartbeatStore(
            configuration.state_path
        )
        self._idle_worker: IdleReflectionWorker | None = None
        self._model_lifecycle_worker: ModelLifecycleWorker | None = None
        self._presentation_bundle: PresentationRuntimeBundle | None = None
        self._presentation_routine: HeadlessPresentationRoutine | None = None
        self._clothing_action_service: ClothingActionService | None = None
        self._wardrobe_generation_service: (
            WardrobeGenerationConversationService | None
        ) = None
        self._ui_draft_store = UIDraftStore(configuration.state_path)
        self._text_ui = UITextClient(
            conversation=self._conversation_service,
            drafts=self._ui_draft_store,
            client_id="local-text",
            principal=local_sparks_principal(),
        )

    @property
    def chat_storage_mode(self) -> str:
        return "local"

    @property
    def chat_state_path(self) -> Path:
        return Path(self._configuration.state_path)

    @property
    def runtime(self) -> SofiaRuntime:
        return self._runtime

    @property
    def evolution(self) -> SofiaEvolutionService:
        return self._evolution

    @property
    def release_manager(self):
        return self._release_manager

    @property
    def act(self) -> SofiaActService:
        return self._act_service

    @property
    def neuro(self) -> NeuroRuntime:
        """Return the shared authority-free neural prioritization runtime."""
        return self._neuro

    @property
    def neuro_inputs(self) -> NeuroInputCoordinator:
        return self._neuro_inputs

    @property
    def goals(self) -> GoalService:
        return self._goals

    @property
    def last_neuro_input_error(self) -> str | None:
        return self._last_neuro_input_error

    @property
    def cognitive_evidence(self) -> CognitiveEvidenceLedger:
        return self._cognitive_evidence

    @property
    def cognitive_evidence_graph(self) -> EvidenceGraph:
        return self._cognitive_evidence_graph

    @property
    def cognitive_evidence_acquisition(self) -> EvidenceAcquisitionCoordinator:
        return self._cognitive_evidence_acquisition

    def _answer_v2(self, **kwargs):
        expression_provider = kwargs.pop("expression_context_provider", None)
        draft = self._fleet_machine_answers.planned_answer(**kwargs)
        if draft is None:
            draft = self._knowledge_answers.planned_answer(**kwargs)
        if draft is None:
            draft = self._projection_answers.planned_answer(**kwargs)
        if draft is None:
            return None
        expression = (
            expression_provider()
            if callable(expression_provider)
            else None
        )
        if expression is None:
            return CognitiveResponse(
                content=draft.content,
                evidence_refs=draft.evidence_refs,
            )
        return self._personality_answer_renderer.render(
            draft,
            expression_context=expression,
        )

    def _cognition_entity_candidates(self) -> tuple[EntityCandidate, ...]:
        """Project Fleet identities for reference resolution, never as facts."""
        candidates = []
        for host in self._runtime.ops_service.fleet():
            host_id = host.get("host_id")
            node_id = host.get("node_id")
            if not isinstance(host_id, str) or not host_id.strip():
                continue
            subject_id = (
                f"fleet-node:{node_id}"
                if isinstance(node_id, str) and node_id.strip()
                else f"fleet-host:{host_id}"
            )
            candidates.append(EntityCandidate(
                subject_id=subject_id,
                kind="fleet-node",
                aliases=(host_id,),
            ))
        return tuple(candidates)

    def _goal_context_for_principal(self, principal, now: datetime) -> str | None:
        return self._goals.prompt_context(principal, now=now)

    def observe_body_reflex(self, observation: BodyReflexObservation):
        """Accept only a BODY-owned post-reflex summary; never a motor command."""
        return self._neuro_inputs.observe_body(observation)

    def observe_voice_sensory(self, observation: VoiceSensoryObservation):
        """Accept live acoustic salience without treating it as semantic truth."""
        return self._neuro_inputs.observe_voice(observation)

    def _notify_goal_review(self, goal, now: datetime) -> None:
        """Queue review through ACT's existing policy/dedupe/delivery path."""
        route = self._act_service.delivery_route or notification_route_from_environment(
            state_path=Path(self._configuration.state_path),
        )
        if route is None:
            return
        channel, destination = route
        self._act_service.queue_system_notice(
            notice_id=f"goal-review:{goal.id}",
            recipient_id=SPARKS_PRINCIPAL_ID,
            channel=channel,
            destination=destination,
            evidence_id=goal.evidence_refs[0],
            content=(
                f"I noticed {goal.reason.rstrip('.').casefold()} and want to make "
                f"'{goal.title}' an active goal. It needs your review first."
            ),
            created_at=now,
            expires_at=min(goal.expires_at, now.replace(microsecond=0) + timedelta(days=7))
            if goal.expires_at is not None else now + timedelta(days=7),
        )

    @property
    def memory_review(self) -> MemoryReviewService:
        return self._memory_review

    @property
    def background_coordinator(
        self,
    ) -> ApplicationBackgroundCoordinator | None:
        return self._background

    @property
    def conversation(self) -> ConversationService:
        return self._conversation_service

    @property
    def startup_awareness_error(self) -> CognitiveEngineError | None:
        """Return the latest optional startup-awareness model failure."""
        return self._startup_awareness_error

    @property
    def idle_reflection_worker(self) -> IdleReflectionWorker | None:
        return getattr(self, "_idle_worker", None)

    def open_channel_conversation(
        self,
        *,
        session_id: str | None = None,
    ) -> ConversationService:
        """Open one audience-scoped conversation on the canonical runtime.

        Each channel keeps its own durable session/audience binding while all
        channels share identity, memory, environment, avatar state, cognition,
        and the application-owned inference lock.
        """
        if (
            self._runtime.state.value != "ready"
            or self._conversation_service.session is None
        ):
            raise SofiaApplicationError(
                "Sofía application must be fully started before opening "
                "a channel conversation."
            )
        conversation_store = ConversationStore(
            self._configuration.state_path
        )
        service: ConversationService = OptInInteractionConversationService(
            runtime=self._runtime,
            conversation_store=conversation_store,
            activity_group=self._conversation_activity,
        )
        service.set_learning_coordinator(
            self._conversation_learning
        )
        service.set_habit_continuity(
            self._habit_continuity
        )
        service.set_pre_response_hook(
            self._refresh_trusted_live_state_before_response
        )
        service.set_voice_runtime_provider(
            self.voice_runtime_status
        )
        service.set_neuro_runtime(
            self._neuro
        )
        service.set_turn_kernel(self._turn_kernel)
        service.set_v2_answer_handler(self._answer_v2)
        service.set_goal_context_provider(
            self._goal_context_for_principal
        )
        service.set_goal_command_handler(
            GoalConversationResolver(self._goals).resolve
        )
        clothing_actions = getattr(
            self,
            "_clothing_action_service",
            None,
        )
        if clothing_actions is not None:
            service.set_clothing_action_handler(
                clothing_actions.handle
            )
        wardrobe_generation = getattr(
            self,
            "_wardrobe_generation_service",
            None,
        )
        if wardrobe_generation is not None:
            service.set_wardrobe_generation_handler(
                wardrobe_generation.handle
            )
        try:
            service.open()
            service.start(session_id=session_id)
        except Exception:
            service.close()
            raise
        self._channel_conversations.append(service)
        return service

    @property
    def text_ui(self) -> UITextClient:
        """Return the local text-first UI over the canonical conversation."""
        return self._text_ui

    @property
    def tts(self) -> TextToSpeechService:
        """Return the application-owned non-blocking TTS service."""
        return self._tts

    def voice_runtime_status(self) -> TTSStatus:
        """Return current host-owned TTS runtime evidence."""
        return self._tts.status()

    def speak(
        self,
        content: str,
        *,
        urgency: VoiceUrgency = VoiceUrgency.NORMAL,
    ) -> TTSPlaybackReceipt:
        """Queue one persisted Sofía reply for local speech output."""
        if not isinstance(content, str) or not content.strip():
            raise ValueError("speech content must be nonempty")
        if not isinstance(urgency, VoiceUrgency):
            raise TypeError("urgency must be VoiceUrgency")

        profile = VoiceProsodyProfile()
        service = self._conversation_service
        current_emotional_state = getattr(
            service,
            "current_emotional_state",
            None,
        )
        if (
            callable(current_emotional_state)
            and self._runtime.personality is not None
        ):
            now = datetime.now(timezone.utc)
            environment = self._runtime.environment_service.snapshot(
                now=now,
                refresh_providers=False,
            )
            emotion = current_emotional_state(now=now)
            influence = ContinuityInfluence.from_state(
                emotion=emotion,
                environment=environment,
            )
            profile = VoiceProsodyMatrix().plan(
                influence,
                urgency=urgency,
            ).profile

        receipt = self._tts.submit(
            content,
            profile=profile,
        )
        urgency_value = {
            VoiceUrgency.NORMAL: 0.25,
            VoiceUrgency.IMPORTANT: 0.65,
            VoiceUrgency.URGENT: 0.95,
        }[urgency]
        try:
            self._neuro.observe_signal(NeuralSignal(
                source=f"speech:{receipt.state.value}",
                kind="voice",
                value=urgency_value,
                confidence=1.0,
                novelty=0.4,
                urgency=urgency_value,
                observed_at=datetime.now(timezone.utc),
                ttl_seconds=120.0,
            ))
        except Exception as exc:
            # Speech delivery already has its own receipt; attention telemetry
            # cannot change or invalidate that authoritative outcome.
            self._last_neuro_input_error = type(exc).__name__
        return receipt


    @staticmethod
    def _environment_fingerprint(
        settings: RuntimeUserSettings,
    ) -> tuple[tuple[str, str], ...]:
        if not isinstance(settings, RuntimeUserSettings):
            raise TypeError("settings must be RuntimeUserSettings")
        return tuple(
            sorted(settings.environment_mapping().items())
        )

    def _reload_environment_if_settings_changed(self) -> bool:
        """Hot-reload persisted ENVIRONMENT settings without restarting Sofía."""
        settings = self._environment_settings_store.load()
        fingerprint = self._environment_fingerprint(settings)
        if fingerprint == self._environment_settings_fingerprint:
            return False

        refreshed_configuration = create_production_configuration(
            state_path=self._configuration.state_path
        )
        refreshed_configuration = apply_reviewed_configuration(
            refreshed_configuration,
            self._runtime.state_plane,
        )
        refreshed_service = create_environment_service(
            refreshed_configuration
        )
        self._runtime.replace_environment_service(
            refreshed_service
        )
        self._environment_settings_fingerprint = fingerprint
        return True

    def _refresh_trusted_live_state_before_response(
        self,
        *,
        content: str,
        principal,
        channel: str,
    ) -> None:
        """Refresh host-owned contextual presentation before any user turn.

        This samples trusted local/user time from ENVIRONMENT without forcing a
        provider refresh. Weather questions still use their dedicated evidence
        path; this hook exists so AVATAR state cannot remain stale between the
        background presentation ticks.
        """
        _ = content, principal, channel
        self._reload_environment_if_settings_changed()
        self._evaluate_contextual_presentation(
            now=datetime.now(timezone.utc),
            refresh_environment=False,
        )
        self._refresh_neuro_inputs(
            now=datetime.now(timezone.utc),
            content=content,
            principal=principal,
            refresh_environment=False,
        )

    def _refresh_neuro_inputs(
        self,
        *,
        now: datetime,
        content: str = "",
        principal=None,
        refresh_environment: bool = False,
    ):
        """Sample authoritative read-only state; NEURO remains non-authoritative."""
        try:
            environment = self._runtime.environment_service.snapshot(
                now=now,
                refresh_providers=refresh_environment,
            )
            service = self._conversation_service
            emotion = None
            if isinstance(service, EmotionalConversationService):
                if principal is None:
                    emotion = service.current_emotional_state(now=now)
                else:
                    # Channel turns may be bound to a principal other than the
                    # local desktop owner.  Read that relationship's canonical
                    # emotional state explicitly so NEURO cannot carry one
                    # person's affective context into another conversation.
                    emotion = service.emotional_journal.current_state(
                        now=now,
                        subject=principal.principal_id,
                        scope=principal.relationship_scope,
                    )
            if (
                self._neuro_telemetry_at is None
                or (now - self._neuro_telemetry_at).total_seconds() >= 60.0
            ):
                self._neuro_telemetry = collect_local_telemetry()
                self._neuro_telemetry_at = now
            memories = ()
            habits = ()
            relationship = None
            goal_priorities = ()
            if principal is not None:
                if content.strip():
                    memories = self._runtime.memory_system.recall_relevant(
                        content,
                        principal=principal,
                    )
                habits = self._habit_pattern_store.patterns(
                    principal_id=principal.principal_id,
                    audience_id=principal.audience_id,
                )
                relationship = self._relationship_store.get(
                    principal.principal_id
                )
                goal_priorities = tuple(
                    (goal, self._goal_production.priority(
                        goal,
                        now=now,
                        conversation=content,
                        mark_evaluated=True,
                    ).value)
                    for goal in self._goals.list_visible(principal)
                    if goal.status is GoalStatus.ACTIVE
                )[:32]
            bundle = getattr(self, "_presentation_bundle", None)
            avatar = (
                None
                if bundle is None
                else bundle.authority.snapshot()
            )
            session = service.session
            snapshot = self._neuro_inputs.refresh(
                now=now,
                environment=environment,
                emotion=emotion,
                telemetry=self._neuro_telemetry,
                voice=self.voice_runtime_status(),
                avatar=avatar,
                memories=memories,
                habits=habits,
                relationship=relationship,
                goal_priorities=goal_priorities,
                session_id=None if session is None else session.id,
            )
            self._last_neuro_input_error = None
            return snapshot
        except Exception as exc:
            # Attention is advisory. Its refresh cannot make chat unavailable.
            self._last_neuro_input_error = type(exc).__name__
            return None

    def _evaluate_contextual_presentation_when_idle(
        self,
        *,
        now: datetime,
        refresh_environment: bool,
        idle_seconds: float,
    ):
        """Serialize one background AVATAR mutation behind foreground turns.

        The coordinator performs an initial idle check before dispatch. A user
        turn can begin after that check, so recheck while holding the shared
        model lock before touching PresentationAuthority.
        """
        with self._model_lock:
            if not self._conversation_service.ready_for_idle_reflection(
                idle_seconds=idle_seconds
            ):
                return None
            return self._evaluate_contextual_presentation(
                now=now,
                refresh_environment=refresh_environment,
            )

    def _wardrobe_autonomy_context(
        self,
    ) -> WardrobeAutonomyContext | None:
        """Project fresh trusted context for one user wardrobe request."""
        service = self._conversation_service
        if (
            not isinstance(service, EmotionalConversationService)
            or self._runtime.personality is None
        ):
            return None

        now = datetime.now(timezone.utc)
        environment = self._runtime.environment_service.snapshot(
            now=now,
            refresh_providers=False,
        )
        current_emotion = service.current_emotional_state(now=now)
        continuity = ContinuityInfluence.from_state(
            emotion=current_emotion,
            environment=environment,
        )
        influence_plan = ContextualInfluenceMatrix().plan(
            InfluenceSurface.WARDROBE_REQUEST_AUTONOMY,
            continuity,
        )

        wardrobe_context = None
        if environment.season is not None:
            wardrobe_context = WardrobeContext.from_environment_snapshot(
                environment,
                activity=Activity.CONVERSATION,
                emotion_influences=wardrobe_emotion_influences(
                    continuity
                ),
            )

        return WardrobeAutonomyContext(
            continuity=continuity,
            influence_plan=influence_plan,
            wardrobe_context=wardrobe_context,
        )

    def _install_presentation_bundle(
        self,
        bundle: PresentationRuntimeBundle,
    ) -> None:
        """Install one canonical AVATAR bundle across all live presentation paths."""
        if not isinstance(bundle, PresentationRuntimeBundle):
            raise TypeError("bundle must be PresentationRuntimeBundle")
        self._runtime.set_avatar_presentation(bundle.authority)
        self._runtime.set_avatar_matrix_builder(bundle.matrix_for)
        self._presentation_bundle = bundle
        self._clothing_action_service = ClothingActionService(
            bundle,
            context_provider=self._wardrobe_autonomy_context,
            adult_verified=bool(
                getattr(
                    self._configuration,
                    "avatar_private_adult_verified",
                    False,
                )
            ),
        )
        self._conversation_service.set_clothing_action_handler(
            self._clothing_action_service.handle
        )
        self._wardrobe_generation_service = (
            WardrobeGenerationConversationService(
                self.generate_wardrobe_piece_from_brief,
                resolve_pending=self.resolve_pending_generated_wardrobe_piece,
            )
        )
        self._conversation_service.set_wardrobe_generation_handler(
            self._wardrobe_generation_service.handle
        )
        self._presentation_routine = HeadlessPresentationRoutine(
            authority=bundle.authority,
            store=bundle.store,
            planner=OutfitPlanner(
                bundle.catalog.wardrobe,
                bundle.catalog.presets,
                designs={
                    blueprint.garment.item_id: blueprint.design
                    for blueprint in bundle.catalog.blueprints
                },
            ),
        )

    def evaluate_generated_wardrobe_piece(
        self,
        blueprint: GarmentBlueprint,
    ) -> GarmentAcceptanceResult:
        """Let Sofía's live cognition decide ownership, then enforce the gate."""
        if not isinstance(blueprint, GarmentBlueprint):
            raise TypeError("blueprint must be GarmentBlueprint")
        with self._model_lock:
            decision = GeneratedGarmentDecisionService(
                self._runtime.respond
            ).decide(blueprint)
            result = self.decide_generated_wardrobe_piece(
                blueprint,
                decision,
            )
            pending_store = PendingGeneratedWardrobeStore(
                self._configuration.state_path
            )
            if result.ask_sparks:
                pending_store.save(blueprint, decision)
            else:
                pending_store.clear(
                    item_id=blueprint.garment.item_id
                )
            return result

    def pending_generated_wardrobe_piece(
        self,
    ) -> PendingGeneratedGarment | None:
        """Return the durable generated piece currently awaiting Sparks."""
        return PendingGeneratedWardrobeStore(
            self._configuration.state_path
        ).load()

    def resolve_pending_generated_wardrobe_piece(
        self,
        sparks_input: str,
    ) -> tuple[GarmentBlueprint, GarmentAcceptanceResult] | None:
        """Use Sparks' input as preference evidence, then let Sofía decide again."""
        if (
            not isinstance(sparks_input, str)
            or not sparks_input.strip()
            or len(sparks_input.strip()) > 1200
        ):
            raise ValueError(
                "sparks_input must be bounded nonempty text"
            )
        with self._model_lock:
            pending_store = PendingGeneratedWardrobeStore(
                self._configuration.state_path
            )
            pending = pending_store.load()
            if pending is None:
                return None
            decision = GeneratedGarmentDecisionService(
                self._runtime.respond
            ).decide_with_sparks_input(
                pending.blueprint,
                prior_reason=pending.reason,
                sparks_input=sparks_input,
            )
            result = self.decide_generated_wardrobe_piece(
                pending.blueprint,
                decision,
            )
            if result.ask_sparks:
                pending_store.save(
                    pending.blueprint,
                    decision,
                )
            else:
                pending_store.clear(
                    item_id=pending.blueprint.garment.item_id
                )
            return pending.blueprint, result

    def generate_wardrobe_piece_from_brief(
        self,
        brief: GarmentGenerationBrief,
    ) -> tuple[GarmentBlueprint, GarmentAcceptanceResult]:
        """Generate a proposal, then require Sofía's independent ownership decision."""
        if not isinstance(brief, GarmentGenerationBrief):
            raise TypeError("brief must be GarmentGenerationBrief")
        with self._model_lock:
            request = GeneratedGarmentProposalService(
                self._runtime.respond
            ).generate(brief)
            return self.generate_and_evaluate_wardrobe_piece(
                request
            )

    def generate_and_evaluate_wardrobe_piece(
        self,
        request: GarmentDesignRequest,
    ) -> tuple[GarmentBlueprint, GarmentAcceptanceResult]:
        """Create one typed proposal, then require Sofía's ownership decision."""
        if not isinstance(request, GarmentDesignRequest):
            raise TypeError("request must be GarmentDesignRequest")
        with self._model_lock:
            bundle = self._presentation_bundle
            if bundle is None:
                raise SofiaApplicationError(
                    "AVATAR presentation must be started before wardrobe generation."
                )
            blueprint = WardrobeStudio(bundle.catalog).design_piece(
                request
            )
            result = self.evaluate_generated_wardrobe_piece(
                blueprint
            )
            return blueprint, result

    def decide_generated_wardrobe_piece(
        self,
        blueprint: GarmentBlueprint,
        acceptance: SofiaGarmentAcceptance,
    ) -> GarmentAcceptanceResult:
        """Apply Sofía's decision and refresh accepted ownership into live AVATAR."""
        with self._model_lock:
            bundle = self._presentation_bundle
            if bundle is None:
                raise SofiaApplicationError(
                    "AVATAR presentation must be started before wardrobe ownership decisions."
                )
            studio = WardrobeStudio(
                bundle.catalog,
                authority=bundle.authority,
                store=bundle.store,
                generated_store=GeneratedWardrobeStore(
                    self._configuration.state_path
                ),
            )
            result = studio.decide_generated_piece(
                blueprint,
                acceptance,
            )
            if not result.persisted:
                return result
            if self._runtime.embodiment is None:
                raise SofiaApplicationError(
                    "AVATAR presentation requires canonical embodiment."
                )
            refreshed = load_or_bootstrap_presentation(
                embodiment=self._runtime.embodiment,
                state_path=self._configuration.state_path,
            )
            self._install_presentation_bundle(refreshed)
            return result

    def _evaluate_contextual_presentation(
        self,
        *,
        now: datetime,
        refresh_environment: bool,
    ):
        """Evaluate one bounded ENVIRONMENT/EMOTION -> AVATAR presentation step."""
        routine = getattr(self, "_presentation_routine", None)
        if routine is None or not getattr(self, "_avatar_routines_enabled", True):
            return None
        environment = self._runtime.environment_service.snapshot(
            now=now,
            refresh_providers=refresh_environment,
        )
        operation_id = (
            "contextual-presentation:"
            + now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S")
            + f":r{routine.authority.current.revision}"
        )
        # Season is location-dependent and must never be guessed. Daypart does
        # not require season, though, so the reviewed all-season lounge/default
        # presets remain available from the trusted user/host local clock.
        if environment.season is None:
            local_now = (
                environment.user_local_time
                or environment.host_local_time
                or now
            )
            return routine.evaluate_daypart_fallback(
                now=local_now,
                operation_id=operation_id,
            )

        emotion_influences = ()
        service = self._conversation_service
        if (
            isinstance(service, EmotionalConversationService)
            and self._runtime.personality is not None
        ):
            current_emotion = service.current_emotional_state(now=now)
            continuity = ContinuityInfluence.from_state(
                emotion=current_emotion,
                environment=environment,
            )
            emotion_influences = wardrobe_emotion_influences(continuity)

        context = WardrobeContext.from_environment_snapshot(
            environment,
            activity=Activity.CONVERSATION,
            emotion_influences=emotion_influences,
        )
        bundle = getattr(self, "_presentation_bundle", None)
        preferences = (
            ()
            if bundle is None
            else bundle.catalog.reviewed_preferences()
        )
        return routine.evaluate(
            context,
            operation_id=operation_id,
            preferences=preferences,
        )

    def _rollback_failed_start(self) -> tuple[str, ...]:
        """Best-effort unwind for resources opened by a failed start attempt."""
        errors: list[str] = []

        coordinator = getattr(self, "_background", None)
        if coordinator is not None:
            try:
                coordinator.stop()
            except Exception as exc:
                errors.append(f"background:{type(exc).__name__}")
            self._background = None
            self._idle_worker = None

        lifecycle_worker = getattr(
            self,
            "_model_lifecycle_worker",
            None,
        )
        if lifecycle_worker is not None:
            try:
                lifecycle_worker.stop()
            except Exception as exc:
                errors.append(f"model_lifecycle:{type(exc).__name__}")
            self._model_lifecycle_worker = None

        for service in reversed(
            tuple(getattr(self, "_channel_conversations", ()))
        ):
            try:
                service.close()
            except Exception as exc:
                errors.append(f"channel:{type(exc).__name__}")
        self._channel_conversations.clear()

        tts = getattr(self, "_tts", None)
        if tts is not None:
            try:
                tts.stop()
            except Exception as exc:
                errors.append(f"tts:{type(exc).__name__}")

        try:
            self._conversation_service.close()
        except Exception as exc:
            errors.append(f"conversation:{type(exc).__name__}")

        ui_draft_store = getattr(self, "_ui_draft_store", None)
        if ui_draft_store is not None:
            try:
                ui_draft_store.close()
            except Exception as exc:
                errors.append(f"ui_drafts:{type(exc).__name__}")

        try:
            self._runtime.set_avatar_matrix_builder(None)
        except Exception as exc:
            errors.append(f"avatar_matrix:{type(exc).__name__}")

        self._presentation_bundle = None
        self._presentation_routine = None
        self._clothing_action_service = None
        try:
            self._conversation_service.set_clothing_action_handler(None)
        except Exception as exc:
            errors.append(f"clothing_handler:{type(exc).__name__}")

        if getattr(
            getattr(self._runtime, "state", None),
            "value",
            None,
        ) == "ready":
            try:
                self._runtime.shutdown()
            except Exception as exc:
                errors.append(f"runtime:{type(exc).__name__}")

        return tuple(errors)

    def start(self, session_id: str | None = None) -> CognitiveResponse | None:
        """Start the runtime and session, then optionally start idle reflection.

        When session_id is omitted, create a new conversation. When supplied,
        explicitly resume that persisted conversation. Startup awareness runs
        before any optional idle model inference; no background work is claimed
        for periods when this process was not running.
        """
        runtime_state_value = getattr(
            getattr(self._runtime, "state", None),
            "value",
            None,
        )
        if (
            runtime_state_value is not None
            and runtime_state_value not in {"created", "stopped"}
        ):
            raise SofiaApplicationError(
                "Sofía application can only start from a stopped state."
            )
        conversation_activity = getattr(self, "_conversation_activity", None)
        if conversation_activity is not None:
            conversation_activity.accept_foreground()

        try:
            from sofia.config.user_settings import RuntimeUserSettingsStore
            preferences = RuntimeUserSettingsStore(self._configuration.state_path).load()
            self._avatar_routines_enabled = preferences.avatar_routines_enabled
            enabled = (preferences.idle_reflections_enabled if preferences.idle_reflections_enabled is not None else _idle_reflections_enabled())
            habit_enabled = (preferences.habit_learning_enabled if preferences.habit_learning_enabled is not None else _habit_learning_enabled())
        except (TypeError, ValueError) as exc:
            raise SofiaApplicationError(
                "Sofía application failed to start."
            ) from exc

        try:
            ui_draft_store = getattr(
                self,
                "_ui_draft_store",
                None,
            )
            if ui_draft_store is not None:
                ui_draft_store.open()
            self._runtime.start()
            model_lifecycle = getattr(
                self._runtime,
                "model_lifecycle",
                None,
            )
            if model_lifecycle is not None:
                model_lifecycle.install_missing()
            environment_service = getattr(
                self._runtime,
                "environment_service",
                None,
            )
            environment_snapshot = (
                environment_service.snapshot(
                    now=datetime.now(timezone.utc),
                    refresh_providers=True,
                )
                if environment_service is not None
                else None
            )
            act_service = getattr(self, "_act_service", None)
            if (
                environment_snapshot is not None
                and environment_snapshot.timezone is not None
                and act_service is not None
                and preferences.outreach is None
            ):
                act_service.set_local_timezone(
                    environment_snapshot.timezone
                )
            release_manager = getattr(self, "_release_manager", None)
            if release_manager is not None:
                release_manager.reconcile_pointer()
            if self._runtime.embodiment is None:
                raise SofiaApplicationError(
                    "AVATAR presentation requires canonical embodiment."
                )
            bundle = load_or_bootstrap_presentation(
                embodiment=self._runtime.embodiment,
                state_path=self._configuration.state_path,
            )
            self._install_presentation_bundle(bundle)
            # Filter internal database noise in *both* pending awareness and
            # the runtime's cognitive context before the first model call.
            # The unfiltered snapshot stays preserved in the observation store.
            normalize_runtime_workspace_awareness(self._runtime)
            self._conversation_service.open()
            self._conversation_service.start(session_id=session_id)
            self._tts.start()
            self._evaluate_contextual_presentation(
                now=datetime.now(timezone.utc),
                refresh_environment=True,
            )
            self._refresh_neuro_inputs(
                now=datetime.now(timezone.utc),
                principal=(
                    self._conversation_service._principal_context()
                    if hasattr(self._conversation_service, "_principal_context")
                    else None
                ),
                refresh_environment=False,
            )
            goal_production = getattr(self, "_goal_production", None)
            if goal_production is not None:
                goal_production.reconcile_startup(
                    now=datetime.now(timezone.utc),
                )
            self._startup_awareness_error = None
            try:
                response = self._conversation_service.deliver_pending_awareness()
            except CognitiveEngineError as exc:
                # Continuity awareness is optional startup narration. A model
                # load/provider failure must not prevent the canonical runtime
                # or desktop UI from starting. The event remains pending
                # because ConversationService consumes it only after a
                # successful persisted response.
                self._startup_awareness_error = exc
                response = None
            reflection_enabled = bool(
                enabled and self._runtime.personality is not None
            )
            habit_continuity = getattr(
                self,
                "_habit_continuity",
                None,
            )
            habit_runtime_enabled = bool(
                habit_enabled and habit_continuity is not None
            )
            act_delivery_enabled = bool(
                act_service is not None
                and act_service.delivery_enabled
            )
            presentation_runtime_enabled = (
                self._presentation_routine is not None and preferences.avatar_routines_enabled
            )
            fleet_discovery_config = getattr(
                self._configuration,
                "fleet_discovery",
                None,
            )
            fleet_discovery_source = (
                None
                if fleet_discovery_config is None
                else create_configured_fleet_discovery_source(
                    self._configuration
                )
            )
            fleet_discovery_enabled = (
                fleet_discovery_source is not None
            )
            ops_service = getattr(self._runtime, "ops_service", None)
            fleet_reconciliation_enabled = (
                ops_service is not None
                and hasattr(ops_service, "observe_reconciliation")
            )
            # A fully composed application always has this NEURO bridge. The
            # structural checks keep deliberately minimal lifecycle fixtures
            # and alternate hosts from being mistaken for production wiring.
            neuro_runtime_enabled = (
                hasattr(self, "_neuro_inputs")
                and isinstance(
                    self._conversation_service,
                    EmotionalConversationService,
                )
            )
            background_needed = (
                neuro_runtime_enabled
                or reflection_enabled
                or habit_runtime_enabled
                or act_delivery_enabled
                or presentation_runtime_enabled
                or fleet_discovery_enabled
                or fleet_reconciliation_enabled
                or backup_topology_enabled()
            )
            if background_needed:
                if not isinstance(self._conversation_service, EmotionalConversationService):
                    raise SofiaApplicationError("Idle reflection requires an emotional conversation service.")
                coordinator = create_background_coordinator(
                    self,
                    reflection_enabled=reflection_enabled,
                    habit_runtime_enabled=habit_runtime_enabled,
                    act_delivery_enabled=act_delivery_enabled,
                    presentation_runtime_enabled=presentation_runtime_enabled,
                    fleet_discovery_source=fleet_discovery_source,
                    fleet_reconciliation_enabled=fleet_reconciliation_enabled,
                )
                # Register ownership before any thread can start, so failed
                # startup always unwinds the coordinator through rollback.
                self._background = coordinator
                self._idle_worker = coordinator.idle
                coordinator.start()
                if (
                    getattr(self._runtime, "runtime_id", None) is not None
                    and getattr(self, "_heartbeat_store", None) is not None
                ):
                    coordinator._publish_heartbeat(
                        now=datetime.now(timezone.utc),
                        healthy=True,
                    )

            model_lifecycle = getattr(
                self._runtime,
                "model_lifecycle",
                None,
            )
            if (
                model_lifecycle is not None
                and model_lifecycle.policy.enabled
            ):
                interval = min(
                    60.0,
                    max(
                        5.0,
                        model_lifecycle.policy.idle_unload_seconds / 4,
                    ),
                )
                lifecycle_worker = ModelLifecycleWorker(
                    manager=model_lifecycle,
                    interval_seconds=interval,
                )
                self._model_lifecycle_worker = lifecycle_worker
                lifecycle_worker.start()
            return response
        except KeyboardInterrupt:
            self._rollback_failed_start()
            raise
        except Exception as exc:
            cleanup_errors = self._rollback_failed_start()
            error = SofiaApplicationError(
                "Sofía application failed to start."
            )
            if cleanup_errors:
                error.add_note(
                    "Startup rollback also reported: "
                    + ", ".join(cleanup_errors)
                )
            raise error from exc

    def shutdown(self) -> None:
        """Stop background work, then serialize teardown after foreground work."""
        coordinator = getattr(self, "_background", None)
        if coordinator is not None:
            try:
                coordinator.stop()
            except RuntimeError as exc:
                raise SofiaApplicationError(
                    "Background coordination has not stopped safely."
                ) from exc
            self._background = None
            self._idle_worker = None
        lifecycle_worker = getattr(
            self,
            "_model_lifecycle_worker",
            None,
        )
        if lifecycle_worker is not None:
            try:
                lifecycle_worker.stop()
            except RuntimeError as exc:
                raise SofiaApplicationError(
                    "Model lifecycle worker has not stopped safely."
                ) from exc
            self._model_lifecycle_worker = None

        # Background mutation retains the application lock. Foreground turns
        # have per-session locks and are
        # drained through the shared activity group before stores are closed.
        conversation_activity = getattr(self, "_conversation_activity", None)
        if conversation_activity is not None:
            conversation_activity.begin_shutdown()
        with self._model_lock:
            try:
                for service in reversed(
                    getattr(self, "_channel_conversations", ())
                ):
                    service.close()
                self._channel_conversations.clear()
                bundle = getattr(self, "_presentation_bundle", None)
                if bundle is not None:
                    bundle.store.save(bundle.authority)
                self._runtime.shutdown()
            except (
                SofiaRuntimeError,
                PresentationStoreError,
                RuntimeError,
            ) as exc:
                raise SofiaApplicationError(
                    "Sofía application failed to shut down."
                ) from exc
            finally:
                try:
                    self._tts.stop()
                except Exception:
                    pass
                self._runtime.set_avatar_matrix_builder(None)
                self._presentation_bundle = None
                self._presentation_routine = None
                self._clothing_action_service = None
                self._conversation_service.set_clothing_action_handler(None)
                self._conversation_service.close()
                ui_draft_store = getattr(
                    self,
                    "_ui_draft_store",
                    None,
                )
                if ui_draft_store is not None:
                    ui_draft_store.close()
