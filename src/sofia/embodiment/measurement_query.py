from dataclasses import dataclass

from sofia.embodiment.model import Embodiment, Measurement


@dataclass(frozen=True)
class MeasurementFact:
    """
    One authoritative embodiment measurement resolved for cognition.

    The value is retrieved directly from the canonical embodiment state.
    """

    name: str
    measurement: Measurement

    def __post_init__(self) -> None:
        if not isinstance(self.name, str):
            raise TypeError(
                "MeasurementFact name must be a string."
            )

        if not self.name:
            raise ValueError(
                "MeasurementFact name must not be empty."
            )

        if not isinstance(self.measurement, Measurement):
            raise TypeError(
                "MeasurementFact measurement must be a Measurement."
            )


@dataclass(frozen=True)
class MeasurementQueryResult:
    """
    Deterministic result of resolving a natural-language measurement query.

    recognized=False means the request is not a supported canonical
    measurement query. No authoritative lookup is performed in that case.
    """

    recognized: bool
    facts: tuple[MeasurementFact, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.recognized, bool):
            raise TypeError(
                "MeasurementQueryResult recognized must be a bool."
            )

        if not isinstance(self.facts, tuple):
            raise TypeError(
                "MeasurementQueryResult facts must be a tuple."
            )

        for fact in self.facts:
            if not isinstance(fact, MeasurementFact):
                raise TypeError(
                    "MeasurementQueryResult facts must contain "
                    "MeasurementFact instances."
                )

        if not self.recognized and self.facts:
            raise ValueError(
                "Unrecognized measurement queries cannot contain facts."
            )


class MeasurementQueryResolver:
    """
    Deterministically recognizes and resolves canonical measurement queries.

    Query recognition is intentionally conservative. This class does not
    use an LLM, fuzzy matching, semantic inference, unit conversion, or
    generated values.

    Once a supported measurement query is recognized, every canonical
    measurement is retrieved directly from the authoritative Embodiment.
    """

    _SUPPORTED_QUERY_FORMS = frozenset(
        {
            "what are your measurements",
            "what are your body measurements",
            "what are your canonical measurements",
            "what are your canonical body measurements",
            "tell me your measurements",
            "tell me your body measurements",
            "tell me your canonical measurements",
            "tell me your canonical body measurements",
            "give me your measurements",
            "give me your body measurements",
            "give me your canonical measurements",
            "give me your canonical body measurements",
            "what is your height weight bust underbust waist and hips",
            "what are your height weight bust underbust waist and hips",
        }
    )

    _CANONICAL_MEASUREMENT_NAMES = (
        "height",
        "weight",
        "bust",
        "underbust",
        "waist",
        "hips",
    )

    def resolve(
        self,
        query: str,
        embodiment: Embodiment,
    ) -> MeasurementQueryResult:
        """
        Recognize and resolve a canonical measurement query.

        Unsupported queries return an unrecognized result without
        accessing embodiment measurements.
        """

        if not isinstance(query, str):
            raise TypeError(
                "Measurement query must be a string."
            )

        if not isinstance(embodiment, Embodiment):
            raise TypeError(
                "Measurement query resolver embodiment must be an "
                "Embodiment."
            )

        normalized_query = self._normalize_query(query)

        if normalized_query not in self._SUPPORTED_QUERY_FORMS:
            return MeasurementQueryResult(
                recognized=False,
            )

        facts = tuple(
            MeasurementFact(
                name=name,
                measurement=embodiment.get_measurement(name),
            )
            for name in self._CANONICAL_MEASUREMENT_NAMES
        )

        return MeasurementQueryResult(
            recognized=True,
            facts=facts,
        )

    @staticmethod
    def _normalize_query(query: str) -> str:
        normalized = " ".join(
            query.strip().lower().split()
        )

        if normalized.endswith("?"):
            normalized = normalized[:-1].rstrip()

        return normalized