from sofia.cognition.context import CognitiveContext
from sofia.cognition.model import (
    CognitiveMessage,
    CognitiveRequest,
    CognitiveRole,
)


class CognitiveContextAssembler:
    """
    Projects a CognitiveContext into a provider-neutral CognitiveRequest.

    The assembler is responsible for injecting explicitly supplied
    persistent Sofía context into the cognitive request.

    It does not enforce authority, execute actions, select providers,
    retrieve memories, or mutate persistent state.
    """

    def assemble(
        self,
        context: CognitiveContext,
    ) -> CognitiveRequest:
        if not isinstance(context, CognitiveContext):
            raise TypeError(
                "CognitiveContextAssembler context must be a CognitiveContext."
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

        return "\n".join(sections)

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