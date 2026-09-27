"""Application bootstrap and controlled lifecycle for Sofía."""
from __future__ import annotations

import os
from pathlib import Path

from sofia.avatar.presentation_store import PresentationStoreError
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
from sofia.application.fleet_runtime import configure_fleet_enrollment_notices
from sofia.application.memory_review import MemoryReviewService
from sofia.application.conversation_learning import ConversationLearningCoordinator
from sofia.application.release_runtime import create_release_manager
from sofia.composition.root import compose
from sofia.config.model import SofiaConfiguration
from sofia.conversation.store import ConversationStore
from sofia.cognition.model import CognitiveResponse
from sofia.interaction.opt_in_service import OptInInteractionConversationService
from sofia.runtime.internal_workspace import normalize_runtime_workspace_awareness
from sofia.run.heartbeat import ApplicationHeartbeat, ApplicationHeartbeatStore
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
        conversation_store = ConversationStore(configuration.state_path)
        self._conversation_service: ConversationService = OptInInteractionConversationService(
            runtime=self._runtime, conversation_store=conversation_store,
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
        self._presentation_bundle: PresentationRuntimeBundle | None = None
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

    @property
    def text_ui(self) -> UITextClient:
        """Return the local text-first UI over the canonical conversation."""
        return self._text_ui

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
            if self._release_manager is not None:
                self._release_manager.reconcile_pointer()
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
            # Filter internal database noise in *both* pending awareness and
            # the runtime's cognitive context before the first model call.
            # The unfiltered snapshot stays preserved in the observation store.
            normalize_runtime_workspace_awareness(self._runtime)
            self._conversation_service.open()
            self._conversation_service.start(session_id=session_id)
            response = self._conversation_service.deliver_pending_awareness()
            background_needed = (
                enabled
                or habit_enabled
                or self._act_service.delivery_enabled
            )
            if enabled and self._runtime.personality is None:
                raise SofiaApplicationError(
                    "Idle reflection requires a loaded personality."
                )
            if background_needed:
                if not isinstance(self._conversation_service, EmotionalConversationService):
                    raise SofiaApplicationError("Idle reflection requires an emotional conversation service.")
                coordinator = ApplicationBackgroundCoordinator(
                    service=self._conversation_service,
                    state_path=Path(self._configuration.state_path),
                    reflection_enabled=enabled,
                )
                coordinator.set_act_delivery(
                    lambda now: self._act_service.deliver_one(
                        now=now,
                        busy=False,
                    )
                )
                runtime_id = self._runtime.runtime_id
                if runtime_id is None:
                    raise SofiaApplicationError(
                        "RUN heartbeat requires a live runtime ID."
                    )
                def publish_heartbeat(now, healthy):
                    self._heartbeat_store.publish(
                        ApplicationHeartbeat(
                            instance_id=str(runtime_id),
                            recorded_at=now,
                            ready=bool(
                                healthy
                                and self._runtime.state.value == "ready"
                            ),
                            runtime_state=self._runtime.state.value,
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
                    __import__("datetime").datetime.now(
                        __import__("datetime").timezone.utc
                    ),
                    True,
                )
                self._background = coordinator
                self._idle_worker = coordinator.idle
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
        try:
            bundle = getattr(self, "_presentation_bundle", None)
            if bundle is not None:
                bundle.store.save(bundle.authority)
            self._runtime.shutdown()
        except (SofiaRuntimeError, PresentationStoreError, RuntimeError) as exc:
            raise SofiaApplicationError("Sofía application failed to shut down.") from exc
        finally:
            self._presentation_bundle = None
            self._conversation_service.close()
            ui_draft_store = getattr(
                self,
                "_ui_draft_store",
                None,
            )
            if ui_draft_store is not None:
                ui_draft_store.close()
