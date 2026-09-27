"""Shared least-privilege integration descriptor and health contract."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class SideEffectClass(str, Enum):
    READ_ONLY = "read_only"
    REVERSIBLE_WRITE = "reversible_write"
    DESTRUCTIVE = "destructive"
    EXTERNAL_DELIVERY = "external_delivery"


@dataclass(frozen=True, slots=True)
class IntegrationDescriptor:
    adapter_id: str
    service: str
    version: str
    host_id: str | None
    account_id: str | None
    capabilities: tuple[str, ...]
    side_effect_class: SideEffectClass

    def __post_init__(self) -> None:
        for label, value in (
            ("adapter_id", self.adapter_id),
            ("service", self.service),
            ("version", self.version),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{label} required")
        if not isinstance(self.capabilities, tuple) or any(
            not isinstance(item, str) or not item.strip()
            for item in self.capabilities
        ):
            raise ValueError("capabilities must be a tuple of nonempty strings")
        if len(set(self.capabilities)) != len(self.capabilities):
            raise ValueError("capabilities must be unique")
        if not isinstance(self.side_effect_class, SideEffectClass):
            raise TypeError("side_effect_class must be SideEffectClass")


@dataclass(frozen=True, slots=True)
class IntegrationHealth:
    adapter_id: str
    observed_at: datetime
    available: bool
    version: str | None = None
    detail: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.adapter_id, str) or not self.adapter_id.strip():
            raise ValueError("adapter_id required")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        if not isinstance(self.available, bool):
            raise TypeError("available must be boolean")
        if self.version is not None and not self.version.strip():
            raise ValueError("version must be nonempty when set")
