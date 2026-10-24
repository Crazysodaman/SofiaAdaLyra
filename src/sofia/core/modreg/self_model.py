"""Sofía's capability self-model over Platform observations.

Sofía's working understanding of her own capabilities is a projection
over exactly two evidence sources: her own module registry (Core-side,
untrusted-candidate manifests never treated as installed) and the
Platform's typed module observations (describe/health/placement/
outcomes). The eight catalog notions — discovered, compatible,
installed, active, authorized, available, healthy, verified-executed —
are kept distinct instead of blurred into one boolean. Anything the
Platform has not observed is UNKNOWN.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from sofia.core.modreg.platform import (
    ModuleDescribeObservation,
    ModuleObservationKind,
    OutcomeStatus,
    PlatformModuleObserver,
)
from sofia.core.modreg.registry import (
    ModuleRegistryError,
    ModuleRegistryService,
    TrustState,
)


class Grounding(str, Enum):
    """Tri-state for every aspect: observed yes/no or unknown."""

    YES = "observed_yes"
    NO = "observed_no"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class CapabilityPermissionAspect:
    """One capability's permission standing, honestly tri-stated."""

    capability: str
    permission_required: Grounding
    grant_state: Grounding

    def __post_init__(self) -> None:
        for value in (self.permission_required, self.grant_state):
            if not isinstance(value, Grounding):
                raise TypeError("permission aspects must be Grounding")


@dataclass(frozen=True, slots=True)
class ModuleAwarenessRow:
    """One logical module's distinct-state awareness row.

    `compatible` carries the registry compatibility verdict for a
    verified manifest (never a file-existence claim).
    """

    module_id: str
    version: Grounding
    version_text: str | None
    manifest_trust: Grounding
    discovered: Grounding
    installed: Grounding
    active: Grounding
    healthy: Grounding
    available: Grounding
    capabilities: tuple[str, ...]
    permission_aspects: tuple[CapabilityPermissionAspect, ...]
    simulated_capabilities: tuple[str, ...]
    verified_outcomes: int
    denied_outcomes: int
    unverified_outcomes: int
    placements: tuple[tuple[str, str, str], ...]
    compatible: Grounding
    notes: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.module_id, str) or not self.module_id:
            raise ValueError("module_id must be nonempty")
        names = (
            self.version,
            self.manifest_trust,
            self.discovered,
            self.installed,
            self.active,
            self.healthy,
            self.available,
            self.compatible,
        )
        if any(not isinstance(item, Grounding) for item in names):
            raise TypeError("awareness fields must be Grounding enums")
        if self.version_text is not None and not isinstance(
            self.version_text, str
        ):
            raise TypeError("version_text must be str or None")

    def required_permissions(self) -> tuple[str, ...]:
        """Capabilities explicitly marked permission-required."""
        return tuple(
            aspect.capability
            for aspect in self.permission_aspects
            if aspect.permission_required is Grounding.YES
        )


_HEALTH_OK = ModuleObservationKind.HEALTHY


def _now() -> datetime:
    return datetime.now(timezone.utc)


class CapabilitySelfModel:
    """Read-only projection; never a capability store and never a grant."""

    def __init__(
        self,
        registry: ModuleRegistryService | None,
        platform: PlatformModuleObserver | None,
    ) -> None:
        if registry is not None and not isinstance(
            registry, ModuleRegistryService
        ):
            raise TypeError("registry must be a ModuleRegistryService or None")
        if platform is not None and not isinstance(
            platform, PlatformModuleObserver
        ):
            raise TypeError(
                "platform must be a PlatformModuleObserver or None"
            )
        self._registry = registry
        self._platform = platform
        self._compat_cache: dict[
            str, dict[str, str]
        ] | None = None

    def set_platform_observer(
        self, observer: PlatformModuleObserver | None,
    ) -> None:
        """Composition-time injection of the typed Platform observer."""
        if observer is not None and not isinstance(
            observer, PlatformModuleObserver
        ):
            raise TypeError("observer must be a PlatformModuleObserver or None")
        self._platform = observer

    def _compatibility(
        self, registry, name: str,
    ) -> tuple[str, ...]:
        try:
            entries = registry.compatibility_report(name)
        except (LookupError, ModuleRegistryError):
            return ("registry-error:compatibility",)
        verdicts = dict(entries)
        return tuple(
            f"dependency:{dep}:{verdict}"
            for dep, verdict in verdicts.items()
            if verdict != "compatible"
        ) or ("all-compatible",)

    def _registry_rows(
        self,
    ) -> tuple[dict[str, TrustState], dict[str, str]]:
        if self._registry is None:
            return {}, {}
        snapshot: dict[str, TrustState] = {}
        versions: dict[str, str] = {}
        for registration in self._registry.store.all_current():
            snapshot[registration.manifest.name] = (
                registration.trust_state
            )
            versions[registration.manifest.name] = (
                registration.manifest.version
            )
        return snapshot, versions

    def project(
        self,
        *,
        now: datetime | None = None,
    ) -> tuple[ModuleAwarenessRow, ...]:
        moment = now or _now()
        if now is not None and (
            now.tzinfo is None or now.utcoffset() is None
        ):
            raise ValueError("now must be timezone-aware")
        trust, versions = self._registry_rows()
        described: dict[str, ModuleDescribeObservation] = {}
        health_rows: dict[str, list] = {}
        placements: dict[str, list] = {}
        outcomes: dict[str, list] = {}
        if self._platform is not None:
            for row in self._platform.described():
                described.setdefault(row.module_id, row)
            for row in self._platform.health():
                health_rows.setdefault(row.module_instance_id, []).append(row)
            for row in self._platform.placements():
                placements.setdefault(row.module_id, []).append(row)
            for row in self._platform.outcomes():
                outcomes.setdefault(row.module_id, []).append(row)
        health_modules = {
            instance_id.split("@", 1)[0]
            for instance_id in health_rows
        }
        names = sorted(
            set(trust) | set(described) | set(placements) | health_modules
        )
        rows: list[ModuleAwarenessRow] = []
        for module_id in names:
            instance_rows = [
                row
                for key, sample in health_rows.items()
                if key == module_id or key.startswith(module_id + "@")
                for row in sample
            ]
            latest_by_instance = {}
            for sample in instance_rows:
                previous = latest_by_instance.get(sample.module_instance_id)
                if previous is None or sample.observed_at > previous.observed_at:
                    latest_by_instance[sample.module_instance_id] = sample
            latest_rows = tuple(latest_by_instance.values())
            fresh_rows = tuple(
                sample for sample in latest_rows
                if sample.fresh_until >= moment
            )
            row_stale = bool(latest_rows) and len(fresh_rows) != len(latest_rows)
            inactive_observed = any(
                sample.lifecycle != "ACTIVE" for sample in fresh_rows
            )
            unhealthy_observed = any(
                sample.health is not _HEALTH_OK for sample in fresh_rows
            )
            blocked_observed = any(
                sample.blocked_dependencies for sample in fresh_rows
            )
            if module_id in described:
                installed_state = Grounding.YES
            else:
                # An observer returning no row is absence of evidence, not a
                # complete negative inventory of every possible host/module.
                installed_state = Grounding.UNKNOWN
            active = (
                Grounding.NO if inactive_observed
                else Grounding.YES if fresh_rows and not row_stale
                else Grounding.UNKNOWN
            )
            healthy = (
                Grounding.NO if unhealthy_observed or blocked_observed
                else Grounding.YES if fresh_rows and not row_stale
                else Grounding.UNKNOWN
            )
            if (
                installed_state is Grounding.YES
                and active is Grounding.YES
                and healthy is Grounding.YES
            ):
                available = Grounding.YES
            elif installed_state is Grounding.UNKNOWN:
                available = Grounding.UNKNOWN
            else:
                available = Grounding.NO
            capability_specs: tuple[str, ...] = (
                described[module_id].capabilities
                if module_id in described
                else ()
            )
            permission_required_map: dict[str, bool] = (
                {
                    capability: capability in described[
                        module_id
                    ].requires_permission
                    for capability in capability_specs
                }
            )
            aspects = tuple(
                CapabilityPermissionAspect(
                    capability=capability,
                    permission_required=(
                        Grounding.YES
                        if permission_required_map[capability]
                        else Grounding.NO
                    )
                    if module_id in described
                    else Grounding.UNKNOWN,
                    # Historical outcomes describe past attempts. They are
                    # never evidence of a current, scoped, unexpired grant.
                    grant_state=Grounding.UNKNOWN,
                )
                for capability in capability_specs
            )
            verified = sum(
                1
                for outcome in outcomes.get(module_id, [])
                if outcome.status is OutcomeStatus.SUCCEEDED_VERIFIED
            )
            denied = sum(
                1
                for outcome in outcomes.get(module_id, [])
                if outcome.status is OutcomeStatus.DENIED
            )
            unverified = sum(
                1
                for outcome in outcomes.get(module_id, [])
                if outcome.status
                in (
                    OutcomeStatus.SUCCEEDED_REPORTED_UNVERIFIED,
                    OutcomeStatus.OUTCOME_UNKNOWN,
                )
            )
            sim = frozenset(
                described[module_id].simulated_only
            ) if module_id in described else frozenset()
            placement_rows = tuple(
                sorted(
                    (c.component, c.host_identity, c.placement_mode.value)
                    for c in placements.get(module_id, [])
                )
            )
            state = trust.get(module_id)
            compat = self._compatibility(self._registry, module_id) if (
                state is TrustState.VERIFIED and self._registry is not None
            ) else ()
            compatible = (
                Grounding.YES if compat == ("all-compatible",)
                else (
                    Grounding.NO if compat
                    else Grounding.UNKNOWN
                )
            )
            notes = list(
                compat if compat and compat != ("all-compatible",) else ()
            )
            if row_stale:
                notes.append("stale-observation")
            rows.append(
                ModuleAwarenessRow(
                    module_id=module_id,
                    version=(
                        Grounding.UNKNOWN
                        if not versions.get(
                            module_id,
                            described[module_id].version
                            if module_id in described else None,
                        )
                        else Grounding.YES
                    ),
                    version_text=versions.get(
                        module_id,
                        described[module_id].version
                        if module_id in described else None,
                    ),
                    manifest_trust=(
                        Grounding.YES if state is TrustState.VERIFIED
                        else (
                            Grounding.NO if state is not None
                            else Grounding.UNKNOWN
                        )
                    ),
                    discovered=(
                        Grounding.YES if state is not None else Grounding.NO
                    ) if self._registry is not None else Grounding.UNKNOWN,
                    installed=installed_state,
                    active=active,
                    healthy=healthy,
                    available=available,
                    capabilities=capability_specs,
                    permission_aspects=aspects,
                    simulated_capabilities=tuple(sorted(sim)),
                    verified_outcomes=verified,
                    denied_outcomes=denied,
                    unverified_outcomes=unverified,
                    placements=placement_rows,
                    compatible=compatible,
                    notes=tuple(notes),
                )
            )
        return tuple(rows)

    def awareness_summary(
        self, *, limit: int = 2000,
    ) -> str:
        """Bounded honest summary for Sofía's own working context."""
        rows = self.project()
        lines = [
            "SOFÍA'S MODULE AWARENESS (Platform observations + own manifest"
            " registry; availability never implies authority; unknowns stay"
            " unknown):"
        ]
        if not rows:
            lines.append(
                "- No module rows observed; Core itself remains running."
            )
        for row in rows:
            line = (
                f"- {row.module_id}"
                + (f" {row.version_text}" if row.version else "")
            )
            if row.installed is Grounding.YES:
                line += "; installed"
                line += ", active" if row.active is Grounding.YES else (
                    ", not active"
                    if row.active is Grounding.NO else ""
                )
                if row.available is Grounding.YES:
                    line += ", available"
                elif row.available is Grounding.NO:
                    line += ", unavailable"
            else:
                line += "; not installed"
            if row.discovered is Grounding.YES:
                line += ", manifest verified" if (
                    row.manifest_trust is Grounding.YES
                ) else ", candidate manifest only"
            if row.required_permissions():
                line += f"; permissions required: {row.required_permissions()}"
            if row.simulated_capabilities:
                line += "; simulated only: " + ", ".join(
                    row.simulated_capabilities
                )
            if row.verified_outcomes:
                line += f"; verified outcomes: {row.verified_outcomes}"
            if row.denied_outcomes:
                line += f"; denial observations: {row.denied_outcomes}"
            if row.unverified_outcomes:
                line += f"; unverified outcomes: {row.unverified_outcomes}"
            for component, host, mode in row.placements:
                line += f"; {component}@{host}({mode})"
            for note in row.notes:
                line += f"; {note}"
            lines.append(line)
        text = "\n".join(lines)
        if len(text) <= limit:
            return text
        truncated = text[: limit].rsplit("\n", 1)[0]
        return truncated + "\n[module awareness summary truncated]"
