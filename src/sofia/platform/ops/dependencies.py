"""Reviewed software requirements and durable platform health evidence.

The registry describes what a feature needs; it does not install software or
grant permission to do so.  Installation remains behind Fleet/SAFE authority.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
import re
import sqlite3
from typing import Iterable


_ID = re.compile(r"^[a-z][a-z0-9_.-]{0,95}$")
_PLATFORMS = frozenset({"windows", "linux", "any"})


class DependencyTier(str, Enum):
    REQUIRED = "required"
    FEATURE = "feature"
    OPTIONAL = "optional"


class DependencyHealth(str, Enum):
    HEALTHY = "healthy"
    MISSING = "missing"
    INCOMPATIBLE = "incompatible"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class SoftwareDependency:
    dependency_id: str
    display_name: str
    tier: DependencyTier
    platforms: frozenset[str]
    features: frozenset[str] = frozenset()
    executable: str | None = None
    python_module: str | None = None
    minimum_version: str | None = None
    maximum_version: str | None = None
    install_provider: str | None = None
    signed_artifact_required: bool = True
    offline_cache_eligible: bool = True
    health_command: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if _ID.fullmatch(self.dependency_id) is None:
            raise ValueError("dependency_id must be a canonical identifier")
        if not self.display_name.strip() or len(self.display_name) > 160:
            raise ValueError("display_name must be bounded text")
        if not isinstance(self.tier, DependencyTier):
            raise TypeError("tier must be DependencyTier")
        if not self.platforms or not self.platforms <= _PLATFORMS:
            raise ValueError("platforms must contain windows, linux, or any")
        if "any" in self.platforms and len(self.platforms) != 1:
            raise ValueError("any cannot be combined with another platform")
        if self.tier is DependencyTier.FEATURE and not self.features:
            raise ValueError("feature dependencies require at least one feature")
        if self.tier is DependencyTier.REQUIRED and self.features:
            raise ValueError("required dependencies cannot be feature-scoped")
        if not self.executable and not self.python_module:
            raise ValueError("an executable or Python module probe is required")
        for feature in self.features:
            if _ID.fullmatch(feature) is None:
                raise ValueError("feature IDs must be canonical identifiers")
        if self.health_command and self.executable is None:
            raise ValueError("health commands require an executable")

    def supports(self, platform: str) -> bool:
        return "any" in self.platforms or platform.casefold() in self.platforms


class DependencyRegistry:
    """Immutable reviewed dependency catalog with deterministic resolution."""

    def __init__(self, dependencies: Iterable[SoftwareDependency]) -> None:
        values = tuple(dependencies)
        by_id = {item.dependency_id: item for item in values}
        if len(by_id) != len(values):
            raise ValueError("dependency IDs must be unique")
        self._by_id = by_id

    def all(self) -> tuple[SoftwareDependency, ...]:
        return tuple(self._by_id[key] for key in sorted(self._by_id))

    def get(self, dependency_id: str) -> SoftwareDependency:
        try:
            return self._by_id[dependency_id]
        except KeyError as exc:
            raise KeyError(f"unknown dependency: {dependency_id}") from exc

    def resolve(
        self, *, platform: str, enabled_features: Iterable[str] = (),
        include_optional: bool = False,
    ) -> tuple[SoftwareDependency, ...]:
        normalized = platform.casefold()
        if normalized not in {"windows", "linux"}:
            raise ValueError("platform must be windows or linux")
        features = frozenset(enabled_features)
        selected = []
        for dependency in self.all():
            if not dependency.supports(normalized):
                continue
            if dependency.tier is DependencyTier.REQUIRED:
                selected.append(dependency)
            elif dependency.tier is DependencyTier.FEATURE:
                if dependency.features & features:
                    selected.append(dependency)
            elif include_optional:
                selected.append(dependency)
        return tuple(selected)


@dataclass(frozen=True, slots=True)
class DependencyObservation:
    host_id: str
    dependency_id: str
    status: DependencyHealth
    observed_version: str | None
    source: str
    observed_at: datetime
    artifact_sha256: str | None = None
    signature_verified: bool | None = None
    detail: str = ""

    def __post_init__(self) -> None:
        for value, label in (
            (self.host_id, "host_id"), (self.dependency_id, "dependency_id"),
            (self.source, "source"),
        ):
            if not isinstance(value, str) or not value.strip() or len(value) > 160:
                raise ValueError(f"{label} must be bounded text")
        if not isinstance(self.status, DependencyHealth):
            raise TypeError("status must be DependencyHealth")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        if self.artifact_sha256 is not None and re.fullmatch(
            r"[0-9a-f]{64}", self.artifact_sha256,
        ) is None:
            raise ValueError("artifact_sha256 must be lowercase SHA-256")
        if self.signature_verified is not None and type(self.signature_verified) is not bool:
            raise TypeError("signature_verified must be bool or None")


class DependencyEvidenceStore:
    """Append-only observations; absence of evidence remains unknown."""

    def __init__(self, state_path: Path | str) -> None:
        self.path = Path(state_path)
        with closing(self._connect()) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS ops_dependency_observation (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    host_id TEXT NOT NULL,
                    dependency_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    observed_version TEXT,
                    source TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    artifact_sha256 TEXT,
                    signature_verified INTEGER,
                    detail TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ops_dependency_latest
                    ON ops_dependency_observation(host_id,dependency_id,sequence DESC);
            """)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def record(self, observation: DependencyObservation) -> int:
        if not isinstance(observation, DependencyObservation):
            raise TypeError("DependencyObservation required")
        with closing(self._connect()) as db, db:
            cursor = db.execute(
                """INSERT INTO ops_dependency_observation
                (host_id,dependency_id,status,observed_version,source,observed_at,
                 artifact_sha256,signature_verified,detail)
                VALUES(?,?,?,?,?,?,?,?,?)""",
                (
                    observation.host_id, observation.dependency_id,
                    observation.status.value, observation.observed_version,
                    observation.source,
                    observation.observed_at.astimezone(timezone.utc).isoformat(),
                    observation.artifact_sha256,
                    None if observation.signature_verified is None
                    else int(observation.signature_verified),
                    observation.detail[:1000],
                ),
            )
            return int(cursor.lastrowid)

    def latest(self, host_id: str, dependency_id: str) -> DependencyObservation | None:
        with closing(self._connect()) as db:
            row = db.execute(
                """SELECT * FROM ops_dependency_observation
                WHERE host_id=? AND dependency_id=? ORDER BY sequence DESC LIMIT 1""",
                (host_id, dependency_id),
            ).fetchone()
        if row is None:
            return None
        return DependencyObservation(
            host_id=row["host_id"], dependency_id=row["dependency_id"],
            status=DependencyHealth(row["status"]),
            observed_version=row["observed_version"], source=row["source"],
            observed_at=datetime.fromisoformat(row["observed_at"]),
            artifact_sha256=row["artifact_sha256"],
            signature_verified=(None if row["signature_verified"] is None
                                else bool(row["signature_verified"])),
            detail=row["detail"],
        )

    def projection(self, host_id: str, registry: DependencyRegistry) -> tuple[dict, ...]:
        result = []
        for dependency in registry.all():
            observation = self.latest(host_id, dependency.dependency_id)
            result.append({
                "dependency_id": dependency.dependency_id,
                "tier": dependency.tier.value,
                "features": sorted(dependency.features),
                "status": "unknown" if observation is None else observation.status.value,
                "observed_version": None if observation is None else observation.observed_version,
                "observed_at": None if observation is None else observation.observed_at.isoformat(),
            })
        return tuple(result)


def default_dependency_registry() -> DependencyRegistry:
    """Repository-reviewed cross-platform contract; versions come from locks."""
    return DependencyRegistry((
        SoftwareDependency(
            "runtime.python", "Python runtime", DependencyTier.REQUIRED,
            frozenset({"any"}), executable="python", minimum_version="3.12",
            install_provider="platform-bootstrap", health_command=("--version",),
        ),
        SoftwareDependency(
            "runtime.sofia", "Sofía application", DependencyTier.REQUIRED,
            frozenset({"any"}), python_module="sofia",
            install_provider="signed-wheel", health_command=(),
        ),
        SoftwareDependency(
            "security.cryptography", "Cryptography", DependencyTier.REQUIRED,
            frozenset({"any"}), python_module="cryptography",
            install_provider="locked-python-wheel",
        ),
        SoftwareDependency(
            "storage.sqlite", "SQLite runtime", DependencyTier.REQUIRED,
            frozenset({"any"}), python_module="sqlite3",
            install_provider="python-standard-library",
        ),
        SoftwareDependency(
            "fleet.windows-powershell", "Windows PowerShell", DependencyTier.FEATURE,
            frozenset({"windows"}), frozenset({"fleet.bootstrap"}),
            executable="powershell.exe", install_provider="operating-system",
            health_command=("-NoProfile", "-Command", "$PSVersionTable.PSVersion.ToString()"),
        ),
        SoftwareDependency(
            "fleet.windows-service", "Windows service support", DependencyTier.FEATURE,
            frozenset({"windows"}), frozenset({"fleet.agent"}),
            python_module="win32serviceutil", install_provider="locked-python-wheel",
        ),
        SoftwareDependency(
            "fleet.linux-service", "systemd service manager", DependencyTier.FEATURE,
            frozenset({"linux"}), frozenset({"fleet.agent"}), executable="systemctl",
            install_provider="operating-system", health_command=("--version",),
        ),
        SoftwareDependency(
            "fleet.linux-sha256", "GNU SHA-256 verifier", DependencyTier.FEATURE,
            frozenset({"linux"}), frozenset({"fleet.bootstrap"}),
            executable="sha256sum", install_provider="operating-system",
            health_command=("--version",),
        ),
        SoftwareDependency(
            "cognition.ollama", "Ollama model runtime", DependencyTier.FEATURE,
            frozenset({"any"}), frozenset({"cognition.local"}), executable="ollama",
            install_provider="vendor-signed-package", health_command=("--version",),
        ),
        SoftwareDependency(
            "creative.blender", "Blender", DependencyTier.OPTIONAL,
            frozenset({"any"}), frozenset({"creative.3d", "creative.animation"}),
            executable="blender", install_provider="vendor-signed-package",
            health_command=("--version",),
        ),
        SoftwareDependency(
            "creative.ffmpeg", "FFmpeg", DependencyTier.OPTIONAL,
            frozenset({"any"}), frozenset({"creative.audio", "creative.animation"}),
            executable="ffmpeg", install_provider="platform-package-manager",
            health_command=("-version",),
        ),
        SoftwareDependency(
            "ops.docker", "Docker Engine", DependencyTier.OPTIONAL,
            frozenset({"any"}), frozenset({"ops.docker"}), executable="docker",
            install_provider="vendor-signed-package", health_command=("version",),
        ),
        SoftwareDependency(
            "ops.hyperv", "Hyper-V PowerShell module", DependencyTier.OPTIONAL,
            frozenset({"windows"}), frozenset({"ops.virtualization"}),
            executable="powershell.exe", install_provider="windows-feature",
            health_command=("-NoProfile", "-Command", "Get-Module -ListAvailable Hyper-V"),
        ),
        SoftwareDependency(
            "integration.portainer", "Portainer API client", DependencyTier.OPTIONAL,
            frozenset({"any"}), frozenset({"integration.portainer"}),
            python_module="urllib.request", install_provider="python-standard-library",
        ),
        SoftwareDependency(
            "integration.home-assistant", "Home Assistant API client", DependencyTier.OPTIONAL,
            frozenset({"any"}), frozenset({"integration.home-assistant"}),
            python_module="urllib.request", install_provider="python-standard-library",
        ),
        SoftwareDependency(
            "integration.jmri", "JMRI JSON API client", DependencyTier.OPTIONAL,
            frozenset({"any"}), frozenset({"integration.jmri"}),
            python_module="urllib.request", install_provider="python-standard-library",
        ),
    ))
