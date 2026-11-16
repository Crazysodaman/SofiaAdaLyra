"""Public ``aegis`` management client.

This is deliberately a *client* surface, not a startup owner.  It never
constructs a Core, opens the Platform service process lock, queries protected
Core state, mutates an OS service, or fabricates live management health.

Read-only local configuration and already-durable Platform evidence may be
displayed.  Anything that requires the authenticated Platform management
transport reports ``NOT_OBSERVED`` until a real client is configured.  Every
mutation is refused before any transport or native service API is touched.
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
from typing import Iterable, Sequence

CLI_SCHEMA = "aegis.platform.cli"
EXIT_OK = 0
EXIT_USAGE = 2
EXIT_REFUSED = 3
NOT_OBSERVED = "NOT_OBSERVED"

OWNER_APPROVAL_REQUIRED = "OWNER_APPROVAL_REQUIRED"
MANAGEMENT_APPROVAL_REQUIRED = "MANAGEMENT_APPROVAL_REQUIRED"
AUTHENTICATED_CORE_BINDING_REQUIRED = "AUTHENTICATED_CORE_BINDING_REQUIRED"
AEGIS_GUI_NOT_AVAILABLE = "AEGIS_GUI_NOT_AVAILABLE"
AEGIS_TUI_NOT_AVAILABLE = "AEGIS_TUI_NOT_AVAILABLE"

_IDENTITY_HOME_ENV = "AEGIS_PLATFORM_IDENTITY_HOME"
_SERVICE_ENDPOINT_ENVS = (
    "AEGIS_PLATFORM_SERVICE_ENDPOINT",
    "AEGIS_PLATFORM_MANAGEMENT_ENDPOINT",
    "AEGIS_PLATFORM_ENDPOINT",
    "SOFIA_PLATFORM_SERVICE_ENDPOINT",
    "SOFIA_PLATFORM_MANAGEMENT_ENDPOINT",
)
_STATE_PATH_ENVS = (
    "AEGIS_PLATFORM_LOCAL_STATE",
    "AEGIS_LOCAL_STATE",
    "AEGIS_PLATFORM_STATE_PATH",
    "AEGIS_PLATFORM_DB",
    "AEGIS_PLATFORM_DATABASE",
    "SOFIA_PLATFORM_LOCAL_STATE",
    "SOFIA_PLATFORM_DB",
)
_AUTOSTART_POLICY_ENVS = (
    "AEGIS_PLATFORM_AUTOSTART_POLICY_DB",
    "SOFIA_PLATFORM_AUTOSTART_POLICY_DB",
)
_AUTOSTART_MODULES = (
    "sofia.platform.run.autostart_policy",
    "sofia.platform.run.autostart",
    "sofia.platform.config.autostart",
)
_AUTOSTART_TABLES = (
    "platform_autostart_policy",
    "aegis_autostart_policy",
    "autostart_policy",
    "startup_policy",
)
_MODULE_TABLES = ("platform_module_lifecycle",)
_CORE_TABLE = "ops_synthetic_core_binding"

_MAX_ROWS = 256
_MAX_TEXT = 200
_MAX_DIAGNOSTIC_BYTES = 16_384

_GUI_EXECUTABLES = (
    "aegis-control-center",
    "aegis-control-center.exe",
    "sofia-desktop",
    "sofia-desktop.exe",
)
_TUI_EXECUTABLES = (
    "aegis-tui",
    "aegis-tui.exe",
    "aegis_tui",
    "aegis_tui.exe",
)

_CORE_MUTATIONS = frozenset({"start", "stop", "detach", "remove"})
_MODULE_MUTATIONS = frozenset({
    "start", "stop", "restart", "enable", "disable", "install", "remove",
    "uninstall", "update", "reinstall", "block", "unblock",
})


def _emit(payload: object, *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, sort_keys=True, ensure_ascii=False))
    else:
        _print_text(payload)


def _print_text(value: object, indent: int = 0) -> None:
    prefix = "  " * indent
    if isinstance(value, dict):
        for key in sorted(value):
            member = value[key]
            if isinstance(member, (dict, list)):
                print(f"{prefix}{key}:")
                _print_text(member, indent + 1)
            else:
                print(f"{prefix}{key}: {member}")
    elif isinstance(value, list):
        if not value:
            print(f"{prefix}[]")
            return
        for index, member in enumerate(value):
            if isinstance(member, (dict, list)):
                print(f"{prefix}[{index}]")
                _print_text(member, indent + 1)
            else:
                print(f"{prefix}- {member}")
    else:
        print(f"{prefix}{value}")


def _error_payload(code: str, message: str, *, command: str) -> dict[str, object]:
    return {
        "schema": f"{CLI_SCHEMA}.error.v1",
        "ok": False,
        "command": command,
        "code": code,
        "message": message,
        "executed": False,
        "authority_granted": False,
    }


def _refuse(
    code: str, message: str, *, command: str, as_json: bool,
    observation: dict[str, object] | None = None,
) -> int:
    payload = _error_payload(code, message, command=command)
    if observation is not None:
        payload["observation"] = observation
    if as_json:
        _emit(payload, as_json=True)
    else:
        print(f"aegis {command} refused: {code}: {message}", file=sys.stderr)
    return EXIT_REFUSED


def _redact_text(value: object, *, limit: int = _MAX_TEXT) -> str:
    text = str(value)
    text = "".join(char for char in text if char >= " " and char != "\x7f")
    home = os.path.expanduser("~")
    if home and home != "/" and home in text:
        text = text.replace(home, "<home>")
    return text[:limit]


def _bounded_rows(rows: Iterable[Sequence[object]], columns: Sequence[str]) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for row in rows:
        if len(result) >= _MAX_ROWS:
            break
        item: dict[str, object] = {}
        for column, value in zip(columns, row):
            if isinstance(value, str):
                item[column] = _redact_text(value)
            elif value is None or type(value) in (int, bool):
                item[column] = value
            else:
                item[column] = _redact_text(value)
        result.append(item)
    return result


def _roles_payload() -> dict[str, object]:
    try:
        from sofia.platform.config.roles import PlatformRoleConfiguration
        return PlatformRoleConfiguration.from_environment().to_payload()
    except Exception as exc:  # configuration is observation, not authority
        return {
            "schema": "companion.platform.roles.v1",
            "state": "UNAVAILABLE",
            "reason": type(exc).__name__,
        }


def _identity_payload() -> dict[str, object]:
    raw_home = os.environ.get(_IDENTITY_HOME_ENV, "").strip()
    if not raw_home:
        return {"state": "NOT_CONFIGURED"}
    try:
        from sofia.platform.state.installation_identity import InstallationIdentityStore
        identity = InstallationIdentityStore(Path(raw_home)).load()
    except Exception as exc:
        return {"state": "UNAVAILABLE", "reason": type(exc).__name__}
    return {
        "state": "OBSERVED",
        "identity_id": identity.identity.canonical_uuid,
        "serial": identity.identity.serial,
        "fingerprint": identity.public_key_sha256,
        "public_key_sha256": identity.public_key_sha256,
    }


def _service_endpoint_payload(*, redact_value: bool = False) -> dict[str, object]:
    for name in _SERVICE_ENDPOINT_ENVS:
        value = os.environ.get(name, "").strip()
        if value:
            return {
                "state": "OBSERVED",
                "source": name,
                "endpoint": "<configured>" if redact_value else _redact_text(value),
            }
    return {"state": "NOT_CONFIGURED"}


def _state_path() -> Path | None:
    for name in _STATE_PATH_ENVS:
        value = os.environ.get(name, "").strip()
        if value:
            return Path(value)
    return None


def _safe_state_path(path: Path | None) -> tuple[Path | None, str | None]:
    if path is None:
        return None, "PLATFORM_LOCAL_STATE_NOT_CONFIGURED"
    try:
        from sofia.platform.state.private_file import (
            assert_no_redirected_components, assert_not_protected_state_path,
        )
        assert_not_protected_state_path(path)
        assert_no_redirected_components(path, include_leaf=True)
    except PermissionError as exc:
        reason = (
            "PROTECTED_CORE_STATE_PATH"
            if "protected canonical Core state" in str(exc)
            else "UNSAFE_PLATFORM_STATE_PATH"
        )
        return None, reason
    except Exception:
        return None, "UNSAFE_PLATFORM_STATE_PATH"
    if not path.is_file():
        return None, "PLATFORM_LOCAL_STATE_ABSENT"
    return path, None


def _open_read_only(path: Path) -> sqlite3.Connection:
    uri = path.resolve().as_uri() + "?mode=ro"
    db = sqlite3.connect(uri, uri=True, timeout=2.0)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA query_only=ON")
    db.execute("PRAGMA busy_timeout=2000")
    return db


def _table_names(db: sqlite3.Connection) -> set[str]:
    rows = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    return {str(row[0]) for row in rows}


def _not_observed(reason: str, **extra: object) -> dict[str, object]:
    payload: dict[str, object] = {"state": NOT_OBSERVED, "reason": reason}
    payload.update(extra)
    return payload


def _core_bindings(core_id: str | None = None) -> dict[str, object]:
    path, reason = _safe_state_path(_state_path())
    if path is None:
        return _not_observed(reason or "PLATFORM_LOCAL_STATE_NOT_CONFIGURED")
    try:
        db = _open_read_only(path)
    except (OSError, sqlite3.Error):
        return _not_observed("PLATFORM_STATE_UNREADABLE")
    try:
        if _CORE_TABLE not in _table_names(db):
            return _not_observed(
                "SYNTHETIC_CORE_BINDINGS_TABLE_ABSENT",
                source=_redact_text(path),
            )
        columns = (
            "owner_id", "core_id", "lineage_id", "generation", "state",
            "artifact_sha256", "version", "installed_at", "updated_at",
            "last_operation", "last_outcome",
        )
        query = (
            "SELECT " + ",".join(columns) + f" FROM {_CORE_TABLE}"
        )
        parameters: tuple[object, ...] = ()
        if core_id is not None:
            query += " WHERE core_id=?"
            parameters = (core_id,)
        query += " ORDER BY core_id LIMIT ?"
        parameters += (_MAX_ROWS,)
        rows = db.execute(query, parameters).fetchall()
    except sqlite3.Error:
        return _not_observed("PLATFORM_STATE_UNREADABLE", source=_redact_text(path))
    finally:
        db.close()
    bindings = _bounded_rows(rows, columns)
    payload: dict[str, object] = {
        "state": "OBSERVED",
        "source": _redact_text(path),
        "authority": "READ_ONLY_PLATFORM_EVIDENCE",
        "bindings": bindings,
    }
    if core_id is not None:
        payload["requested_core_id"] = _redact_text(core_id)
        payload["found"] = bool(bindings)
    return payload


def _module_records(module_id: str | None = None) -> dict[str, object]:
    path, reason = _safe_state_path(_state_path())
    if path is None:
        return _not_observed(reason or "PLATFORM_LOCAL_STATE_NOT_CONFIGURED")
    try:
        db = _open_read_only(path)
    except (OSError, sqlite3.Error):
        return _not_observed("PLATFORM_STATE_UNREADABLE")
    try:
        tables = _table_names(db)
        table = next((name for name in _MODULE_TABLES if name in tables), None)
        if table is None:
            return _not_observed(
                "CANONICAL_MODULE_STORE_ABSENT", source=_redact_text(path),
            )
        columns = (
            "module_id", "version", "package_digest", "lifecycle",
            "revision", "active_profile", "updated_at",
        )
        query = "SELECT " + ",".join(columns) + f" FROM {table}"
        parameters: tuple[object, ...] = ()
        if module_id is not None:
            query += " WHERE module_id=?"
            parameters = (module_id,)
        query += " ORDER BY module_id LIMIT ?"
        parameters += (_MAX_ROWS,)
        rows = db.execute(query, parameters).fetchall()
    except sqlite3.Error:
        return _not_observed("PLATFORM_STATE_UNREADABLE", source=_redact_text(path))
    finally:
        db.close()
    modules = _bounded_rows(rows, columns)
    payload: dict[str, object] = {
        "state": "OBSERVED",
        "source": _redact_text(path),
        "authority": "READ_ONLY_PLATFORM_EVIDENCE",
        "modules": modules,
    }
    if module_id is not None:
        payload["requested_module_id"] = _redact_text(module_id)
        payload["found"] = bool(modules)
    return payload


def _policy_path() -> Path | None:
    for name in _AUTOSTART_POLICY_ENVS:
        value = os.environ.get(name, "").strip()
        if value:
            return Path(value)
    state = _state_path()
    if state is not None:
        candidate = state.parent / "autostart-policy.db"
        if candidate.exists():
            return candidate
    return None


def _import_autostart_module():
    for name in _AUTOSTART_MODULES:
        try:
            return importlib.import_module(name)
        except ModuleNotFoundError:
            continue
        except ImportError:
            return None
    return None


def _autostart_policy_summary() -> dict[str, object]:
    module = _import_autostart_module()
    if module is not None:
        summary = getattr(module, "canonical_policy_summary", None)
        if callable(summary):
            try:
                observed = summary()
            except Exception as exc:
                return _not_observed(
                    "AUTOSTART_POLICY_UNAVAILABLE", reason_detail=type(exc).__name__,
                )
            if isinstance(observed, dict):
                return {
                    "state": "OBSERVED",
                    "source": "AUTOSTART_MODULE",
                    "summary": {
                        _redact_text(key): _redact_text(value)
                        if isinstance(value, (str, int, bool)) or value is None
                        else type(value).__name__
                        for key, value in list(observed.items())[:32]
                    },
                }
            return _not_observed("AUTOSTART_MODULE_SUMMARY_INVALID")
    path = _policy_path()
    if path is None:
        return _not_observed("CANONICAL_AUTOSTART_POLICY_DB_ABSENT")
    try:
        from sofia.platform.state.private_file import (
            assert_no_redirected_components, assert_not_protected_state_path,
        )
        assert_not_protected_state_path(path)
        assert_no_redirected_components(path, include_leaf=True)
        if not path.is_file():
            return _not_observed("CANONICAL_AUTOSTART_POLICY_DB_ABSENT")
        db = _open_read_only(path)
    except PermissionError as exc:
        reason = (
            "PROTECTED_CORE_STATE_PATH"
            if "protected canonical Core state" in str(exc)
            else "AUTOSTART_POLICY_DB_UNREADABLE"
        )
        return _not_observed(reason)
    except (OSError, sqlite3.Error):
        return _not_observed("AUTOSTART_POLICY_DB_UNREADABLE")
    try:
        tables = _table_names(db)
        table = next((name for name in _AUTOSTART_TABLES if name in tables), None)
        if table is None:
            return _not_observed("AUTOSTART_POLICY_TABLE_ABSENT")
        total = int(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        enabled = None
        table_columns = {
            str(row[1]) for row in db.execute(f"PRAGMA table_info({table})")
        }
        if "enabled" in table_columns:
            enabled = int(db.execute(
                f"SELECT COUNT(*) FROM {table} WHERE enabled IN (1, '1', 'true')"
            ).fetchone()[0])
    except sqlite3.Error:
        return _not_observed("AUTOSTART_POLICY_DB_UNREADABLE")
    finally:
        db.close()
    return {
        "state": "OBSERVED",
        "source": _redact_text(path),
        "summary": {
            "entry_count": min(total, 100_000),
            "enabled_count": None if enabled is None else min(enabled, 100_000),
            "table": table,
        },
    }


def _reconciliation_summary() -> dict[str, object]:
    path, reason = _safe_state_path(_state_path())
    if path is None:
        return _not_observed(reason or "PLATFORM_LOCAL_STATE_NOT_CONFIGURED")
    try:
        db = _open_read_only(path)
    except (OSError, sqlite3.Error):
        return _not_observed("PLATFORM_STATE_UNREADABLE")
    try:
        if "ops_synthetic_core_operation" not in _table_names(db):
            return _not_observed("SYNTHETIC_CORE_OPERATION_TABLE_ABSENT")
        unresolved = int(db.execute(
            "SELECT COUNT(*) FROM ops_synthetic_core_operation "
            "WHERE outcome IS NULL"
        ).fetchone()[0])
    except sqlite3.Error:
        return _not_observed("PLATFORM_STATE_UNREADABLE")
    finally:
        db.close()
    return {
        "state": "OBSERVED",
        "outcome": (
            "RECONCILIATION_REQUIRED" if unresolved else "NO_UNRESOLVED_OPERATIONS"
        ),
        "unresolved_operations": min(unresolved, 100_000),
    }


def _service_status_payload() -> dict[str, object]:
    """Read-only OS service observation using reviewed existing observers.

    A trusted unit digest / SCM command pin is mandatory.  Without one this
    reports NOT_OBSERVED instead of guessing an installation or health.
    """
    if sys.platform == "win32":
        command = os.environ.get("AEGIS_PLATFORM_SERVICE_COMMAND", "").strip()
        if not command:
            return _not_observed("OS_SERVICE_PIN_NOT_CONFIGURED", source="SCM")
        try:
            from sofia.platform.ops.platform_installer_native_preflight import (
                inspect_windows_scm_service,
            )
            observation = inspect_windows_scm_service(
                expected_binary_command=command,
            ).to_payload()
        except Exception as exc:
            return _not_observed("OS_SERVICE_OBSERVATION_UNAVAILABLE",
                                 detail=type(exc).__name__, source="SCM")
        observation["state"] = "OBSERVED"
        observation["platform_ready"] = NOT_OBSERVED
        observation["core_activated"] = False
        observation["service_mutated"] = False
        return observation
    if sys.platform.startswith("linux"):
        digest = os.environ.get(
            "AEGIS_PLATFORM_SERVICE_UNIT_SHA256", "",
        ).strip()
        if not digest:
            return _not_observed("OS_SERVICE_PIN_NOT_CONFIGURED", source="systemd")
        unit_path = os.environ.get(
            "AEGIS_PLATFORM_SERVICE_UNIT_PATH",
            "/etc/systemd/system/aegis-platform.service",
        ).strip()
        try:
            from sofia.platform.ops.platform_installer_native_preflight import (
                inspect_debian_systemd_service,
            )
            observation = inspect_debian_systemd_service(
                expected_unit_sha256=digest, unit_path=unit_path,
            ).to_payload()
        except Exception as exc:
            return _not_observed("OS_SERVICE_OBSERVATION_UNAVAILABLE",
                                 detail=type(exc).__name__, source="systemd")
        observation["state"] = "OBSERVED"
        observation["platform_ready"] = NOT_OBSERVED
        observation["core_activated"] = False
        observation["service_mutated"] = False
        return observation
    return _not_observed("OS_SERVICE_OBSERVATION_UNSUPPORTED_PLATFORM")


def _zero_core_payload() -> dict[str, object]:
    roles = _roles_payload()
    configured = roles.get("roles", [])
    return {
        "valid": True,
        "core_required": False,
        "core_host_configured": (
            isinstance(configured, list) and "CORE_HOST" in configured
        ),
        "reason": "Platform startup and management are independent of Core activation",
    }


def _startup_payload() -> dict[str, object]:
    identity = _identity_payload()
    state_path = _state_path()
    reconciliation = _reconciliation_summary()
    blockers: list[str] = []
    if identity.get("state") == "NOT_CONFIGURED":
        blockers.append("PLATFORM_IDENTITY_NOT_CONFIGURED")
    if state_path is None:
        blockers.append("PLATFORM_LOCAL_STATE_NOT_CONFIGURED")
    if reconciliation.get("outcome") == "RECONCILIATION_REQUIRED":
        blockers.append("RECONCILIATION_REQUIRED")
    return {
        "schema": f"{CLI_SCHEMA}.startup.v1",
        "zero_core": _zero_core_payload(),
        "autostart_policy": _autostart_policy_summary(),
        "reconciliation": reconciliation,
        "blockers": blockers,
    }


def _status_payload() -> dict[str, object]:
    role_configuration = _roles_payload()
    configured_roles = role_configuration.get("roles")
    return {
        "schema": f"{CLI_SCHEMA}.status.v1",
        "roles": (
            list(configured_roles)
            if isinstance(configured_roles, list) else []
        ),
        "role_configuration": role_configuration,
        "zero_core": _zero_core_payload(),
        "platform_identity": _identity_payload(),
        "service_endpoint": _service_endpoint_payload(),
        "management": {
            "state": NOT_OBSERVED,
            "reason": "AUTHENTICATED_MANAGEMENT_CLIENT_NOT_IMPLEMENTED",
        },
    }


def _chat_payload() -> dict[str, object]:
    binding_state: dict[str, object] = {"state": "NOT_CONFIGURED"}
    store_path = os.environ.get("SOFIA_CORE_LINK_BINDING_STORE", "").strip()
    if store_path:
        try:
            from sofia.platform.core_link import CoreLinkBindingStore
            snapshot = CoreLinkBindingStore(Path(store_path)).load()
            selected = snapshot.selected()
        except Exception as exc:
            binding_state = {
                "state": "UNAVAILABLE",
                "reason": type(exc).__name__,
            }
        else:
            binding_state = {
                "state": "READABLE_NOT_AUTHORITY",
                "store_revision": snapshot.revision,
                "selected": (
                    None if selected is None else selected.redacted_status()
                ),
            }
    return {
        "schema": f"{CLI_SCHEMA}.chat.v1",
        "binding": binding_state,
        "transport": {"state": NOT_OBSERVED},
        "conversation": {"state": NOT_OBSERVED},
    }


def _diagnostics_payload() -> dict[str, object]:
    core = _core_bindings()
    module = _module_records()
    service = _service_status_payload()
    startup = _startup_payload()
    autostart = startup.get("autostart_policy")
    if isinstance(autostart, dict):
        autostart.pop("source", None)
    payload: dict[str, object] = {
        "schema": f"{CLI_SCHEMA}.diagnostics.v1",
        "roles": _roles_payload(),
        "platform_identity": _identity_payload(),
        "service_endpoint": _service_endpoint_payload(redact_value=True),
        "management": {
            "state": NOT_OBSERVED,
            "reason": "AUTHENTICATED_MANAGEMENT_CLIENT_NOT_IMPLEMENTED",
        },
        "service": {
            "state": service.get("state", NOT_OBSERVED),
            "reason": service.get("reason"),
            "process_state": service.get("process_state"),
            "health": service.get("health"),
        },
        "core": {
            "state": core.get("state", NOT_OBSERVED),
            "binding_count": len(core.get("bindings", [])),
            "reason": core.get("reason"),
        },
        "module": {
            "state": module.get("state", NOT_OBSERVED),
            "module_count": len(module.get("modules", [])),
            "reason": module.get("reason"),
        },
        "startup": startup,
        "redaction": {
            "secrets_included": False,
            "maximum_bytes": _MAX_DIAGNOSTIC_BYTES,
        },
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    if len(encoded.encode("utf-8")) > _MAX_DIAGNOSTIC_BYTES:
        return {
            "schema": f"{CLI_SCHEMA}.diagnostics.v1",
            "state": NOT_OBSERVED,
            "reason": "DIAGNOSTIC_SUMMARY_EXCEEDS_BOUND",
            "management": {
                "state": NOT_OBSERVED,
                "reason": "AUTHENTICATED_MANAGEMENT_CLIENT_NOT_IMPLEMENTED",
            },
            "redaction": {
                "secrets_included": False,
                "maximum_bytes": _MAX_DIAGNOSTIC_BYTES,
            },
        }
    return payload


def _find_executable(names: Sequence[str]) -> str | None:
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    return None


def _launch_packaged(
    names: Sequence[str], *, command: str, missing_code: str, as_json: bool,
) -> int:
    executable = _find_executable(names)
    if executable is None:
        return _refuse(
            missing_code,
            f"packaged {command} executable is not installed or on PATH",
            command=command,
            as_json=as_json,
        )
    try:
        subprocess.Popen([executable], close_fds=True)
    except OSError as exc:
        return _refuse(
            missing_code,
            f"packaged {command} executable could not be launched: {type(exc).__name__}",
            command=command,
            as_json=as_json,
        )
    payload = {
        "schema": f"{CLI_SCHEMA}.launch.v1",
        "command": command,
        "state": "LAUNCHED",
        "executable": _redact_text(executable),
        "executed": True,
        "authority_granted": False,
    }
    _emit(payload, as_json=as_json)
    return EXIT_OK


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aegis",
        description=(
            "Read-only local Platform client. Mutations require the "
            "authenticated Platform management authority."
        ),
    )
    parser.add_argument(
        "--json", action="store_true", dest="global_json",
        help="emit machine-readable JSON after the subcommand",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    status = subparsers.add_parser("status", help="show local Platform status")
    status.add_argument("--json", action="store_true")

    startup = subparsers.add_parser(
        "startup", help="show startup diagnostics without starting anything",
    )
    startup.add_argument("--json", action="store_true")

    service = subparsers.add_parser("service", help="observe the OS service")
    service_sub = service.add_subparsers(dest="service_command", required=True)
    service_status = service_sub.add_parser("status", help="read-only service observation")
    service_status.add_argument("--json", action="store_true")
    for operation in ("start", "stop", "restart"):
        mutation = service_sub.add_parser(operation, help=f"refuse {operation} without owner approval")
        mutation.add_argument("--json", action="store_true")

    core = subparsers.add_parser("core", help="observe synthetic Core bindings")
    core_sub = core.add_subparsers(dest="core_command", required=True)
    core_list = core_sub.add_parser("list", help="list durable Core bindings")
    core_list.add_argument("--json", action="store_true")
    core_status = core_sub.add_parser("status", help="read one durable Core binding")
    core_status.add_argument("core_id", nargs="?")
    core_status.add_argument("--json", action="store_true")
    for operation in sorted(_CORE_MUTATIONS):
        mutation = core_sub.add_parser(operation, help=f"refuse {operation} without management approval")
        mutation.add_argument("core_id", nargs="?")
        mutation.add_argument("--json", action="store_true")

    module = subparsers.add_parser("module", help="observe canonical module records")
    module_sub = module.add_subparsers(dest="module_command", required=True)
    module_list = module_sub.add_parser("list", help="list canonical module records")
    module_list.add_argument("--json", action="store_true")
    module_status = module_sub.add_parser("status", help="read one canonical module record")
    module_status.add_argument("module_id", nargs="?")
    module_status.add_argument("--json", action="store_true")
    for operation in sorted(_MODULE_MUTATIONS):
        mutation = module_sub.add_parser(operation, help=f"refuse {operation} without management approval")
        mutation.add_argument("module_id", nargs="?")
        mutation.add_argument("--json", action="store_true")

    chat = subparsers.add_parser("chat", help="refuse chat without a real Core Link")
    chat.add_argument("message", nargs="?")
    chat.add_argument("--json", action="store_true")

    diagnostics = subparsers.add_parser(
        "diagnostics", help="bounded redacted local diagnostics",
    )
    diagnostics.add_argument("--json", action="store_true")

    gui = subparsers.add_parser("gui", help="launch the packaged GUI when present")
    gui.add_argument("--json", action="store_true")
    tui = subparsers.add_parser("tui", help="launch the packaged TUI when present")
    tui.add_argument("--json", action="store_true")
    return parser


def _as_json(args: argparse.Namespace) -> bool:
    return bool(getattr(args, "json", False) or getattr(args, "global_json", False))


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    as_json = _as_json(args)

    if args.command == "status":
        _emit(_status_payload(), as_json=as_json)
        return EXIT_OK
    if args.command == "startup":
        _emit(_startup_payload(), as_json=as_json)
        return EXIT_OK
    if args.command == "diagnostics":
        _emit(_diagnostics_payload(), as_json=as_json)
        return EXIT_OK
    if args.command == "service":
        if args.service_command == "status":
            _emit(_service_status_payload(), as_json=as_json)
            return EXIT_OK
        return _refuse(
            OWNER_APPROVAL_REQUIRED,
            "OS service lifecycle changes require the authenticated service owner workflow",
            command=f"service {args.service_command}",
            as_json=as_json,
        )
    if args.command == "core":
        if args.core_command == "list":
            _emit(_core_bindings(), as_json=as_json)
            return EXIT_OK
        if args.core_command == "status":
            _emit(
                _core_bindings(getattr(args, "core_id", None)),
                as_json=as_json,
            )
            return EXIT_OK
        return _refuse(
            MANAGEMENT_APPROVAL_REQUIRED,
            "Core lifecycle changes require authenticated Platform management approval",
            command=f"core {args.core_command}",
            as_json=as_json,
        )
    if args.command == "module":
        if args.module_command == "list":
            _emit(_module_records(), as_json=as_json)
            return EXIT_OK
        if args.module_command == "status":
            _emit(
                _module_records(getattr(args, "module_id", None)),
                as_json=as_json,
            )
            return EXIT_OK
        return _refuse(
            MANAGEMENT_APPROVAL_REQUIRED,
            "module lifecycle changes require authenticated Platform management approval",
            command=f"module {args.module_command}",
            as_json=as_json,
        )
    if args.command == "chat":
        return _refuse(
            AUTHENTICATED_CORE_BINDING_REQUIRED,
            "no authenticated Core Link transport is configured; no conversation was created",
            command="chat",
            as_json=as_json,
            observation=_chat_payload(),
        )
    if args.command == "gui":
        return _launch_packaged(
            _GUI_EXECUTABLES, command="gui",
            missing_code=AEGIS_GUI_NOT_AVAILABLE, as_json=as_json,
        )
    if args.command == "tui":
        return _launch_packaged(
            _TUI_EXECUTABLES, command="tui",
            missing_code=AEGIS_TUI_NOT_AVAILABLE, as_json=as_json,
        )
    parser.error("unhandled aegis command")
    return EXIT_USAGE


if __name__ == "__main__":
    raise SystemExit(main())
