"""Stable role-aware launcher for the generic Platform installation."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Sequence

from sofia.platform.config.roles import PlatformRole, PlatformRoleConfiguration


def _roles() -> PlatformRoleConfiguration:
    return PlatformRoleConfiguration.from_environment()


def _require_local_core(command: str) -> PlatformRoleConfiguration:
    roles = _roles()
    if not roles.supports(PlatformRole.CORE_HOST):
        if roles.supports(PlatformRole.CORE_LINK):
            raise RuntimeError(
                f"{command} remote Core Link transport is not configured; "
                "refusing to instantiate a local Core or canonical database"
            )
        raise RuntimeError(
            f"{command} requires CORE_HOST or an approved CORE_LINK binding"
        )
    return roles


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="companion-runtime")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status", help="Show configured Platform roles")
    subparsers.add_parser("desktop", help="Open the configured desktop client")
    subparsers.add_parser("tray", help="Open the configured tray client")
    subparsers.add_parser("settings", help="Open the configured settings client")
    subparsers.add_parser(
        "control-center", help="Open the configured Platform Control Center",
    )
    install = subparsers.add_parser(
        "install-ui", help="Install per-user GUI launchers",
    )
    install.add_argument("--tray-autostart", action="store_true")
    install.add_argument("--desktop-autostart", action="store_true")
    install.add_argument("--desktop-shortcuts", action="store_true")
    args = parser.parse_args(argv)

    try:
        if args.command == "status":
            payload = _roles().to_payload()
            store_path = os.environ.get("SOFIA_CORE_LINK_BINDING_STORE", "").strip()
            if store_path:
                from sofia.platform.core_link import CoreLinkBindingStore

                snapshot = CoreLinkBindingStore(Path(store_path)).load()
                selected = snapshot.selected()
                payload["core_link"] = {
                    "store_revision": snapshot.revision,
                    "selected": None if selected is None else selected.redacted_status(),
                }
            print(json.dumps(payload, sort_keys=True))
            return 0

        if args.command == "install-ui":
            from sofia.platform.ui_launchers import (
                UILauncherInstallOptions, install_user_launchers,
            )

            receipt = install_user_launchers(UILauncherInstallOptions(
                tray_autostart=args.tray_autostart,
                desktop_autostart=args.desktop_autostart,
                desktop_shortcuts=args.desktop_shortcuts,
            ))
            print(json.dumps({
                "platform": receipt.platform,
                "installed": list(receipt.installed),
                "autostart": list(receipt.autostart),
            }, sort_keys=True))
            return 0

        roles = _roles()
        if (
            args.command in {"desktop", "tray", "settings", "control-center"}
            and not roles.supports(PlatformRole.CORE_HOST)
            and roles.supports(PlatformRole.CORE_LINK)
        ):
            if args.command == "desktop":
                from sofia.modules.ui.core_link_desktop import run_core_link_desktop

                return run_core_link_desktop()
            if args.command == "settings":
                from sofia.modules.ui.core_link_settings import run_core_link_settings

                return run_core_link_settings()
            if args.command == "control-center":
                from sofia.modules.ui.core_link_control_center import (
                    run_core_link_control_center,
                )

                return run_core_link_control_center()
            from sofia.modules.ui.core_link_tray import run_core_link_tray

            return run_core_link_tray()

        _require_local_core(args.command)
        if args.command == "desktop":
            from sofia.core.launcher import main as core_main

            return core_main(argv=())
        if args.command == "tray":
            from sofia.modules.ui.tray_agent import main as tray_main

            return tray_main([])
        if args.command == "settings":
            from sofia.modules.ui.settings_window import main as settings_main

            return settings_main([])
        if args.command == "control-center":
            from sofia.modules.ui.settings_window import main as settings_main

            return settings_main([])
        raise AssertionError("unreachable launcher command")
    except (OSError, RuntimeError, TypeError, ValueError, PermissionError) as exc:
        print(
            f"companion-runtime {args.command} refused: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

