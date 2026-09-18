from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sofia.capability.gateway import CapabilityGateway
from sofia.capability.model import CapabilityResult
from sofia.capability.proposal import CapabilityProposal
from sofia.cognition.model import (
    CognitiveToolCall,
    CognitiveToolDefinition,
)
from sofia.filesystem.model import FilesystemResult
from sofia.codebase.evidence import format_codebase_evidence
from sofia.codebase.model import CodebaseInspectionEvidence


class CognitiveToolError(Exception):
    """Raised when a cognitive tool call cannot be dispatched."""


@dataclass(frozen=True)
class CognitiveToolBinding:
    """
    Binds a provider-visible cognitive tool to a canonical capability.

    The binding is host-owned. The cognitive provider cannot modify it.
    """

    definition: CognitiveToolDefinition
    capability_name: str
    requested_scope: Any = None
    fixed_parameters: tuple[tuple[str, Any], ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(
            self.definition,
            CognitiveToolDefinition,
        ):
            raise TypeError(
                "CognitiveToolBinding definition must be a "
                "CognitiveToolDefinition."
            )

        if not isinstance(self.capability_name, str):
            raise TypeError(
                "CognitiveToolBinding capability_name must be a string."
            )

        if not self.capability_name.strip():
            raise ValueError(
                "CognitiveToolBinding capability_name must not be empty."
            )

        if not isinstance(self.fixed_parameters, tuple):
            raise TypeError(
                "CognitiveToolBinding fixed_parameters must be a tuple."
            )

        for item in self.fixed_parameters:
            if (
                not isinstance(item, tuple)
                or len(item) != 2
                or not isinstance(item[0], str)
            ):
                raise TypeError(
                    "CognitiveToolBinding fixed_parameters must contain "
                    "(str, value) pairs."
                )


class CognitiveToolDispatcher:
    """
    Converts structured cognitive tool calls into capability proposals.

    This class does not execute capability handlers directly.
    All execution goes through CapabilityGateway.
    """

    def __init__(
        self,
        gateway: CapabilityGateway,
        bindings: tuple[CognitiveToolBinding, ...],
    ) -> None:
        if not isinstance(gateway, CapabilityGateway):
            raise TypeError(
                "CognitiveToolDispatcher gateway must be a "
                "CapabilityGateway."
            )

        if not isinstance(bindings, tuple):
            raise TypeError(
                "CognitiveToolDispatcher bindings must be a tuple."
            )

        self._gateway = gateway

        by_name: dict[str, CognitiveToolBinding] = {}

        for binding in bindings:
            if not isinstance(
                binding,
                CognitiveToolBinding,
            ):
                raise TypeError(
                    "CognitiveToolDispatcher bindings must contain "
                    "CognitiveToolBinding instances."
                )

            if binding.definition.name in by_name:
                raise ValueError(
                    "Duplicate cognitive tool name: "
                    f"{binding.definition.name}"
                )

            by_name[binding.definition.name] = binding

        self._bindings = by_name

    @property
    def definitions(self) -> tuple[CognitiveToolDefinition, ...]:
        return tuple(
            binding.definition
            for binding in self._bindings.values()
        )

    def dispatch(
        self,
        tool_call: CognitiveToolCall,
    ) -> CapabilityResult:
        if not isinstance(
            tool_call,
            CognitiveToolCall,
        ):
            raise TypeError(
                "CognitiveToolDispatcher tool_call must be a "
                "CognitiveToolCall."
            )

        try:
            binding = self._bindings[tool_call.name]
        except KeyError as exc:
            raise CognitiveToolError(
                f"Unknown cognitive tool: {tool_call.name}"
            ) from exc

        parameters = dict(tool_call.arguments)

        for key, value in binding.fixed_parameters:
            if key in parameters and parameters[key] != value:
                raise CognitiveToolError(
                    f"Tool {tool_call.name!r} attempted to override "
                    f"host-controlled parameter {key!r}."
                )

            parameters[key] = value

        proposal = CapabilityProposal(
            capability_name=binding.capability_name,
            parameters=parameters,
            rationale=(
                "Capability invocation requested by the cognitive "
                f"tool {tool_call.name!r}."
            ),
            requested_scope=binding.requested_scope,
        )

        return self._gateway.execute(proposal)

    @staticmethod
    def format_result(
        tool_call: CognitiveToolCall,
        result: CapabilityResult,
    ) -> str:
        lines = [
            "COGNITIVE TOOL RESULT",
            f"Tool: {tool_call.name}",
            f"Capability: {result.capability}",
            f"Result: {result.kind.value}",
        ]

        if result.error is not None:
            lines.append(
                f"Error: {result.error}"
            )

        if result.evidence is not None:
            lines.extend(
                [
                    "",
                    "OBSERVED EVIDENCE",
                ]
            )

            evidence = result.evidence

            if isinstance(
                evidence,
                FilesystemResult,
            ):
                lines.extend(
                    CognitiveToolDispatcher._format_filesystem_result(
                        evidence
                    )
                )

            elif isinstance(
                evidence,
                CodebaseInspectionEvidence,
            ):
                lines.append(
                    format_codebase_evidence(evidence)
                )

            else:
                lines.append(
                    str(evidence)
                )

        return "\n".join(lines)

    @staticmethod
    def _format_filesystem_result(
        result: FilesystemResult,
    ) -> list[str]:
        lines = [
            f"Operation: {result.operation.value}",
            f"Kind: {result.kind.value}",
            f"Path: {result.path}",
            f"Message: {result.message}",
        ]

        if result.entries:
            lines.append("Entries:")

            for entry in result.entries:
                lines.append(
                    f"- {entry}"
                )

        if result.content is not None:
            lines.extend(
                [
                    "File content:",
                    result.content,
                ]
            )

        return lines


def create_default_tool_bindings(
    filesystem_root: Path,
) -> tuple[CognitiveToolBinding, ...]:
    """
    Construct the host-owned cognitive tools exposed to the LLM.

    These tools are intentionally read-only.
    """

    if not isinstance(filesystem_root, Path):
        raise TypeError(
            "filesystem_root must be a Path."
        )

    root = filesystem_root.resolve()

    return (
        CognitiveToolBinding(
            definition=CognitiveToolDefinition(
                name="inspect_file",
                description=(
                    "Read one UTF-8 source or text file inside "
                    "Sofía's authorized filesystem scope. "
                    "Use this when exact file contents are required. "
                    "This tool is read-only."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": (
                                "Repository-relative file path."
                            ),
                        },
                    },
                    "required": ["path"],
                    "additionalProperties": False,
                },
            ),
            capability_name="filesystem.inspect",
            requested_scope=root,
            fixed_parameters=(
                ("operation", "read_file"),
            ),
        ),
        CognitiveToolBinding(
            definition=CognitiveToolDefinition(
                name="inspect_directory",
                description=(
                    "List entries in a directory inside Sofía's "
                    "authorized filesystem scope. "
                    "This tool is read-only."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": (
                                "Repository-relative directory path. "
                                "Defaults to the repository root."
                            ),
                        },
                    },
                    "additionalProperties": False,
                },
            ),
            capability_name="filesystem.inspect",
            requested_scope=root,
            fixed_parameters=(
                ("operation", "list_directory"),
            ),
        ),
        CognitiveToolBinding(
            definition=CognitiveToolDefinition(
                name="search_code",
                description=(
                    "Search the authorized codebase for files matching "
                    "a pathlib filename pattern, such as '*.py' or "
                    "'gateway.py'. This is read-only."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": (
                                "Filename pattern to search for."
                            ),
                        },
                    },
                    "required": ["pattern"],
                    "additionalProperties": False,
                },
            ),
            capability_name="filesystem.inspect",
            requested_scope=root,
            fixed_parameters=(
                ("operation", "search_files"),
            ),
        ),
        CognitiveToolBinding(
            definition=CognitiveToolDefinition(
                name="inspect_codebase",
                description=(
                    "Perform bounded, read-only structural inspection "
                    "of the authorized Sofía codebase, including Python "
                    "modules, symbols, imports, and relationships."
                ),
                parameters={
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
            ),
            capability_name="codebase.inspect",
            requested_scope=root,
        ),
    )