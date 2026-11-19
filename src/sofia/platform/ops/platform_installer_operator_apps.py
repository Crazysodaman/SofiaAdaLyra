"""Owner-approved installed-host operator application launchers.

This module builds a deterministic launcher plan from exact installed paths and
performs only the reviewed launcher/PATH/shortcut effects named by that plan.
It is not an installation authority: every mutating call consumes an existing
one-use SAFE owner approval whose parameters include the plan digest.

Generated launchers carry an ownership marker plus the exact source and target
hashes used to create them. Foreign launchers are never adopted or overwritten.
Protected Platform identity/state and Core data are never touched.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import stat
from typing import Protocol
from uuid import uuid4

from sofia.platform.ops.platform_installation import (
    PlatformInstallationDenied, PlatformInstallationStore,
)
from sofia.platform.run.process_lock import StateProcessLock
from sofia.platform.safe.execution_approval import (
    ExecutionApprovalVerifier, execution_fingerprint,
)
from sofia.platform.safe.operator_stop import OperatorStopStore
from sofia.platform.state.private_file import (
    assert_no_redirected_components, atomic_write_private_text,
)
from sofia.sdk.platform_release import PlatformReleaseTarget

OPERATOR_APPS_CAPABILITY = "platform.operator_apps.apply"
PLAN_SCHEMA = "aegis.platform.operator-apps-plan.v1"
RECEIPT_SCHEMA = "aegis.platform.operator-apps-receipt.v1"
STATE_SCHEMA = "aegis.platform.operator-apps-state.v1"
SHORTCUT_SCHEMA = "aegis.platform.operator-app-shortcut.v1"
OWNERSHIP_MARKER = "aegis-operator-app-owned-v1"
_RECEIPT_FILE = "operator-apps-receipt.json"
_STATE_FILE = "operator-apps-state.json"
_OPERATIONS = frozenset(("install", "update", "repair", "uninstall"))
_BIN_NAMES = frozenset((
    "aegis", "aegis.cmd", "aegis.bat", "aegis.ps1", "aegis.exe",
))
_MAX_FILE_BYTES = 4 * 1024**2


class OperatorAppsDenied(PlatformInstallationDenied):
    """The launcher plan or ownership contract refuses this operation."""


class OperatorAppsApprovalRequired(OperatorAppsDenied):
    def __init__(self, fingerprint: str, *, operation: str):
        super().__init__("operator application launcher owner approval required")
        self.fingerprint = fingerprint
        self.operation = operation


@dataclass(frozen=True, slots=True)
class OperatorAppsConfiguration:
    """Exact installed paths and reviewed scope for one launcher plan."""

    target: PlatformReleaseTarget
    runtime_python: Path
    code_directory: Path
    bin_directory: Path
    approved_roots: tuple[Path, ...]
    gui_executable: Path | None = None
    tui_executable: Path | None = None
    start_menu_directory: Path | None = None
    desktop_directory: Path | None = None
    global_bin_directory: Path | None = None
    protected_paths: tuple[Path, ...] = ()
    path_scope: str = "user"
    include_powershell: bool = False
    include_desktop_shortcut: bool = False
    start_at_login: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.target, PlatformReleaseTarget):
            raise TypeError("typed exact release target required")
        if self.path_scope not in ("user", "machine"):
            raise ValueError("path scope must be user or machine")
        if type(self.include_powershell) is not bool:
            raise TypeError("include_powershell must be boolean")
        if type(self.include_desktop_shortcut) is not bool:
            raise TypeError("include_desktop_shortcut must be boolean")
        if type(self.start_at_login) is not bool:
            raise TypeError("start_at_login must be boolean")
        if not self.approved_roots:
            raise OperatorAppsDenied("at least one approved launcher root is required")


class PathAdapter(Protocol):
    """Caller-supplied PATH storage. Never used before owner approval."""

    def read(self) -> str: ...

    def write(self, value: str) -> None: ...


@dataclass
class InMemoryPathAdapter:
    value: str = ""

    def read(self) -> str:
        return self.value

    def write(self, value: str) -> None:
        self.value = value


class WindowsRegistryPathAdapter:
    """Per-user or machine Windows PATH storage behind the same abstraction."""

    def __init__(self, *, scope: str = "user") -> None:
        if scope not in ("user", "machine"):
            raise ValueError("Windows PATH scope must be user or machine")
        self.scope = scope

    def _key(self):
        import winreg

        if self.scope == "user":
            return winreg.HKEY_CURRENT_USER, r"Environment"
        return (
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
        )

    def read(self) -> str:
        import winreg

        root, name = self._key()
        with winreg.OpenKey(root, name, 0, winreg.KEY_READ) as key:
            try:
                value, _kind = winreg.QueryValueEx(key, "Path")
            except FileNotFoundError:
                return ""
        return str(value)

    def write(self, value: str) -> None:
        import winreg

        root, name = self._key()
        with winreg.OpenKey(root, name, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, value)


@dataclass(frozen=True, slots=True)
class ShortcutSpec:
    path: Path
    sidecar: Path
    target: Path
    arguments: str
    working_directory: Path
    description: str
    source_sha256: str
    target_sha256: str


class ShortcutAdapter(Protocol):
    """Testable adapter for the OS shortcut mechanism."""

    def create(self, spec: ShortcutSpec) -> None: ...

    def remove(self, spec: ShortcutSpec) -> None: ...


class StartupAdapter(Protocol):
    """Testable adapter for optional per-user sign-in startup."""

    def enable(self, *, command: str) -> bool: ...

    def disable(self) -> bool: ...


class WindowsRunKeyStartupAdapter:
    """Write only the reviewed per-user Aegis startup value in HKCU Run."""

    value_name = "AegisPlatformUI"

    def enable(self, *, command: str) -> bool:
        if os.name != "nt":
            raise OperatorAppsDenied("start-at-login is supported only on Windows")
        if not isinstance(command, str) or not command.strip() or "\x00" in command:
            raise OperatorAppsDenied("invalid startup command")
        import winreg

        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_READ | winreg.KEY_SET_VALUE,
        ) as key:
            try:
                current, _kind = winreg.QueryValueEx(key, self.value_name)
            except FileNotFoundError:
                current = None
            if current == command:
                return False
            winreg.SetValueEx(key, self.value_name, 0, winreg.REG_SZ, command)
            return True

    def disable(self) -> bool:
        if os.name != "nt":
            return False
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            try:
                winreg.DeleteValue(key, self.value_name)
            except FileNotFoundError:
                return False
            return True


class PyWin32ShortcutAdapter:
    """Windows .lnk adapter using pywin32 COM only when explicitly invoked."""

    def create(self, spec: ShortcutSpec) -> None:
        import win32com.client  # type: ignore[import-not-found]

        shell = win32com.client.Dispatch("WScript.Shell")
        link = shell.CreateShortCut(str(spec.path))
        link.TargetPath = str(spec.target)
        link.Arguments = spec.arguments
        link.WorkingDirectory = str(spec.working_directory)
        link.Description = spec.description
        link.Save()

    def remove(self, spec: ShortcutSpec) -> None:
        spec.path.unlink(missing_ok=True)


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _absolute(path: Path | str, name: str) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        raise OperatorAppsDenied(f"{name} must be an absolute path")
    resolved = Path(os.path.abspath(str(candidate)))
    assert_no_redirected_components(resolved, include_leaf=True)
    return resolved


def _within(path: Path, root: Path) -> bool:
    left = os.path.normcase(os.path.abspath(str(path)))
    right = os.path.normcase(os.path.abspath(str(root)))
    try:
        return os.path.commonpath((left, right)) == right
    except ValueError:
        return False


def _assert_approved(path: Path, roots: tuple[Path, ...]) -> None:
    if not any(_within(path, root) for root in roots):
        raise OperatorAppsDenied("launcher path is outside every approved root")


def _assert_not_protected(path: Path, protected: tuple[Path, ...]) -> None:
    lowered = path.name.lower()
    if lowered == "sofia.db" or lowered.startswith("sofia.db-"):
        raise OperatorAppsDenied("protected Core state is never an operator app path")
    for item in protected:
        if path == item or item in path.parents:
            raise OperatorAppsDenied("protected identity/state path overlaps launcher plan")


def _sha256_file(path: Path) -> str:
    assert_no_redirected_components(path, include_leaf=True)
    info = path.stat(follow_symlinks=False)
    if not stat.S_ISREG(info.st_mode) or not 1 <= info.st_size <= _MAX_FILE_BYTES:
        raise OperatorAppsDenied("source application is not a bounded regular file")
    digest = sha256()
    descriptor = os.open(
        path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0),
    )
    try:
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            for block in iter(lambda: stream.read(65_536), b""):
                digest.update(block)
    finally:
        os.close(descriptor)
    return digest.hexdigest()


def _require_directory(path: Path, name: str) -> Path:
    if not path.is_dir() or path.is_symlink():
        raise OperatorAppsDenied(f"{name} must be an existing non-redirected directory")
    return path


def _require_file(path: Path, name: str) -> Path:
    if not path.is_file() or path.is_symlink():
        raise OperatorAppsDenied(f"{name} must be an existing non-redirected file")
    return path


def _ownership_header(style: str, source_sha256: str, target_sha256: str) -> str:
    if style == "cmd":
        newline = "\r\n"
        return (
            f"REM AEGIS_OPERATOR_APP_OWNER={OWNERSHIP_MARKER}{newline}"
            f"REM AEGIS_SOURCE_SHA256={source_sha256}{newline}"
            f"REM AEGIS_TARGET_SHA256={target_sha256}{newline}"
        )
    if style == "desktop":
        return (
            f"X-Aegis-Ownership={OWNERSHIP_MARKER}\n"
            f"X-Aegis-Source-Sha256={source_sha256}\n"
            f"X-Aegis-Target-Sha256={target_sha256}\n"
        )
    return (
        f"# AEGIS_OPERATOR_APP_OWNER={OWNERSHIP_MARKER}\n"
        f"# AEGIS_SOURCE_SHA256={source_sha256}\n"
        f"# AEGIS_TARGET_SHA256={target_sha256}\n"
    )


def _render(style: str, source_sha256: str, body: str, *,
            prefix: str = "") -> tuple[str, str]:
    target_sha256 = sha256(body.encode("utf-8")).hexdigest()
    return prefix + _ownership_header(style, source_sha256, target_sha256) + body, target_sha256


def _normalize_roots(values) -> tuple[Path, ...]:
    roots = tuple(_absolute(item, "approved root") for item in values)
    if not roots:
        raise OperatorAppsDenied("at least one approved launcher root is required")
    return roots


def _reject_windows_unsafe(value: str, name: str) -> None:
    if any(char in value for char in ('"', "%", "\r", "\n", "\x00")):
        raise OperatorAppsDenied(f"{name} contains characters unsafe for a launcher")


def _windows_shim(python: Path, code: Path, source_sha256: str) -> tuple[str, str]:
    _reject_windows_unsafe(str(python), "runtime Python")
    _reject_windows_unsafe(str(code), "code directory")
    body = (
        "@echo off\r\n"
        "setlocal\r\n"
        f'"{python}" -E -s -P -B -c '
        '"import sys; sys.path.insert(0, sys.argv[1]); '
        'from sofia.platform.cli import main; sys.exit(main(sys.argv[2:]))" '
        f'"{code}" %*\r\n'
        "exit /b %ERRORLEVEL%\r\n"
    )
    return _render("cmd", source_sha256, body)


def _powershell_shim(python: Path, code: Path, source_sha256: str) -> tuple[str, str]:
    _reject_windows_unsafe(str(python), "runtime Python")
    _reject_windows_unsafe(str(code), "code directory")
    body = (
        f'& "{python}" -E -s -P -B -c '
        "'import sys; sys.path.insert(0, sys.argv[1]); "
        "from sofia.platform.cli import main; sys.exit(main(sys.argv[2:]))' "
        f'"{code}" @args\n'
        "exit $LASTEXITCODE\n"
    )
    return _render("hash", source_sha256, body)


def _shell_quote(value: str) -> str:
    if "\x00" in value or "\n" in value or "\r" in value:
        raise OperatorAppsDenied("launcher path contains control characters")
    return "'" + value.replace("'", "'\"'\"'") + "'"


def _posix_script(python: Path, code: Path, source_sha256: str) -> tuple[str, str]:
    body = (
        f"exec {_shell_quote(str(python))} -E -s -P -B -c "
        "'import sys; sys.path.insert(0, sys.argv[1]); "
        "from sofia.platform.cli import main; sys.exit(main(sys.argv[2:]))' "
        f"{_shell_quote(str(code))} \"$@\"\n"
    )
    return _render("hash", source_sha256, body, prefix="#!/bin/sh\n")


def _desktop_entry(launcher: Path, source_sha256: str) -> tuple[str, str]:
    escaped = str(launcher).replace("\\", "\\\\").replace('"', '\\"')
    body = (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Aegis Platform\n"
        'Comment=Open the installed Aegis Platform\n'
        f'Exec="{escaped}" gui\n'
        "Terminal=false\n"
        "Categories=Utility;\n"
        "StartupNotify=true\n"
    )
    return _render("desktop", source_sha256, body)


def _shortcut_sidecar(spec: ShortcutSpec, link_sha256: str | None = None) -> str:
    return _canonical_json({
        "schema": SHORTCUT_SCHEMA,
        "ownership_marker": OWNERSHIP_MARKER,
        "path": str(spec.path),
        "target": str(spec.target),
        "arguments": spec.arguments,
        "working_directory": str(spec.working_directory),
        "source_sha256": spec.source_sha256,
        "target_sha256": spec.target_sha256,
        "link_sha256": link_sha256,
    }) + "\n"


def _shortcut(path: Path, launcher: Path, launcher_sha256: str,
             *, arguments: str = "gui") -> ShortcutSpec:
    sidecar = path.with_name(path.name + ".aegis-owner.json")
    spec_sha256 = sha256(_canonical_json({
        "path": str(path), "target": str(launcher), "arguments": arguments,
        "working_directory": str(launcher.parent),
    }).encode("utf-8")).hexdigest()
    return ShortcutSpec(
        path=path, sidecar=sidecar, target=launcher, arguments=arguments,
        working_directory=launcher.parent,
        description="Open the installed Aegis Platform",
        source_sha256=launcher_sha256, target_sha256=spec_sha256,
    )


def _plan_inputs(config: OperatorAppsConfiguration) -> dict[str, object]:
    def value(path: Path | None) -> str | None:
        return None if path is None else str(path)

    return {
        "target": config.target.value,
        "runtime_python": str(config.runtime_python),
        "code_directory": str(config.code_directory),
        "bin_directory": str(config.bin_directory),
        "gui_executable": value(config.gui_executable),
        "tui_executable": value(config.tui_executable),
        "start_menu_directory": value(config.start_menu_directory),
        "desktop_directory": value(config.desktop_directory),
        "global_bin_directory": value(config.global_bin_directory),
        "approved_roots": [str(item) for item in config.approved_roots],
        "protected_paths": [str(item) for item in config.protected_paths],
        "path_scope": config.path_scope,
        "include_powershell": config.include_powershell,
        "include_desktop_shortcut": config.include_desktop_shortcut,
        "start_at_login": config.start_at_login,
    }


def build_operator_apps_plan(config: OperatorAppsConfiguration) -> dict[str, object]:
    """Return a deterministic, non-executable launcher plan."""
    if not isinstance(config, OperatorAppsConfiguration):
        raise TypeError("OperatorAppsConfiguration required")
    roots = _normalize_roots(config.approved_roots)
    protected = tuple(
        _absolute(item, "protected path") for item in config.protected_paths
    )
    python = _absolute(config.runtime_python, "runtime Python")
    code = _absolute(config.code_directory, "code directory")
    bin_dir = _absolute(config.bin_directory, "Aegis bin directory")
    _require_file(python, "runtime Python")
    _require_directory(code, "code directory")
    for path, name in (
        (python, "runtime Python"), (code, "code directory"),
        (bin_dir, "Aegis bin directory"),
    ):
        _assert_approved(path, roots)
        _assert_not_protected(path, protected)
    source_sha256 = _sha256_file(python)

    gui = None if config.gui_executable is None else _absolute(
        config.gui_executable, "GUI executable")
    tui = None if config.tui_executable is None else _absolute(
        config.tui_executable, "TUI executable")
    for path, name in ((gui, "GUI executable"), (tui, "TUI executable")):
        if path is None:
            continue
        _require_file(path, name)
        _assert_approved(path, roots)
        _assert_not_protected(path, protected)

    files: list[dict[str, object]] = []
    planned_paths: set[Path] = set()

    def add_file(path: Path, kind: str, content: str, target_sha256: str,
                 mode: int, *, source: str | None = None) -> None:
        _assert_approved(path, roots)
        _assert_not_protected(path, protected)
        if path in planned_paths:
            raise OperatorAppsDenied("duplicate launcher target in plan")
        planned_paths.add(path)
        files.append({
            "kind": kind, "path": str(path), "mode": f"{mode:04o}",
            "source_sha256": source if source is not None else source_sha256,
            "target_sha256": target_sha256,
            "content_sha256": sha256(content.encode("utf-8")).hexdigest(),
            "ownership_marker": OWNERSHIP_MARKER,
        })

    launcher_arguments = "gui" if gui is not None else ("tui" if tui is not None else None)
    shortcuts: list[ShortcutSpec] = []
    if config.target is PlatformReleaseTarget.WINDOWS_X86_64:
        content, digest = _windows_shim(python, code, source_sha256)
        add_file(bin_dir / "aegis.cmd", "windows-cmd-shim", content, digest, 0o644)
        launcher = bin_dir / "aegis.cmd"
        launcher_sha256 = sha256(content.encode("utf-8")).hexdigest()
        if config.include_powershell:
            content, digest = _powershell_shim(python, code, source_sha256)
            add_file(bin_dir / "aegis.ps1", "windows-powershell-shim", content, digest, 0o644)
        if config.start_menu_directory is not None:
            start = _absolute(config.start_menu_directory, "Start Menu directory")
            _assert_approved(start, roots)
            if launcher_arguments is None:
                raise OperatorAppsDenied("Start Menu shortcut requires a GUI or TUI executable")
            shortcuts.append(_shortcut(
                start / "Aegis Platform.lnk", launcher, launcher_sha256,
                arguments=launcher_arguments,
            ))
        if config.include_desktop_shortcut:
            if config.desktop_directory is None:
                raise OperatorAppsDenied("desktop shortcut requires a desktop directory")
            desktop = _absolute(config.desktop_directory, "desktop directory")
            _assert_approved(desktop, roots)
            if launcher_arguments is None:
                raise OperatorAppsDenied("desktop shortcut requires a GUI or TUI executable")
            shortcuts.append(_shortcut(
                desktop / "Aegis Platform.lnk", launcher, launcher_sha256,
                arguments=launcher_arguments,
            ))
    else:
        content, digest = _posix_script(python, code, source_sha256)
        primary = bin_dir / "aegis"
        add_file(primary, "posix-script", content, digest, 0o755)
        launcher = primary
        launcher_sha256 = sha256(content.encode("utf-8")).hexdigest()
        if config.global_bin_directory is not None:
            global_bin = _absolute(config.global_bin_directory, "global bin directory")
            _assert_approved(global_bin, roots)
            wrapper, digest = _render(
                "hash", launcher_sha256,
                f"exec {_shell_quote(str(primary))} \"$@\"\n",
                prefix="#!/bin/sh\n",
            )
            add_file(global_bin / "aegis", "posix-wrapper", wrapper, digest, 0o755,
                     source=launcher_sha256)
        if config.desktop_directory is not None:
            applications = _absolute(config.desktop_directory, "desktop directory")
            _assert_approved(applications, roots)
            if gui is None:
                raise OperatorAppsDenied("desktop entry requires a GUI executable")
            desktop, digest = _desktop_entry(launcher, launcher_sha256)
            add_file(applications / "aegis-platform.desktop", "desktop-entry",
                     desktop, digest, 0o644, source=launcher_sha256)

    startup_command = (
        None if (config.target is not PlatformReleaseTarget.WINDOWS_X86_64
                 or launcher_arguments is None)
        else f'"{launcher}" {launcher_arguments}'
    )
    files_by_path = {Path(item["path"]) for item in files}
    for directory in {path.parent for path in files_by_path}:
        for name in _BIN_NAMES:
            candidate = directory / name
            if candidate in files_by_path:
                continue
            if candidate.exists() or candidate.is_symlink():
                raise OperatorAppsDenied(
                    "a foreign or competing aegis launcher already occupies the target"
                )

    plan: dict[str, object] = {
        "schema": PLAN_SCHEMA,
        "configuration": _plan_inputs(config),
        "target": config.target.value,
        "path": {
            "entry": str(bin_dir),
            "scope": config.path_scope,
            "action": (
                "ENSURE"
                if config.target is PlatformReleaseTarget.WINDOWS_X86_64
                else "NOT_APPLICABLE"
            ),
        },
        "applications": {
            "gui": None if gui is None else {
                "path": str(gui), "sha256": _sha256_file(gui),
            },
            "tui": None if tui is None else {
                "path": str(tui), "sha256": _sha256_file(tui),
            },
        },
        "files": sorted(files, key=lambda item: str(item["path"])),
        "shortcuts": [{
            "path": str(item.path), "sidecar": str(item.sidecar),
            "target": str(item.target), "arguments": item.arguments,
            "working_directory": str(item.working_directory),
            "description": item.description,
            "source_sha256": item.source_sha256,
            "target_sha256": item.target_sha256,
        } for item in sorted(shortcuts, key=lambda item: str(item.path))],
        "startup": {
            "requested": config.start_at_login,
            "supported": startup_command is not None,
            "command": startup_command,
            "action": "ENSURE" if config.start_at_login else "NO_CHANGE",
        },
        "executed": False,
        "owner_approved": False,
        "core_activated": False,
    }
    plan["plan_digest"] = sha256(_canonical_json(plan).encode("utf-8")).hexdigest()
    return plan


def _parameters(operation: str, plan: dict[str, object]) -> dict[str, object]:
    return {
        "operation": operation,
        "plan_digest": plan["plan_digest"],
        "target": plan["target"],
        "bin_directory": plan["path"]["entry"],
        "path_scope": plan["path"]["scope"],
        "file_count": len(plan["files"]),
        "shortcut_count": len(plan["shortcuts"]),
        "startup_requested": plan["startup"]["requested"],
    }


def operator_apps_request(
    operation: str, config: OperatorAppsConfiguration,
) -> dict[str, object]:
    if operation not in _OPERATIONS:
        raise OperatorAppsDenied("unsupported operator application operation")
    plan = build_operator_apps_plan(config)
    parameters = _parameters(operation, plan)
    return {
        "schema": "aegis.platform.operator-apps-request.v1",
        "capability": OPERATOR_APPS_CAPABILITY,
        "operation": operation,
        "parameters": parameters,
        "plan": plan,
        "fingerprint": execution_fingerprint(OPERATOR_APPS_CAPABILITY, parameters),
        "authorized": False,
        "executed": False,
    }


def _split_path(value: str, *, windows: bool) -> list[str]:
    separator = ";" if windows else ":"
    return value.split(separator) if value else []


def _path_entry_present(value: str, entry: str, *, windows: bool) -> bool:
    normalized = os.path.normcase(entry.rstrip("\\/")) if windows else entry.rstrip("/")
    for item in _split_path(value, windows=windows):
        candidate = item.strip().strip('"')
        if not candidate:
            continue
        candidate = os.path.normcase(candidate.rstrip("\\/")) if windows else candidate.rstrip("/")
        if candidate == normalized:
            return True
    return False


def _add_path(value: str, entry: str, *, windows: bool) -> tuple[str, bool]:
    if _path_entry_present(value, entry, windows=windows):
        return value, False
    separator = ";" if windows else ":"
    if not value:
        return entry, True
    return value.rstrip(separator) + separator + entry, True


def _remove_path(value: str, entry: str, *, windows: bool) -> tuple[str, bool]:
    normalized = os.path.normcase(entry.rstrip("\\/")) if windows else entry.rstrip("/")
    kept: list[str] = []
    removed = False
    for item in _split_path(value, windows=windows):
        candidate = item.strip().strip('"')
        if candidate:
            compare = (os.path.normcase(candidate.rstrip("\\/")) if windows
                       else candidate.rstrip("/"))
            if compare == normalized:
                removed = True
                continue
        kept.append(item)
    separator = ";" if windows else ":"
    return separator.join(kept), removed


def _read_bounded_text(path: Path) -> str:
    assert_no_redirected_components(path, include_leaf=True)
    info = path.stat(follow_symlinks=False)
    if not stat.S_ISREG(info.st_mode) or info.st_size > _MAX_FILE_BYTES:
        raise OperatorAppsDenied("operator app file is not a bounded regular file")
    return path.read_text(encoding="utf-8")


def _is_owned_text(content: str) -> bool:
    return OWNERSHIP_MARKER in content


def _owned_bytes(data: bytes) -> bool:
    return OWNERSHIP_MARKER.encode("utf-8") in data


def _ensure_parent(path: Path, roots: tuple[Path, ...]) -> None:
    _assert_approved(path, roots)
    assert_no_redirected_components(path.parent, include_leaf=True)
    missing = []
    cursor = path.parent
    while not cursor.exists():
        missing.append(cursor)
        cursor = cursor.parent
    for directory in reversed(missing):
        _assert_approved(directory, roots)
        directory.mkdir(mode=0o755, exist_ok=True)
        assert_no_redirected_components(directory, include_leaf=True)


def _publish_file(path: Path, content: str, mode: int, roots: tuple[Path, ...]) -> bool:
    _ensure_parent(path, roots)
    data = content.encode("utf-8")
    if path.exists() or path.is_symlink():
        if path.is_symlink():
            raise OperatorAppsDenied("refuse to replace a redirected launcher target")
        existing = path.read_bytes()
        if existing == data:
            if os.name != "nt":
                path.chmod(mode)
            return False
        if not _owned_bytes(existing):
            raise OperatorAppsDenied("refuse to overwrite a foreign launcher file")
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    descriptor = os.open(
        temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if os.name != "nt":
            temporary.chmod(mode)
        os.replace(temporary, path)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if temporary.exists():
            temporary.unlink(missing_ok=True)
    return True


def _remove_file(path: Path) -> bool:
    if not (path.exists() or path.is_symlink()):
        return False
    if path.is_symlink():
        raise OperatorAppsDenied("refuse to remove a redirected launcher target")
    data = path.read_bytes()
    if not _owned_bytes(data):
        raise OperatorAppsDenied("refuse to remove a foreign launcher file")
    path.unlink()
    return True


def _shortcut_from_plan(item: dict[str, object]) -> ShortcutSpec:
    return ShortcutSpec(
        path=Path(str(item["path"])), sidecar=Path(str(item["sidecar"])),
        target=Path(str(item["target"])), arguments=str(item["arguments"]),
        working_directory=Path(str(item["working_directory"])),
        description=str(item["description"]),
        source_sha256=str(item["source_sha256"]),
        target_sha256=str(item["target_sha256"]),
    )


def _shortcut_document(spec: ShortcutSpec) -> dict[str, object] | None:
    try:
        if spec.sidecar.is_symlink() or not spec.sidecar.is_file():
            return None
        document = json.loads(_read_bounded_text(spec.sidecar))
    except (OSError, ValueError, TypeError):
        return None
    if (
        type(document) is not dict
        or document.get("schema") != SHORTCUT_SCHEMA
        or document.get("ownership_marker") != OWNERSHIP_MARKER
        or document.get("path") != str(spec.path)
        or document.get("target") != str(spec.target)
        or document.get("arguments") != spec.arguments
        or document.get("target_sha256") != spec.target_sha256
    ):
        return None
    return document


def _shortcut_owned(spec: ShortcutSpec) -> bool:
    return _shortcut_document(spec) is not None


def _create_shortcut(spec: ShortcutSpec, adapter: ShortcutAdapter) -> bool:
    document = _shortcut_document(spec)
    if (spec.sidecar.exists() or spec.sidecar.is_symlink()) and document is None:
        raise OperatorAppsDenied("refuse to overwrite a foreign shortcut sidecar")
    if (spec.path.exists() or spec.path.is_symlink()) and document is None:
        raise OperatorAppsDenied("refuse to overwrite a foreign shortcut")
    if spec.path.is_symlink():
        raise OperatorAppsDenied("refuse to replace a redirected shortcut target")
    if document is not None and spec.path.is_file():
        expected_link = document.get("link_sha256")
        if expected_link == _sha256_file(spec.path):
            return False
    if spec.path.exists():
        if not spec.path.is_file():
            raise OperatorAppsDenied("shortcut target is not a regular file")
    adapter.create(spec)
    if not spec.path.is_file() or spec.path.is_symlink():
        raise OperatorAppsDenied("shortcut adapter did not create a regular file")
    sidecar_content = _shortcut_sidecar(spec, _sha256_file(spec.path))
    _publish_file(spec.sidecar, sidecar_content, 0o644, (spec.sidecar.parent,))
    return True


def _remove_shortcut(spec: ShortcutSpec, adapter: ShortcutAdapter) -> bool:
    if not (spec.path.exists() or spec.path.is_symlink()) and not (
        spec.sidecar.exists() or spec.sidecar.is_symlink()
    ):
        return False
    if not _shortcut_owned(spec):
        raise OperatorAppsDenied("refuse to remove a foreign shortcut")
    if spec.path.exists() or spec.path.is_symlink():
        if spec.path.is_symlink():
            raise OperatorAppsDenied("refuse to remove a redirected shortcut")
        adapter.remove(spec)
    if spec.sidecar.exists() or spec.sidecar.is_symlink():
        spec.sidecar.unlink()
    return True


def _receipt_path(store: PlatformInstallationStore) -> Path:
    return Path(store.path).absolute().parent / _RECEIPT_FILE


def _state_path(store: PlatformInstallationStore) -> Path:
    return Path(store.path).absolute().parent / _STATE_FILE


def _load_state(store: PlatformInstallationStore) -> dict[str, object] | None:
    path = _state_path(store)
    if not path.exists() and not path.is_symlink():
        return None
    try:
        document = json.loads(_read_bounded_text(path))
    except (OSError, ValueError, TypeError) as error:
        raise OperatorAppsDenied("operator app state is unreadable") from error
    if type(document) is not dict or document.get("schema") != STATE_SCHEMA:
        raise OperatorAppsDenied("operator app state is inconsistent")
    return document


def _write_receipt(store: PlatformInstallationStore, receipt: dict[str, object]) -> None:
    atomic_write_private_text(_receipt_path(store), _canonical_json(receipt) + "\n")


def _write_state(store: PlatformInstallationStore, state: dict[str, object]) -> None:
    atomic_write_private_text(_state_path(store), _canonical_json(state) + "\n")


def _execute_install(
    *, operation: str, plan: dict[str, object], config: OperatorAppsConfiguration,
    path_adapter: PathAdapter, shortcut_adapter: ShortcutAdapter,
    store: PlatformInstallationStore, startup_adapter: StartupAdapter | None = None,
) -> dict[str, object]:
    previous = _load_state(store)
    roots = tuple(Path(str(item)) for item in plan["configuration"]["approved_roots"])
    windows = config.target is PlatformReleaseTarget.WINDOWS_X86_64
    installed: list[str] = []
    shortcut_actions: list[dict[str, object]] = []
    changed = False
    for item in plan["files"]:
        path = Path(str(item["path"]))
        kind = str(item["kind"])
        if kind.endswith("cmd-shim"):
            content, digest = _windows_shim(
                Path(plan["configuration"]["runtime_python"]),
                Path(plan["configuration"]["code_directory"]),
                str(item["source_sha256"]),
            )
        elif kind == "windows-powershell-shim":
            content, digest = _powershell_shim(
                Path(plan["configuration"]["runtime_python"]),
                Path(plan["configuration"]["code_directory"]),
                str(item["source_sha256"]),
            )
        elif kind == "posix-script":
            content, digest = _posix_script(
                Path(plan["configuration"]["runtime_python"]),
                Path(plan["configuration"]["code_directory"]),
                str(item["source_sha256"]),
            )
        elif kind == "posix-wrapper":
            primary = Path(plan["configuration"]["bin_directory"]) / "aegis"
            content, digest = _render(
                "hash", str(item["source_sha256"]),
                f"exec {_shell_quote(str(primary))} \"$@\"\n",
                prefix="#!/bin/sh\n",
            )
        elif kind == "desktop-entry":
            launcher = Path(plan["configuration"]["bin_directory"]) / "aegis"
            content, digest = _desktop_entry(launcher, str(item["source_sha256"]))
        else:
            raise OperatorAppsDenied("unsupported launcher kind in plan")
        if digest != item["target_sha256"]:
            raise OperatorAppsDenied("launcher content changed after approval")
        if sha256(content.encode("utf-8")).hexdigest() != item["content_sha256"]:
            raise OperatorAppsDenied("launcher content differs from approved plan")
        mode = int(str(item["mode"]), 8)
        if _publish_file(path, content, mode, roots):
            installed.append(str(path))
            changed = True
        else:
            installed.append(str(path))

    for raw in plan["shortcuts"]:
        spec = _shortcut_from_plan(raw)
        if _create_shortcut(spec, shortcut_adapter):
            shortcut_actions.append({"path": str(spec.path), "action": "CREATE"})
            changed = True
        else:
            shortcut_actions.append({"path": str(spec.path), "action": "NO_CHANGE"})

    startup_action = {"requested": bool(plan["startup"]["requested"]), "action": "NO_CHANGE"}
    startup_was_ours = bool(previous is not None and previous.get("startup_added_by_us") is True)
    if plan["startup"]["requested"]:
        if plan["startup"]["supported"] is not True or not plan["startup"]["command"]:
            raise OperatorAppsDenied("start-at-login is unavailable for this target/launcher")
        adapter = startup_adapter or WindowsRunKeyStartupAdapter()
        if adapter.enable(command=str(plan["startup"]["command"])):
            startup_action["action"] = "ENABLE"
            startup_was_ours = True
            changed = True
    elif startup_was_ours:
        adapter = startup_adapter or WindowsRunKeyStartupAdapter()
        if adapter.disable():
            startup_action["action"] = "DISABLE"
            changed = True
        startup_was_ours = False

    entry = str(plan["path"]["entry"])
    path_action = {"entry": entry, "scope": config.path_scope, "action": "NO_CHANGE"}
    added = False
    if windows:
        before = path_adapter.read()
        after, added = _add_path(before, entry, windows=windows)
        if added:
            path_adapter.write(after)
            path_action["action"] = "ADD"
            changed = True

    path_added_by_us = added or bool(
        previous is not None and previous.get("path_added_by_us") is True
    )
    state = {
        "schema": STATE_SCHEMA,
        "plan_digest": plan["plan_digest"],
        "path_entry": entry,
        "path_scope": config.path_scope,
        "path_added_by_us": path_added_by_us,
        "files": [str(item["path"]) for item in plan["files"]],
        "shortcuts": [str(raw["path"]) for raw in plan["shortcuts"]],
        "startup_added_by_us": startup_was_ours,
    }
    _write_state(store, state)
    return {
        "installed_paths": installed,
        "removed_paths": [],
        "path_action": path_action,
        "shortcut_actions": shortcut_actions,
        "changed": changed,
    }


def _execute_uninstall(
    *, plan: dict[str, object], config: OperatorAppsConfiguration,
    path_adapter: PathAdapter, shortcut_adapter: ShortcutAdapter,
    store: PlatformInstallationStore, startup_adapter: StartupAdapter | None = None,
) -> dict[str, object]:
    windows = config.target is PlatformReleaseTarget.WINDOWS_X86_64
    removed: list[str] = []
    shortcut_actions: list[dict[str, object]] = []
    changed = False
    for raw in plan["shortcuts"]:
        spec = _shortcut_from_plan(raw)
        if _remove_shortcut(spec, shortcut_adapter):
            shortcut_actions.append({"path": str(spec.path), "action": "REMOVE"})
            removed.append(str(spec.path))
            changed = True
        else:
            shortcut_actions.append({"path": str(spec.path), "action": "NO_CHANGE"})
    for item in plan["files"]:
        path = Path(str(item["path"]))
        if _remove_file(path):
            removed.append(str(path))
            changed = True

    state = _load_state(store)
    startup_action = {"requested": False, "action": "NO_CHANGE"}
    if state is not None and state.get("startup_added_by_us") is True:
        adapter = startup_adapter or WindowsRunKeyStartupAdapter()
        if adapter.disable():
            startup_action["action"] = "DISABLE"
            changed = True
    path_action = {
        "entry": str(plan["path"]["entry"]), "scope": config.path_scope,
        "action": "NO_CHANGE",
    }
    if (windows and state is not None
            and state.get("path_added_by_us") is True):
        before = path_adapter.read()
        after, removed_path = _remove_path(
            before, str(plan["path"]["entry"]), windows=windows,
        )
        if removed_path:
            path_adapter.write(after)
            path_action["action"] = "REMOVE"
            changed = True
    if state is not None:
        _state_path(store).unlink(missing_ok=True)
    return {
        "installed_paths": [],
        "removed_paths": removed,
        "path_action": path_action,
        "shortcut_actions": shortcut_actions,
        "startup_action": startup_action,
        "changed": changed,
    }


def _observed_effects(
    plan: dict[str, object], operation: str, store: PlatformInstallationStore,
) -> dict[str, object]:
    """Best-effort truthful observation after an interrupted effect batch."""
    paths: list[str] = []
    changed = False
    for item in plan["files"]:
        path = Path(str(item["path"]))
        if not (path.exists() or path.is_symlink()) or path.is_symlink():
            continue
        try:
            owned = _owned_bytes(path.read_bytes())
        except OSError:
            owned = False
        if owned:
            paths.append(str(path))
            changed = True
    shortcut_actions: list[dict[str, object]] = []
    for raw in plan["shortcuts"]:
        spec = _shortcut_from_plan(raw)
        if _shortcut_owned(spec) or spec.path.exists():
            shortcut_actions.append({"path": str(spec.path), "action": "OBSERVED"})
            changed = True
    state = _load_state(store)
    path_action = {
        "entry": str(plan["path"]["entry"]),
        "scope": str(plan["path"]["scope"]),
        "action": "OBSERVED" if state is not None else "NO_CHANGE",
    }
    if operation == "uninstall":
        removed = [item for item in paths if not Path(item).exists()]
        return {
            "installed_paths": [], "removed_paths": removed,
            "path_action": path_action,
            "shortcut_actions": shortcut_actions, "changed": changed,
        }
    return {
        "installed_paths": paths, "removed_paths": [],
        "path_action": path_action,
        "shortcut_actions": shortcut_actions, "changed": changed,
    }


def _receipt(
    *, operation: str, plan: dict[str, object], outcome: str,
    effects: dict[str, object] | None, error: str | None = None,
) -> dict[str, object]:
    payload = {
        "schema": RECEIPT_SCHEMA,
        "operation": operation,
        "outcome": outcome,
        "plan_digest": plan["plan_digest"],
        "target": plan["target"],
        "installed_paths": (effects or {}).get("installed_paths", []),
        "removed_paths": (effects or {}).get("removed_paths", []),
        "path_action": (effects or {}).get("path_action", {
            "entry": plan["path"]["entry"], "scope": plan["path"]["scope"],
            "action": "NO_CHANGE",
        }),
        "shortcut_actions": (effects or {}).get("shortcut_actions", []),
        "startup_action": (effects or {}).get("startup_action", {
            "requested": bool(plan.get("startup", {}).get("requested")),
            "action": "NO_CHANGE",
        }),
        "owner_approved": True,
        "executed": effects is not None,
        "core_activated": False,
        "protected_state_touched": False,
    }
    if error is not None:
        payload["error"] = error
    return payload


def apply_owner_approved_operator_apps(
    *,
    approval_id: str | None,
    operation: str,
    config: OperatorAppsConfiguration,
    state_path: Path | str,
    store: PlatformInstallationStore,
    path_adapter: PathAdapter,
    shortcut_adapter: ShortcutAdapter,
    startup_adapter: StartupAdapter | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    """Consume one exact owner approval, then apply the launcher plan."""
    if operation not in _OPERATIONS:
        raise OperatorAppsDenied("unsupported operator application operation")
    if not isinstance(store, PlatformInstallationStore):
        raise TypeError("canonical B1 installation store required")
    plan = build_operator_apps_plan(config)
    parameters = _parameters(operation, plan)
    if not isinstance(approval_id, str) or not approval_id.strip():
        raise OperatorAppsApprovalRequired(
            execution_fingerprint(OPERATOR_APPS_CAPABILITY, parameters),
            operation=operation,
        )
    if OperatorStopStore(Path(state_path).absolute()).current().active:
        raise OperatorAppsDenied("operator STOP is active")

    with StateProcessLock(
        store.path, resource="aegis-operator-apps",
        lock_directory=Path(store.path).absolute().parent,
    ):
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None or current.utcoffset() is None:
            raise ValueError("time must be timezone aware")
        ExecutionApprovalVerifier(state_path).consume(
            approval_id=approval_id,
            capability=OPERATOR_APPS_CAPABILITY,
            parameters=parameters,
            now=current,
        )
        effects = None
        try:
            if operation == "uninstall":
                effects = _execute_uninstall(
                    plan=plan, config=config, path_adapter=path_adapter,
                    shortcut_adapter=shortcut_adapter, store=store,
                    startup_adapter=startup_adapter,
                )
            else:
                effects = _execute_install(
                    operation=operation, plan=plan, config=config,
                    path_adapter=path_adapter, shortcut_adapter=shortcut_adapter,
                    store=store, startup_adapter=startup_adapter,
                )
        except Exception as error:
            observed = _observed_effects(plan, operation, store)
            outcome = "OUTCOME_UNKNOWN" if observed["changed"] else "FAILED"
            receipt = _receipt(
                operation=operation, plan=plan, outcome=outcome,
                effects=observed, error=type(error).__name__,
            )
            _write_receipt(store, receipt)
            raise
        receipt = _receipt(
            operation=operation, plan=plan, outcome="SUCCEEDED", effects=effects,
        )
        _write_receipt(store, receipt)
        return receipt
