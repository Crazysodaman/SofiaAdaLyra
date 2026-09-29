"""Application bootstrap and controlled lifecycle for Sofía."""
from __future__ import annotations

import os
import socket
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock

from sofia.avatar.influence import wardrobe_emotion_influences
from sofia.avatar.interact_bridge import HostEnvironmentEvidence
from sofia.avatar.presentation_routine import HeadlessPresentationRoutine
from sofia.avatar.presentation_store import PresentationStoreError
from sofia.avatar.wardrobe_routine import Activity, OutfitPlanner
from sofia.avatar.wardrobe_studio import WardrobeStudio
from sofia.avatar.runtime_state import (
    PresentationRuntimeBundle,
    load_or_bootstrap_presentation,
)
from sofia.application.emotional_conversation import EmotionalConversationService
from sofia.application.conversation_service import ConversationService
from sofia.application.idle_reflection import IdleReflectionWorker
from sofia.application.background import ApplicationBackgroundCoordinator
from sofia.application.act_service import SofiaActService
from sofia.application.act_runtime import configure_act_delivery_from_environment
from sofia.application.evolution import SofiaEvolutionService
from sofia.application.fleet_runtime import (
    configure_fleet_enrollment_notices,
    create_fleet_candidate_notifier,
)
from sofia.application.memory_review import MemoryReviewService
from sofia.application.conversation_learning import ConversationLearningCoordinator
from sofia.application.release_runtime import create_release_manager
from sofia.composition.root import compose
from sofia.config.model import SofiaConfiguration
from sofia.conversation.store import ConversationStore
from sofia.cognition.engine import CognitiveEngineError
from sofia.cognition.model import CognitiveResponse
from sofia.cognition.model_lifecycle import ModelLifecycleWorker
from sofia.interaction.opt_in_service import OptInInteractionConversationService
from sofia.runtime.internal_workspace import normalize_runtime_workspace_awareness
from sofia.run.heartbeat import ApplicationHeartbeat, ApplicationHeartbeatStore
from sofia.ops.activity import ActivityMode, HostActivityStore
from sofia.ops.agent_discovery import (
    create_configured_fleet_discovery_source,
)
from sofia.ops.discovery import (
    FleetDiscoveryCoordinator,
    FleetDiscoveryEnrollmentReconciler,
)
from sofia.distributed.endpoint_policy_durable import DurableEndpointPolicy
from sofia.distributed.identity_durable import DurableNodeIdentityRegistry
from sofia.personality.influence import ContinuityInfluence
from sofia.habits.continuity import HabitContinuityCoordinator
from sofia.runtime.runtime import SofiaRuntime, SofiaRuntimeError
from sofia.social.principals import local_sparks_principal
from sofia.state.component_schema import verify_production_component_schemas
from sofia.ui.drafts import UIDraftStore
from sofia.ui.text import UITextClient


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
    """Explicit supervised opt-in; never assume authorization from capability."""
    setting = os.environ.get("SOFIA_IDLE_REFLECTIONS", "").strip().lower()
    if setting in ("", "0", "false", "off"):
        return False
    if setting in ("1", "true", "on"):
        return True
    raise ValueError("SOFIA_IDLE_REFLECTIONS must be 1 or 0 (also accepts true/false).")


class SofiaApplication:
    """Canonical application boundary for Sofía.

    Owns application-level orchestration only.
    Runtime remains responsible for Sofía's runtime lifecycle.
    """

    def __init__(self, configuration: SofiaConfiguration) -> None:
        self._configuration = configuration
        verify_production_component_schemas(configuration.state_path)
        self._runtime: SofiaRuntime = compose(configuration)
        self._evolution = SofiaEvolutionService(
            configuration=configuration,
            state_plane=self._runtime.state_plane,
        )
        self._release_manager = create_release_manager(
            configuration=configuration,
            state_plane=self._runtime.state_plane,
        )
        self._model_lock = RLock()
        self._channel_conversations: list[ConversationService] = []
        conversation_store = ConversationStore(configuration.state_path)
        self._conversation_service: ConversationService = OptInInteractionConversationService(
            runtime=self._runtime,
            conversation_store=conversation_store,
            model_lock=self._model_lock,
        )
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
        self._conversation_service.set_habit_continuity(
            self._habit_continuity
        )
        self._act_service = SofiaActService(
            Path(configuration.state_path)
        )
        configure_act_delivery_from_environment(
            self._act_service
        )
        configure_fleet_enrollment_notices(
            ops_service=self._runtime.ops_service,
            act_service=self._act_service,
        )
        self._background: ApplicationBackgroundCoordinator | None = None
        self._heartbeat_store = ApplicationHeartbeatStore(
            configuration.state_path
        )
        self._idle_worker: IdleReflectionWorker | None = None
        self._model_lifecycle_worker: ModelLifecycleWorker | None = None
        self._presentation_bundle: PresentationRuntimeBundle | None = None
        self._presentation_routine: HeadlessPresentationRoutine | None = None
        self._wardrobe_studio: WardrobeStudio | None = None
        self._ui_draft_store = UIDraftStore(configuration.state_path)
        self._text_ui = UITextClient(
            conversation=self._conversation_service,
            drafts=self._ui_draft_store,
            client_id="local-text",
            principal=local_sparks_principal(),
        )

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
    def memory_review(self) -> MemoryReviewService:
        return self._memory_review

    @property
    def conversation_learning(self) -> ConversationLearningCoordinator:
        return self._conversation_learning

    @property
    def background_coordinator(
        self,
    ) -> ApplicationBackgroundCoordinator | None:
        return self._background

    @property
    def conversation(self) -> ConversationService:
        return self._conversation_service

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
        if self._runtime.state.value != "ready":
            raise SofiaApplicationError(
                "Sofía must be started before opening a channel conversation."
            )
        conversation_store = ConversationStore(
            self._configuration.state_path
        )
        service: ConversationService = OptInInteractionConversationService(
            runtime=self._runtime,
            conversation_store=conversation_store,
            model_lock=self._model_lock,
        )
        service.set_learning_coordinator(
            self._conversation_learning
        )
        service.set_habit_continuity(
            self._habit_continuity
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
    def wardrobe_studio(self) -> WardrobeStudio | None:
        """Return the live AVATAR design/composition studio after startup."""
        return self._wardrobe_studio

    def _evaluate_contextual_presentation(
        self,
        *,
        now: datetime,
        refresh_environment: bool,
    ):
        """Evaluate one bounded ENVIRONMENT/EMOTION -> AVATAR presentation step."""
        routine = getattr(self, "_presentation_routine", None)
        if routine is None:
            return None
        environment = self._runtime.environment_service.snapshot(
            now=now,
            refresh_providers=refresh_environment,
        )
        # Season is location-dependent. Never guess it just to force an outfit.
        if environment.season is None:
            return None

        host_environment = HostEnvironmentEvidence.from_environment_snapshot(
            environment,
            activity=Activity.CONVERSATION,
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

        context = host_environment.planner_context(
            emotion_influences=emotion_influences,
        )
        operation_id = (
            "contextual-presentation:"
            + now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S")
            + f":r{routine.authority.current.revision}"
        )
        return routine.evaluate(
            context,
            operation_id=operation_id,
        )

    def start(self, session_id: str | None = None) -> CognitiveResponse | None:
        """Start the runtime and session, then optionally start idle reflection.

        When session_id is omitted, create a new conversation. When supplied,
        explicitly resume that persisted conversation. Startup awareness runs
        before any optional idle model inference; no background work is claimed
        for periods when this process was not running.
        """
        try:
            enabled = _idle_reflections_enabled()
            habit_enabled = _habit_learning_enabled()
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
            self._runtime.set_avatar_presentation(bundle.authority)
            self._presentation_bundle = bundle
            self._wardrobe_studio = WardrobeStudio(
                bundle.catalog,
                authority=bundle.authority,
            )
            self._presentation_routine = HeadlessPresentationRoutine(
                authority=bundle.authority,
                store=bundle.store,
                planner=OutfitPlanner(
                    bundle.catalog.wardrobe,
                    bundle.catalog.presets,
                ),
            )
            # Filter internal database noise in *both* pending awareness and
            # the runtime's cognitive context before the first model call.
            # The unfiltered snapshot stays preserved in the observation store.
            normalize_runtime_workspace_awareness(self._runtime)
            self._conversation_service.open()
            self._conversation_service.start(session_id=session_id)
            self._evaluate_contextual_presentation(
                now=datetime.now(timezone.utc),
                refresh_environment=True,
            )
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
                self._presentation_routine is not None
            )
            fleet_discovery_source = (
                create_configured_fleet_discovery_source(
                    self._configuration
                )
            )
            fleet_discovery_enabled = (
                fleet_discovery_source is not None
            )
            background_needed = (
                reflection_enabled
                or habit_runtime_enabled
                or act_delivery_enabled
                or presentation_runtime_enabled
                or fleet_discovery_enabled
            )
            if background_needed:
                if not isinstance(self._conversation_service, EmotionalConversationService):
                    raise SofiaApplicationError("Idle reflection requires an emotional conversation service.")
                coordinator = ApplicationBackgroundCoordinator(
                    service=self._conversation_service,
                    state_path=Path(self._configuration.state_path),
                    reflection_enabled=reflection_enabled,
                )
                activity_store = HostActivityStore(
                    self._configuration.state_path
                )
                host_id = socket.gethostname()

                def deliver_act(now):
                    activity = activity_store.state(host_id).effective
                    busy = activity in {
                        ActivityMode.GAMING,
                        ActivityMode.BUSY,
                        ActivityMode.DO_NOT_DISTURB,
                    }
                    return act_service.deliver_one(
                        now=now,
                        busy=busy,
                    )

                if act_service is not None:
                    coordinator.set_act_delivery(deliver_act)

                def bridge_reflection_outreach(now):
                    service = self._conversation_service
                    if not hasattr(service, "current_emotional_state"):
                        return None
                    emotion = service.current_emotional_state(now=now)
                    environment = self._runtime.environment_service.snapshot(
                        now=now,
                        refresh_providers=False,
                    )
                    influence = ContinuityInfluence.from_state(
                        emotion=emotion,
                        environment=environment,
                    )
                    if act_service is None:
                        return None
                    count = act_service.bridge_reflection_outbox(
                        reflections=service.reflection_journal,
                        scope=service.relationship_scope,
                        now=now,
                        influence=influence,
                    )
                    return count or None

                coordinator.set_task(
                    "reflection_outreach",
                    bridge_reflection_outreach,
                )

                if fleet_discovery_enabled:
                    discovery = FleetDiscoveryCoordinator(
                        self._runtime.ops_service.registry,
                        candidate_notifier=create_fleet_candidate_notifier(
                            act_service=self._act_service,
                        ),
                    )

                    def discover_fleet_candidates(now):
                        result = discovery.run(fleet_discovery_source)
                        base = Path(self._configuration.state_path).parent
                        identities = DurableNodeIdentityRegistry(
                            base / "remote-identities.db"
                        )
                        endpoints = DurableEndpointPolicy(
                            base / "remote-endpoints.db"
                        )
                        try:
                            reconciled = FleetDiscoveryEnrollmentReconciler(
                                enrollment_service=(
                                    self._runtime.ops_service.enrollment
                                ),
                                identity_registry=identities,
                                endpoint_policy=endpoints,
                            ).reconcile(result)
                        finally:
                            identities.close()
                            endpoints.close()
                        count = (
                            len(result.created_host_ids)
                            + len(result.rejected_host_ids)
                            + len(reconciled.enrolled_host_ids)
                        )
                        return count or None

                    coordinator.set_task(
                        "fleet_discovery",
                        discover_fleet_candidates,
                        interval_seconds=float(
                            self._configuration.fleet_discovery.interval_seconds
                        ),
                    )

                if presentation_runtime_enabled:
                    def evaluate_avatar_presentation(now):
                        result = self._evaluate_contextual_presentation(
                            now=now,
                            refresh_environment=True,
                        )
                        return (
                            result
                            if result is not None and result.changed
                            else None
                        )

                    coordinator.set_task(
                        "avatar_presentation",
                        evaluate_avatar_presentation,
                        interval_seconds=900.0,
                    )

                def analyze_habits(now):
                    service = self._conversation_service
                    principal = (
                        service._principal_context()
                        if hasattr(service, "_principal_context")
                        else None
                    )
                    if principal is None:
                        return None
                    count = self._habit_continuity.analyze_conversation_patterns(
                        principal_id=principal.principal_id,
                        audience_id=principal.audience_id,
                        now=now,
                    )
                    return count or None

                def decay_habits(now):
                    service = self._conversation_service
                    principal = (
                        service._principal_context()
                        if hasattr(service, "_principal_context")
                        else None
                    )
                    if principal is None:
                        return None
                    count = self._habit_continuity.decay_patterns(
                        principal_id=principal.principal_id,
                        audience_id=principal.audience_id,
                        now=now,
                    )
                    return count or None

                def evaluate_expectations(now):
                    service = self._conversation_service
                    principal = (
                        service._principal_context()
                        if hasattr(service, "_principal_context")
                        else None
                    )
                    if principal is None:
                        return None
                    count = self._habit_continuity.evaluate_expectations(
                        principal_id=principal.principal_id,
                        audience_id=principal.audience_id,
                        now=now,
                    )
                    return count or None

                last_coverage_at = datetime.now(timezone.utc)

                def record_habit_coverage(now):
                    nonlocal last_coverage_at
                    service = self._conversation_service
                    principal = (
                        service._principal_context()
                        if hasattr(service, "_principal_context")
                        else None
                    )
                    if principal is None:
                        last_coverage_at = now
                        return None
                    self._habit_continuity.record_runtime_coverage(
                        principal_id=principal.principal_id,
                        audience_id=principal.audience_id,
                        started_at=last_coverage_at,
                        ended_at=now,
                    )
                    last_coverage_at = now
                    return True

                if habit_runtime_enabled:
                    coordinator.set_task(
                        "habit_observation",
                        record_habit_coverage,
                    )
                    coordinator.set_task(
                        "habit_analysis",
                        analyze_habits,
                    )
                    coordinator.set_task(
                        "habit_decay",
                        decay_habits,
                    )
                    coordinator.set_task(
                        "expectation_evaluation",
                        evaluate_expectations,
                    )
                runtime_id = getattr(self._runtime, "runtime_id", None)
                heartbeat_store = getattr(
                    self,
                    "_heartbeat_store",
                    None,
                )
                if runtime_id is not None and heartbeat_store is not None:
                    def publish_heartbeat(now, healthy):
                        runtime_state = getattr(
                            getattr(self._runtime, "state", None),
                            "value",
                            "ready" if healthy else "unknown",
                        )
                        heartbeat_store.publish(
                            ApplicationHeartbeat(
                                instance_id=str(runtime_id),
                                recorded_at=now,
                                ready=bool(
                                    healthy and runtime_state == "ready"
                                ),
                                runtime_state=runtime_state,
                                database_writable=True,
                                background_running=True,
                                detail=(
                                    "application background loop healthy"
                                    if healthy
                                    else "application background loop reported an error"
                                ),
                            )
                        )
                    coordinator.set_heartbeat(publish_heartbeat)
                    coordinator.start()
                    publish_heartbeat(
                        datetime.now(timezone.utc),
                        True,
                    )
                else:
                    coordinator.start()
                self._background = coordinator
                self._idle_worker = coordinator.idle

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
                lifecycle_worker.start()
                self._model_lifecycle_worker = lifecycle_worker
            return response
        except (
            SofiaRuntimeError,
            PresentationStoreError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as exc:
            raise SofiaApplicationError("Sofía application failed to start.") from exc

    def shutdown(self) -> None:
        """Stop idle inference *before* closing the shared cognitive runtime."""
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
        except (SofiaRuntimeError, PresentationStoreError, RuntimeError) as exc:
            raise SofiaApplicationError("Sofía application failed to shut down.") from exc
        finally:
            self._presentation_bundle = None
            self._presentation_routine = None
            self._wardrobe_studio = None
            self._conversation_service.close()
            ui_draft_store = getattr(
                self,
                "_ui_draft_store",
                None,
            )
            if ui_draft_store is not None:
                ui_draft_store.close()
