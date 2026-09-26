"""Application bootstrap and controlled lifecycle for Sofía."""
from __future__ import annotations

from datetime import datetime, timezone
import os

from sofia.avatar.presentation_store import PresentationStoreError
from sofia.avatar.runtime_state import (
    PresentationRuntimeBundle,
    load_or_bootstrap_presentation,
)
from sofia.application.emotional_conversation import EmotionalConversationService
from sofia.application.conversation_service import ConversationService
from sofia.application.idle_reflection import IdleReflectionWorker
from sofia.composition.root import compose
from sofia.config.model import SofiaConfiguration
from sofia.conversation.store import ConversationStore
from sofia.cognition.model import CognitiveResponse
from sofia.interaction.opt_in_service import OptInInteractionConversationService
from sofia.runtime.internal_workspace import normalize_runtime_workspace_awareness
from sofia.runtime.model import RuntimeState
from sofia.runtime.runtime import SofiaRuntime, SofiaRuntimeError
from sofia.ui.drafts import UIDraftStore
from sofia.ui.text import UITextClient


class SofiaApplicationError(RuntimeError):
    """Raised when application bootstrap or lifecycle fails."""


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
        self._runtime: SofiaRuntime = compose(configuration)
        conversation_store = ConversationStore(configuration.state_path)
        self._conversation_service: ConversationService = OptInInteractionConversationService(
            runtime=self._runtime, conversation_store=conversation_store,
        )
        self._idle_worker: IdleReflectionWorker | None = None
        self._presentation_bundle: PresentationRuntimeBundle | None = None
        self._ui_draft_store = UIDraftStore(configuration.state_path)
        self._text_ui = UITextClient(
            conversation=self._conversation_service,
            drafts=self._ui_draft_store,
            client_id="local-text",
        )

    @property
    def runtime(self) -> SofiaRuntime:
        return self._runtime

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
        if self._runtime.state not in (RuntimeState.CREATED, RuntimeState.STOPPED):
            raise SofiaApplicationError(
                "Sofía application can only start from CREATED or STOPPED."
            )

        control = self._runtime.control_plane
        lifecycle = None
        conversation_opened = False
        ui_opened = False
        try:
            enabled = _idle_reflections_enabled()
            ui_draft_store = getattr(
                self,
                "_ui_draft_store",
                None,
            )
            if ui_draft_store is not None:
                ui_draft_store.open()
                ui_opened = True

            # ConversationStore creates the canonical message schema during
            # application construction, so RUN can open before runtime startup.
            control.open()
            lifecycle = control.run_lifecycle_store
            lifecycle.begin_start(at=datetime.now(timezone.utc))

            self._runtime.start()
            lifecycle.mark_recovering(
                at=datetime.now(timezone.utc),
                detail="runtime core started; reconciling application state",
            )
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
            conversation_opened = True
            self._conversation_service.start(session_id=session_id)
            response = self._conversation_service.deliver_pending_awareness()
            if enabled and self._runtime.personality is not None:
                if not isinstance(self._conversation_service, EmotionalConversationService):
                    raise SofiaApplicationError("Idle reflection requires an emotional conversation service.")
                worker = IdleReflectionWorker(
                    service=self._conversation_service,
                    state_path=self._configuration.state_path,
                )
                worker.start()
                self._idle_worker = worker

            lifecycle.mark_ready(at=datetime.now(timezone.utc))
            return response
        except (
            SofiaRuntimeError,
            PresentationStoreError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as exc:
            if lifecycle is not None:
                try:
                    lifecycle.mark_failed(
                        at=datetime.now(timezone.utc),
                        detail=f"startup failed: {type(exc).__name__}",
                    )
                except Exception:
                    pass

            worker = getattr(self, "_idle_worker", None)
            if worker is not None:
                try:
                    worker.stop()
                except Exception:
                    pass
                self._idle_worker = None

            if self._runtime.state is RuntimeState.READY:
                try:
                    self._runtime.shutdown()
                except Exception:
                    pass

            self._presentation_bundle = None
            if control.opened:
                control.close()
            if conversation_opened:
                try:
                    self._conversation_service.close()
                except Exception:
                    pass
            if ui_opened:
                ui_draft_store = getattr(self, "_ui_draft_store", None)
                if ui_draft_store is not None:
                    try:
                        ui_draft_store.close()
                    except Exception:
                        pass
            raise SofiaApplicationError("Sofía application failed to start.") from exc

    def shutdown(self) -> None:
        """Drain background work, stop the runtime, and persist RUN lifecycle."""
        if self._runtime.state is not RuntimeState.READY:
            raise SofiaApplicationError(
                "Sofía application can only shut down from READY."
            )

        control = self._runtime.control_plane
        lifecycle = (
            control.run_lifecycle_store
            if control.opened
            else None
        )
        if lifecycle is not None:
            lifecycle.begin_drain(at=datetime.now(timezone.utc))

        worker = getattr(self, "_idle_worker", None)
        if worker is not None:
            try:
                worker.stop()
            except RuntimeError as exc:
                if lifecycle is not None:
                    lifecycle.mark_failed(
                        at=datetime.now(timezone.utc),
                        detail="idle reflection did not stop safely",
                    )
                raise SofiaApplicationError("Idle reflection has not stopped safely.") from exc
            self._idle_worker = None

        try:
            if lifecycle is not None:
                lifecycle.begin_stop(at=datetime.now(timezone.utc))
            bundle = getattr(self, "_presentation_bundle", None)
            if bundle is not None:
                bundle.store.save(bundle.authority)
            self._runtime.shutdown()
            if lifecycle is not None:
                lifecycle.mark_stopped(at=datetime.now(timezone.utc))
        except (SofiaRuntimeError, PresentationStoreError, RuntimeError) as exc:
            if lifecycle is not None:
                try:
                    lifecycle.mark_failed(
                        at=datetime.now(timezone.utc),
                        detail=f"shutdown failed: {type(exc).__name__}",
                    )
                except Exception:
                    pass
            raise SofiaApplicationError("Sofía application failed to shut down.") from exc
        finally:
            if control.opened:
                control.close()
            self._presentation_bundle = None
            self._conversation_service.close()
            ui_draft_store = getattr(
                self,
                "_ui_draft_store",
                None,
            )
            if ui_draft_store is not None:
                ui_draft_store.close()
