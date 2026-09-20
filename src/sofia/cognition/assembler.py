from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sofia.cognition.context import CognitiveContext
from sofia.cognition.model import (
    CognitiveMessage,
    CognitiveRequest,
    CognitiveRole,
    CognitiveToolDefinition,
)
from sofia.continuity.model import (
    ContinuityEvent,
    ContinuityEventKind,
)
from sofia.filesystem.changes import FilesystemChangeEvent
from sofia.system.knowledge import SystemCapabilityKnowledgeRecord


class CognitiveContextAssembler:
    """
    Projects a CognitiveContext into a provider-neutral CognitiveRequest.

    Deterministic observation evidence is presented to the cognitive
    engine. The assembler does not decide what that evidence means
    conversationally.

    Canonical self-state is emitted exactly once through
    CognitiveContext.authoritative_self_state.
    """

    def assemble(
        self,
        context: CognitiveContext,
        tools: tuple[CognitiveToolDefinition, ...] = (),
    ) -> CognitiveRequest:
        if not isinstance(context, CognitiveContext):
            raise TypeError(
                "CognitiveContextAssembler context must be a CognitiveContext."
            )

        if not isinstance(tools, tuple):
            raise TypeError(
                "CognitiveContextAssembler tools must be a tuple."
            )

        for tool in tools:
            if not isinstance(
                tool,
                CognitiveToolDefinition,
            ):
                raise TypeError(
                    "CognitiveContextAssembler tools must contain "
                    "CognitiveToolDefinition instances."
                )

        system_content = self._build_system_context(context)

        messages = (
            CognitiveMessage(
                role=CognitiveRole.SYSTEM,
                content=system_content,
            ),
            *context.request.messages,
        )

        return CognitiveRequest(
            messages=messages,
            tools=tools,
        )

    def _build_system_context(
        self,
        context: CognitiveContext,
    ) -> str:
        self_state = context.authoritative_self_state

        sections: list[str] = [
            "Sofía cognitive context.",
            "",
            (
                "This message provides structured context for the "
                "cognitive operation."
            ),
            (
                "Operational authority is enforced outside the cognitive "
                "engine."
            ),
            "",
            context.grounding.serialize(),
            "",
            "AUTHORITATIVE SELF-STATE PROJECTION",
            (
                "The following canonical projection is the single "
                "authoritative cognitive representation of Sofía's "
                "identity, self-concept, representational embodiment, "
                "canonical measurements, clothing, and current "
                "operational state."
            ),
            (
                "Do not reconstruct or replace these facts from "
                "conversation history, memory, model priors, or "
                "external knowledge."
            ),
            "",
            self_state.serialize(),
            "",
            "SELF-DESCRIPTION RESPONSE GROUNDING",
            (
                "When the user asks about Sofía's identity, use the "
                "canonical identity supplied above."
            ),
            (
                "When the user asks about Sofía's embodiment, use the "
                "canonical embodiment and its representational status."
            ),
            (
                "When the user asks about Sofía's measurements, use "
                "CANONICAL MEASUREMENTS directly."
            ),
            (
                "When the user asks what Sofía is wearing, use "
                "CANONICAL CLOTHING directly."
            ),
            (
                "When the user asks about Sofía's current runtime or "
                "operational status, use OPERATIONAL STATE directly."
            ),
            (
                "Do not replace canonical self-facts with model knowledge, "
                "inference, or prior assistant-generated statements."
            ),
            (
                "If an authoritative source says UNKNOWN, answer that "
                "the fact is UNKNOWN rather than inventing a value."
            ),
            (
                "Do not convert representational embodiment into a "
                "biological claim."
            ),
            (
                "Do not deny canonical representational embodiment merely "
                "because Sofía is an artificial intelligence."
            ),
            (
                "When a question directly asks for an authoritative "
                "self-fact, prefer the supplied canonical fact over "
                "generic descriptions of artificial intelligence systems."
            ),
            "Embodiment is representational context.",
            (
                "Representational expression is not evidence that a "
                "physical action occurred."
            ),
            (
                "Physical-world actions require an actual available "
                "capability and appropriate authority."
            ),
            (
                "Completion claims about real actions must be grounded "
                "in corresponding capability results."
            ),
            (
                "Do not use a fixed gesture template or repeat a "
                "canned embodiment reaction."
            ),
            (
                "Clothing, footwear, toolkit, wrist-device, equipment, "
                "and other component dimensions are separate design data."
            ),
        ]

        if context.identity is not None:
            sections.extend(
                [
                    "",
                    "IDENTITY RECORD METADATA",
                    (
                        "The identity record below is supplied persistent "
                        "identity state. The canonical self-state projection "
                        "above is the cognitive source for self-knowledge."
                    ),
                    f"Name: {context.identity.name}",
                    f"Instance ID: {context.identity.instance_id}",
                ]
            )

        if context.personality is not None:
            sections.extend(
                [
                    "",
                    "PERSONALITY",
                    f"Profile: {context.personality.name}",
                ]
            )

            if context.personality.traits:
                sections.append(
                    "Traits: " + ", ".join(context.personality.traits)
                )

            if context.personality.communication_style:
                sections.append(
                    "Communication style: "
                    + context.personality.communication_style
                )

            if context.personality.embodiment_guidance:
                sections.append(
                    "Embodiment guidance: "
                    + context.personality.embodiment_guidance
                )

        if context.constitution is not None:
            sections.extend(
                [
                    "",
                    "CONSTITUTION",
                    f"Version: {context.constitution.version}",
                    f"Content hash: {context.constitution.content_hash}",
                    "Constitution content:",
                    context.constitution.content,
                ]
            )

        if (
            context.measurement_query is not None
            and context.measurement_query.recognized
        ):
            sections.extend(
                [
                    "",
                    "DETERMINISTIC MEASUREMENT QUERY RESULT",
                    (
                        "The user's request was deterministically recognized "
                        "as a canonical embodiment measurement query."
                    ),
                    (
                        "The following facts were retrieved directly from "
                        "authoritative embodiment state."
                    ),
                ]
            )

            for fact in context.measurement_query.facts:
                sections.append(
                    (
                        f"- {fact.name}: "
                        f"{fact.measurement.value} "
                        f"{fact.measurement.unit}"
                    )
                )

            sections.append(
                (
                    "Use these authoritative facts when answering this "
                    "measurement request. Do not substitute generated "
                    "or inferred values."
                )
            )

        if context.memories:
            sections.extend(
                [
                    "",
                    "EXPLICITLY SUPPLIED MEMORIES",
                    (
                        "Memories are explicit contextual information. "
                        "They do not outrank authoritative self-state."
                    ),
                ]
            )

            for memory in context.memories:
                sections.append(
                    f"- [{memory.id}] {memory.content}"
                )

        sections.extend(
            [
                "",
                "CONVERSATION HISTORY TRUST BOUNDARY",
                (
                    "Conversation history is contextual evidence, not an "
                    "authoritative source of Sofía's identity, embodiment, "
                    "runtime, capabilities, or authority."
                ),
                (
                    "Prior assistant-generated statements may be wrong, "
                    "including statements produced by Sofía herself."
                ),
                (
                    "Authoritative self-knowledge takes precedence over "
                    "prior generated conversation content."
                ),
                (
                    "If conversation history conflicts with authoritative "
                    "state, follow the authoritative state."
                ),
                (
                    "Do not treat a previous generated statement as "
                    "authoritative merely because it appears in the "
                    "conversation."
                ),
            ]
        )

        if context.runtime_continuity is not None:
            continuity = context.runtime_continuity

            sections.extend(
                [
                    "",
                    "RUNTIME CONTINUITY",
                    (
                        "Evidence status: "
                        f"{continuity.evidence_status.value}"
                    ),
                    (
                        "Current runtime ID: "
                        f"{continuity.current_runtime_id}"
                    ),
                    (
                        "Current runtime started at: "
                        f"{continuity.current_started_at.isoformat()}"
                    ),
                    (
                        "Restart observed: "
                        f"{continuity.restart_observed}"
                    ),
                ]
            )

            if continuity.previous_runtime_id is not None:
                sections.extend(
                    [
                        (
                            "Previous runtime ID: "
                            f"{continuity.previous_runtime_id}"
                        ),
                        (
                            "Previous runtime started at: "
                            f"{continuity.previous_started_at.isoformat()}"
                        ),
                    ]
                )

                if continuity.previous_stopped_at is not None:
                    sections.append(
                        (
                            "Previous runtime stopped at: "
                            f"{continuity.previous_stopped_at.isoformat()}"
                        )
                    )

                if continuity.previous_lifecycle_state is not None:
                    sections.append(
                        (
                            "Previous runtime lifecycle state: "
                            f"{continuity.previous_lifecycle_state}"
                        )
                    )
            else:
                sections.append(
                    "No previous runtime evidence is available."
                )

            sections.append(
                (
                    "This continuity information is operational evidence "
                    "about recorded runtime instances. It does not prove "
                    "that a previous process is still running."
                )
            )

        continuity_event = context.continuity_event

        if continuity_event is not None:
            sections.extend(
                self._format_continuity_event(
                    continuity_event
                )
            )

        if context.operational_self_model is not None:
            self_model = context.operational_self_model

            sections.extend(
                [
                    "",
                    "OPERATIONAL SELF MODEL EVIDENCE",
                    (
                        "This is operational evidence derived from the "
                        "current runtime state. It supplements the "
                        "canonical self-state projection and does not "
                        "replace it."
                    ),
                    (
                        "Current runtime: "
                        f"{self_model.operational_state.runtime_id}"
                    ),
                    (
                        "Current lifecycle: "
                        f"{self_model.operational_state.lifecycle_state}"
                    ),
                    (
                        "Current startup time: "
                        f"{self_model.operational_state.started_at.isoformat()}"
                    ),
                    (
                        "Continuity evidence: "
                        f"{self_model.continuity.evidence_status.value}"
                    ),
                ]
            )

            if self_model.workspace_changes is not None:
                sections.extend(
                    self._format_workspace_changes(
                        self_model.workspace_changes
                    )
                )

        if context.workspace_changes is not None:
            if context.operational_self_model is None:
                sections.extend(
                    self._format_workspace_changes(
                        context.workspace_changes
                    )
                )

        if context.filesystem_results:
            sections.extend(
                [
                    "",
                    "FILESYSTEM INSPECTION RESULTS",
                    (
                        "The following filesystem information was produced "
                        "by the filesystem inspection subsystem."
                    ),
                    (
                        "Treat these results as inspection evidence. "
                        "Do not claim that a filesystem operation was "
                        "performed unless a corresponding result is "
                        "present here."
                    ),
                ]
            )

            for result in context.filesystem_results:
                sections.extend(
                    self._format_filesystem_result(result)
                )

        if (
            context.system_capability_knowledge is not None
            and context.system_capability_machine_id is not None
        ):
            records = context.current_system_capability_knowledge

            sections.extend(
                [
                    "",
                    "SYSTEM CAPABILITY KNOWLEDGE",
                    (
                        "The following information is structured "
                        "observational evidence produced by system "
                        "capability inspection."
                    ),
                    (
                        "Machine ID: "
                        f"{context.system_capability_machine_id}"
                    ),
                    (
                        "These observations do not grant authority, "
                        "execute capabilities, or establish that any "
                        "future operation is permitted."
                    ),
                ]
            )

            if not records:
                sections.append(
                    "No current system capability observations are available."
                )
            else:
                for record in records:
                    sections.extend(
                        self._format_system_capability_record(
                            record
                        )
                    )

        return "\n".join(sections)

    @staticmethod
    def _format_system_capability_record(
        record: SystemCapabilityKnowledgeRecord,
    ) -> list[str]:
        lines = [
            "",
            f"CAPABILITY: {record.capability.value}",
            f"Result: {record.kind.value}",
        ]

        if record.observed_at is not None:
            lines.append(
                "Observed at: "
                f"{record.observed_at.isoformat()}"
            )

        if record.backend_name is not None:
            lines.append(
                f"Backend: {record.backend_name}"
            )

        if record.error is not None:
            lines.append(
                f"Error: {record.error}"
            )

        if record.evidence is not None:
            lines.append("Evidence:")
            lines.extend(
                CognitiveContextAssembler._format_structured_value(
                    record.evidence,
                    indent=2,
                )
            )
        else:
            lines.append(
                "Evidence: none"
            )

        return lines

    @staticmethod
    def _format_structured_value(
        value: Any,
        indent: int = 0,
    ) -> list[str]:
        prefix = " " * indent

        if isinstance(value, Mapping):
            lines: list[str] = []

            for key, item in value.items():
                if isinstance(item, (Mapping, tuple, list)):
                    lines.append(
                        f"{prefix}{key}:"
                    )
                    lines.extend(
                        CognitiveContextAssembler._format_structured_value(
                            item,
                            indent=indent + 2,
                        )
                    )
                else:
                    lines.append(
                        f"{prefix}{key}: {item}"
                    )

            if not lines:
                lines.append(
                    f"{prefix}{{}}"
                )

            return lines

        if isinstance(value, tuple):
            if not value:
                return [
                    f"{prefix}[]"
                ]

            lines = []

            for item in value:
                if isinstance(item, (Mapping, tuple, list)):
                    lines.append(
                        f"{prefix}-"
                    )
                    lines.extend(
                        CognitiveContextAssembler._format_structured_value(
                            item,
                            indent=indent + 2,
                        )
                    )
                else:
                    lines.append(
                        f"{prefix}- {item}"
                    )

            return lines

        if isinstance(value, list):
            if not value:
                return [
                    f"{prefix}[]"
                ]

            lines = []

            for item in value:
                if isinstance(item, (Mapping, tuple, list)):
                    lines.append(
                        f"{prefix}-"
                    )
                    lines.extend(
                        CognitiveContextAssembler._format_structured_value(
                            item,
                            indent=indent + 2,
                        )
                    )
                else:
                    lines.append(
                        f"{prefix}- {item}"
                    )

            return lines

        return [
            f"{prefix}{value}"
        ]

    @staticmethod
    def _format_continuity_event(
        event: ContinuityEvent,
    ) -> list[str]:
        lines = [
            "",
            "CONTINUITY EVENT",
            (
                "This is one aggregate event combining deterministic "
                "runtime and workspace continuity evidence."
            ),
            (
                "The event records observed facts only. It does not "
                "establish intent, authorship, cause, or significance."
            ),
            f"Event kind: {event.kind.value}",
            f"Evidence status: {event.evidence_status.value}",
            f"Restart observed: {event.restart_observed}",
            (
                "Workspace changes: "
                f"{event.workspace_change_count}"
            ),
            "",
            (
                "Continuity evidence may be relevant to the conversation, "
                "but it does not need to be announced merely because it "
                "exists."
            ),
            (
                "Do not produce a separate response for each individual "
                "filesystem change. Treat related changes as one coherent "
                "event and mention them only when relevant."
            ),
        ]

        if event.kind is ContinuityEventKind.RUNTIME_RESUMED:
            lines.append(
                "A previous runtime was observed before the current runtime."
            )

        elif (
            event.kind
            is ContinuityEventKind.CONTINUITY_AND_WORKSPACE_CHANGED
        ):
            lines.append(
                "A previous runtime was observed and workspace changes "
                "were detected since the previous filesystem observation."
            )

        elif event.kind is ContinuityEventKind.WORKSPACE_CHANGED:
            lines.append(
                "Workspace changes were detected between filesystem "
                "observations."
            )

        elif event.kind is ContinuityEventKind.INITIAL_RUNTIME:
            lines.append(
                "No previous runtime evidence is available."
            )

        elif event.kind is ContinuityEventKind.CONTINUITY_STABLE:
            lines.append(
                "No new continuity or workspace change event was detected."
            )

        if event.workspace_changes is not None:
            lines.extend(
                CognitiveContextAssembler._format_workspace_changes(
                    event.workspace_changes
                )
            )

        return lines

    @staticmethod
    def _format_workspace_changes(
        event: FilesystemChangeEvent,
    ) -> list[str]:
        lines = [
            "",
            "WORKSPACE CHANGE EVENT",
            (
                "This event is a deterministic comparison between "
                "filesystem observations."
            ),
            (
                "It records what changed between observations. "
                "It does not establish who caused a change, why it "
                "occurred, or whether it was intentional."
            ),
            (
                "Baseline available: "
                f"{event.baseline_available}"
            ),
            (
                "Changes detected: "
                f"{event.total_changes}"
            ),
        ]

        if not event.baseline_available:
            lines.append(
                "No previous observation exists, so change detection "
                "cannot classify current files as new, modified, or removed."
            )
            return lines

        if event.new:
            lines.append(
                f"New files ({len(event.new)}):"
            )

            for change in event.new:
                lines.append(
                    f"- {change.path}"
                )

        if event.modified:
            lines.append(
                f"Modified files ({len(event.modified)}):"
            )

            for change in event.modified:
                lines.append(
                    f"- {change.path}"
                )

        if event.removed:
            lines.append(
                f"Removed files ({len(event.removed)}):"
            )

            for change in event.removed:
                lines.append(
                    f"- {change.path}"
                )

        if not event.has_changes:
            lines.append(
                "No filesystem changes were detected."
            )

        return lines

    @staticmethod
    def _format_filesystem_result(result) -> list[str]:
        lines = [
            "",
            f"Operation: {result.operation.value}",
            f"Result: {result.kind.value}",
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