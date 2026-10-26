"""Fail-closed component update impact analysis.

The planner is deliberately inert: it computes the smallest reviewed
maintenance scope from the component supervisor's registered dependency
graph.  It never stages a package, consumes an approval, or starts/stops a
component.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Mapping

from .components import ComponentKind


_ID = re.compile(r"^[a-z][a-z0-9_.-]{0,95}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


class UpdateChangeKind(str, Enum):
    CORE_ONLY = "core_only"
    MODULE_ONLY = "module_only"
    INFERENCE_ONLY = "inference_only"
    PLATFORM = "platform"
    SHARED_ABI = "shared_abi"
    DATA_ONLY = "data_only"
    STATE_SCHEMA = "state_schema"


@dataclass(frozen=True, slots=True)
class ComponentUpdateCandidate:
    change_kind: UpdateChangeKind
    source_digest: str
    target_digest: str
    component_id: str | None = None
    compatibility_verified: bool | None = None
    atomic_reload_supported: bool = False
    abi_consumers: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.change_kind, UpdateChangeKind):
            raise TypeError("change_kind must be UpdateChangeKind")
        for label, value in (
            ("source_digest", self.source_digest),
            ("target_digest", self.target_digest),
        ):
            if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
                raise ValueError(f"{label} must be SHA-256")
        if self.source_digest == self.target_digest:
            raise ValueError("source and target releases must differ")
        if self.component_id is not None and (
            not isinstance(self.component_id, str)
            or _ID.fullmatch(self.component_id) is None
        ):
            raise ValueError("component_id must be a bounded identifier")
        if self.compatibility_verified not in {True, False, None}:
            raise TypeError("compatibility_verified must be bool or None")
        if type(self.atomic_reload_supported) is not bool:
            raise TypeError("atomic_reload_supported must be bool")
        if type(self.abi_consumers) is not tuple or any(
            not isinstance(item, str) or _ID.fullmatch(item) is None
            for item in self.abi_consumers
        ) or len(set(self.abi_consumers)) != len(self.abi_consumers):
            raise ValueError("abi_consumers must be unique component identifiers")


@dataclass(frozen=True, slots=True)
class UpdateImpactPlan:
    candidate: ComponentUpdateCandidate
    drain_components: tuple[str, ...]
    pause_dependents: tuple[str, ...]
    unaffected_components: tuple[str, ...]
    platform_restart_required: bool
    impact_resolved: bool
    blocked_reasons: tuple[str, ...]

    @property
    def blocked(self) -> bool:
        return bool(self.blocked_reasons)


def plan_component_update(
    candidate: ComponentUpdateCandidate,
    *,
    component_kinds: Mapping[str, ComponentKind],
    dependencies: Mapping[str, tuple[str, ...]],
    active_release_digests: Mapping[str, str],
) -> UpdateImpactPlan:
    """Return deterministic impact from authoritative registered topology."""
    if not isinstance(candidate, ComponentUpdateCandidate):
        raise TypeError("candidate must be ComponentUpdateCandidate")
    nodes = set(component_kinds)
    if nodes != set(dependencies):
        raise ValueError("component kind and dependency topology must match")
    if any(not isinstance(kind, ComponentKind) for kind in component_kinds.values()):
        raise TypeError("component kinds must be typed")
    if any(dependency not in nodes for values in dependencies.values() for dependency in values):
        raise ValueError("dependency topology references an unknown component")
    if any(
        component not in nodes or _DIGEST.fullmatch(digest) is None
        for component, digest in active_release_digests.items()
    ):
        raise ValueError("active release evidence is invalid")

    blocked: list[str] = []
    if candidate.compatibility_verified is not True:
        blocked.append(
            "compatibility_failed" if candidate.compatibility_verified is False
            else "compatibility_unknown"
        )

    target = candidate.component_id
    component_scopes = {
        UpdateChangeKind.CORE_ONLY: ComponentKind.CORE,
        UpdateChangeKind.MODULE_ONLY: ComponentKind.OPTIONAL_MODULE,
        UpdateChangeKind.INFERENCE_ONLY: ComponentKind.INFERENCE,
    }
    expected_kind = component_scopes.get(candidate.change_kind)
    if expected_kind is not None:
        if target is None or target not in nodes:
            blocked.append("target_component_unknown")
        elif component_kinds[target] is not expected_kind:
            blocked.append("target_component_kind_mismatch")
        elif target not in active_release_digests:
            blocked.append("source_release_unknown")
        elif active_release_digests[target] != candidate.source_digest:
            blocked.append("source_release_mismatch")

    unknown_consumers = tuple(item for item in candidate.abi_consumers if item not in nodes)
    if unknown_consumers:
        blocked.append("abi_consumer_unknown")

    reverse: dict[str, set[str]] = {node: set() for node in nodes}
    for node, values in dependencies.items():
        for dependency in values:
            reverse[dependency].add(node)

    def dependent_closure(seeds: set[str]) -> set[str]:
        result: set[str] = set()
        pending = list(seeds)
        while pending:
            node = pending.pop()
            for dependent in reverse[node]:
                if dependent not in result and dependent not in seeds:
                    result.add(dependent)
                    pending.append(dependent)
        return result

    platform_restart = candidate.change_kind in {
        UpdateChangeKind.PLATFORM, UpdateChangeKind.STATE_SCHEMA,
    }
    drains: set[str] = set()
    pauses: set[str] = set()
    if expected_kind is not None and target in nodes:
        drains.add(target)
        pauses.update(dependent_closure({target}))
    elif candidate.change_kind is UpdateChangeKind.SHARED_ABI:
        if not candidate.abi_consumers:
            blocked.append("abi_consumers_required")
        else:
            drains.update(item for item in candidate.abi_consumers if item in nodes)
            pauses.update(dependent_closure(drains))
            platform_restart = any(
                component_kinds[item] is ComponentKind.PLATFORM
                for item in drains
            )
    elif candidate.change_kind is UpdateChangeKind.DATA_ONLY:
        if not candidate.atomic_reload_supported:
            blocked.append("atomic_reload_not_supported")
    elif candidate.change_kind in {UpdateChangeKind.PLATFORM, UpdateChangeKind.STATE_SCHEMA}:
        drains.update(nodes)

    pauses.difference_update(drains)
    affected = drains | pauses
    return UpdateImpactPlan(
        candidate=candidate,
        drain_components=tuple(sorted(drains)),
        pause_dependents=tuple(sorted(pauses)),
        unaffected_components=tuple(sorted(nodes - affected)),
        platform_restart_required=platform_restart,
        # This only means the maintenance scope is known. It is deliberately
        # not execution authorization or an instruction to activate.
        impact_resolved=not blocked,
        blocked_reasons=tuple(sorted(set(blocked))),
    )
