"""Resolve artifact hashes for an exact platform-specific dependency lock."""
from __future__ import annotations

import argparse
from hashlib import sha256
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

from sofia.dev.supply_chain import (
    LockedDependency,
    parse_requirements_lock,
)


def _wheel_identity(path: Path) -> tuple[str, str]:
    if not path.name.endswith(".whl"):
        raise ValueError("dependency artifact must be a wheel")
    with zipfile.ZipFile(path, "r") as archive:
        metadata_names = [
            name
            for name in archive.namelist()
            if name.endswith(".dist-info/METADATA")
        ]
        if len(metadata_names) != 1:
            raise ValueError("wheel must contain exactly one METADATA file")
        metadata = archive.read(metadata_names[0]).decode(
            "utf-8",
            errors="strict",
        )
    package_name = None
    version = None
    for line in metadata.splitlines():
        if line.startswith("Name: "):
            package_name = line[6:].strip()
        elif line.startswith("Version: "):
            version = line[9:].strip()
        if package_name and version:
            break
    if not package_name or not version:
        raise ValueError("wheel metadata is missing Name or Version")
    return package_name, version


def _normalized_name(value: str) -> str:
    return value.casefold().replace("_", "-").replace(".", "-")


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_dependency(
    dependency: LockedDependency,
    *,
    python_executable: str = sys.executable,
) -> LockedDependency:
    if not isinstance(dependency, LockedDependency):
        raise TypeError("dependency must be LockedDependency")
    with tempfile.TemporaryDirectory(
        prefix="sofia-lock-"
    ) as temp_root:
        root = Path(temp_root)
        completed = subprocess.run(
            [
                python_executable,
                "-m",
                "pip",
                "download",
                "--disable-pip-version-check",
                "--only-binary=:all:",
                "--no-deps",
                "--dest",
                str(root),
                f"{dependency.name}=={dependency.version}",
            ],
            text=True,
            capture_output=True,
            timeout=180,
            check=False,
        )
        if completed.returncode:
            detail = completed.stderr.strip() or completed.stdout.strip()
            raise RuntimeError(
                f"unable to download locked artifact for "
                f"{dependency.name}=={dependency.version}: {detail}"
            )
        wheels = tuple(root.glob("*.whl"))
        if len(wheels) != 1:
            raise RuntimeError(
                f"expected exactly one wheel for "
                f"{dependency.name}=={dependency.version}"
            )
        observed_name, observed_version = _wheel_identity(wheels[0])
        if (
            _normalized_name(observed_name)
            != _normalized_name(dependency.name)
            or observed_version != dependency.version
        ):
            raise RuntimeError(
                "downloaded dependency identity does not match exact lock"
            )
        return LockedDependency(
            dependency.name,
            dependency.version,
            _sha256(wheels[0]),
        )


def write_hashed_lock(
    source: Path,
    destination: Path,
    *,
    python_executable: str = sys.executable,
) -> tuple[LockedDependency, ...]:
    dependencies = parse_requirements_lock(source)
    hashed = tuple(
        (
            dependency
            if dependency.sha256 is not None
            else hash_dependency(
                dependency,
                python_executable=python_executable,
            )
        )
        for dependency in dependencies
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        "# Sofía Ada Lyra exact platform dependency lock\n"
        + "\n".join(
            f"{item.name}=={item.version} --hash=sha256:{item.sha256}"
            for item in hashed
        )
        + "\n",
        encoding="utf-8",
    )
    return hashed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m sofia.dev.dependency_lock"
    )
    parser.add_argument("source")
    parser.add_argument("destination")
    args = parser.parse_args(argv)
    try:
        dependencies = write_hashed_lock(
            Path(args.source),
            Path(args.destination),
        )
        print(
            f"hashed dependency lock written: {args.destination} "
            f"entries={len(dependencies)}"
        )
        return 0
    except Exception as exc:
        print(
            f"dependency lock hashing failed: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
