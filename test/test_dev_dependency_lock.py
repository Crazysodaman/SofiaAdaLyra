from pathlib import Path
import zipfile

import pytest

from sofia.dev import dependency_lock
from sofia.dev.supply_chain import LockedDependency


def make_wheel(path: Path, name: str, version: str) -> Path:
    wheel = path / f"{name.replace('-', '_')}-{version}-py3-none-any.whl"
    dist = f"{name.replace('-', '_')}-{version}.dist-info"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(
            f"{dist}/METADATA",
            f"Name: {name}\nVersion: {version}\n",
        )
        archive.writestr(f"{dist}/RECORD", "")
    return wheel


def test_wheel_identity_uses_metadata_not_filename(tmp_path):
    wheel = make_wheel(tmp_path, "Example-Pkg", "1.2.3")
    assert dependency_lock._wheel_identity(wheel) == (
        "Example-Pkg",
        "1.2.3",
    )


def test_write_hashed_lock_preserves_existing_hash(
    tmp_path,
    monkeypatch,
):
    source = tmp_path / "raw.lock"
    source.write_text(
        "alpha==1.0 --hash=sha256:" + ("a" * 64) + "\n"
        "beta==2.0\n",
        encoding="utf-8",
    )
    destination = tmp_path / "hashed.lock"

    def fake_hash(item, *, python_executable):
        assert item.name == "beta"
        return LockedDependency("beta", "2.0", "b" * 64)

    monkeypatch.setattr(
        dependency_lock,
        "hash_dependency",
        fake_hash,
    )

    result = dependency_lock.write_hashed_lock(
        source,
        destination,
        python_executable="python",
    )

    assert [item.sha256 for item in result] == [
        "a" * 64,
        "b" * 64,
    ]
    assert destination.read_text(encoding="utf-8").splitlines() == [
        "# Sofía Ada Lyra exact platform dependency lock",
        "alpha==1.0 --hash=sha256:" + ("a" * 64),
        "beta==2.0 --hash=sha256:" + ("b" * 64),
    ]


def test_hash_dependency_rejects_wrong_download_identity(
    tmp_path,
    monkeypatch,
):
    class Result:
        returncode = 0
        stderr = ""
        stdout = ""

    def fake_run(argv, **kwargs):
        dest = Path(argv[argv.index("--dest") + 1])
        make_wheel(dest, "other", "1.0")
        return Result()

    monkeypatch.setattr(
        dependency_lock.subprocess,
        "run",
        fake_run,
    )

    with pytest.raises(RuntimeError, match="identity"):
        dependency_lock.hash_dependency(
            LockedDependency("wanted", "1.0"),
            python_executable="python",
        )
