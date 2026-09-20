"""Application bootstrap and controlled lifecycle for Sofía."""
from __future__ import annotations

import os

from sofia.application.emotional_conversation import EmotionalConversationService
from sofia.application.conversation_service import ConversationService
from sofia.application.idle_reflection import IdleReflectionWorker
from sofia.composition.root import compose
from sofia.config.model import SofiaConfiguration
from sofia.conversation.store import ConversationStore
from sofia.cognition.model import CognitiveResponse
from sofia.runtime.runtime import SofiaRuntime, SofiaRuntimeError


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
        self._conversation_service: ConversationService = EmotionalConversationService(
            runtime=self._runtime, conversation_store=conversation_store,
        )
        self._idle_worker: IdleReflectionWorker | None = None

    @property
    def runtime(self) -> SofiaRuntime:
        return self._runtime

    @property
    def conversation(self) -> ConversationService:
        return self._conversation_service

    @property
    def idle_reflection_worker(self) -> IdleReflectionWorker | None:
        return self._idle_worker

    def start(self, session_id: str | None = None) -> CognitiveResponse | None:
        """Start the runtime and session, then optionally start idle reflection.

        When session_id is omitted, create a new conversation. When supplied,
        explicitly resume that persisted conversation. Startup awareness runs
        before any optional idle model inference; no background work is claimed
        for periods when this process was not running.
        """
        try:
            enabled = _idle_reflections_enabled()
            self._runtime.start()
            self._conversation_service.open()
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
            return response
        except (SofiaRuntimeError, RuntimeError, TypeError, ValueError) as exc:
            raise SofiaApplicationError("Sofía application failed to start.") from exc

    def shutdown(self) -> None:
        """Stop idle inference *before* closing the shared cognitive runtime."""
        worker = self._idle_worker
        if worker is not None:
            try:
                worker.stop()
            except RuntimeError as exc:
                # Do not shut down a runtime while its model request may be live.
                raise SofiaApplicationError("Idle reflection has not stopped safely.") from exc
            self._idle_worker = None
        try:
            self._runtime.shutdown()
        except SofiaRuntimeError as exc:
            raise SofiaApplicationError("Sofía application failed to shut down.") from exc
        finally:
            self._conversation_service.close()
