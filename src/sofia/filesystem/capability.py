from collections.abc import Callable

from sofia.capability.model import (
    Capability,
    CapabilityRequest,
)
from sofia.filesystem.inspector import FilesystemInspector
from sofia.filesystem.model import (
    FilesystemResult,
)


FILESYSTEM_INSPECT_CAPABILITY = Capability(
    name="filesystem.inspect",
    description=(
        "Perform bounded, read-only filesystem inspection "
        "inside the explicitly authorized Sofía filesystem scope."
    ),
)


class FilesystemCapability:
    """
    Adapter between the generic capability system and the existing
    read-only filesystem inspection subsystem.

    The inspector is obtained at execution time so runtime
    authorization and revocation remain authoritative.
    """

    def __init__(
        self,
        inspector_provider: Callable[[], FilesystemInspector],
    ) -> None:
        if not callable(inspector_provider):
            raise TypeError(
                "FilesystemCapability inspector_provider must be callable."
            )

        self._inspector_provider = inspector_provider

    @property
    def capability(self) -> Capability:
        return FILESYSTEM_INSPECT_CAPABILITY

    def execute(
        self,
        request: CapabilityRequest,
    ) -> FilesystemResult:
        if not isinstance(
            request,
            CapabilityRequest,
        ):
            raise TypeError(
                "FilesystemCapability request must be a "
                "CapabilityRequest."
            )

        if request.capability.name != (
            FILESYSTEM_INSPECT_CAPABILITY.name
        ):
            raise ValueError(
                "FilesystemCapability received an unsupported "
                "capability request."
            )

        operation = request.parameters.get("operation")

        if not isinstance(operation, str):
            raise ValueError(
                "FilesystemCapability requires an operation parameter."
            )

        inspector = self._inspector_provider()

        if not isinstance(
            inspector,
            FilesystemInspector,
        ):
            raise TypeError(
                "FilesystemCapability inspector_provider returned "
                "an invalid object."
            )

        if operation == "read_file":
            path = request.parameters.get("path")

            if not isinstance(path, str):
                raise ValueError(
                    "read_file requires a string path parameter."
                )

            return inspector.read_file(path)

        if operation == "list_directory":
            path = request.parameters.get(
                "path",
                ".",
            )

            if not isinstance(path, str):
                raise ValueError(
                    "list_directory path must be a string."
                )

            return inspector.list_directory(path)

        if operation == "search_files":
            pattern = request.parameters.get("pattern")

            if not isinstance(pattern, str):
                raise ValueError(
                    "search_files requires a string pattern parameter."
                )

            return inspector.search_files(pattern)

        raise ValueError(
            f"Unsupported filesystem operation: {operation}"
        )