"""Deterministic release/schema/Fleet compatibility matrix.

This VERIFY-owned matrix consumes immutable release metadata plus independently
observed host/build/trust evidence. It never signs a release, grants activation
authority, or invents missing evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re

from sofia.dev.release import ReleaseManifest
from sofia.distributed.version import FleetProtocolVersion


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA = re.compile(r"^[0-9a-f]{40}$")


class CompatibilityState(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True, slots=True)
class CompatibilityCheck:
    dimension: str
    state: CompatibilityState
    required: bool
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.dimension, str) or not self.dimension.strip():
            raise ValueError("compatibility dimension must be nonempty")
        if not isinstance(self.state, CompatibilityState):
            raise TypeError("state must be CompatibilityState")
        if type(self.required) is not bool:
            raise TypeError("required must be bool")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("compatibility reason must be nonempty")


@dataclass(frozen=True, slots=True)
class ReleaseCompatibilityInputs:
    git_revision: str
    application_version: str
    python_version: str
    dependency_lock_sha256: str
    sbom_sha256: str
    provenance_sha256: str
    state_schema_revision: int
    fleet_protocol_version: str
    fleet_agent_version: str
    constitution_sha256: str
    configuration_schema_version: int
    source_tests_passed: bool
    semantic_integrity_verified: bool
    signature_verified: bool
    lineage_verified: bool
    anti_rollback_verified: bool
    artifact_sha256: str | None = None
    model_id: str | None = None
    model_sha256: str | None = None
    asset_sha256: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if _GIT_SHA.fullmatch(self.git_revision) is None:
            raise ValueError("git_revision must be a lowercase 40-character SHA")
        for name in (
            "application_version",
            "python_version",
            "fleet_protocol_version",
            "fleet_agent_version",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be nonempty")
        for name in (
            "dependency_lock_sha256",
            "sbom_sha256",
            "provenance_sha256",
            "constitution_sha256",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
                raise ValueError(f"{name} must be a lowercase SHA-256 digest")
        if self.artifact_sha256 is not None and _SHA256.fullmatch(
            self.artifact_sha256
        ) is None:
            raise ValueError("artifact_sha256 must be None or lowercase SHA-256")
        if self.model_sha256 is not None and _SHA256.fullmatch(
            self.model_sha256
        ) is None:
            raise ValueError("model_sha256 must be None or lowercase SHA-256")
        if self.model_id is not None and (
            not isinstance(self.model_id, str) or not self.model_id.strip()
        ):
            raise ValueError("model_id must be None or nonempty")
        if self.model_sha256 is not None and self.model_id is None:
            raise ValueError("model_sha256 requires model_id")
        if type(self.state_schema_revision) is not int or self.state_schema_revision < 1:
            raise ValueError("state_schema_revision must be positive")
        if (
            type(self.configuration_schema_version) is not int
            or self.configuration_schema_version < 1
        ):
            raise ValueError("configuration_schema_version must be positive")
        for name in (
            "source_tests_passed",
            "semantic_integrity_verified",
            "signature_verified",
            "lineage_verified",
            "anti_rollback_verified",
        ):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"{name} must be bool")
        if not isinstance(self.asset_sha256, tuple):
            raise TypeError("asset_sha256 must be a tuple")
        seen: set[str] = set()
        for name, digest in self.asset_sha256:
            if not isinstance(name, str) or not name.strip() or name in seen:
                raise ValueError("asset names must be distinct and nonempty")
            if _SHA256.fullmatch(digest) is None:
                raise ValueError("asset digests must be lowercase SHA-256")
            seen.add(name)
        FleetProtocolVersion.parse(self.fleet_protocol_version)


@dataclass(frozen=True, slots=True)
class ReleaseCompatibilityResult:
    release_id: str
    checks: tuple[CompatibilityCheck, ...]

    @property
    def accepted(self) -> bool:
        return all(
            check.state is CompatibilityState.PASS
            for check in self.checks
            if check.required
        )

    @property
    def failures(self) -> tuple[CompatibilityCheck, ...]:
        return tuple(
            check
            for check in self.checks
            if check.required and check.state is not CompatibilityState.PASS
        )

    @property
    def warnings(self) -> tuple[CompatibilityCheck, ...]:
        return tuple(
            check
            for check in self.checks
            if not check.required
            and check.state in {
                CompatibilityState.FAIL,
                CompatibilityState.UNKNOWN,
            }
        )


class ReleaseCompatibilityMatrix:
    """Evaluate one release candidate without granting activation authority."""

    @staticmethod
    def _equal(
        dimension: str,
        observed,
        expected,
        *,
        required: bool = True,
    ) -> CompatibilityCheck:
        matched = observed == expected
        return CompatibilityCheck(
            dimension,
            CompatibilityState.PASS if matched else CompatibilityState.FAIL,
            required,
            (
                "observed value matches release manifest"
                if matched
                else "observed value does not match release manifest"
            ),
        )

    @staticmethod
    def _boolean(dimension: str, value: bool) -> CompatibilityCheck:
        return CompatibilityCheck(
            dimension,
            CompatibilityState.PASS if value else CompatibilityState.FAIL,
            True,
            "independent evidence is affirmative" if value else "independent evidence is not affirmative",
        )

    def evaluate(
        self,
        manifest: ReleaseManifest,
        observed: ReleaseCompatibilityInputs,
    ) -> ReleaseCompatibilityResult:
        if not isinstance(manifest, ReleaseManifest):
            raise TypeError("manifest must be ReleaseManifest")
        if not isinstance(observed, ReleaseCompatibilityInputs):
            raise TypeError("observed must be ReleaseCompatibilityInputs")

        checks: list[CompatibilityCheck] = [
            self._equal("git_revision", observed.git_revision, manifest.git_revision),
            self._equal(
                "application_version",
                observed.application_version,
                manifest.application_version,
            ),
            self._equal("python_version", observed.python_version, manifest.python_version),
            self._equal(
                "dependency_lock",
                observed.dependency_lock_sha256,
                manifest.dependency_lock_sha256,
            ),
            self._equal("sbom", observed.sbom_sha256, manifest.sbom_sha256),
            self._equal(
                "provenance",
                observed.provenance_sha256,
                manifest.provenance_sha256,
            ),
            CompatibilityCheck(
                "state_schema",
                (
                    CompatibilityState.PASS
                    if manifest.supports_state_schema(observed.state_schema_revision)
                    else CompatibilityState.FAIL
                ),
                True,
                (
                    "State Plane schema is inside the release compatibility window"
                    if manifest.supports_state_schema(observed.state_schema_revision)
                    else "State Plane schema is outside the release compatibility window"
                ),
            ),
            self._equal(
                "configuration_schema",
                observed.configuration_schema_version,
                manifest.configuration_schema_version,
            ),
            self._equal(
                "fleet_agent_version",
                observed.fleet_agent_version,
                manifest.fleet_agent_version,
            ),
            self._equal(
                "constitution",
                observed.constitution_sha256,
                manifest.constitution_sha256,
            ),
            self._boolean("source_tests", observed.source_tests_passed),
            self._boolean(
                "semantic_integrity",
                observed.semantic_integrity_verified,
            ),
            self._boolean("signature", observed.signature_verified),
            self._boolean("lineage", observed.lineage_verified),
            self._boolean("anti_rollback", observed.anti_rollback_verified),
        ]

        required_protocol = FleetProtocolVersion.parse(
            manifest.fleet_protocol_version
        )
        actual_protocol = FleetProtocolVersion.parse(
            observed.fleet_protocol_version
        )
        protocol_ok = actual_protocol.compatible_with(required_protocol)
        checks.append(
            CompatibilityCheck(
                "fleet_protocol",
                CompatibilityState.PASS if protocol_ok else CompatibilityState.FAIL,
                True,
                (
                    "observed Fleet protocol satisfies the release requirement"
                    if protocol_ok
                    else "observed Fleet protocol is incompatible with the release"
                ),
            )
        )

        if manifest.artifact_sha256 is None:
            checks.append(
                CompatibilityCheck(
                    "artifact",
                    CompatibilityState.UNKNOWN,
                    False,
                    "release manifest does not pin a deployable artifact digest",
                )
            )
        elif observed.artifact_sha256 is None:
            checks.append(
                CompatibilityCheck(
                    "artifact",
                    CompatibilityState.UNKNOWN,
                    True,
                    "release requires an artifact digest but none was observed",
                )
            )
        else:
            checks.append(
                self._equal(
                    "artifact",
                    observed.artifact_sha256,
                    manifest.artifact_sha256,
                )
            )

        expected_assets = dict(manifest.asset_sha256)
        observed_assets = dict(observed.asset_sha256)
        if not expected_assets:
            checks.append(
                CompatibilityCheck(
                    "assets",
                    CompatibilityState.NOT_APPLICABLE,
                    False,
                    "release manifest does not pin additional assets",
                )
            )
        else:
            assets_ok = all(
                observed_assets.get(name) == digest
                for name, digest in expected_assets.items()
            )
            checks.append(
                CompatibilityCheck(
                    "assets",
                    CompatibilityState.PASS if assets_ok else CompatibilityState.FAIL,
                    True,
                    (
                        "all manifest-pinned assets match"
                        if assets_ok
                        else "one or more manifest-pinned assets are missing or mismatched"
                    ),
                )
            )

        if manifest.model_id is None:
            checks.append(
                CompatibilityCheck(
                    "model_identity",
                    CompatibilityState.NOT_APPLICABLE,
                    False,
                    "release manifest does not pin a cognitive model",
                )
            )
        else:
            checks.append(
                self._equal(
                    "model_identity",
                    observed.model_id,
                    manifest.model_id,
                )
            )
            if manifest.model_sha256 is None:
                checks.append(
                    CompatibilityCheck(
                        "model_digest",
                        CompatibilityState.UNKNOWN,
                        False,
                        "model identity is pinned but model bytes are not digest-pinned",
                    )
                )
            elif observed.model_sha256 is None:
                checks.append(
                    CompatibilityCheck(
                        "model_digest",
                        CompatibilityState.UNKNOWN,
                        True,
                        "release pins model bytes but no observed model digest is available",
                    )
                )
            else:
                checks.append(
                    self._equal(
                        "model_digest",
                        observed.model_sha256,
                        manifest.model_sha256,
                    )
                )

        return ReleaseCompatibilityResult(
            release_id=manifest.release_id,
            checks=tuple(checks),
        )
