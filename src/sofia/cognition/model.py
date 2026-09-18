from dataclasses import dataclass
from enum import Enum
from typing import Any


class CognitiveRole(Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass(frozen=True)
class CognitiveToolDefinition:
    """
    Provider-neutral description of a cognitive tool.

    A tool definition describes what the cognitive engine may request.
    It contains no executable callable and grants no authority.
    """

    name: str
    description: str
    parameters: dict[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.name, str):
            raise TypeError(
                "CognitiveToolDefinition name must be a string."
            )

        if not self.name.strip():
            raise ValueError(
                "CognitiveToolDefinition name must not be empty."
            )

        if not isinstance(self.description, str):
            raise TypeError(
                "CognitiveToolDefinition description must be a string."
            )

        if not self.description.strip():
            raise ValueError(
                "CognitiveToolDefinition description must not be empty."
            )

        if not isinstance(self.parameters, dict):
            raise TypeError(
                "CognitiveToolDefinition parameters must be a dict."
            )


@dataclass(frozen=True)
class CognitiveToolCall:
    """
    Structured request from a cognitive provider to invoke a tool.

    This object contains request data only. It does not contain a
    callable, capability handler, filesystem object, or authority.
    """

    name: str
    arguments: dict[str, Any]
    call_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str):
            raise TypeError(
                "CognitiveToolCall name must be a string."
            )

        if not self.name.strip():
            raise ValueError(
                "CognitiveToolCall name must not be empty."
            )

        if not isinstance(self.arguments, dict):
            raise TypeError(
                "CognitiveToolCall arguments must be a dict."
            )

        if (
            self.call_id is not None
            and not isinstance(self.call_id, str)
        ):
            raise TypeError(
                "CognitiveToolCall call_id must be a string or None."
            )


@dataclass(frozen=True)
class CognitiveMessage:
    role: CognitiveRole
    content: str
    tool_calls: tuple[CognitiveToolCall, ...] = ()
    tool_call_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.role, CognitiveRole):
            raise ValueError(
                "CognitiveMessage role must be a CognitiveRole."
            )

        if not isinstance(self.content, str):
            raise TypeError(
                "CognitiveMessage content must be a string."
            )

        if not isinstance(self.tool_calls, tuple):
            raise TypeError(
                "CognitiveMessage tool_calls must be a tuple."
            )

        for tool_call in self.tool_calls:
            if not isinstance(tool_call, CognitiveToolCall):
                raise TypeError(
                    "CognitiveMessage tool_calls must contain "
                    "CognitiveToolCall instances."
                )

        if (
            self.tool_call_id is not None
            and not isinstance(self.tool_call_id, str)
        ):
            raise TypeError(
                "CognitiveMessage tool_call_id must be a string or None."
            )

        if self.role is CognitiveRole.TOOL:
            if self.tool_call_id is None:
                raise ValueError(
                    "CognitiveMessage TOOL messages require a tool_call_id."
                )

        if self.role is not CognitiveRole.ASSISTANT:
            if self.tool_calls:
                raise ValueError(
                    "Only ASSISTANT messages may contain tool calls."
                )


@dataclass(frozen=True)
class CognitiveRequest:
    messages: tuple[CognitiveMessage, ...]
    tools: tuple[CognitiveToolDefinition, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.messages, tuple):
            raise TypeError(
                "CognitiveRequest messages must be a tuple."
            )

        for message in self.messages:
            if not isinstance(message, CognitiveMessage):
                raise TypeError(
                    "CognitiveRequest messages must contain "
                    "CognitiveMessage instances."
                )

        if not isinstance(self.tools, tuple):
            raise TypeError(
                "CognitiveRequest tools must be a tuple."
            )

        for tool in self.tools:
            if not isinstance(tool, CognitiveToolDefinition):
                raise TypeError(
                    "CognitiveRequest tools must contain "
                    "CognitiveToolDefinition instances."
                )


@dataclass(frozen=True)
class CognitiveResponse:
    content: str
    tool_calls: tuple[CognitiveToolCall, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.content, str):
            raise TypeError(
                "CognitiveResponse content must be a string."
            )

        if not isinstance(self.tool_calls, tuple):
            raise TypeError(
                "CognitiveResponse tool_calls must be a tuple."
            )

        for tool_call in self.tool_calls:
            if not isinstance(tool_call, CognitiveToolCall):
                raise TypeError(
                    "CognitiveResponse tool_calls must contain "
                    "CognitiveToolCall instances."
                )