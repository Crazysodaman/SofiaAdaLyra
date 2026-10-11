"""Source contract for reproducible Venus Fleet wheel build. Not executed."""
from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def test_build_backend_install_requires_published_hash_locked_wheel():
    script = (ROOT / "Setup-SofiaFleetArtemis.ps1").read_text(encoding="utf-8")
    lock = (ROOT / "requirements.build.lock.windows-py312.txt").read_text(
        encoding="utf-8"
    )
    assert re.search(
        r"setuptools==80\.9\.0\s+--hash=sha256:"
        r"062d34222ad13e0cc312a4c02d73f059e86a4acbfbdea8f8f76b28c99f306922",
        lock,
    )
    assert 'Join-Path $PSScriptRoot "requirements.build.lock.windows-py312.txt"' in script
    backend = script[script.index('Write-Step "Ensure hash-verified wheel-build backend"'):]
    backend = backend[:backend.index('Write-Step "Build Fleet wheel from clean committed snapshot"')]
    assert "--require-hashes" in backend
    assert "--only-binary=:all:" in backend
    assert "--no-deps -r $buildBackendLock" in backend
    assert "setuptools==80.9.0" not in backend
    assert "Hash-verified setuptools build-backend installation failed" in backend
