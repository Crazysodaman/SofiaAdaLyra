"""Tests for local, conservative, user-session VTube Studio process lifecycle.

All tests simulate Steam folders/processes; nothing launches Steam or VTS.
"""
from __future__ import annotations

from pathlib import Path
import json
import os

import pytest

from sofia.avatar import vtube_studio_host as host


def _create_vts(root: Path):
    root.mkdir(parents=True, exist_ok=True)
    (root / "VTube Studio.exe").write_bytes(b"test executable placeholder")
    (root / "start_without_steam.bat").write_text("@echo off")
    return root


def test_discover_reads_non_c_steam_library_from_vdf(tmp_path):
    steam = tmp_path / "Steam"
    other = tmp_path / "Z-drive" / "SteamLibrary"
    _create_vts(other / "steamapps" / "common" / "VTube Studio")
    (steam / "steamapps").mkdir(parents=True)
    (steam / "steamapps" / "libraryfolders.vdf").write_text(
        '"libraryfolders"\n{\n"0" {"path" "C:\\\\Steam"}\n'
        f'"1" {{ "path" "{str(other)}" }}\n"2" "{str(other)}"\n}}',
        encoding="utf-8",
    )
    # On Windows the VDF contains an absolute Windows path, not /tmp;
    # the legacy slot text still exercises local fixture discovery.
    assert host.locate_vtube_studio(steam_roots=(steam,)) == (
        other / "steamapps" / "common" / "VTube Studio"
    )


def test_custom_drive_override_precedence(tmp_path, monkeypatch):
    steam = _create_vts(tmp_path / "Steam" / "steamapps" / "common" / "VTube Studio")
    override = _create_vts(tmp_path / "A-different-disk" / "VTube Studio")
    monkeypatch.setenv("SOFIA_VTS_INSTALL_DIR", str(override))
    assert host.locate_vtube_studio(steam_roots=(steam,)) == override
    with pytest.raises(host.AvatarHostError, match="no valid standalone launcher"):
        host.locate_vtube_studio(explicit=tmp_path / "missing")


def test_missing_steamfree_launcher_refused(tmp_path):
    install = tmp_path / "VTube Studio"
    install.mkdir()
    (install / "VTube Studio.exe").write_bytes(b"placeholder")
    assert host.verified_install_root(install) is None


class FakeProcess:
    def __init__(self, pid, started, path):
        self.info = {
            "pid": pid, "name": "VTube Studio.exe",
            "exe": str(path), "create_time": started,
        }


def test_existing_instance_is_not_owned_and_is_never_launched(tmp_path):
    existing = FakeProcess(22, 1234.0, tmp_path / "VTube Studio.exe")
    result = host.launch_on_demand(
        session=1, process_list=lambda: [existing],
        startfile=lambda *args, **kwargs: pytest.fail("must not relaunch an already-running VTS"),
        ownership_file=tmp_path / "owned.json",
    )
    assert result["result"] == "reused_existing"
    assert result["may_close"] is False
    assert not (tmp_path / "owned.json").exists()
    assert host.request_graceful_close(
        session=1, process_list=lambda: [existing],
        ownership_file=tmp_path / "owned.json",
        send_close=lambda pid: pytest.fail("must not close user-owned VTS"),
    )["close_sent"] is False


def test_owned_process_may_request_graceful_close_only(tmp_path):
    install = _create_vts(tmp_path / "steamapps" / "common" / "VTube Studio")
    exe = install / "VTube Studio.exe"
    proc = FakeProcess(450, 123456.5, exe)
    started = []
    count = [0]
    def processes():
        count[0] += 1
        return [] if count[0] == 1 else [proc]
    record = tmp_path / "owner.json"
    result = host.launch_on_demand(
        install_dir=install, session=3, ownership_file=record,
        process_list=processes,
        startfile=lambda path, *, cwd: started.append((path, cwd)),
        sleep=lambda _sec: None,
    )
    assert result["result"] == "launched_owned"
    assert started == [(str(install / "start_without_steam.bat"), str(install))]
    assert json.loads(record.read_text())["pid"] == 450
    requested = []
    closed = host.request_graceful_close(
        session=3, ownership_file=record, process_list=lambda: [proc],
        send_close=lambda pid: requested.append(pid) or 1,
    )
    assert closed["result"] == "graceful_close_requested"
    assert requested == [450]


def test_pid_reuse_never_closes_unrelated_process(tmp_path):
    own = host.OwnedVTS(100, 998.5, str(tmp_path / "VTube Studio.exe"),
                        2, host.socket.gethostname())
    record = tmp_path / "owner.json"
    record.write_text(json.dumps(host.asdict(own)))
    recycled = FakeProcess(100, 999.5, tmp_path / "VTube Studio.exe")
    result = host.request_graceful_close(
        session=2, process_list=lambda: [recycled], ownership_file=record,
        send_close=lambda _pid: pytest.fail("must not kill recycled PID"),
    )
    assert result["close_sent"] is False


def test_different_session_or_computer_cannot_close(tmp_path):
    own = host.OwnedVTS(100, 998.5, str(tmp_path / "VTube Studio.exe"),
                        2, "other-host")
    record = tmp_path / "owner.json"
    record.write_text(json.dumps(host.asdict(own)))
    proc = FakeProcess(100, 998.5, tmp_path / "VTube Studio.exe")
    assert host.request_graceful_close(
        session=2, process_list=lambda: [proc], ownership_file=record,
    )["close_sent"] is False


def test_bad_process_ownership_record_never_grants_close(tmp_path):
    record = tmp_path / "owner.json"
    record.write_text('{"pid": 55, "started": 1234}')
    assert host.request_graceful_close(
        session=1, process_list=lambda: [], ownership_file=record,
    )["result"] == "not_owned"


def test_host_cli_discovery_does_not_launch_process(tmp_path, monkeypatch, capsys):
    install = _create_vts(tmp_path / "VTube Studio")
    monkeypatch.setattr(host, "locate_vtube_studio", lambda *, explicit=None: install)
    assert host.main(["--discover"]) == 0
    assert json.loads(capsys.readouterr().out)["found"] == str(install)


def test_invalid_host_platform_fails_safe(monkeypatch):
    monkeypatch.setattr(host.sys, "platform", "linux")
    with pytest.raises(host.AvatarHostError, match="requires Windows"):
        host._interactive_windows_session()


def test_steamfree_bat_launch_workdir_is_install_dir_not_checkout(tmp_path, monkeypatch):
    """Regression for Windows: START ./"VTube Studio.exe" failed on H: when installed on E:."""
    install = _create_vts(tmp_path / "E-drive" / "SteamLibrary" / "steamapps" / "common" / "VTube Studio")
    checkout = tmp_path / "H-drive" / "Users" / "SofiaAdaLyra"
    checkout.mkdir(parents=True)
    monkeypatch.chdir(checkout)
    calls = []
    outcome = host.launch_on_demand(
        install_dir=install, session=2,
        ownership_file=tmp_path / "no-launch-record.json",
        process_list=lambda: [],
        startfile=lambda file, *, cwd: calls.append((file, cwd)),
        sleep=lambda _seconds: None, wait_iterations=1,
    )
    assert calls == [(str(install / "start_without_steam.bat"), str(install))]
    assert Path.cwd() == checkout  # Sofía's own cwd must never change
    assert outcome["result"] == "launch_not_verified"
    assert outcome["started_by_sofia"] is False
    assert outcome["may_close"] is False
    assert not (tmp_path / "no-launch-record.json").exists()


def test_launcher_fails_closed_if_batch_start_raises(tmp_path):
    install = _create_vts(tmp_path / "SteamLibrary" / "steamapps" / "common" / "VTube Studio")
    record = tmp_path / "record.json"

    def fail_launch(path, *, cwd):
        assert cwd == str(install)
        raise OSError("simulated launch error")

    with pytest.raises(OSError, match="simulated launch"):
        host.launch_on_demand(
            install_dir=install, session=1,
            ownership_file=record, process_list=lambda: [],
            startfile=fail_launch,
        )
    assert not record.exists()


def test_status_reports_real_exit_not_just_graceful_close_request(tmp_path):
    app = tmp_path / "VTube Studio.exe"
    proc = FakeProcess(23864, 123456.5, app)
    record = host.OwnedVTS(
        proc.info["pid"], proc.info["create_time"],
        proc.info["exe"], 3, host.socket.gethostname(),
    )
    tracked = tmp_path / "owned.json"
    tracked.write_text(json.dumps(host.asdict(record)))
    active = host.inspect_host_status(
        session=3, process_list=lambda: [proc], ownership_file=tracked,
    )
    assert active == {
        "running": True, "running_instances": 1,
        "owned_instance_running": True,
        "owned_pid": 23864, "safe_to_close": True,
    }
    after_exit = host.inspect_host_status(
        session=3, process_list=lambda: [], ownership_file=tracked,
    )
    assert after_exit == {
        "running": False, "running_instances": 0,
        "owned_instance_running": False,
        "owned_pid": None, "safe_to_close": False,
    }


def test_status_refuses_ownership_for_preexisting_untracked_vts(tmp_path):
    proc = FakeProcess(301, 1234.0, tmp_path / "VTube Studio.exe")
    result = host.inspect_host_status(
        session=3, process_list=lambda: [proc],
        ownership_file=tmp_path / "no-record.json",
    )
    assert result["running"] is True
    assert result["owned_instance_running"] is False
    assert result["safe_to_close"] is False
