"""Source-level contracts for the opt-in release binary smoke tool.

These tests never create a venv, launch the release binary, touch the Windows
SCM, or require elevation.  The live proof remains the opt-in tool itself.
"""
from pathlib import Path

import pytest

from tools import aegis_release_binary_smoke as tool


def test_binary_arguments_match_exact_rust_service_contract():
    args = tool.build_binary_args(
        Path("C:/bundle/aegis-platform-service.exe"),
        Path("C:/venv/Scripts/python.exe"),
        Path("C:/run/identity"),
        Path("C:/run/platform.db"),
        "12345678-1234-4abc-8abc-1234567890ab",
        "a" * 64,
    )
    assert args == [
        str(Path("C:/bundle/aegis-platform-service.exe")),
        "--python", str(Path("C:/venv/Scripts/python.exe")),
        "--identity-home", str(Path("C:/run/identity")),
        "--state", str(Path("C:/run/platform.db")),
        "--platform-id", "12345678-1234-4abc-8abc-1234567890ab",
        "--public-key-sha256", "a" * 64,
    ]


def _ready(**changes):
    value = {
        "schema": tool.SERVICE_SCHEMA,
        "phase": "ready",
        "platform_id": "12345678-1234-4abc-8abc-1234567890ab",
        "generation": 3,
        "supervisor_pid": 100,
        "worker_pid": 101,
        "operator_stop": False,
        "management_listening": True,
    }
    value.update(changes)
    return value


def test_readiness_binds_platform_process_generation_and_listener():
    platform_id = "12345678-1234-4abc-8abc-1234567890ab"
    assert tool.validate_ready(_ready(), process_pid=100, platform_id=platform_id) == _ready()
    for change in (
        {"platform_id": "00000000-0000-0000-0000-000000000000"},
        {"generation": 0},
        {"supervisor_pid": 999},
        {"worker_pid": 100},
        {"worker_pid": None},
        {"operator_stop": True},
        {"management_listening": False},
        {"phase": "healthy"},
        {"schema": "aegis.platform.service-control.v0"},
    ):
        with pytest.raises(tool.SmokeError):
            tool.validate_ready(_ready(**change), process_pid=100, platform_id=platform_id)


def test_restart_must_advance_generation():
    first = tool.validate_ready(_ready(generation=4), process_pid=100,
                               platform_id=_ready()["platform_id"])
    second = tool.validate_ready(_ready(generation=5, supervisor_pid=200, worker_pid=201),
                                process_pid=200, platform_id=_ready()["platform_id"])
    tool.validate_restart_generation(first, second)
    with pytest.raises(tool.SmokeError):
        tool.validate_restart_generation(second, first)


def test_dependency_seed_is_offline_and_excludes_core_and_ollama(tmp_path):
    for name in ("cryptography", "cryptography-50.0.1.dist-info", "win32",
                 "win32comext", "cffi", "pycparser", "tzdata", "pywin32_system32"):
        (tmp_path / name).mkdir()
    (tmp_path / "pywin32.pth").write_text("win32\nwin32\\lib\n", encoding="utf-8")
    (tmp_path / "_cffi_backend.cp312-win_amd64.pyd").write_bytes(b"")
    for forbidden in ("sofia", "ollama", "unrelated", "sofia_core-1.0.dist-info"):
        (tmp_path / forbidden).mkdir()
    selected = {entry.name for entry in tool.select_dependency_entries(tmp_path)}
    assert {"cryptography", "cryptography-50.0.1.dist-info", "win32",
            "win32comext", "cffi", "pycparser", "tzdata", "pywin32_system32",
            "pywin32.pth", "_cffi_backend.cp312-win_amd64.pyd"} <= selected
    assert not selected & {"sofia", "ollama", "unrelated", "sofia_core-1.0.dist-info"}
