import re
from pathlib import Path

from sofia.capability.gateway import CapabilityGateway
from sofia.capability.model import (
    CapabilityProposal,
    CapabilityResultKind,
)
from sofia.filesystem.model import (
    FilesystemOperation,
    FilesystemResult,
    FilesystemResultKind,
)
from sofia.runtime.runtime import SofiaRuntime


class FilesystemOrchestrator:
    """
    Translate supported natural-language filesystem requests into
    bounded filesystem capability operations.

    The orchestrator does not grant authorization and does not perform
    filesystem operations directly. Authorization is established only at
    an authenticated application boundary; this parser delegates bounded
    inspection requests to SofiaRuntime's filesystem capability.
    """

    _READ_PATTERN = re.compile(
        r"^(?:please\s+)?read(?:\s+file)?\s+(.+)$",
        re.IGNORECASE,
    )

    _INSPECT_PATTERN = re.compile(
        r"^(?:please\s+)?inspect\s+(?:path\s+)?(.+)$",
        re.IGNORECASE,
    )

    _CHECK_PATH_PATTERN = re.compile(
        r"^(?:please\s+)?check\s+(?:path\s+)?(.+)$",
        re.IGNORECASE,
    )

    _SEARCH_PATTERN = re.compile(
        r"^(?:please\s+)?(?:search|find)\s+"
        r"(?:files?\s+)?(?:for|matching)\s+(.+)$",
        re.IGNORECASE,
    )

    _LIST_PATTERN = re.compile(
        r"^(?:please\s+)?"
        r"(?:list|show)\s+(?:the\s+)?"
        r"(?:files|directory|contents)"
        r"(?:\s+of\s+(.+))?$",
        re.IGNORECASE,
    )

    _OWN_FILES_PHRASES = (
        "check your own files",
        "check your files",
        "inspect your own files",
        "inspect your files",
        "list your files",
        "list your directory",
        "show your files",
        "show your directory",
    )

    def __init__(
        self,
        runtime: SofiaRuntime,
    ) -> None:
        if not isinstance(runtime, SofiaRuntime):
            raise TypeError(
                "FilesystemOrchestrator runtime must be a SofiaRuntime."
            )

        self._runtime = runtime

    def process(
        self,
        content: str,
    ) -> tuple[FilesystemResult, ...]:
        """
        Process filesystem-related intent.

        Authorization is handled by the canonical CapabilitySystem boundary,
        not by this parser or the inspector's legacy transient grant bit.

        Non-filesystem requests return an empty tuple.
        """

        if not isinstance(content, str):
            raise TypeError(
                "FilesystemOrchestrator content must be a string."
            )

        normalized = " ".join(
            content.strip().lower().split()
        )

        if not normalized:
            return ()

        operation_request = self._parse_operation(
            content
        )

        if operation_request is None:
            return ()

        operation, target = operation_request

        parameters: dict[str, str] = {"operation": operation.value}
        if operation is FilesystemOperation.SEARCH_FILES:
            parameters["pattern"] = str(target)
        else:
            parameters["path"] = str(target)

        result = CapabilityGateway(
            self._runtime.capability_system
        ).execute(
            CapabilityProposal(
                capability_name="filesystem.inspect",
                parameters=parameters,
                requested_scope=self._runtime.configuration.filesystem_root,
                rationale=(
                    "Read-only repository inspection requested through the "
                    "conversation filesystem orchestrator."
                ),
            )
        )
        if (
            result.kind is CapabilityResultKind.SUCCESS
            and isinstance(result.evidence, FilesystemResult)
        ):
            return (result.evidence,)

        kind = (
            FilesystemResultKind.UNAUTHORIZED
            if result.kind in {
                CapabilityResultKind.UNAUTHORIZED,
                CapabilityResultKind.DENIED,
            }
            else FilesystemResultKind.UNAVAILABLE
        )
        return (
            FilesystemResult(
                operation=operation,
                kind=kind,
                path=Path(str(target)),
                message=(
                    result.error
                    or "Central filesystem capability could not complete the request."
                ),
            ),
        )

    @staticmethod
    def _looks_like_filesystem_target(argument: str) -> bool:
        """Reject generic "inspect X" prose that is not plausibly a path.

        The legacy filesystem parser runs before cognition. Without this guard,
        requests such as "inspect the local network interfaces" are interpreted
        as repository-relative paths and can poison the later operational reply
        with a bogus filesystem authorization result.
        """
        value = argument.strip()
        lowered = value.casefold()
        if not value:
            return False
        if lowered in {
            ".", "..", "your files", "your own files", "your directory",
            "your own directory", "repository", "repo", "codebase",
        }:
            return True
        if any(token in lowered for token in (
            " file", "files", " folder", "folders", " directory", "directories",
            " path", "filesystem", "repository", "repo", "codebase",
        )):
            return True
        if value.startswith(("./", "../", ".\\", "..\\", "\\", "/")):
            return True
        if re.match(r"^[A-Za-z]:[\\/]", value):
            return True
        if "/" in value or "\\" in value:
            return True
        # Common filename form such as README.md or pyproject.toml.
        if re.fullmatch(r"[A-Za-z0-9_.-]+\.[A-Za-z0-9_.-]+", value):
            return True
        return False

    @staticmethod
    def _project_area_alias(argument: str) -> str:
        normalized = " ".join(
            argument.strip().casefold().replace("_", " ").split()
        )
        aliases = {
            "avatar wardrobe": "src/sofia/avatar",
            "avatar/wardrobe": "src/sofia/avatar",
            "avatar wardrobe folder": "src/sofia/avatar",
            "wardrobe": "src/sofia/avatar",
        }
        return aliases.get(normalized, argument)

    def _parse_operation(
        self,
        content: str,
    ) -> tuple[
        FilesystemOperation,
        Path | str,
    ] | None:
        normalized = " ".join(
            content.strip().split()
        )

        lowered = normalized.lower()

        if any(
            phrase == lowered
            for phrase in self._OWN_FILES_PHRASES
        ):
            return (
                FilesystemOperation.LIST_DIRECTORY,
                ".",
            )

        match = self._READ_PATTERN.match(
            normalized
        )

        if match is not None:
            return (
                FilesystemOperation.READ_FILE,
                self._clean_argument(
                    match.group(1)
                ),
            )

        match = self._INSPECT_PATTERN.match(
            normalized
        )

        if match is not None:
            argument = self._clean_argument(match.group(1))
            if not self._looks_like_filesystem_target(argument):
                return None
            if not self._looks_like_filesystem_target(argument):
                return None
            return (
                FilesystemOperation.INSPECT_PATH,
                argument,
            )

        match = self._CHECK_PATH_PATTERN.match(
            normalized
        )

        if match is not None:
            argument = self._clean_argument(
                match.group(1)
            )
            folder_match = re.fullmatch(
                r"(?:the\s+)?(?:folder|directory)\s*:?\s*(.+)",
                argument,
                re.IGNORECASE,
            )
            if folder_match is not None:
                target = self._project_area_alias(
                    self._clean_argument(folder_match.group(1))
                )
                return (
                    FilesystemOperation.LIST_DIRECTORY,
                    target,
                )

            argument = self._project_area_alias(argument)

            if argument.lower() in {
                "your files",
                "your own files",
                "your directory",
                "your own directory",
            }:
                return (
                    FilesystemOperation.LIST_DIRECTORY,
                    ".",
                )

            return (
                FilesystemOperation.INSPECT_PATH,
                argument,
            )

        match = self._SEARCH_PATTERN.match(
            normalized
        )

        if match is not None:
            return (
                FilesystemOperation.SEARCH_FILES,
                self._clean_argument(
                    match.group(1)
                ),
            )

        match = self._LIST_PATTERN.match(
            normalized
        )

        if match is not None:
            target = match.group(1)

            if target is None:
                target = "."

            return (
                FilesystemOperation.LIST_DIRECTORY,
                self._clean_argument(target),
            )

        return None

    @staticmethod
    def _clean_argument(
        argument: str,
    ) -> str:
        argument = argument.strip()

        if (
            len(argument) >= 2
            and argument[0] == argument[-1]
            and argument[0] in {
                "\"",
                "'",
                "`",
            }
        ):
            argument = argument[1:-1]

        return argument.strip()