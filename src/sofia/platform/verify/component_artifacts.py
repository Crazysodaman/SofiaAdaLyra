"""Component artifact verifier for G2-B physical package separation.

This module is the programmatic contract for separately buildable component
wheels (``sofia-sdk``, ``sofia-platform``, ``sofia-core``) built from the
integrated source tree under :mod:`packaging.components.toml`.

Verification is content-based, per the platform/core link design:

- wheel contents (paths and metadata) are observed directly from the wheel;
- import isolation is verified against extracted wheel payloads so installed
  artifact semantics are exercised, not checkout source-tree semantics;
- the Core-blocked import surface here is the installed-artifact counterpart
  of the source-tree canonical list owned by
  ``test_platform_import_isolation.py``, and tests assert coverage of that
  canonical list.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

BUILD_SCHEMA = "sofia.platform.components.build.v1"
MANIFEST_SCHEMA = "sofia.platform.components.manifest.v1"
MANIFEST_RELPATH = "packaging/components.toml"

CORE_ASSET_FILES: tuple[str, ...] = (
    "sofia/core/constitution/constitution.md",
    "sofia/core/constitution/constitution.sha256",
    "sofia/core/identity/identity.json",
    "sofia/core/embodiment/avatar.json",
    "sofia/core/personality/personality.json",
)

COMPONENT_DISTRIBUTIONS: tuple[str, ...] = ("sdk", "platform", "core")

#: Modules the installed Platform artifact must import with Core absent.
#: Installed-artifact counterpart of the source-tree canonical isolation
#: surface; the source test asserts this list covers its canonical list.
INSTALLED_ISOLATED_MODULES: tuple[str, ...] = (
    "sofia.platform.launcher",
    "sofia.platform.config",
    "sofia.platform.config.defaults",
    "sofia.platform.config.environment",
    "sofia.platform.config.identity_bootstrap",
    "sofia.platform.config.inference_endpoint",
    "sofia.platform.config.layout",
    "sofia.platform.config.model",
    "sofia.platform.config.reviewed_projection",
    "sofia.platform.config.roles",
    "sofia.platform.config.user_settings",
    "sofia.platform.core_link",
    "sofia.platform.core_link.access",
    "sofia.platform.core_link.binding",
    "sofia.platform.core_link.transport",
    "sofia.platform.state",
    "sofia.platform.state.atomic_file",
    "sofia.platform.state.canonical_sqlite",
    "sofia.platform.state.component_schema",
    "sofia.platform.state.factory",
    "sofia.platform.state.json_repository",
    "sofia.platform.state.model",
    "sofia.platform.state.namespaces",
    "sofia.platform.state.path_policy",
    "sofia.platform.state.performance",
    "sofia.platform.state.plane",
    "sofia.platform.state.platform",
    "sofia.platform.state.private_file",
    "sofia.platform.state.replication",
    "sofia.platform.state.sdk_facade",
    "sofia.platform.state.sqlite_access",
    "sofia.platform.state.sqlite_plane",
    "sofia.platform.state.sqlite_uri",
    "sofia.platform.ops.backup",
    "sofia.sdk",
    "sofia.sdk.contracts",
    "sofia.sdk.core_link",
    "sofia.sdk.cognition_model",
    "sofia.sdk.principals",
    "sofia.sdk.cognition",
    "sofia.sdk.module_settings",
    "sofia.sdk.state",
)

LAUNCHER_STATUS_PROBE = (
    "from sofia.platform.launcher import main\n"
    "main(['status'])\n"
)

COMPONENT_IMPORT_PROBE = (
    "import sofia.core.identity.model\n"
    "import sofia.core.constitution\n"
    "import sofia.sdk.cognition_model\n"
    "import sofia.platform.config.environment\n"
    "assert sofia.core.identity.model.IdentityBootstrapMode is not None\n"
)


class ComponentArtifactError(RuntimeError):
    """Raised when a component artifact violates the separation contract."""


@dataclass(frozen=True)
class ComponentArtifactReport:
    """Observed facts about one built component wheel."""

    distribution: str
    wheel: Path
    sha256: str
    name: str
    version: str
    files: frozenset[str]
    requires_dist: tuple[str, ...]
    entry_points: tuple[str, ...]

    def contains(self, path_prefix: str) -> bool:
        normalized = path_prefix.rstrip("/") + "/"
        return any(path.startswith(normalized) for path in self.files)

    def contains_any(self, paths: Sequence[str]) -> bool:
        return any(self.contains(path) for path in paths)


@dataclass(frozen=True)
class ComponentSeparationReport:
    """Observed separation facts across all three component wheels."""

    wheels: Mapping[str, ComponentArtifactReport]
    core_free_platform: bool
    core_free_sdk: bool
    platform_free_core: bool
    platform_free_sdk: bool
    sdk_free_core: bool
    sdk_free_platform: bool
    core_assets_present: bool
    platform_entry_point_present: bool
    package_root_single_owner: bool
    dependency_graph_acyclic: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "schema": BUILD_SCHEMA,
            "core_free_platform": self.core_free_platform,
            "core_free_sdk": self.core_free_sdk,
            "platform_free_core": self.platform_free_core,
            "platform_free_sdk": self.platform_free_sdk,
            "sdk_free_core": self.sdk_free_core,
            "sdk_free_platform": self.sdk_free_platform,
            "core_assets_present": self.core_assets_present,
            "platform_entry_point_present": self.platform_entry_point_present,
            "package_root_single_owner": self.package_root_single_owner,
            "dependency_graph_acyclic": self.dependency_graph_acyclic,
        }


def repository_root(start: Path | None = None) -> Path:
    """Return the checkout root that owns this package."""

    current = (start or Path(__file__)).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").is_file() and (candidate / MANIFEST_RELPATH).is_file():
            return candidate
    raise ComponentArtifactError("repository root with component manifest not found")


def load_component_manifest(repo: Path | None = None) -> dict[str, dict[str, object]]:
    """Load and validate ``packaging/components.toml``."""

    root = repo if repo is not None else repository_root()
    manifest_path = root / MANIFEST_RELPATH
    data = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    if data.get("schema") != MANIFEST_SCHEMA:
        raise ComponentArtifactError(f"unexpected manifest schema: {data.get('schema')!r}")
    components = data.get("components")
    if not isinstance(components, dict) or set(components) != set(COMPONENT_DISTRIBUTIONS):
        raise ComponentArtifactError("manifest must declare exactly sdk, platform, core")
    for name, component in components.items():
        packages = component.get("packages")
        if not isinstance(packages, list) or not packages:
            raise ComponentArtifactError(f"component {name!r} declares no packages")
        deps = component.get("dependencies", [])
        if not isinstance(deps, list):
            raise ComponentArtifactError(f"component {name!r} dependencies must be a list")
        if not isinstance(component.get("package_data", {}), dict):
            raise ComponentArtifactError(f"component {name!r} package_data must be a table")
        if not isinstance(component.get("entry_points", {}), dict):
            raise ComponentArtifactError(f"component {name!r} entry_points must be a table")
    return components


def _wheel_name_prefix(distribution: str) -> str:
    return distribution.replace("-", "_") + "-"


def _parse_entry_points(archive: zipfile.ZipFile, names: Sequence[str]) -> tuple[str, ...]:
    entry_paths = [name for name in names if name.endswith(".dist-info/entry_points.txt")]
    if not entry_paths:
        return ()
    entry_lines: list[str] = []
    in_section = False
    text = archive.read(entry_paths[0]).decode("utf-8")
    for line in text.splitlines():
        if line.startswith("["):
            in_section = line.startswith("[console_scripts]")
            continue
        if in_section and "=" in line:
            entry_lines.append(line.strip())
    return tuple(sorted(entry_lines))


def inspect_wheel(wheel: Path, distribution: str) -> ComponentArtifactReport:
    """Read wheel facts directly from the wheel archive."""

    payload = wheel.read_bytes()
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        dist_infos = [name for name in names if name.endswith(".dist-info/METADATA")]
        if len(dist_infos) != 1:
            raise ComponentArtifactError(f"{wheel.name}: expected one dist-info, got {dist_infos!r}")
        metadata_text = archive.read(dist_infos[0]).decode("utf-8")
        name = version = None
        requires: list[str] = []
        for line in metadata_text.splitlines():
            if line.startswith("Name:"):
                name = line.split(":", 1)[1].strip()
            elif line.startswith("Version:"):
                version = line.split(":", 1)[1].strip()
            elif line.startswith("Requires-Dist:"):
                requires.append(line.split(":", 1)[1].strip())
        if name is None or version is None:
            raise ComponentArtifactError(f"{wheel.name}: missing Name/Version metadata")
        if name != distribution:
            raise ComponentArtifactError(
                f"{wheel.name}: metadata name {name!r} does not match distribution {distribution!r}"
            )
        files = frozenset(name for name in names if not name.endswith("/"))
        return ComponentArtifactReport(
            distribution=distribution,
            wheel=wheel,
            sha256=hashlib.sha256(payload).hexdigest(),
            name=name,
            version=version,
            files=files,
            requires_dist=tuple(sorted(requires)),
            entry_points=_parse_entry_points(archive, names),
        )


def wheel_matches_identity(wheel: Path, identity: Mapping[str, str]) -> bool:
    """True when a wheel file binds exactly to a component identity.

    identity keys: distribution, version, sha256. Non-raising: a wheel that
    does not match the distribution is not an error, it is simply a miss.
    """

    try:
        report = inspect_wheel(wheel, identity["distribution"])
    except ComponentArtifactError:
        return False
    return (
        report.version == identity["version"]
        and report.sha256 == identity["sha256"]
    )


def _generate_pyproject(
    component: Mapping[str, object],
    version: str,
) -> str:
    packages = list(component["packages"])  # type: ignore[arg-type]
    dependencies = list(component.get("dependencies", []))  # type: ignore[arg-type]
    package_data = component.get("package_data", {})  # type: ignore[arg-type]
    entry_points = component.get("entry_points", {})  # type: ignore[arg-type]

    include = [f"{package}*" for package in packages]
    for relpath in component.get("extra_files", []):  # type: ignore[union-attr]
        parent = str(relpath).replace("\\", "/").split("/")[0]  # type: ignore[operator]
        if parent and f"{parent}*" not in include and parent not in include:
            include.append(parent)
    lines: list[str] = []
    lines.append("[build-system]")
    lines.append('requires = ["setuptools==80.9.0"]')
    lines.append("build-backend = 'setuptools.build_meta'")
    lines.append("")
    lines.append("[project]")
    lines.append(f'name = "{component["distribution"]}"')
    lines.append(f'version = "{version}"')
    lines.append('description = "Sofia component artifact"')
    lines.append('requires-python = ">=3.11"')
    if dependencies:
        lines.append("dependencies = [")
        for dep in dependencies:
            lines.append(f'    "{dep}",')
        lines.append("]")
    else:
        lines.append("dependencies = []")
    if entry_points:
        lines.append("[project.scripts]")
        for script, target in entry_points.items():
            lines.append(f'{script} = "{target}"')
    lines.append("")
    lines.append("[tool.setuptools]")
    lines.append("include-package-data = false")
    lines.append("")
    lines.append("[tool.setuptools.packages.find]")
    lines.append('where = ["src"]')
    lines.append("include = [")
    for entry in include:
        lines.append(f'    "{entry}",')
    lines.append("]")
    if package_data:
        lines.append("")
        lines.append("[tool.setuptools.package-data]")
        for package, files in package_data.items():
            rendered = ", ".join(f'"{file}"' for file in files)
            lines.append(f'"{package}" = [{rendered}]')
    lines.append("")
    return "\n".join(lines)


def _stage_component(
    repo: Path,
    component: Mapping[str, object],
    stage_root: Path,
) -> list[str]:
    packages = list(component["packages"])  # type: ignore[arg-type]
    staged: list[str] = []
    source_root = repo / "src"
    for package in packages:
        package_path = package.replace(".", "/")
        source_package = source_root / package_path
        if not source_package.is_dir():
            raise ComponentArtifactError(f"missing package source: {source_package}")
        shutil.copytree(source_package, stage_root / "src" / package_path)
        for path in sorted((stage_root / "src" / package_path).rglob("*")):
            if path.is_file():
                staged.append(path.relative_to(stage_root).as_posix())
    package_data = component.get("package_data", {})  # type: ignore[arg-type]
    for package, files in package_data.items():  # type: ignore[union-attr]
        for file_name in files:
            asset = source_root / package.replace(".", "/") / file_name  # type: ignore[union-attr]
            if not asset.is_file():
                raise ComponentArtifactError(f"missing declared asset: {asset}")
    for relpath in component.get("extra_files", []):  # type: ignore[union-attr]
        source_file = source_root / relpath  # type: ignore[operator]
        if not source_file.is_file():
            raise ComponentArtifactError(f"missing declared extra file: {source_file}")
        destination = stage_root / "src" / relpath
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_file, destination)
        staged.append(("src/" + str(relpath).replace("\\", "/")))
    return staged


def build_component(
    distribution: str,
    output_dir: Path,
    *,
    repo: Path | None = None,
    version: str = "0.1.0",
    manifest: Mapping[str, Mapping[str, object]] | None = None,
) -> Path:
    """Build one component wheel from reviewed source into ``output_dir``."""

    if distribution not in COMPONENT_DISTRIBUTIONS:
        raise ComponentArtifactError(f"unknown component: {distribution!r}")
    root = repo if repo is not None else repository_root()
    components = manifest if manifest is not None else load_component_manifest(root)
    component = components[distribution]
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="sofia-component-build-") as tmp:
        stage_root = Path(tmp) / "stage"
        stage_root.mkdir()
        _stage_component(root, component, stage_root)
        (stage_root / "pyproject.toml").write_text(
            _generate_pyproject(component, version),
            encoding="utf-8",
        )
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "wheel",
                "--no-build-isolation",
                "--no-deps",
                "--disable-pip-version-check",
                "-w",
                str(output_dir),
                str(stage_root),
            ],
            capture_output=True,
            text=True,
            cwd=str(stage_root),
        )
        if completed.returncode != 0:
            raise ComponentArtifactError(
                f"pip wheel failed for {distribution}:\nstdout: {completed.stdout}\nstderr: {completed.stderr.strip()}"
            )
    distribution_name = str(component["distribution"])
    candidates = sorted(output_dir.glob(f"{_wheel_name_prefix(distribution_name)}*.whl"))
    if not candidates:
        raise ComponentArtifactError(
            f"pip wheel produced no artifact for {distribution_name!r} in {output_dir}\n"
            f"pip stdout: {completed.stdout}\npip stderr: {completed.stderr.strip()}"
        )
    return candidates[-1]


def _extract_wheel(wheel: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(wheel) as archive:
        archive.extractall(destination)


def _run_core_blocked_probe(
    extracted: Sequence[Path],
    probe_source: str,
    *,
    env_extra: Mapping[str, str] | None = None,
) -> None:
    python_path = os.pathsep.join(str(path) for path in extracted)
    env = {key: value for key, value in os.environ.items() if not key.startswith("SOFIA_")}
    env["PYTHONPATH"] = python_path
    env.update(env_extra or {})
    completed = subprocess.run(
        [sys.executable, "-c", probe_source],
        capture_output=True,
        text=True,
        env=env,
    )
    if completed.returncode != 0:
        raise ComponentArtifactError(
            "installed-artifact Core-blocked probe failed:\n"
            f"stdout: {completed.stdout}\nstderr: {completed.stderr}"
        )


def verify_component_separation(
    wheels: Mapping[str, Path],
) -> ComponentSeparationReport:
    """Observe wheel contents and assert the exclusive-ownership contract."""

    missing = set(COMPONENT_DISTRIBUTIONS) - set(wheels)
    if missing:
        raise ComponentArtifactError(f"missing component wheels: {sorted(missing)}")
    components = load_component_manifest()
    reports = {
        distribution: inspect_wheel(
            Path(wheel), str(components[distribution]["distribution"])
        )
        for distribution, wheel in wheels.items()
    }
    platform_report = reports["platform"]
    core_report = reports["core"]
    sdk_report = reports["sdk"]

    core_free_platform = not platform_report.contains("sofia/core")
    core_free_sdk = not sdk_report.contains("sofia/core")
    platform_free_core = not core_report.contains("sofia/platform")
    platform_free_sdk = not sdk_report.contains("sofia/platform")
    sdk_free_core = not core_report.contains("sofia/sdk")
    sdk_free_platform = not sdk_report.contains("sofia/platform")
    core_assets_present = set(CORE_ASSET_FILES) <= core_report.files
    platform_entry_point_present = (
        "companion-runtime = sofia.platform.launcher:main" in platform_report.entry_points
    )
    package_root_owners = [
        report.distribution
        for report in reports.values()
        if "sofia/__init__.py" in report.files
    ]
    package_root_single_owner = package_root_owners == ["sofia-sdk"]
    dependency_graph_acyclic = (
        "sofia-sdk" in platform_report.requires_dist
        and "sofia-platform" in core_report.requires_dist
        and "sofia-sdk" in core_report.requires_dist
    )
    failures = [
        fact
        for fact in (
            core_free_platform,
            core_free_sdk,
            platform_free_core,
            platform_free_sdk,
            sdk_free_core,
            sdk_free_platform,
            core_assets_present,
            platform_entry_point_present,
            package_root_single_owner,
            dependency_graph_acyclic,
        )
        if not fact
    ]
    if failures:
        raise ComponentArtifactError(
            "component separation violated "
            f"(failures: {len(failures)}); inspect wheel contents via inspect_wheel"
        )
    return ComponentSeparationReport(
        wheels=reports,
        core_free_platform=core_free_platform,
        core_free_sdk=core_free_sdk,
        platform_free_core=platform_free_core,
        platform_free_sdk=platform_free_sdk,
        sdk_free_core=sdk_free_core,
        sdk_free_platform=sdk_free_platform,
        core_assets_present=core_assets_present,
        platform_entry_point_present=platform_entry_point_present,
        package_root_single_owner=package_root_single_owner,
        dependency_graph_acyclic=dependency_graph_acyclic,
    )


def verify_installed_imports(
    wheels: Mapping[str, Path],
    *,
    isolated_modules: Sequence[str] = INSTALLED_ISOLATED_MODULES,
    run_launcher_status: bool = True,
) -> dict[str, object]:
    """Import the Platform artifact's Core-free surface with Core absent.

    Wheels are extracted to a temporary directory and imported through
    PYTHONPATH, exercising installed-artifact semantics without installing
    into the running environment.
    """

    isolated = list(isolated_modules)
    probe_lines = [f"import {module}" for module in isolated]
    probe_lines.append("import sys")
    probe_lines.append("core_modules = [name for name in sys.modules if name.startswith('sofia.core')]")
    probe_lines.append("assert not core_modules, core_modules")
    if run_launcher_status:
        probe_lines.append(LAUNCHER_STATUS_PROBE.strip())
    probe_source = "\n".join(probe_lines) + "\n"

    with tempfile.TemporaryDirectory(prefix="sofia-component-verify-") as tmp:
        # sofia is a regular package, so wheels are installed into one
        # site-packages; extraction mirrors installed semantics with a single
        # union directory rather than separate namespace portions.
        site_dir = Path(tmp) / "site"
        for distribution in ("sdk", "platform"):
            _extract_wheel(Path(wheels[distribution]), site_dir)
        _run_core_blocked_probe(
            [site_dir],
            probe_source,
            env_extra={
                "SOFIA_PLATFORM_ROLES": "CORE_LINK,MODULE_HOST",
                "SOFIA_CORE_LINK_TRANSPORT": "stdio",
            },
        )
    return {
        "schema": BUILD_SCHEMA,
        "isolated_modules": isolated,
        "launcher_status": run_launcher_status,
    }


def verify_integrated_parity(wheels: Mapping[str, Path]) -> dict[str, object]:
    """Import Core, Platform and SDK together from all three artifacts."""

    with tempfile.TemporaryDirectory(prefix="sofia-parity-verify-") as tmp:
        site_dir = Path(tmp) / "site"
        for distribution in ("sdk", "platform", "core"):
            _extract_wheel(Path(wheels[distribution]), site_dir)
        _run_core_blocked_probe([site_dir], COMPONENT_IMPORT_PROBE)
    return {"schema": BUILD_SCHEMA, "parity_imports": "ok"}


def build_all_components(
    output_dir: Path,
    *,
    repo: Path | None = None,
    version: str = "0.1.0",
) -> dict[str, Path]:
    """Build all three component wheels and return their paths."""

    components = load_component_manifest(repo)
    built = {
        distribution: build_component(
            distribution,
            output_dir,
            repo=repo,
            version=version,
            manifest=components,
        )
        for distribution in COMPONENT_DISTRIBUTIONS
    }
    return built


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for component artifact builds and verification."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dist",
        choices=COMPONENT_DISTRIBUTIONS,
        help="component to build; omit to build and verify all three",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repo", type=Path, default=None)
    parser.add_argument("--version", default="0.1.0")
    args = parser.parse_args(argv)
    wheels: dict[str, Path]
    if args.dist is not None:
        wheels = {
            args.dist: build_component(
                args.dist, args.output, repo=args.repo, version=args.version
            )
        }
        report = inspect_wheel(wheels[args.dist], args.dist)
        print(
            json.dumps(
                {
                    "schema": BUILD_SCHEMA,
                    "distribution": report.distribution,
                    "wheel": str(report.wheel),
                    "sha256": report.sha256,
                    "files": len(report.files),
                }
            )
        )
        return 0
    wheels = build_all_components(
        args.output, repo=args.repo, version=args.version
    )
    separation = verify_component_separation(wheels)
    verify_installed_imports(wheels)
    verify_integrated_parity(wheels)
    print(json.dumps({"schema": BUILD_SCHEMA, "separation": separation.as_dict()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
