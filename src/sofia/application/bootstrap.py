from sofia.composition.root import compose
from sofia.config.model import SofiaConfiguration
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
        self._runtime: SofiaRuntime = compose(configuration)

    @property
    def runtime(self) -> SofiaRuntime:
        return self._runtime

    def start(self) -> None:
        """
        Start the Sofía application.
        """

        try:
            self._runtime.start()
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