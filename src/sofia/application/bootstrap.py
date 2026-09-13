from sofia.composition.root import (
    compose,
    compose_conversation_service,
)
from sofia.config.model import SofiaConfiguration
from sofia.runtime.runtime import SofiaRuntime, SofiaRuntimeError
from sofia.application.conversation_service import ConversationService


class SofiaApplicationError(RuntimeError):
    """Raised when application bootstrap or lifecycle fails."""


class SofiaApplication:
    """
    Canonical application boundary for Sofía.

    Owns application-level orchestration only.
    Runtime remains responsible for Sofía's runtime lifecycle.
    """

    def __init__(
        self,
        configuration: SofiaConfiguration,
    ) -> None:
        self._configuration = configuration
        self._runtime: SofiaRuntime = compose(
            configuration
        )
        self._conversation_service: ConversationService = (
            compose_conversation_service(
                configuration,
                self._runtime,
            )
        )

    @property
    def runtime(self) -> SofiaRuntime:
        return self._runtime

    @property
    def conversation(self) -> ConversationService:
        return self._conversation_service

    def start(self) -> None:
        """
        Start the Sofía application.
        """

        try:
            self._runtime.start()
            self._conversation_service.start()
        except SofiaRuntimeError as exc:
            raise SofiaApplicationError(
                "Sofía application failed to start."
            ) from exc

    def shutdown(self) -> None:
        """
        Shut down the Sofía application.
        """

        try:
            self._runtime.shutdown()
        except SofiaRuntimeError as exc:
            raise SofiaApplicationError(
                "Sofía application failed to shut down."
            ) from exc