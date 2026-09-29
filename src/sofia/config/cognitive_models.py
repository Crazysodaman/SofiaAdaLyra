"""Resolve effective cognitive model roles from runtime configuration."""
from __future__ import annotations

from dataclasses import dataclass

from sofia.config.model import ProviderConfiguration, SofiaConfiguration


@dataclass(frozen=True, slots=True)
class CognitiveModelSelection:
    """Effective provider roles without any concrete model-name assumptions."""

    routing_enabled: bool
    primary: ProviderConfiguration
    secondary: ProviderConfiguration | None = None

    @classmethod
    def from_configuration(
        cls,
        configuration: SofiaConfiguration,
    ) -> "CognitiveModelSelection":
        if not isinstance(configuration, SofiaConfiguration):
            raise TypeError("configuration must be a SofiaConfiguration")

        routing = configuration.routing
        if routing is not None and routing.enabled:
            if routing.primary is None or routing.secondary is None:
                raise ValueError(
                    "enabled cognitive routing requires primary and secondary "
                    "provider configurations"
                )
            return cls(
                routing_enabled=True,
                primary=routing.primary,
                secondary=routing.secondary,
            )

        return cls(
            routing_enabled=False,
            primary=configuration.provider,
            secondary=None,
        )

    @property
    def providers(self) -> tuple[ProviderConfiguration, ...]:
        if self.secondary is None:
            return (self.primary,)
        return (self.primary, self.secondary)

    @property
    def model_names(self) -> tuple[str, ...]:
        """Return configured model names once each, preserving role order."""
        return tuple(
            dict.fromkeys(provider.model for provider in self.providers)
        )
