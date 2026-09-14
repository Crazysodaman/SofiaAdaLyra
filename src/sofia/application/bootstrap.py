from sofia.application.conversation_service import ConversationService
from sofia.composition.root import compose
from sofia.config.model import SofiaConfiguration
from sofia.conversation.store import ConversationStore
from sofia.runtime.runtime import SofiaRuntime, SofiaRuntimeError


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

        conversation_store = ConversationStore(
            configuration.state_path
        )

        self._conversation_service: ConversationService = (
            ConversationService(
                runtime=self._runtime,
                conversation_store=conversation_store,
            )
        )

    @property
    def runtime(self) -> SofiaRuntime:
        return self._runtime

    @property
    def conversation(self) -> ConversationService:
        return self._conversation_service

    def start(
        self,
        session_id: str | None = None,
    ) -> None:
        """
        Start the Sofía application.

        When session_id is omitted, a new conversation is created.
        When session_id is provided, that persisted conversation
        is explicitly resumed.
        """

        try:
            self._runtime.start()
            self._conversation_service.open()
            self._conversation_service.start(
                session_id=session_id,
            )
        except (
            SofiaRuntimeError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as exc:
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
        finally:
            self._conversation_service.close()