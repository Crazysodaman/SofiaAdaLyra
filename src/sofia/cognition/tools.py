from dataclasses import asdict,dataclass,is_dataclass
from pathlib import Path
from enum import Enum
import json
from typing import Any

from sofia.authority.model import Authority
from sofia.capability.gateway import CapabilityGateway
from sofia.capability.model import CapabilityResult
from sofia.capability.model import CapabilityProposal
from sofia.cognition.model import (
    CognitiveToolCall,
    CognitiveToolDefinition,
)
from sofia.codebase.evidence import format_codebase_evidence
from sofia.codebase.model import CodebaseInspectionEvidence
from sofia.filesystem.model import FilesystemResult
from sofia.social.model import PrincipalContext
from sofia.safe.permissions import (
    PermissionLevel,
    capability_permission_policy,
)


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
    include_principal_metadata: bool = False
    produces_execution_receipt: bool = False
    execution_receipt_evidence_match: tuple[str, Any] | None = None

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

        if not isinstance(self.include_principal_metadata, bool):
            raise TypeError(
                "CognitiveToolBinding include_principal_metadata must be boolean."
            )

        if not isinstance(self.produces_execution_receipt, bool):
            raise TypeError(
                "CognitiveToolBinding produces_execution_receipt must be boolean."
            )

        if self.execution_receipt_evidence_match is not None:
            match = self.execution_receipt_evidence_match
            if (
                not isinstance(match, tuple)
                or len(match) != 2
                or not isinstance(match[0], str)
                or not match[0].strip()
            ):
                raise TypeError(
                    "CognitiveToolBinding execution_receipt_evidence_match "
                    "must be None or a (nonempty str, value) pair."
                )
            if not self.produces_execution_receipt:
                raise ValueError(
                    "execution_receipt_evidence_match requires "
                    "produces_execution_receipt=True."
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

    Tool definitions exposed to the cognitive engine are filtered
    against the authority governing the current cognitive operation.
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
        """
        Return every host-known tool definition.

        This property is retained for host-side inspection and
        compatibility. CognitiveSystem must use
        definitions_for_authority() when constructing an LLM request.
        """

        return tuple(
            binding.definition
            for binding in self._bindings.values()
        )

    def definitions_for_authority(
        self,
        authority: Authority,
        *,
        allowed_capabilities: tuple[str, ...] | None = None,
    ) -> tuple[CognitiveToolDefinition, ...]:
        """
        Return only tool definitions authorized for the current
        cognitive operation.

        Unauthorized tools are removed before the provider receives
        the cognitive request.
        """

        if not isinstance(authority, Authority):
            raise TypeError(
                "CognitiveToolDispatcher authority must be an Authority."
            )

        if allowed_capabilities is not None:
            if not isinstance(allowed_capabilities, tuple):
                raise TypeError(
                    "allowed_capabilities must be a tuple or None"
                )
            allowed = set()
            for capability in allowed_capabilities:
                if not isinstance(capability, str) or not capability.strip():
                    raise ValueError(
                        "allowed_capabilities must contain nonempty strings"
                    )
                allowed.add(capability)
        else:
            allowed = None

        return tuple(
            binding.definition
            for binding in self._bindings.values()
            if authority.can_use_capability(
                binding.capability_name
            )
            and (
                allowed is None
                or binding.capability_name in allowed
            )
        )

    def _automatic_calls_for_levels(
        self,
        authority: Authority,
        *,
        allowed_capabilities: tuple[str, ...],
        levels: frozenset[PermissionLevel],
        call_id_prefix: str,
    ) -> tuple[CognitiveToolCall, ...]:
        """Build host-selected no-argument calls for explicitly allowed levels."""
        if not isinstance(authority, Authority):
            raise TypeError("authority must be Authority")
        if not isinstance(allowed_capabilities, tuple):
            raise TypeError("allowed_capabilities must be a tuple")
        if not isinstance(levels, frozenset) or not levels:
            raise TypeError("levels must be a nonempty frozenset")
        if not isinstance(call_id_prefix, str) or not call_id_prefix.strip():
            raise ValueError("call_id_prefix must be a nonempty string")

        allowed = set(allowed_capabilities)
        calls: list[CognitiveToolCall] = []
        for binding in self._bindings.values():
            capability = binding.capability_name
            if capability not in allowed:
                continue
            if capability_permission_policy(capability).level not in levels:
                continue
            if not authority.can_use_capability(capability):
                continue
            schema = binding.definition.parameters
            required = schema.get("required", ()) if isinstance(schema, dict) else ()
            if required:
                continue
            calls.append(
                CognitiveToolCall(
                    name=binding.definition.name,
                    arguments={},
                    call_id=f"{call_id_prefix}:{binding.definition.name}",
                )
            )
        return tuple(calls)

    def automatic_read_only_calls(
        self,
        authority: Authority,
        *,
        allowed_capabilities: tuple[str, ...],
    ) -> tuple[CognitiveToolCall, ...]:
        """Build host-selected no-argument Level-1 observation calls."""
        return self._automatic_calls_for_levels(
            authority,
            allowed_capabilities=allowed_capabilities,
            levels=frozenset((PermissionLevel.OBSERVE_READ,)),
            call_id_prefix="host-read",
        )

    def automatic_evidence_calls(
        self,
        authority: Authority,
        *,
        allowed_capabilities: tuple[str, ...],
    ) -> tuple[CognitiveToolCall, ...]:
        """Build deterministic zero-argument Level-1/Level-2 evidence calls.

        The matrix must already have selected the capability for the current
        tool-assisted turn. Level 3+ capabilities are never host-preflighted,
        and tools with required arguments remain model/operator supplied.
        """
        return self._automatic_calls_for_levels(
            authority,
            allowed_capabilities=allowed_capabilities,
            levels=frozenset(
                (
                    PermissionLevel.OBSERVE_READ,
                    PermissionLevel.SAFE_AUTONOMOUS,
                )
            ),
            call_id_prefix="host-auto",
        )

    def tool_result_produces_execution_receipt(
        self,
        tool_name: str,
        result: CapabilityResult,
    ) -> bool:
        """Return whether one successful host result proves execution."""
        if not isinstance(tool_name, str):
            raise TypeError("tool_name must be a string")
        if not isinstance(result, CapabilityResult):
            raise TypeError("result must be a CapabilityResult")
        try:
            binding = self._bindings[tool_name]
        except KeyError as exc:
            raise CognitiveToolError(
                f"Unknown cognitive tool: {tool_name}"
            ) from exc
        if not binding.produces_execution_receipt:
            return False
        match = binding.execution_receipt_evidence_match
        if match is None:
            return True
        key, expected = match
        return (
            isinstance(result.evidence, dict)
            and result.evidence.get(key) == expected
        )

    def dispatch(
        self,
        tool_call: CognitiveToolCall,
        *,
        principal: PrincipalContext | None = None,
        allowed_capabilities: tuple[str, ...] | None = None,
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

        if allowed_capabilities is not None:
            if not isinstance(allowed_capabilities, tuple):
                raise TypeError(
                    "allowed_capabilities must be a tuple or None"
                )
            allowed = set()
            for capability in allowed_capabilities:
                if not isinstance(capability, str) or not capability.strip():
                    raise ValueError(
                        "allowed_capabilities must contain nonempty strings"
                    )
                allowed.add(capability)
            if binding.capability_name not in allowed:
                raise CognitiveToolError(
                    f"Tool {tool_call.name!r} was not exposed for this turn."
                )

        parameters = dict(tool_call.arguments)

        reserved = ("__principal_id", "__audience_id", "__audience_kind")
        if any(key in parameters for key in reserved):
            raise CognitiveToolError(
                "Cognitive tool attempted to supply host-controlled identity metadata."
            )
        if binding.include_principal_metadata and principal is not None:
            if not isinstance(principal, PrincipalContext):
                raise TypeError("principal must be a PrincipalContext or None")
            parameters["__principal_id"] = principal.principal_id
            parameters["__audience_id"] = principal.audience_id
            parameters["__audience_kind"] = principal.audience_kind.value

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
                    CognitiveToolDispatcher._format_generic_evidence(
                        evidence
                    )
                )

        return "\n".join(lines)


    @staticmethod
    def _format_generic_evidence(value: Any) -> str:
        def normalize(item):
            if is_dataclass(item):
                return normalize(asdict(item))
            if isinstance(item, Enum):
                return item.value
            if isinstance(item, Path):
                return str(item)
            if isinstance(item, dict):
                return {str(k): normalize(v) for k,v in item.items()}
            if isinstance(item, (tuple,list,set,frozenset)):
                return [normalize(v) for v in item]
            if item is None or isinstance(item,(str,int,float,bool)):
                return item
            return str(item)
        try:
            return json.dumps(normalize(value),ensure_ascii=False,sort_keys=True,indent=2)
        except (TypeError,ValueError):
            return str(value)

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
    Construct the host-owned cognitive tools.

    These tools are intentionally read-only.

    Authorization determines which of these definitions are exposed
    to the cognitive engine for a given operation.
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

def create_system_tool_bindings() -> tuple[CognitiveToolBinding, ...]:
    """Read-only local system tools. Authority still controls exposure."""
    return (
        CognitiveToolBinding(
            definition=CognitiveToolDefinition(
                name="inspect_processes",
                description="Inspect local running processes. Read-only.",
                parameters={"type":"object","properties":{
                    "pid":{"type":"integer"},
                    "limit":{"type":"integer"}
                },"additionalProperties":False},
            ),
            capability_name="process.inspect",
        ),
        CognitiveToolBinding(
            definition=CognitiveToolDefinition(
                name="inspect_system",
                description="Inspect the local operating system, host identity and uptime. Read-only.",
                parameters={"type":"object","properties":{},"additionalProperties":False},
            ),
            capability_name="system.inspect",
        ),
        CognitiveToolBinding(
            definition=CognitiveToolDefinition(
                name="inspect_network",
                description="Inspect local network interfaces, routes and DNS. Read-only.",
                parameters={"type":"object","properties":{
                    "interface":{"type":"string"},
                    "limit":{"type":"integer"}
                },"additionalProperties":False},
            ),
            capability_name="network.inspect",
        ),
        CognitiveToolBinding(
            definition=CognitiveToolDefinition(
                name="inspect_hardware",
                description="Inspect local CPU, GPU, memory, storage, network adapters and virtualization hardware. Read-only.",
                parameters={"type":"object","properties":{},"additionalProperties":False},
            ),
            capability_name="hardware.inspect",
        ),
        CognitiveToolBinding(
            definition=CognitiveToolDefinition(
                name="inspect_services",
                description="Inspect local service state and configuration. Read-only.",
                parameters={"type":"object","properties":{
                    "name":{"type":"string"},
                    "state":{"type":"string"},
                    "limit":{"type":"integer"}
                },"additionalProperties":False},
            ),
            capability_name="service.inspect",
        ),
    )
