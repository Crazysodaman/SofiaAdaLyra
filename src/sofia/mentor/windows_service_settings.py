"""Optional MENTOR QA settings for the existing Windows Sofía service.

There is no new service, writer, account or scheduler. Registry custom options
belong to pywin32 ServiceFramework's existing SofiaAdaLyra service. Running
services do not automatically reload changed options or Python source.

No local machine changes happen except on an explicit --apply owner CLI.
Never alter StatePath, credentials, watchdog or protected authorization.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import sys
from typing import Callable

SERVICE = "SofiaAdaLyra"
FLAG_OPTION = "MentorBehaviorEnabled"
ROOT_OPTION = "MentorSourceRoot"
PROFILE = Path("src/sofia/personality/personality.json")


class MentorServiceSettingsError(ValueError):
    pass


@dataclass(frozen=True)
class MentorServiceSettings:
    enabled: bool
    source_root: Path | None

    def environment(self) -> dict[str, str]:
        """Only two allowlisted variables, never inherited credentials."""
        if not self.enabled:
            return {"SOFIA_MENTOR_BEHAVIOR_ENABLED": "false"}
        if self.source_root is None:
            raise MentorServiceSettingsError("enabled MENTOR needs a valid source root")
        return {
            "SOFIA_MENTOR_BEHAVIOR_ENABLED": "true",
            "SOFIA_MENTOR_SOURCE_ROOT": str(self.source_root),
        }


def _reject_service_network_path(path: Path) -> None:
    """LocalSystem cannot safely rely on a user's UNC/mapped network drive.

    Network shares are not an appropriate trust boundary for the canonical
    Windows service. Never auto-copy, remap drives or store credentials.
    """
    raw = str(path)
    if raw.startswith("\\\\") or raw.startswith("//"):
        raise MentorServiceSettingsError(
            "service source root must be a locally installed checkout, not a UNC "
            "network share (LocalSystem cannot rely on interactive share access)"
        )
    # Windows drive mappings can look like ordinary drive letters. Reject
    # remote drives using the read-only Windows volume classification.
    if sys.platform == "win32":
        drive = path.drive
        if drive and len(drive) == 2 and drive[1] == ":":
            import ctypes
            drive_kind = ctypes.windll.kernel32.GetDriveTypeW(drive + "\\\\")
            if drive_kind == 4:
                raise MentorServiceSettingsError(
                    "service source root is a mapped network drive; "
                    "use a locally deployed, version-verified checkout"
                )
            if drive_kind in (0, 1):
                raise MentorServiceSettingsError(
                    "service source root is on an unrecognized volume"
                )


def _read_registry_option(
    service: str, option: str, default: str,
    *, registry=None,
) -> str:
    """Only KEY_QUERY_VALUE. Unlike pywin32's helper, never RegCreateKey."""
    if registry is None:
        if sys.platform != "win32":
            raise MentorServiceSettingsError("Windows service registry unavailable")
        import winreg
        registry = winreg
    if service != SERVICE or option not in (FLAG_OPTION, ROOT_OPTION):
        raise MentorServiceSettingsError("unrecognized MENTOR registry option")
    key_path = (
        "SYSTEM\\\\CurrentControlSet\\\\Services\\\\" + SERVICE + "\\\\Parameters"
    )
    try:
        with registry.OpenKey(
            registry.HKEY_LOCAL_MACHINE, key_path, 0, registry.KEY_QUERY_VALUE,
        ) as handle:
            value, value_type = registry.QueryValueEx(handle, option)
    except FileNotFoundError:
        return default
    except PermissionError:
        raise MentorServiceSettingsError(
            "reading the MENTOR service registry settings was denied; "
            "status has not changed any service configuration"
        ) from None
    except OSError:
        raise MentorServiceSettingsError(
            "could not read the service's MENTOR registry settings"
        ) from None
    if not isinstance(value, str):
        raise MentorServiceSettingsError("invalid MENTOR registry value type")
    return value


def validate_root(value: str | Path) -> Path:
    """Check the requested checkout is truly local; never create directories."""
    if not isinstance(value, (str, Path)) or not str(value).strip():
        raise MentorServiceSettingsError("a local checkout path is required")
    if isinstance(value, str) and ("\n" in value or "\r" in value or "\0" in value):
        raise MentorServiceSettingsError("unsafe checkout path")
    target = Path(value).expanduser()
    _reject_service_network_path(target)
    if target.is_symlink() or not target.is_dir():
        raise MentorServiceSettingsError("source root missing or redirected")
    target = target.resolve(strict=True)
    _reject_service_network_path(target)
    profile = target / PROFILE
    if profile.is_symlink() or not profile.is_file():
        raise MentorServiceSettingsError("source root lacks Sofía personality profile")
    if target not in profile.resolve(strict=True).parents:
        raise MentorServiceSettingsError("profile escapes requested root")
    if not (target / "src/sofia/mentor/behavior_monitor.py").is_file():
        raise MentorServiceSettingsError("source root lacks current MENTOR monitor code")
    return target


def decode_options(enabled: object, root: object) -> MentorServiceSettings:
    """Unconfigured legacy service remains disabled, never guesses a checkout."""
    value = "" if enabled is None else enabled
    if not isinstance(value, str) or value.strip().lower() not in (
        "", "0", "1", "true", "false",
    ):
        raise MentorServiceSettingsError("unrecognized MENTOR service setting")
    is_on = value.strip().lower() in ("true", "1")
    return MentorServiceSettings(
        enabled=is_on,
        source_root=validate_root(root) if is_on else None,
    )


def load_custom_service_settings(
    *, getter: Callable | None = None,
) -> MentorServiceSettings:
    if getter is None:
        if sys.platform != "win32":
            raise MentorServiceSettingsError("Windows SCM configuration unavailable")
        getter = _read_registry_option
    enabled = getter(SERVICE, FLAG_OPTION, "")
    root = getter(SERVICE, ROOT_OPTION, "")
    return decode_options(enabled, root)


def service_settings_status(*, getter: Callable | None = None) -> dict:
    """No hidden runtime introspection: report configured registry options only."""
    settings = load_custom_service_settings(getter=getter)
    return {
        "schema": "sofia.mentor.service-settings.v1",
        "service": SERVICE,
        "configured_enabled": settings.enabled,
        "configured_root_valid": settings.source_root is not None,
        "configured_source_root": (
            str(settings.source_root) if settings.source_root else None
        ),
        "running_service_has_reloaded_settings": "unknown",
        "running_release_has_monitor_code": "unknown",
        "runtime_review_count": "unknown",
        "local_system_score_file_account": "separate_from_interactive_shell",
        "automatic_service_restart": False,
        "changed_canonical_state": False,
    }


def configure_custom_service_settings(
    *, root: Path | str, apply: bool,
    setter: Callable | None = None,
) -> dict:
    """Explicit admin-only setting update; never restart the Windows service."""
    checkout = validate_root(root)
    if apply is not True:
        return {"operation": "preview", "service": SERVICE,
                "settings_valid": True, "will_restart": False,
                "will_change_state_path": False, "source_root": str(checkout)}
    if setter is None:
        if sys.platform != "win32":
            raise MentorServiceSettingsError("Windows service administration required")
        import win32serviceutil
        setter = win32serviceutil.SetServiceCustomOption
    # Commit path first; only then enable the optional reviewer.
    setter(SERVICE, ROOT_OPTION, str(checkout))
    setter(SERVICE, FLAG_OPTION, "true")
    return {"operation": "configured_not_restarted", "service": SERVICE,
            "enabled_for_next_start": True, "will_restart": False,
            "source_root": str(checkout), "will_change_state_path": False}


def disable_custom_service_settings(*, apply: bool,
                                    setter: Callable | None = None) -> dict:
    if apply is not True:
        return {"operation": "disable-preview", "service": SERVICE,
                "will_restart": False, "will_change_state_path": False}
    if setter is None:
        if sys.platform != "win32":
            raise MentorServiceSettingsError("Windows service administration required")
        import win32serviceutil
        setter = win32serviceutil.SetServiceCustomOption
    setter(SERVICE, FLAG_OPTION, "false")
    return {"operation": "disabled_on_next_start", "service": SERVICE,
            "will_restart": False, "will_change_state_path": False}
