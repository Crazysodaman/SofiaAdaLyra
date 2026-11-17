"""Public aegis client: read-only truth, Core-free import and fail-closed mutations."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from types import SimpleNamespace
import tomllib

import pytest

from sofia.platform import cli


_ENVIRONMENT_KEYS = (
    "SOFIA_PLATFORM_ROLES",
    "AEGIS_PLATFORM_IDENTITY_HOME",
    "AEGIS_PLATFORM_SERVICE_ENDPOINT",
    "AEGIS_PLATFORM_MANAGEMENT_ENDPOINT",
    "AEGIS_PLATFORM_ENDPOINT",
    "SOFIA_PLATFORM_SERVICE_ENDPOINT",
    "SOFIA_PLATFORM_MANAGEMENT_ENDPOINT",
    "AEGIS_PLATFORM_LOCAL_STATE",
    "AEGIS_LOCAL_STATE",
    "AEGIS_PLATFORM_STATE_PATH",
    "SOFIA_PLATFORM_LOCAL_STATE",
    "AEGIS_PLATFORM_AUTOSTART_POLICY_DB",
    "SOFIA_PLATFORM_AUTOSTART_POLICY_DB",
    "AEGIS_PLATFORM_SERVICE_COMMAND",
    "AEGIS_PLATFORM_SERVICE_UNIT_SHA256",
    "AEGIS_PLATFORM_SERVICE_UNIT_PATH",
    "AEGIS_PLATFORM_EXPECTED_ID",
    "AEGIS_PLATFORM_ID",
    "AEGIS_PLATFORM_EXPECTED_GENERATION",
    "AEGIS_PLATFORM_GENERATION",
    "AEGIS_PLATFORM_SERVICE_UID",
    "AEGIS_PLATFORM_SERVICE_GID",
    "AEGIS_PLATFORM_SERVICE_PID",
    "AEGIS_PLATFORM_SOCKET_GROUP_GID",
    "SOFIA_CORE_LINK_BINDING_STORE",
)


@pytest.fixture(autouse=True)
def clean_aegis_environment(monkeypatch):
    for key in _ENVIRONMENT_KEYS:
        monkeypatch.delenv(key, raising=False)


def _json_output(capsys) -> dict[str, object]:
    return json.loads(capsys.readouterr().out)


def _create_core_db(path: Path) -> None:
    with sqlite3.connect(path) as db:
        db.executescript(
            """
            CREATE TABLE ops_synthetic_core_binding(
                owner_id TEXT NOT NULL,
                core_id TEXT NOT NULL,
                lineage_id TEXT NOT NULL,
                generation INTEGER NOT NULL,
                state TEXT NOT NULL,
                artifact_sha256 TEXT NOT NULL,
                version TEXT NOT NULL,
                installed_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_operation TEXT,
                last_outcome TEXT,
                detail TEXT NOT NULL DEFAULT '',
                PRIMARY KEY(owner_id, core_id)
            );
            CREATE TABLE ops_synthetic_core_operation(
                operation_id TEXT PRIMARY KEY,
                core_id TEXT NOT NULL,
                outcome TEXT
            );
            """
        )


def _create_module_db(path: Path) -> None:
    with sqlite3.connect(path) as db:
        db.executescript(
            """
            CREATE TABLE platform_module_lifecycle(
                module_id TEXT PRIMARY KEY,
                version TEXT NOT NULL,
                package_digest TEXT NOT NULL,
                lifecycle TEXT NOT NULL,
                revision INTEGER NOT NULL,
                active_profile TEXT,
                staged_path TEXT,
                reason TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )


def test_status_json_reports_local_role_and_unobserved_management(monkeypatch, capsys):
    monkeypatch.setenv("SOFIA_PLATFORM_ROLES", "MODULE_HOST")

    assert cli.main(["status", "--json"]) == 0

    payload = _json_output(capsys)
    assert payload["schema"] == "aegis.platform.cli.status.v1"
    assert payload["roles"] == ["MODULE_HOST"]
    assert payload["role_configuration"]["roles"] == ["MODULE_HOST"]
    assert payload["platform_identity"] == {"state": "NOT_CONFIGURED"}
    assert payload["service_endpoint"] == {"state": "NOT_CONFIGURED"}
    assert payload["management"] == {
        "state": "NOT_OBSERVED",
        "reason": "AUTHENTICATED_MANAGEMENT_NOT_CONFIGURED",
    }


def test_zero_core_status_and_startup_are_valid_without_a_core(monkeypatch, capsys):
    monkeypatch.setenv("SOFIA_PLATFORM_ROLES", "MODULE_HOST")

    assert cli.main(["status", "--json"]) == 0
    status = _json_output(capsys)
    assert status["zero_core"] == {
        "valid": True,
        "core_required": False,
        "core_host_configured": False,
        "reason": "Platform startup and management are independent of Core activation",
    }

    assert cli.main(["startup", "--json"]) == 0
    startup = _json_output(capsys)
    assert startup["zero_core"]["valid"] is True
    assert startup["zero_core"]["core_required"] is False


def test_status_reads_public_identity_and_endpoint_but_not_live_health(
    monkeypatch, capsys,
):
    monkeypatch.setenv("SOFIA_PLATFORM_ROLES", "MODULE_HOST")
    monkeypatch.setenv("AEGIS_PLATFORM_IDENTITY_HOME", "/configured/identity")
    monkeypatch.setenv(
        "AEGIS_PLATFORM_SERVICE_ENDPOINT", "unix:///run/aegis-platform/mgmt-7.sock",
    )

    class FakeIdentity:
        identity = SimpleNamespace(
            canonical_uuid="11111111-1111-1111-1111-111111111111", serial=7,
        )
        public_key_sha256 = "a" * 64

    class FakeIdentityStore:
        def __init__(self, home):
            assert home == Path("/configured/identity")

        def load(self):
            return FakeIdentity()

    import sofia.platform.state.installation_identity as installation_identity
    monkeypatch.setattr(
        installation_identity, "InstallationIdentityStore", FakeIdentityStore,
    )

    assert cli.main(["status", "--json"]) == 0

    payload = _json_output(capsys)
    assert payload["platform_identity"] == {
        "state": "OBSERVED",
        "identity_id": "11111111-1111-1111-1111-111111111111",
        "serial": 7,
        "fingerprint": "a" * 64,
        "public_key_sha256": "a" * 64,
    }
    assert payload["service_endpoint"] == {
        "state": "OBSERVED",
        "source": "AEGIS_PLATFORM_SERVICE_ENDPOINT",
        "endpoint": "unix:///run/aegis-platform/mgmt-7.sock",
    }
    assert payload["management"]["state"] == "NOT_OBSERVED"


def test_core_free_import_isolation_in_fresh_process(tmp_path):
    root = Path(__file__).resolve().parents[1]
    code = (
        "import os,sys,json; "
        "os.environ['SOFIA_PLATFORM_ROLES']='MODULE_HOST'; "
        "from sofia.platform.cli import main; "
        "result=main(['status','--json']); "
        "assert result == 0; "
        "assert not [name for name in sys.modules if name == 'sofia.core' "
        "or name.startswith('sofia.core.')]"
    )
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join(filter(None, (
        str(root / "src"), environment.get("PYTHONPATH"),
    )))
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True,
        timeout=30, env=environment,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("operation", ["start", "stop", "restart"])
def test_service_mutations_fail_closed_without_os_mutation(
    operation, monkeypatch, capsys,
):
    monkeypatch.setattr(
        cli, "_service_status_payload",
        lambda: pytest.fail("service mutation must not observe or call the service"),
    )
    monkeypatch.setattr(
        cli.subprocess, "run",
        lambda *args, **kwargs: pytest.fail("service mutation must not call SCM/systemctl"),
    )
    monkeypatch.setattr(
        cli.subprocess, "Popen",
        lambda *args, **kwargs: pytest.fail("service mutation must not spawn a service"),
    )

    assert cli.main(["service", operation, "--json"]) == 3

    payload = _json_output(capsys)
    assert payload["code"] == "OWNER_APPROVAL_REQUIRED"
    assert payload["executed"] is False


@pytest.mark.parametrize("operation", ["start", "stop", "detach", "remove"])
def test_core_mutations_fail_closed_without_reading_or_writing_state(
    operation, monkeypatch, capsys,
):
    monkeypatch.setattr(
        cli, "_core_bindings",
        lambda *args, **kwargs: pytest.fail("core mutation must not read lifecycle state"),
    )

    assert cli.main(["core", operation, "--json"]) == 3

    payload = _json_output(capsys)
    assert payload["code"] == "MANAGEMENT_APPROVAL_REQUIRED"
    assert payload["executed"] is False


@pytest.mark.parametrize(
    "operation", ["install", "remove", "start", "stop", "disable", "update"],
)
def test_module_mutations_fail_closed(operation, monkeypatch, capsys):
    monkeypatch.setattr(
        cli, "_module_records",
        lambda *args, **kwargs: pytest.fail("module mutation must not read lifecycle state"),
    )

    assert cli.main(["module", operation, "--json"]) == 3

    payload = _json_output(capsys)
    assert payload["code"] == "MANAGEMENT_APPROVAL_REQUIRED"
    assert payload["executed"] is False


def test_absent_read_states_are_truthful_and_do_not_create_files(
    monkeypatch, tmp_path, capsys,
):
    missing = tmp_path / "platform.db"
    monkeypatch.setenv("AEGIS_PLATFORM_LOCAL_STATE", str(missing))

    assert cli.main(["core", "list", "--json"]) == 0
    core = _json_output(capsys)
    assert core == {
        "state": "NOT_OBSERVED",
        "reason": "PLATFORM_LOCAL_STATE_ABSENT",
        "management": {
            "state": "NOT_OBSERVED",
            "reason": "AUTHENTICATED_MANAGEMENT_NOT_CONFIGURED",
        },
    }

    assert cli.main(["module", "list", "--json"]) == 0
    module = _json_output(capsys)
    assert module == {
        "state": "NOT_OBSERVED",
        "reason": "PLATFORM_LOCAL_STATE_ABSENT",
    }

    assert cli.main(["startup", "--json"]) == 0
    startup = _json_output(capsys)
    assert startup["autostart_policy"]["state"] == "NOT_OBSERVED"
    assert startup["reconciliation"] == {
        "state": "NOT_OBSERVED",
        "reason": "PLATFORM_LOCAL_STATE_ABSENT",
    }
    assert not missing.exists()


def test_core_list_and_status_read_existing_platform_db_read_only(
    monkeypatch, tmp_path, capsys,
):
    state = tmp_path / "platform.db"
    _create_core_db(state)
    with sqlite3.connect(state) as db:
        db.execute(
            "INSERT INTO ops_synthetic_core_binding VALUES"
            "(?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "owner:one",
                "11111111-1111-1111-1111-111111111111",
                "22222222-2222-2222-2222-222222222222",
                3,
                "active",
                "b" * 64,
                "1.2.3",
                "2026-11-16T00:00:00+00:00",
                "2026-11-16T01:00:00+00:00",
                "start",
                "SUCCEEDED",
                "private detail must not be exposed",
            ),
        )
    monkeypatch.setenv("AEGIS_PLATFORM_LOCAL_STATE", str(state))
    before = hashlib.sha256(state.read_bytes()).hexdigest()

    assert cli.main(["core", "list", "--json"]) == 0
    payload = _json_output(capsys)
    assert payload["state"] == "OBSERVED"
    assert payload["authority"] == "READ_ONLY_PLATFORM_EVIDENCE"
    assert len(payload["bindings"]) == 1
    binding = payload["bindings"][0]
    assert binding["core_id"] == "11111111-1111-1111-1111-111111111111"
    assert binding["state"] == "active"
    assert "detail" not in binding

    assert cli.main([
        "core", "status", "11111111-1111-1111-1111-111111111111", "--json",
    ]) == 0
    status = _json_output(capsys)
    assert status["found"] is True
    assert status["bindings"][0]["generation"] == 3

    assert cli.main(["core", "status", "not-bound", "--json"]) == 0
    missing = _json_output(capsys)
    assert missing["found"] is False
    assert missing["bindings"] == []
    assert hashlib.sha256(state.read_bytes()).hexdigest() == before


def test_core_list_refuses_protected_core_database(monkeypatch, tmp_path, capsys):
    protected = tmp_path / "sofia.db"
    _create_core_db(protected)
    monkeypatch.setenv("AEGIS_PLATFORM_LOCAL_STATE", str(protected))

    assert cli.main(["core", "list", "--json"]) == 0

    payload = _json_output(capsys)
    assert payload == {
        "state": "NOT_OBSERVED",
        "reason": "PROTECTED_CORE_STATE_PATH",
        "management": {
            "state": "NOT_OBSERVED",
            "reason": "AUTHENTICATED_MANAGEMENT_NOT_CONFIGURED",
        },
    }


def test_module_list_and_status_read_canonical_module_table(
    monkeypatch, tmp_path, capsys,
):
    state = tmp_path / "platform.db"
    _create_module_db(state)
    with sqlite3.connect(state) as db:
        db.execute(
            "INSERT INTO platform_module_lifecycle VALUES(?,?,?,?,?,?,?,?,?)",
            (
                "module:example", "1.0.0", "c" * 64, "active", 4,
                "isolated", "/private/staged/path", "approved",
                "2026-11-16T00:00:00+00:00",
            ),
        )
    monkeypatch.setenv("AEGIS_PLATFORM_LOCAL_STATE", str(state))

    assert cli.main(["module", "list", "--json"]) == 0
    payload = _json_output(capsys)
    assert payload["state"] == "OBSERVED"
    assert payload["modules"] == [{
        "module_id": "module:example",
        "version": "1.0.0",
        "package_digest": "c" * 64,
        "lifecycle": "active",
        "revision": 4,
        "active_profile": "isolated",
        "updated_at": "2026-11-16T00:00:00+00:00",
    }]

    assert cli.main(["module", "status", "module:example", "--json"]) == 0
    status = _json_output(capsys)
    assert status["found"] is True
    assert status["modules"][0]["revision"] == 4


def test_service_status_without_trusted_pin_is_not_observed(
    monkeypatch, capsys,
):
    monkeypatch.setattr(
        cli.subprocess, "run",
        lambda *args, **kwargs: pytest.fail("untrusted service status must not call an OS service"),
    )

    assert cli.main(["service", "status", "--json"]) == 0

    payload = _json_output(capsys)
    assert payload == {
        "state": "NOT_OBSERVED",
        "reason": "OS_SERVICE_PIN_NOT_CONFIGURED",
        "source": "SCM" if sys.platform == "win32" else (
            "systemd" if sys.platform.startswith("linux") else None
        ),
    }


def test_service_status_uses_reviewed_read_only_observation_when_pinned(
    monkeypatch, capsys,
):
    monkeypatch.setattr(cli.sys, "platform", "linux")
    monkeypatch.setenv(
        "AEGIS_PLATFORM_SERVICE_UNIT_SHA256", "d" * 64,
    )
    observation = SimpleNamespace(to_payload=lambda: {
        "schema": "aegis.installer.native-service-observation.v1",
        "name": "aegis-platform.service",
        "source": "systemd",
        "origin": "MATCHES_CONFIG_UNVERIFIED",
        "process_state": "RUNNING",
        "health": "UNKNOWN",
        "executable_verified": False,
        "authorized": False,
        "executed": False,
    })
    import sofia.platform.ops.platform_installer_native_preflight as preflight
    monkeypatch.setattr(
        preflight, "inspect_debian_systemd_service",
        lambda **kwargs: (kwargs["expected_unit_sha256"] == "d" * 64)
        and observation or pytest.fail("pin was not forwarded"),
    )

    assert cli.main(["service", "status", "--json"]) == 0

    payload = _json_output(capsys)
    assert payload["state"] == "OBSERVED"
    assert payload["process_state"] == "RUNNING"
    assert payload["platform_ready"] == "NOT_OBSERVED"
    assert payload["service_mutated"] is False
    assert payload["executed"] is False


@pytest.mark.parametrize(
    ("command", "code"),
    [("gui", "AEGIS_GUI_NOT_AVAILABLE"), ("tui", "AEGIS_TUI_NOT_AVAILABLE")],
)
def test_gui_and_tui_absent_paths_exit_three_without_spawning(
    command, code, monkeypatch, capsys,
):
    monkeypatch.setattr(cli, "_installed_executable_directories", lambda: [])
    monkeypatch.setattr(cli.shutil, "which", lambda name: None)
    monkeypatch.setattr(
        cli.subprocess, "Popen",
        lambda *args, **kwargs: pytest.fail("absent launcher must not be spawned"),
    )

    assert cli.main([command, "--json"]) == 3

    payload = _json_output(capsys)
    assert payload["code"] == code
    assert payload["executed"] is False


def test_gui_and_tui_launch_only_when_explicitly_invoked(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(cli.sys, "platform", "win32")
    monkeypatch.setattr(cli, "_installed_executable_directories", lambda: [])
    monkeypatch.setattr(
        cli.shutil, "which",
        lambda name: f"C:/packaged/{name}",
    )
    monkeypatch.setattr(
        cli.subprocess, "Popen",
        lambda argv, **kwargs: calls.append((argv, kwargs)),
    )

    assert cli.main(["status", "--json"]) == 0
    _json_output(capsys)
    assert calls == []

    assert cli.main(["gui", "--json"]) == 0
    gui = _json_output(capsys)
    assert gui["state"] == "LAUNCHED"
    assert calls[0][0] == ["C:/packaged/aegis-control-center.exe"]

    assert cli.main(["tui", "--json"]) == 0
    tui = _json_output(capsys)
    assert tui["state"] == "LAUNCHED"
    assert calls[1][0] == ["C:/packaged/aegis_tui.exe"]


def test_chat_fails_closed_without_authenticated_core_binding(capsys):
    assert cli.main(["chat", "hello", "--json"]) == 3

    payload = _json_output(capsys)
    assert payload["code"] == "AUTHENTICATED_CORE_BINDING_REQUIRED"
    assert payload["executed"] is False
    assert "no conversation was created" in payload["message"]


def test_diagnostics_is_bounded_redacted_and_management_stays_unobserved(
    monkeypatch, tmp_path, capsys,
):
    endpoint = tmp_path / "private" / "management.sock"
    monkeypatch.setenv("SOFIA_PLATFORM_ROLES", "MODULE_HOST")
    monkeypatch.setenv("AEGIS_PLATFORM_SERVICE_ENDPOINT", str(endpoint))
    monkeypatch.setenv("AEGIS_PLATFORM_IDENTITY_HOME", str(tmp_path / "identity"))

    assert cli.main(["diagnostics", "--json"]) == 0

    raw = capsys.readouterr().out
    assert len(raw.encode("utf-8")) < 16_384
    payload = json.loads(raw)
    assert payload["management"]["state"] == "NOT_OBSERVED"
    assert payload["redaction"]["secrets_included"] is False
    assert str(tmp_path) not in raw
    assert str(tmp_path) not in payload["service_endpoint"]["endpoint"]


def test_startup_reads_autostart_policy_summary_when_canonical_db_present(
    monkeypatch, tmp_path, capsys,
):
    policy = tmp_path / "autostart-policy.db"
    with sqlite3.connect(policy) as db:
        db.executescript(
            """
            CREATE TABLE platform_autostart_policy(
                service TEXT PRIMARY KEY,
                enabled INTEGER NOT NULL
            );
            """
        )
        db.executemany(
            "INSERT INTO platform_autostart_policy VALUES(?,?)",
            [("platform", 1), ("gui", 0)],
        )
    monkeypatch.setenv("AEGIS_PLATFORM_AUTOSTART_POLICY_DB", str(policy))

    assert cli.main(["startup", "--json"]) == 0

    payload = _json_output(capsys)
    assert payload["autostart_policy"]["state"] == "OBSERVED"
    assert payload["autostart_policy"]["summary"] == {
        "entry_count": 2,
        "enabled_count": 1,
        "table": "platform_autostart_policy",
    }


def test_startup_reports_truthful_reconciliation_outcome(
    monkeypatch, tmp_path, capsys,
):
    state = tmp_path / "platform.db"
    _create_core_db(state)
    with sqlite3.connect(state) as db:
        db.executemany(
            "INSERT INTO ops_synthetic_core_operation VALUES(?,?,?)",
            [
                ("op-1", "11111111-1111-1111-1111-111111111111", None),
                ("op-2", "22222222-2222-2222-2222-222222222222", "SUCCEEDED"),
            ],
        )
    monkeypatch.setenv("AEGIS_PLATFORM_LOCAL_STATE", str(state))

    assert cli.main(["startup", "--json"]) == 0

    payload = _json_output(capsys)
    assert payload["reconciliation"] == {
        "state": "OBSERVED",
        "outcome": "RECONCILIATION_REQUIRED",
        "unresolved_operations": 1,
    }
    assert "RECONCILIATION_REQUIRED" in payload["blockers"]


def test_bare_invocation_opens_the_tui(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(cli.sys, "platform", "win32")
    monkeypatch.setattr(cli, "_installed_executable_directories", lambda: [])
    monkeypatch.setattr(
        cli.shutil, "which", lambda name: f"C:/packaged/{name}",
    )
    monkeypatch.setattr(
        cli.subprocess, "Popen",
        lambda argv, **kwargs: calls.append((argv, kwargs)),
    )

    assert cli.main([]) == 0

    assert calls == [(["C:/packaged/aegis_tui.exe"], {"close_fds": True})]


def test_bare_invocation_without_tui_exits_three(monkeypatch, capsys):
    monkeypatch.setattr(cli, "_installed_executable_directories", lambda: [])
    monkeypatch.setattr(cli.shutil, "which", lambda name: None)
    monkeypatch.setattr(
        cli.subprocess, "Popen",
        lambda *args, **kwargs: pytest.fail("absent TUI must not be spawned"),
    )

    assert cli.main([]) == 3

    captured = capsys.readouterr()
    assert "AEGIS_TUI_NOT_AVAILABLE" in captured.err


def test_version_and_help_are_available(capsys):
    assert cli.main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == cli._package_version()

    with pytest.raises(SystemExit) as exited:
        cli.main(["--help"])
    assert exited.value.code == 0
    help_text = capsys.readouterr().out
    assert "usage: aegis" in help_text
    assert "doctor" in help_text


def test_doctor_startup_is_a_read_only_alias(monkeypatch, tmp_path, capsys):
    missing = tmp_path / "platform.db"
    monkeypatch.setenv("AEGIS_PLATFORM_LOCAL_STATE", str(missing))

    assert cli.main(["doctor", "--startup", "--json"]) == 0

    payload = _json_output(capsys)
    assert payload["schema"] == "aegis.platform.cli.startup.v1"
    assert payload["zero_core"]["core_required"] is False
    assert payload["management"]["state"] == "NOT_OBSERVED"
    assert not missing.exists()


def _management_response(**overrides):
    response = {
        "platform_id": "11111111-1111-1111-1111-111111111111",
        "generation": 3,
        "observed_at": "2026-11-16T00:00:00.000000Z",
        "outcome": "OK",
        "data": {
            "platform_id": "11111111-1111-1111-1111-111111111111",
            "generation": 3,
            "operator_stop": False,
            "core_started": False,
        },
        "denial_code": None,
    }
    response.update(overrides)
    return SimpleNamespace(**response)


def _pin_windows_management(
    monkeypatch, *, endpoint=None, platform_id=None, generation=None,
):
    monkeypatch.setattr(cli.sys, "platform", "win32")
    from sofia.sdk.platform_management_windows_client import (
        windows_management_pipe_name,
    )
    platform_id = platform_id or "11111111-1111-1111-1111-111111111111"
    generation = generation or 3
    pipe_name = windows_management_pipe_name(
        platform_id=platform_id, generation=generation,
    )
    monkeypatch.setenv(
        "AEGIS_PLATFORM_MANAGEMENT_ENDPOINT", endpoint or pipe_name,
    )
    monkeypatch.setenv("AEGIS_PLATFORM_EXPECTED_ID", platform_id)
    monkeypatch.setenv("AEGIS_PLATFORM_EXPECTED_GENERATION", str(generation))
    return platform_id, generation, pipe_name


def test_status_uses_live_windows_client_when_pinned(monkeypatch, capsys):
    platform_id, generation, pipe_name = _pin_windows_management(monkeypatch)
    observed = {}

    def fake_read(**kwargs):
        observed.update(kwargs)
        return _management_response(
            platform_id=platform_id, generation=generation,
        )

    import sofia.sdk.platform_management_windows_client as windows_client
    monkeypatch.setattr(
        windows_client, "read_windows_management", fake_read,
    )

    assert cli.main(["status", "--json"]) == 0

    payload = _json_output(capsys)
    assert payload["management"]["state"] == "OBSERVED"
    assert payload["management"]["authority"] == "AUTHENTICATED_PLATFORM_MANAGEMENT"
    assert payload["management"]["data"]["core_started"] is False
    assert observed == {
        "pipe_name": pipe_name,
        "expected_platform_id": platform_id,
        "expected_generation": generation,
        "operation": "platform.status",
    }


def test_status_accepts_management_pin_flags(monkeypatch, capsys):
    monkeypatch.setattr(cli.sys, "platform", "win32")
    from sofia.sdk.platform_management_windows_client import (
        windows_management_pipe_name,
    )
    platform_id = "11111111-1111-1111-1111-111111111111"
    generation = 3
    pipe_name = windows_management_pipe_name(
        platform_id=platform_id, generation=generation,
    )
    observed = {}

    import sofia.sdk.platform_management_windows_client as windows_client
    def fake_read(**kwargs):
        observed.update(kwargs)
        return _management_response(
            platform_id=platform_id, generation=generation,
        )

    monkeypatch.setattr(
        windows_client, "read_windows_management", fake_read,
    )

    assert cli.main([
        "status", "--json",
        "--endpoint", "\\\\.\\pipe\\" + pipe_name,
        "--expected-platform-id", platform_id,
        "--expected-generation", str(generation),
    ]) == 0

    payload = _json_output(capsys)
    assert payload["management"]["state"] == "OBSERVED"
    assert observed["pipe_name"] == pipe_name


def test_startup_and_core_list_use_live_windows_client(monkeypatch, capsys):
    platform_id, generation, _ = _pin_windows_management(monkeypatch)
    operations = []

    def fake_read(**kwargs):
        operations.append(kwargs["operation"])
        if kwargs["operation"] == "startup.status":
            return _management_response(
                platform_id=platform_id, generation=generation,
                data={
                    "platform_id": platform_id,
                    "generation": generation,
                    "operator_stop": False,
                    "core_started": False,
                    "core_count": 0,
                    "active_core_count": 0,
                    "startup_state": "ZERO_CORE_HEALTHY",
                    "autostart_enabled_count": 0,
                    "autostart_reconciled_at": None,
                    "management_listening": True,
                },
            )
        return _management_response(
            platform_id=platform_id, generation=generation,
            data={
                "platform_id": platform_id,
                "generation": generation,
                "operator_stop": False,
                "cores": [],
            },
        )

    import sofia.sdk.platform_management_windows_client as windows_client
    monkeypatch.setattr(
        windows_client, "read_windows_management", fake_read,
    )

    assert cli.main(["startup", "--json"]) == 0
    startup = _json_output(capsys)
    assert startup["management"]["state"] == "OBSERVED"
    assert startup["management"]["data"]["startup_state"] == "ZERO_CORE_HEALTHY"

    assert cli.main(["core", "list", "--json"]) == 0
    core = _json_output(capsys)
    assert core["management"]["state"] == "OBSERVED"
    assert core["management"]["data"]["cores"] == []
    assert operations == ["startup.status", "core.list"]


def test_live_management_denial_is_reported_not_converted_to_success(
    monkeypatch, capsys,
):
    platform_id, generation, _ = _pin_windows_management(monkeypatch)

    import sofia.sdk.platform_management_windows_client as windows_client
    monkeypatch.setattr(
        windows_client, "read_windows_management",
        lambda **kwargs: _management_response(
            platform_id=platform_id, generation=generation,
            outcome="DENIED", data=None, denial_code="STOPPED",
        ),
    )

    assert cli.main(["status", "--json"]) == 0

    payload = _json_output(capsys)
    assert payload["management"]["state"] == "DENIED"
    assert payload["management"]["denial_code"] == "STOPPED"
    assert "data" not in payload["management"]


def test_live_management_unavailable_is_not_observed(monkeypatch, capsys):
    _pin_windows_management(monkeypatch)

    import sofia.sdk.platform_management_windows_client as windows_client
    def unavailable(**kwargs):
        raise PermissionError("pipe unavailable")

    monkeypatch.setattr(
        windows_client, "read_windows_management", unavailable,
    )

    assert cli.main(["status", "--json"]) == 0

    payload = _json_output(capsys)
    assert payload["management"]["state"] == "NOT_OBSERVED"
    assert payload["management"]["reason"] == "MANAGEMENT_OBSERVATION_UNAVAILABLE"
    assert payload["management"]["detail"] == "PermissionError"


def test_windows_endpoint_pin_rejects_arbitrary_path(monkeypatch, capsys):
    _pin_windows_management(
        monkeypatch, endpoint="\\\\.\\pipe\\AegisPlatform-aaaaaaaa-1",
    )

    import sofia.sdk.platform_management_windows_client as windows_client
    monkeypatch.setattr(
        windows_client, "read_windows_management",
        lambda **kwargs: pytest.fail("mismatched pin must not reach the client"),
    )

    assert cli.main(["status", "--json"]) == 3

    payload = _json_output(capsys)
    assert payload["code"] == "MANAGEMENT_ENDPOINT_PIN_MISMATCH"
    assert payload["executed"] is False


def test_linux_live_management_uses_installed_service_identity_pins(
    monkeypatch, capsys, tmp_path,
):
    monkeypatch.setattr(cli.sys, "platform", "linux")
    socket_path = tmp_path / "run" / "mgmt-3.sock"
    monkeypatch.setenv("AEGIS_PLATFORM_MANAGEMENT_ENDPOINT", str(socket_path))
    monkeypatch.setenv("AEGIS_PLATFORM_EXPECTED_ID", "platform:alpha")
    monkeypatch.setenv("AEGIS_PLATFORM_EXPECTED_GENERATION", "3")
    monkeypatch.setenv("AEGIS_PLATFORM_SERVICE_UID", "1000")
    monkeypatch.setenv("AEGIS_PLATFORM_SERVICE_GID", "1000")
    observed = {}

    import sofia.sdk.platform_management_client as linux_client
    def fake_read(**kwargs):
        observed.update(kwargs)
        return _management_response(
            platform_id="platform:alpha", generation=3,
        )

    monkeypatch.setattr(linux_client, "read_linux_management", fake_read)

    assert cli.main(["status", "--json"]) == 0

    payload = _json_output(capsys)
    assert payload["management"]["state"] == "OBSERVED"
    assert observed["socket_path"] == socket_path
    assert observed["installed_service_uid"] == 1000
    assert observed["installed_service_gid"] == 1000
    assert observed["installed_service_pid"] is None


def test_linux_missing_service_identity_pin_is_not_observed(
    monkeypatch, capsys, tmp_path,
):
    monkeypatch.setattr(cli.sys, "platform", "linux")
    monkeypatch.setenv(
        "AEGIS_PLATFORM_MANAGEMENT_ENDPOINT", str(tmp_path / "mgmt.sock"),
    )
    monkeypatch.setenv("AEGIS_PLATFORM_EXPECTED_ID", "platform:alpha")
    monkeypatch.setenv("AEGIS_PLATFORM_EXPECTED_GENERATION", "3")

    assert cli.main(["status", "--json"]) == 0

    payload = _json_output(capsys)
    assert payload["management"] == {
        "state": "NOT_OBSERVED",
        "reason": "MANAGEMENT_SERVICE_UID_PIN_NOT_CONFIGURED",
    }


def test_linux_installed_locations_are_searched(monkeypatch):
    monkeypatch.setattr(cli.sys, "platform", "linux")
    directories = cli._installed_executable_directories()
    assert Path("/opt/aegis/bin") in directories
    assert Path("/usr/local/bin") in directories


def test_linux_endpoint_pin_rejects_relative_socket(monkeypatch, capsys):
    monkeypatch.setattr(cli.sys, "platform", "linux")
    monkeypatch.setenv("AEGIS_PLATFORM_MANAGEMENT_ENDPOINT", "relative/mgmt.sock")
    monkeypatch.setenv("AEGIS_PLATFORM_EXPECTED_ID", "platform:alpha")
    monkeypatch.setenv("AEGIS_PLATFORM_EXPECTED_GENERATION", "3")
    monkeypatch.setenv("AEGIS_PLATFORM_SERVICE_UID", "1000")
    monkeypatch.setenv("AEGIS_PLATFORM_SERVICE_GID", "1000")

    assert cli.main(["status", "--json"]) == 3

    payload = _json_output(capsys)
    assert payload["code"] == "MANAGEMENT_ENDPOINT_PIN_MISMATCH"


@pytest.mark.parametrize(
    ("command", "filename"),
    [("tui", "aegis_tui.exe"), ("gui", "aegis-control-center.exe")],
)
def test_installed_bin_location_precedes_path(
    command, filename, monkeypatch, tmp_path, capsys,
):
    bindir = tmp_path / "Aegis" / "bin"
    bindir.mkdir(parents=True)
    executable = bindir / filename
    executable.write_text("", encoding="utf-8")
    calls = []
    monkeypatch.setattr(cli.sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(
        cli.shutil, "which",
        lambda name: pytest.fail("installed bin must be checked before PATH"),
    )
    monkeypatch.setattr(
        cli.subprocess, "Popen",
        lambda argv, **kwargs: calls.append((argv, kwargs)),
    )

    assert cli.main([command, "--json"]) == 0

    payload = _json_output(capsys)
    assert payload["state"] == "LAUNCHED"
    assert calls[0][0] == [str(executable)]


@pytest.mark.parametrize(
    ("argv", "code"),
    [
        (["service", "start", "--approval-id", "x", "--json"],
         "OWNER_APPROVAL_REQUIRED"),
        (["core", "autostart", "core-id", "on", "--approval-id", "x",
          "--json"], "MANAGEMENT_REVISION_REQUIRED"),
        (["module", "start", "module-id", "--approval-id", "x", "--json"],
         "MANAGEMENT_APPROVAL_REQUIRED"),
        (["chat", "hello", "--approval-id", "x", "--json"],
         "AUTHENTICATED_CORE_BINDING_REQUIRED"),
    ],
)
def test_cli_approval_id_is_parsed_but_never_grants_authority(
    argv, code, capsys,
):
    assert cli.main(argv) == 3

    payload = _json_output(capsys)
    assert payload["code"] == code
    assert payload["executed"] is False
    assert payload["authority_granted"] is False


def test_pyproject_declares_the_public_aegis_entrypoint():
    root = Path(__file__).resolve().parents[1]
    document = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    assert document["project"]["scripts"]["aegis"] == "sofia.platform.cli:main"


CORE_ID = "22222222-2222-2222-2222-222222222222"


def _mutation_response(
    *, platform_id: str, generation: int,
    operation: str = "core.autostart.enable",
    outcome: str = "SUCCEEDED",
    error_code: str | None = None,
    current_revision: int = 1,
):
    return SimpleNamespace(
        request_id="request:test",
        correlation_id="correlation:test",
        idempotency_key="idempotency:test",
        platform_id=platform_id,
        operation=operation,
        outcome=outcome,
        receipt_id="mutreceipt:test",
        current_generation=generation,
        current_revision=current_revision,
        error_code=error_code,
        detail=None,
        observed_at="2026-11-16T00:00:00.000000Z",
    )


def _autostart_argv(*extra: str) -> list[str]:
    return [
        "core", "autostart", CORE_ID, "on",
        "--approval-id", "approval:one-use",
        "--expected-revision", "1",
        *extra,
        "--json",
    ]


def test_core_autostart_uses_authenticated_mutation_client(
    monkeypatch, capsys,
):
    platform_id, generation, pipe_name = _pin_windows_management(monkeypatch)
    observed = {}

    def fake_mutation(**kwargs):
        observed.update(kwargs)
        return _mutation_response(
            platform_id=platform_id, generation=generation,
            operation=kwargs["operation"],
        )

    import sofia.sdk.platform_management_mutation_client as mutation_client
    monkeypatch.setattr(
        mutation_client, "mutate_windows_management", fake_mutation,
    )
    monkeypatch.setattr(
        cli, "_core_bindings",
        lambda *args, **kwargs: pytest.fail(
            "autostart must not read direct Core state"
        ),
    )
    monkeypatch.setattr(
        cli.sqlite3, "connect",
        lambda *args, **kwargs: pytest.fail(
            "autostart must not open local SQLite"
        ),
    )

    assert cli.main(_autostart_argv()) == 0

    payload = _json_output(capsys)
    assert payload["schema"] == "aegis.platform.cli.core-autostart.v1"
    assert payload["ok"] is True
    assert payload["outcome"] == "SUCCEEDED"
    assert payload["executed"] is True
    assert payload["authority_granted"] is False
    assert payload["receipt_id"] == "mutreceipt:test"
    assert payload["current_revision"] == 1
    assert observed == {
        "pipe_name": pipe_name,
        "expected_platform_id": platform_id,
        "expected_generation": generation,
        "operation": "core.autostart.enable",
        "core_id": CORE_ID,
        "expected_policy_revision": 1,
        "enabled": True,
        "approval_id": "approval:one-use",
        "expected_mutation_revision": 0,
    }


def test_core_autostart_off_uses_disable_operation(monkeypatch, capsys):
    platform_id, generation, _ = _pin_windows_management(monkeypatch)
    observed = {}

    def fake_mutation(**kwargs):
        observed.update(kwargs)
        return _mutation_response(
            platform_id=platform_id, generation=generation,
            operation=kwargs["operation"],
        )

    import sofia.sdk.platform_management_mutation_client as mutation_client
    monkeypatch.setattr(
        mutation_client, "mutate_windows_management", fake_mutation,
    )

    assert cli.main([
        "core", "autostart", CORE_ID, "off",
        "--approval-id", "approval:one-use",
        "--expected-revision", "2",
        "--expected-mutation-revision", "1",
        "--json",
    ]) == 0

    payload = _json_output(capsys)
    assert payload["operation"] == "core.autostart.disable"
    assert observed["operation"] == "core.autostart.disable"
    assert observed["enabled"] is False
    assert observed["expected_policy_revision"] == 2
    assert observed["expected_mutation_revision"] == 1


def test_core_autostart_requires_caller_supplied_approval(
    monkeypatch, capsys,
):
    _pin_windows_management(monkeypatch)

    import sofia.sdk.platform_management_mutation_client as mutation_client
    monkeypatch.setattr(
        mutation_client, "mutate_windows_management",
        lambda **kwargs: pytest.fail("approval-free autostart must not connect"),
    )

    assert cli.main([
        "core", "autostart", CORE_ID, "on",
        "--expected-revision", "1", "--json",
    ]) == 3

    payload = _json_output(capsys)
    assert payload["code"] == "MANAGEMENT_APPROVAL_REQUIRED"
    assert payload["executed"] is False
    assert payload["authority_granted"] is False


def test_core_autostart_requires_exact_revision_and_transport(
    monkeypatch, capsys,
):
    _pin_windows_management(monkeypatch)

    assert cli.main([
        "core", "autostart", CORE_ID, "on",
        "--approval-id", "approval:one-use", "--json",
    ]) == 3
    assert _json_output(capsys)["code"] == "MANAGEMENT_REVISION_REQUIRED"

    for key in (
        "AEGIS_PLATFORM_MANAGEMENT_ENDPOINT",
        "AEGIS_PLATFORM_EXPECTED_ID",
        "AEGIS_PLATFORM_EXPECTED_GENERATION",
    ):
        monkeypatch.delenv(key, raising=False)

    assert cli.main(_autostart_argv()) == 3
    missing = _json_output(capsys)
    assert missing["code"] == "AUTHENTICATED_MANAGEMENT_NOT_CONFIGURED"
    assert missing["executed"] is False


@pytest.mark.parametrize(
    ("outcome", "error_code", "exit_code"),
    [
        ("DENIED", "STALE_REVISION", 3),
        ("DENIED", "STOPPED", 3),
        ("FAILED", "HANDLER_FAILED", 3),
        ("OUTCOME_UNKNOWN", "HANDLER_FAILED_UNKNOWN", 4),
    ],
)
def test_core_autostart_reports_typed_outcomes(
    outcome, error_code, exit_code, monkeypatch, capsys,
):
    platform_id, generation, _ = _pin_windows_management(monkeypatch)
    calls = []

    def fake_mutation(**kwargs):
        calls.append(kwargs)
        return _mutation_response(
            platform_id=platform_id, generation=generation,
            operation=kwargs["operation"], outcome=outcome,
            error_code=error_code,
            current_revision=0 if outcome in {"DENIED", "FAILED"} else 1,
        )

    import sofia.sdk.platform_management_mutation_client as mutation_client
    monkeypatch.setattr(
        mutation_client, "mutate_windows_management", fake_mutation,
    )

    assert cli.main(_autostart_argv()) == exit_code

    payload = _json_output(capsys)
    assert payload["outcome"] == outcome
    assert payload["error_code"] == error_code
    assert payload["executed"] is (True if outcome == "SUCCEEDED" else (
        None if outcome == "OUTCOME_UNKNOWN" else False
    ))
    assert payload["authority_granted"] is False
    assert len(calls) == 1


def test_core_autostart_ambiguous_transport_is_outcome_unknown_without_retry(
    monkeypatch, capsys,
):
    _pin_windows_management(monkeypatch)
    calls = []

    import sofia.sdk.platform_management_mutation_client as mutation_client

    def ambiguous(**kwargs):
        calls.append(kwargs)
        try:
            raise ValueError("malformed response")
        except ValueError as error:
            raise mutation_client.ManagementMutationAmbiguous(
                "unknown outcome"
            ) from error

    monkeypatch.setattr(
        mutation_client, "mutate_windows_management", ambiguous,
    )

    assert cli.main(_autostart_argv()) == 4

    payload = _json_output(capsys)
    assert payload["state"] == "OUTCOME_UNKNOWN"
    assert payload["outcome"] == "OUTCOME_UNKNOWN"
    assert payload["executed"] is None
    assert payload["retryable"] is False
    assert payload["detail"] == "ValueError"
    assert len(calls) == 1


def test_core_autostart_wrong_platform_pin_never_reaches_client(
    monkeypatch, capsys,
):
    _pin_windows_management(
        monkeypatch, endpoint="\\\\.\\pipe\\AegisPlatform-aaaaaaaa-1",
    )

    import sofia.sdk.platform_management_mutation_client as mutation_client
    monkeypatch.setattr(
        mutation_client, "mutate_windows_management",
        lambda **kwargs: pytest.fail("mismatched pin must not reach the client"),
    )

    assert cli.main(_autostart_argv()) == 3

    payload = _json_output(capsys)
    assert payload["code"] == "MANAGEMENT_ENDPOINT_PIN_MISMATCH"
    assert payload["executed"] is False


def test_core_start_and_stop_are_explicitly_unsupported(
    monkeypatch, capsys,
):
    for operation in ("start", "stop"):
        assert cli.main([
            "core", operation, CORE_ID,
            "--approval-id", "approval:one-use", "--json",
        ]) == 3
        payload = _json_output(capsys)
        assert payload["code"] == "UNSUPPORTED_OPERATION"
        assert payload["executed"] is False


def test_core_autostart_state_must_be_on_or_off(capsys):
    with pytest.raises(SystemExit) as exited:
        cli.main([
            "core", "autostart", CORE_ID, "maybe",
            "--approval-id", "approval:one-use",
            "--expected-revision", "1", "--json",
        ])
    assert exited.value.code == 2
