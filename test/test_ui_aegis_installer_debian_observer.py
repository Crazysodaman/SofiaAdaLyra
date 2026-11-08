"""B-006 Linux native observation must deny unsupported/non-systemd hosts.

Read-only OS status and journal digest never imply Platform READY, current
operator enrollment or owner approval. Real Debian12 native service positive
must be independently executed in an authorized disposable guest.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess

import pytest

pytestmark = [
    pytest.mark.pkg_ui,
    pytest.mark.skipif(os.name == "nt", reason="Debian systemd stock Bash"),
]
SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "packaging/installers/observe-debian12-service.sh"
)


def run(*args):
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        capture_output=True, text=True, timeout=20,
    )


def test_observer_parses_and_denies_unpinned_or_mutating_flags():
    syntax = subprocess.run(["bash", "-n", str(SCRIPT)],
                            capture_output=True, text=True, timeout=10)
    assert syntax.returncode == 0, syntax.stderr
    for args in ((), ("--install",), ("--expected-unit-sha256", "123"),
                 ("--expected-unit-sha256", "f" * 64, "--force")):
        attempt = run(*args)
        assert attempt.returncode == 2, attempt.stderr
        assert "OS_RUNNING_NOT_PLATFORM_READY" not in attempt.stdout


def test_non_debian12_host_has_no_native_service_acceptance():
    import subprocess as sp

    release = sp.run(["bash", "-c", ". /etc/os-release; printf '%s' \"$ID:$VERSION_ID\""],
                     capture_output=True, text=True, timeout=10)
    if release.stdout == "debian:12":
        pytest.skip("positive native observation requires signed installed-host fixture")
    outcome = run("--expected-unit-sha256", "a" * 64)
    assert outcome.returncode == 3, (outcome.stdout, outcome.stderr)
    assert "OS_RUNNING_NOT_PLATFORM_READY" not in outcome.stdout
    assert "platform_ready_authenticated" not in outcome.stdout
