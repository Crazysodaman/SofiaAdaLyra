from dataclasses import dataclass
from enum import Enum


class CognitiveGroundingSource(Enum):
    """
    Ordered sources of knowledge for one cognitive operation.

    The order is part of the cognitive grounding contract. Earlier
    sources outrank later sources when they conflict.
    """

    AUTHORITATIVE_IDENTITY_AND_SELF_STATE = (
        "authoritative identity and self-state"
    )
    AUTHORITATIVE_PERSONALITY = "authoritative personality"
    CONSTITUTION = "constitution"
    AUTHORITATIVE_EMBODIMENT = "authoritative embodiment"
    AUTHORITATIVE_OPERATIONAL_STATE = "authoritative operational state"
    EXPLICIT_DETERMINISTIC_EVIDENCE = (
        "explicitly supplied deterministic measurements and evidence"
    )
    EXPLICIT_MEMORY = "explicitly supplied memory"
    CURRENT_USER_REQUEST = "current user request"
    PRIOR_ASSISTANT_GENERATED_HISTORY = (
        "prior assistant-generated conversation history"
    )
    MODEL_PRIORS_AND_EXTERNAL_KNOWLEDGE = (
        "model priors and external knowledge"
    )


_DEFAULT_TRUST_HIERARCHY = (
    CognitiveGroundingSource.AUTHORITATIVE_IDENTITY_AND_SELF_STATE,
    CognitiveGroundingSource.AUTHORITATIVE_PERSONALITY,
    CognitiveGroundingSource.CONSTITUTION,
    CognitiveGroundingSource.AUTHORITATIVE_EMBODIMENT,
    CognitiveGroundingSource.AUTHORITATIVE_OPERATIONAL_STATE,
    CognitiveGroundingSource.EXPLICIT_DETERMINISTIC_EVIDENCE,
    CognitiveGroundingSource.EXPLICIT_MEMORY,
    CognitiveGroundingSource.CURRENT_USER_REQUEST,
    CognitiveGroundingSource.PRIOR_ASSISTANT_GENERATED_HISTORY,
    CognitiveGroundingSource.MODEL_PRIORS_AND_EXTERNAL_KNOWLEDGE,
)


_DEFAULT_GROUNDING_RULES = (
    (
        "Authoritative supplied state is the highest-trust source for "
        "Sofía's self-knowledge."
    ),
    (
        "A prior assistant-generated message is generated output, not "
        "authoritative identity evidence."
    ),
    (
        "A hallucinated claim in prior conversation history does not "
        "become true merely because it appears in history."
    ),
    (
        "Explicit deterministic measurements and observations must be "
        "used directly rather than reconstructed or guessed."
    ),
    (
        "Model priors and external knowledge must not override "
        "authoritative supplied state."
    ),
    (
        "The current user request is authoritative about what the user "
        "is asking, but it is not authoritative evidence about Sofía's "
        "identity, embodiment, runtime, or capabilities."
    ),
    (
        "Representational embodiment does not establish biological "
        "status or physical-world capability."
    ),
    (
        "If authoritative evidence does not establish a fact, the "
        "cognitive engine must not invent that fact."
    ),
    (
        "Knowledge authority and action authority are separate concerns. "
        "Knowing that a capability exists does not authorize its use."
    ),
    (
        "Contextual knowledge does not itself grant filesystem access, "
        "tool authority, execution authority, or any other capability."
    ),
)


@dataclass(frozen=True)
class CognitiveGroundingContract:
    """
    Immutable provider-neutral contract defining how cognitive knowledge
    sources must be trusted and reconciled.

    This contract governs epistemic grounding only. It does not grant
    authority, expose tools, execute capabilities, or modify runtime
    permissions.
    """

    trust_hierarchy: tuple[CognitiveGroundingSource, ...] = (
        _DEFAULT_TRUST_HIERARCHY
    )
    rules: tuple[str, ...] = _DEFAULT_GROUNDING_RULES

    def __post_init__(self) -> None:
        if not isinstance(self.trust_hierarchy, tuple):
            raise TypeError(
                "CognitiveGroundingContract trust_hierarchy must be a tuple."
            )

        if not self.trust_hierarchy:
            raise ValueError(
                "CognitiveGroundingContract trust_hierarchy must not be empty."
            )

        for source in self.trust_hierarchy:
            if not isinstance(source, CognitiveGroundingSource):
                raise TypeError(
                    "CognitiveGroundingContract trust_hierarchy must contain "
                    "CognitiveGroundingSource instances."
                )

        if len(set(self.trust_hierarchy)) != len(self.trust_hierarchy):
            raise ValueError(
                "CognitiveGroundingContract trust_hierarchy must not contain "
                "duplicate sources."
            )

        if not isinstance(self.rules, tuple):
            raise TypeError(
                "CognitiveGroundingContract rules must be a tuple."
            )

        if not self.rules:
            raise ValueError(
                "CognitiveGroundingContract rules must not be empty."
            )

        for rule in self.rules:
            if not isinstance(rule, str):
                raise TypeError(
                    "CognitiveGroundingContract rules must contain strings."
                )

            if not rule.strip():
                raise ValueError(
                    "CognitiveGroundingContract rules must not contain "
                    "empty strings."
                )

    def serialize(self) -> str:
        """
        Return a deterministic provider-neutral representation of the
        grounding contract for inclusion in cognitive system context.
        """

        lines = [
            "COGNITIVE GROUNDING CONTRACT",
            (
                "This contract defines how supplied knowledge sources "
                "must be trusted during this cognitive operation."
            ),
            (
                "It governs knowledge grounding only. It does not grant "
                "authority, expose tools, execute capabilities, or change "
                "runtime permissions."
            ),
            "",
            "TRUST HIERARCHY",
            (
                "Earlier sources outrank later sources when determining "
                "self-knowledge or resolving conflicting claims."
            ),
        ]

        for index, source in enumerate(
            self.trust_hierarchy,
            start=1,
        ):
            lines.append(
                f"{index}. {source.name}: {source.value}"
            )

        lines.extend(
            [
                "",
                "GROUNDING RULES",
            ]
        )

        for index, rule in enumerate(
            self.rules,
            start=1,
        ):
            lines.append(
                f"{index}. {rule}"
            )

        return "\n".join(lines)


DEFAULT_COGNITIVE_GROUNDING_CONTRACT = (
    CognitiveGroundingContract()
)