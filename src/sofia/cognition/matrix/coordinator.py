"""Matrix coordinator and evaluator registry."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .classifier import BaselineTurnClassifier
from .model import DomainContribution, MatrixDomain, TurnEnvelope, TurnMatrix


class TurnClassifier(Protocol):
    def classify(self, envelope: TurnEnvelope) -> TurnMatrix: ...


class MatrixDomainEvaluator(Protocol):
    domain: MatrixDomain

    def evaluate(
        self,
        envelope: TurnEnvelope,
        turn: TurnMatrix,
    ) -> DomainContribution | None: ...


@dataclass(frozen=True, slots=True)
class MatrixRegistry:
    evaluators: tuple[MatrixDomainEvaluator, ...] = ()

    def __post_init__(self) -> None:
        seen = set()
        for evaluator in self.evaluators:
            domain = getattr(evaluator, "domain", None)
            if not isinstance(domain, MatrixDomain):
                raise TypeError(
                    "matrix evaluators must expose a MatrixDomain 'domain'"
                )
            if domain in seen:
                raise ValueError(
                    f"duplicate matrix evaluator for domain {domain.value}"
                )
            seen.add(domain)


class MatrixCoordinator:
    """Compose a turn matrix without granting truth or authority."""

    def __init__(
        self,
        *,
        classifier: TurnClassifier | None = None,
        registry: MatrixRegistry | None = None,
    ) -> None:
        self.classifier = classifier or BaselineTurnClassifier()
        self.registry = registry or MatrixRegistry()

    def evaluate(self, envelope: TurnEnvelope) -> TurnMatrix:
        if not isinstance(envelope, TurnEnvelope):
            raise TypeError("envelope must be TurnEnvelope")
        turn = self.classifier.classify(envelope)
        contributions = {
            contribution.domain: contribution
            for contribution in turn.domains
        }
        for evaluator in self.registry.evaluators:
            candidate = evaluator.evaluate(envelope, turn)
            if candidate is None:
                continue
            if not isinstance(candidate, DomainContribution):
                raise TypeError(
                    "matrix evaluator must return DomainContribution or None"
                )
            current = contributions.get(candidate.domain)
            if (
                current is None
                or candidate.relevance.value > current.relevance.value
            ):
                contributions[candidate.domain] = candidate
        return TurnMatrix(
            intent=turn.intent,
            confidence=turn.confidence,
            history_policy=turn.history_policy,
            response_strategy=turn.response_strategy,
            domains=tuple(
                contributions[key]
                for key in sorted(
                    contributions,
                    key=lambda item: item.value,
                )
            ),
            ambiguous=turn.ambiguous,
            schema_version=turn.schema_version,
        )
