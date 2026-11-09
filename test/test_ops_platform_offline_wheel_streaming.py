"""D028 Core-free wheel review uses bounded memory, signed-byte rechecks.

This is a synthetic local wheel test, not a publisher certificate or a
production release. An actual installer still requires owner approval.
"""
from __future__ import annotations

from hashlib import sha256
import tracemalloc
import zipfile

import pytest

from sofia.platform.ops.platform_installer_offline_seed import _inspect_dependency_wheel
from sofia.platform.ops.platform_release import PlatformReleaseRejected


def _wheel(tmp_path, *, name="tiny-product", expanded=0):
    path = tmp_path / "signed-wheel.whl"
    with zipfile.ZipFile(path, "w", allowZip64=True) as zipper:
        zipper.writestr(
            "tiny_product-1.0.dist-info/METADATA",
            "Metadata-Version: 2.1\nName: " + name + "\nVersion: 1.0\n",
        )
        if expanded:
            with zipper.open("tiny_product/data.bin", "w", force_zip64=True) as writer:
                block = b"\0" * 65536
                remaining = expanded
                while remaining:
                    piece = block[:min(len(block), remaining)]
                    writer.write(piece)
                    remaining -= len(piece)
    digest = sha256()
    with path.open("rb") as reader:
        while chunk := reader.read(65536):
            digest.update(chunk)
    return path, digest.hexdigest(), path.stat().st_size


@pytest.mark.slow
def test_large_signed_dependency_wheel_uses_bounded_ram_for_metadata(tmp_path):
    path, signed_sha, size = _wheel(tmp_path, expanded=32 * 1024**2)
    tracemalloc.start()
    try:
        parsed = _inspect_dependency_wheel(path, signed_sha, size)
        _current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert parsed == "tiny-product"
    assert peak < 12 * 1024**2


def test_streamed_wheel_denies_wrong_signed_sha_or_core_distribution(tmp_path):
    path, expected, size = _wheel(tmp_path)
    with pytest.raises(PlatformReleaseRejected, match="drifted"):
        _inspect_dependency_wheel(path, "f" * 64, size)
    core, digest, total = _wheel(tmp_path, name="ollama")
    with pytest.raises(PlatformReleaseRejected, match="Core/model"):
        _inspect_dependency_wheel(core, digest, total)
