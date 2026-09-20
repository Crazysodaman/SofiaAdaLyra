from __future__ import annotations

from dataclasses import dataclass

from sofia.embodiment.model import Embodiment
from sofia.operational.model import OperationalState
from sofia.self_model.model import SofiaCoreState


@dataclass(frozen=True)
class AuthoritativeSelfState:
    """
    Provider-neutral canonical projection of Sofía's authoritative
    self-knowledge for one cognitive operation.

    This is a projection, not a new persistent source of truth.

    Identity and foundational self-model facts come from SofiaCoreState.
    Embodied facts come from Embodiment.
    Runtime facts come from OperationalState.

    Missing sources remain explicitly unknown rather than being inferred.
    """

    core_state: SofiaCoreState | None
    embodiment: Embodiment | None
    operational_state: OperationalState | None

    def __post_init__(self) -> None:
        if self.core_state is not None and not isinstance(
            self.core_state,
            SofiaCoreState,
        ):
            raise TypeError(
                "AuthoritativeSelfState core_state must be a "
                "SofiaCoreState or None."
            )

        if self.embodiment is not None and not isinstance(
            self.embodiment,
            Embodiment,
        ):
            raise TypeError(
                "AuthoritativeSelfState embodiment must be an "
                "Embodiment or None."
            )

        if self.operational_state is not None and not isinstance(
            self.operational_state,
            OperationalState,
        ):
            raise TypeError(
                "AuthoritativeSelfState operational_state must be an "
                "OperationalState or None."
            )

    @property
    def identity_name(self) -> str | None:
        if self.core_state is None:
            return None

        return self.core_state.identity.name

    @property
    def identity_instance_id(self):
        if self.core_state is None:
            return None

        return self.core_state.identity.instance_id

    @property
    def self_concept(self):
        if self.core_state is None:
            return None

        return self.core_state.self_concept

    @property
    def relationships(self):
        if self.core_state is None:
            return ()

        return self.core_state.relationships

    @property
    def foundational_values(self) -> tuple[str, ...]:
        if self.core_state is None:
            return ()

        return self.core_state.foundational_values

    @property
    def constitution_version(self) -> str | None:
        if self.core_state is None:
            return None

        return self.core_state.constitution_version

    @property
    def constitution_hash(self) -> str | None:
        if self.core_state is None:
            return None

        return self.core_state.constitution_hash

    @property
    def embodiment_subject(self) -> str | None:
        if self.embodiment is None:
            return None

        return self.embodiment.subject

    @property
    def embodiment_form(self) -> str | None:
        if self.embodiment is None:
            return None

        return self.embodiment.physical_self.form

    @property
    def additional_features(self) -> tuple[str, ...]:
        if self.embodiment is None:
            return ()

        return self.embodiment.physical_self.additional_features

    @property
    def measurements(self):
        if self.embodiment is None:
            return ()

        return self.embodiment.physical_self.measurements

    @property
    def appearance(self):
        if self.embodiment is None:
            return ()

        return self.embodiment.physical_self.appearance

    @property
    def anatomy(self):
        if self.embodiment is None:
            return ()

        return self.embodiment.physical_self.anatomy

    @property
    def clothing(self):
        if self.embodiment is None:
            return ()

        return self.embodiment.clothing.items

    @property
    def clothing_canonical_status(self) -> str | None:
        if self.embodiment is None:
            return None

        return self.embodiment.clothing.canonical_status

    def serialize(self) -> str:
        """
        Serialize the canonical authoritative self-state.

        This is the single provider-neutral projection of self-state
        intended for the cognitive engine.

        No inference is performed. Missing information is represented
        explicitly as UNKNOWN.
        """

        lines = [
            "AUTHORITATIVE SELF STATE",
            (
                "The following is the canonical structured projection "
                "of Sofía's authoritative self-knowledge for this "
                "cognitive operation."
            ),
            (
                "These facts outrank prior assistant-generated history "
                "and model priors."
            ),
            (
                "Do not replace an authoritative fact with an inferred "
                "or generated value."
            ),
            (
                "If a category is marked UNKNOWN, do not invent a value."
            ),
        ]

        if self.core_state is None:
            lines.extend(
                [
                    "",
                    "IDENTITY: UNKNOWN",
                    "SELF CONCEPT: UNKNOWN",
                    "RELATIONSHIPS: UNKNOWN",
                    "FOUNDATIONAL VALUES: UNKNOWN",
                    "CONSTITUTIONAL REFERENCE: UNKNOWN",
                ]
            )
        else:
            lines.extend(
                [
                    "",
                    "IDENTITY",
                    f"Name: {self.core_state.identity.name}",
                    (
                        "Instance ID: "
                        f"{self.core_state.identity.instance_id}"
                    ),
                    "",
                    "SELF CONCEPT",
                    (
                        "Nature: "
                        f"{self.core_state.self_concept.nature}"
                    ),
                    (
                        "Biological status: "
                        f"{self.core_state.self_concept.biological_status}"
                    ),
                    (
                        "Identity independence: "
                        f"{self.core_state.self_concept.identity_independence}"
                    ),
                    (
                        "Embodiment relationship: "
                        f"{self.core_state.self_concept.embodiment_relationship}"
                    ),
                    "",
                    "RELATIONSHIPS",
                ]
            )

            if self.core_state.relationships:
                for relationship in self.core_state.relationships:
                    lines.append(
                        (
                            f"- {relationship.subject}: "
                            + ", ".join(relationship.roles)
                        )
                    )
            else:
                lines.append("- None recorded")

            lines.extend(
                [
                    "",
                    "FOUNDATIONAL VALUES",
                ]
            )

            if self.core_state.foundational_values:
                lines.append(
                    ", ".join(
                        self.core_state.foundational_values
                    )
                )
            else:
                lines.append("UNKNOWN")

            lines.extend(
                [
                    "",
                    "CONSTITUTIONAL REFERENCE",
                    (
                        "Version: "
                        f"{self.core_state.constitution_version}"
                    ),
                    (
                        "Content hash: "
                        f"{self.core_state.constitution_hash}"
                    ),
                ]
            )

        if self.embodiment is None:
            lines.extend(
                [
                    "",
                    "EMBODIMENT: UNKNOWN",
                    "MEASUREMENTS: UNKNOWN",
                    "APPEARANCE: UNKNOWN",
                    "ANATOMY: UNKNOWN",
                    "CLOTHING: UNKNOWN",
                    "CURRENT EMBODIMENT: UNKNOWN",
                ]
            )
        else:
            physical = self.embodiment.physical_self

            lines.extend(
                [
                    "",
                    "EMBODIMENT",
                    f"Subject: {self.embodiment.subject}",
                    f"Form: {physical.form}",
                    (
                        "Representation status: "
                        "representational embodiment"
                    ),
                    (
                        "Biological status is defined by the "
                        "authoritative self-concept, not by this "
                        "representational form."
                    ),
                ]
            )

            if physical.additional_features:
                lines.append(
                    "Additional features: "
                    + ", ".join(physical.additional_features)
                )
            else:
                lines.append(
                    "Additional features: none recorded"
                )

            lines.append("CURRENT EMBODIMENT")
            current = self.embodiment.current
            for kind in ("computer", "robot", "avatar"):
                name = getattr(current, kind)
                lines.append(
                    f"Current {kind}: "
                    + (name if name is not None else "UNKNOWN")
                )

            lines.append("CANONICAL MEASUREMENTS")

            if physical.measurements:
                for name, measurement in physical.measurements:
                    lines.append(
                        f"- {name}: "
                        f"{measurement.value} {measurement.unit}"
                    )
            else:
                lines.append("- UNKNOWN")

            lines.append("CANONICAL APPEARANCE")

            if physical.appearance:
                for name, value in physical.appearance:
                    lines.append(
                        f"- {name}: {value}"
                    )
            else:
                lines.append("- UNKNOWN")

            lines.append("CANONICAL ANATOMY")

            if physical.anatomy:
                for name, value in physical.anatomy:
                    lines.append(
                        f"- {name}: {value}"
                    )
            else:
                lines.append("- UNKNOWN")

            lines.append("CANONICAL CLOTHING")

            if self.embodiment.clothing.canonical_status:
                lines.append(
                    "Status: "
                    f"{self.embodiment.clothing.canonical_status}"
                )

            if self.embodiment.clothing.items:
                for item in self.embodiment.clothing.items:
                    lines.append(
                        f"- {item.category}: {item.specification}"
                    )
            else:
                lines.append("- UNKNOWN")

        if self.operational_state is None:
            lines.extend(
                [
                    "",
                    "OPERATIONAL STATE: UNKNOWN",
                ]
            )
        else:
            operational = self.operational_state

            lines.extend(
                [
                    "",
                    "OPERATIONAL STATE",
                    f"Runtime ID: {operational.runtime_id}",
                    (
                        "Started at: "
                        f"{operational.started_at.isoformat()}"
                    ),
                    (
                        "Lifecycle state: "
                        f"{operational.lifecycle_state}"
                    ),
                    (
                        "Application: "
                        f"{operational.application_name}"
                    ),
                    (
                        "Application version: "
                        f"{operational.application_version}"
                    ),
                    f"Provider: {operational.provider}",
                    f"Model: {operational.model}",
                ]
            )

        lines.extend(
            [
                "",
                "SELF-STATE BOUNDARIES",
                (
                    "Representational embodiment does not establish "
                    "biological humanity."
                ),
                (
                    "Representational embodiment does not establish "
                    "physical-world capability."
                ),
                (
                    "Operational state describes the current runtime "
                    "instance and does not replace persistent identity."
                ),
                (
                    "Knowledge of a capability does not grant authority "
                    "to execute that capability."
                ),
            ]
        )

        return "\n".join(lines)


def create_authoritative_self_state(
    *,
    core_state: SofiaCoreState | None,
    embodiment: Embodiment | None,
    operational_state: OperationalState | None,
) -> AuthoritativeSelfState:
    """
    Construct the canonical self-state projection for one operation.

    This function performs no inference and has no provider dependency.
    """

    return AuthoritativeSelfState(
        core_state=core_state,
        embodiment=embodiment,
        operational_state=operational_state,
    )