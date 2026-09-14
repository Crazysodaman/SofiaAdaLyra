import re
from pathlib import Path

from sofia.authorization.evaluator import (
    FilesystemAuthorizationEvaluator,
)
from sofia.filesystem.model import (
    FilesystemOperation,
    FilesystemResult,
)
from sofia.runtime.runtime import SofiaRuntime


class FilesystemOrchestrator:
    """
    Translate supported natural-language filesystem requests into
    bounded filesystem capability operations.

    The orchestrator does not perform filesystem operations directly.
    It coordinates authorization and delegates actual inspection to
    SofiaRuntime's filesystem capability.
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
        self._authorization_evaluator = (
            FilesystemAuthorizationEvaluator(
                scope=runtime.filesystem_inspector.root,
            )
        )

    def process(
        self,
        content: str,
    ) -> tuple[FilesystemResult, ...]:
        """
        Process filesystem-related intent.

        Authorization statements are handled first and do not
        automatically execute an inspection operation.

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

        authorization = (
            self._authorization_evaluator.evaluate(
                content
            )
        )

        if authorization is not None:
            self._runtime.authorize_filesystem(
                authorization
            )
            return ()

        operation_request = self._parse_operation(
            content
        )

        if operation_request is None:
            return ()

        operation, target = operation_request

        inspector = self._runtime.filesystem_inspector

        if operation is FilesystemOperation.LIST_DIRECTORY:
            return (
                inspector.list_directory(target),
            )

        if operation is FilesystemOperation.INSPECT_PATH:
            return (
                inspector.inspect_path(target),
            )

        if operation is FilesystemOperation.READ_FILE:
            return (
                inspector.read_file(target),
            )

        if operation is FilesystemOperation.SEARCH_FILES:
            return (
                inspector.search_files(target),
            )

        return ()

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
            return (
                FilesystemOperation.INSPECT_PATH,
                self._clean_argument(
                    match.group(1)
                ),
            )

        match = self._CHECK_PATH_PATTERN.match(
            normalized
        )

        if match is not None:
            argument = self._clean_argument(
                match.group(1)
            )

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