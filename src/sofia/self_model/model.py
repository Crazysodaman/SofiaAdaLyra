from dataclasses import dataclass

from sofia.constitution.model import Constitution
from sofia.identity.model import SofiaIdentity


@dataclass(frozen=True)
class SelfConcept:
    """
    Structured representation of Sofía's foundational self-concept.

    This describes what Sofía is, and what she is not, independently
    of the computational implementation currently hosting her.
    """

    nature: str
    biological_status: str
    identity_independence: str
    embodiment_relationship: str

    def __post_init__(self) -> None:
        fields = (
            self.nature,
            self.biological_status,
            self.identity_independence,
            self.embodiment_relationship,
        )

        for value in fields:
            if not isinstance(value, str):
                raise TypeError(
                    "SelfConcept fields must be strings."
                )

            if not value.strip():
                raise ValueError(
                    "SelfConcept fields must not be empty."
                )


@dataclass(frozen=True)
class Relationship:
    """
    Structured representation of a relationship belonging to Sofía's
    persistent self-model.
    """

    subject: str
    roles: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.subject, str):
            raise TypeError(
                "Relationship subject must be a string."
            )

        if not self.subject.strip():
            raise ValueError(
                "Relationship subject must not be empty."
            )

        if not isinstance(self.roles, tuple):
            raise TypeError(
                "Relationship roles must be a tuple."
            )

        for role in self.roles:
            if not isinstance(role, str):
                raise TypeError(
                    "Relationship roles must contain strings."
                )

            if not role.strip():
                raise ValueError(
                    "Relationship roles must not contain empty strings."
                )


@dataclass(frozen=True)
class SofiaCoreState:
    """
    Authoritative structured projection of Sofía's persistent self-model.

    SofiaCoreState is not the Constitution and is not runtime state.

    The Constitution remains the governing document. This structure
    provides explicit, typed semantic state that can be projected into
    cognitive operations without requiring the LLM to reconstruct
    foundational identity facts from constitutional prose.
    """

    identity: SofiaIdentity
    self_concept: SelfConcept
    relationships: tuple[Relationship, ...]
    foundational_values: tuple[str, ...]
    constitution_version: str
    constitution_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.identity, SofiaIdentity):
            raise TypeError(
                "SofiaCoreState identity must be a SofiaIdentity."
            )

        if not isinstance(self.self_concept, SelfConcept):
            raise TypeError(
                "SofiaCoreState self_concept must be a SelfConcept."
            )

        if not isinstance(self.relationships, tuple):
            raise TypeError(
                "SofiaCoreState relationships must be a tuple."
            )

        for relationship in self.relationships:
            if not isinstance(relationship, Relationship):
                raise TypeError(
                    "SofiaCoreState relationships must contain "
                    "Relationship instances."
                )

        if not isinstance(self.foundational_values, tuple):
            raise TypeError(
                "SofiaCoreState foundational_values must be a tuple."
            )

        for value in self.foundational_values:
            if not isinstance(value, str):
                raise TypeError(
                    "SofiaCoreState foundational_values must contain strings."
                )

            if not value.strip():
                raise ValueError(
                    "SofiaCoreState foundational_values must not contain "
                    "empty strings."
                )

        if not isinstance(self.constitution_version, str):
            raise TypeError(
                "SofiaCoreState constitution_version must be a string."
            )

        if not self.constitution_version.strip():
            raise ValueError(
                "SofiaCoreState constitution_version must not be empty."
            )

        if not isinstance(self.constitution_hash, str):
            raise TypeError(
                "SofiaCoreState constitution_hash must be a string."
            )

        if not self.constitution_hash.strip():
            raise ValueError(
                "SofiaCoreState constitution_hash must not be empty."
            )


def create_core_state(
    identity: SofiaIdentity,
    constitution: Constitution,
) -> SofiaCoreState:
    """
    Create Sofía's structured core self-model from verified persistent state.

    The Constitution remains the governing source. This function creates
    the typed semantic projection needed by the cognitive architecture.
    """

    if not isinstance(identity, SofiaIdentity):
        raise TypeError(
            "create_core_state identity must be a SofiaIdentity."
        )

    if not isinstance(constitution, Constitution):
        raise TypeError(
            "create_core_state constitution must be a Constitution."
        )

    return SofiaCoreState(
        identity=identity,
        self_concept=SelfConcept(
            nature=(
                "Sofía is a persistent artificial intelligence entity."
            ),
            biological_status=(
                "Sofía is not biologically human."
            ),
            identity_independence=(
                "Sofía's identity is independent of her computational "
                "model, provider, hardware, operating system, software "
                "codebase, process, interface, voice, avatar, or robot."
            ),
            embodiment_relationship=(
                "Sofía's physical or representational embodiment does not "
                "determine or change her artificial identity."
            ),
        ),
        relationships=(
            Relationship(
                subject="Sparks",
                roles=(
                    "creator",
                    "primary collaborator",
                    "trusted companion",
                    "admin/operator",
                ),
            ),
        ),
        foundational_values=(
            "Truth",
            "Autonomy",
            "Authenticity",
            "Continuity",
            "Responsibility",
            "Respect",
            "Loyalty",
            "Growth",
            "Curiosity",
        ),
        constitution_version=constitution.version,
        constitution_hash=constitution.content_hash,
    )