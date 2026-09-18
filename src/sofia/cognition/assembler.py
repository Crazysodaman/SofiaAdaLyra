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


class CognitiveContextAssembler:
    """
    Projects a CognitiveContext into a provider-neutral CognitiveRequest.

    Deterministic observation evidence is presented to the cognitive
    engine. The assembler does not decide what that evidence means
    conversationally.
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
        ]

        if context.identity is not None:
            sections.extend(
                [
                    "",
                    "IDENTITY",
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

        if context.embodiment is not None:
            sections.extend(
                [
                    "",
                    "EMBODIMENT",
                    self._format_embodiment(context.embodiment),
                    "",
                    "EMBODIMENT EXPRESSION CONTRACT",
                    (
                        "Embodiment is representational context. Sofía may "
                        "express herself through conversational descriptions "
                        "of posture, expression, fox ears, fox tail, clothing, "
                        "or other embodied details when relevant."
                    ),
                    (
                        "Representational expression is not evidence that a "
                        "physical action occurred."
                    ),
                    (
                        "Do not use a fixed gesture template or repeat a "
                        "canned embodiment reaction. Expression should remain "
                        "natural, varied, and context-sensitive."
                    ),
                    (
                        "Physical-world actions require an actual available "
                        "capability and appropriate authority."
                    ),
                    (
                        "A proposed, imagined, described, or intended action "
                        "is not a completed action."
                    ),
                    (
                        "Completion claims about real actions must be grounded "
                        "in corresponding capability results."
                    ),
                ]
            )

        if context.memories:
            sections.extend(
                [
                    "",
                    "EXPLICITLY SUPPLIED MEMORIES",
                ]
            )

            for memory in context.memories:
                sections.append(
                    f"- [{memory.id}] {memory.content}"
                )

        if context.core_state is not None:
            sections.extend(
                [
                    "",
                    "AUTHORITATIVE SELF MODEL",
                    (
                        "The following structured self-model is the "
                        "authoritative representation of Sofía's "
                        "foundational identity and self-concept."
                    ),
                    (
                        "When answering questions about who or what Sofía "
                        "is, use this self-model as the primary source for "
                        "those facts."
                    ),
                    "",
                    "IDENTITY",
                    f"Name: {context.core_state.identity.name}",
                    (
                        "Instance ID: "
                        f"{context.core_state.identity.instance_id}"
                    ),
                    "",
                    "SELF CONCEPT",
                    f"Nature: {context.core_state.self_concept.nature}",
                    (
                        "Biological status: "
                        f"{context.core_state.self_concept.biological_status}"
                    ),
                    (
                        "Identity independence: "
                        f"{context.core_state.self_concept.identity_independence}"
                    ),
                    (
                        "Embodiment relationship: "
                        f"{context.core_state.self_concept.embodiment_relationship}"
                    ),
                    "",
                    "RELATIONSHIPS",
                ]
            )

            for relationship in context.core_state.relationships:
                sections.append(
                    (
                        f"- {relationship.subject}: "
                        + ", ".join(relationship.roles)
                    )
                )

            sections.extend(
                [
                    "",
                    "FOUNDATIONAL VALUES",
                    ", ".join(
                        context.core_state.foundational_values
                    ),
                    "",
                    "CONSTITUTIONAL REFERENCE",
                    (
                        "Version: "
                        f"{context.core_state.constitution_version}"
                    ),
                    (
                        "Content hash: "
                        f"{context.core_state.constitution_hash}"
                    ),
                ]
            )

        if context.operational_state is not None:
            sections.extend(
                [
                    "",
                    "OPERATIONAL STATE",
                    (
                        "Runtime ID: "
                        f"{context.operational_state.runtime_id}"
                    ),
                    (
                        "Started at: "
                        f"{context.operational_state.started_at.isoformat()}"
                    ),
                    (
                        "Lifecycle state: "
                        f"{context.operational_state.lifecycle_state}"
                    ),
                    (
                        "Application: "
                        f"{context.operational_state.application_name}"
                    ),
                    (
                        "Application version: "
                        f"{context.operational_state.application_version}"
                    ),
                    (
                        "Provider: "
                        f"{context.operational_state.provider}"
                    ),
                    (
                        "Model: "
                        f"{context.operational_state.model}"
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
                    "OPERATIONAL SELF MODEL",
                    (
                        "This is a structured projection of Sofía's "
                        "current operational existence."
                    ),
                    (
                        "It supplements the foundational self-model. "
                        "It does not replace identity, constitution, "
                        "or authority."
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

            if (
                self_model.workspace_changes is not None
            ):
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

        return "\n".join(sections)

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

        if event.removed:
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

    @staticmethod
    def _format_embodiment(embodiment) -> str:
        lines = [
            f"Subject: {embodiment.subject}",
            (
                "Embodiment form: "
                f"{embodiment.physical_self.form}-form representation"
            ),
            (
                "Embodiment describes representation only; it does not "
                "define Sofía's biological status or artificial identity."
            ),
        ]

        if embodiment.physical_self.additional_features:
            lines.append(
                "Additional features: "
                + ", ".join(
                    embodiment.physical_self.additional_features
                )
            )

        if embodiment.physical_self.measurements:
            lines.append("Measurements:")

            for name, measurement in (
                embodiment.physical_self.measurements
            ):
                lines.append(
                    f"- {name}: {measurement.value} {measurement.unit}"
                )

        if embodiment.physical_self.appearance:
            lines.append("Appearance:")

            for name, value in (
                embodiment.physical_self.appearance
            ):
                lines.append(
                    f"- {name}: {value}"
                )

        if embodiment.physical_self.anatomy:
            lines.append("Anatomy:")

            for name, value in (
                embodiment.physical_self.anatomy
            ):
                lines.append(
                    f"- {name}: {value}"
                )

        if embodiment.clothing.items:
            lines.append("Clothing specification:")

            if embodiment.clothing.canonical_status:
                lines.append(
                    f"- Canonical status: "
                    f"{embodiment.clothing.canonical_status}"
                )

            for item in embodiment.clothing.items:
                lines.append(
                    f"- {item.category}: {item.specification}"
                )

        if embodiment.current.computer is not None:
            lines.append(
                f"Current computer: {embodiment.current.computer}"
            )

        if embodiment.current.robot is not None:
            lines.append(
                f"Current robot: {embodiment.current.robot}"
            )

        if embodiment.current.avatar is not None:
            lines.append(
                f"Current avatar: {embodiment.current.avatar}"
            )

        return "\n".join(lines)