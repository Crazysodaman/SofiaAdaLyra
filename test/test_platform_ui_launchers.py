from pathlib import Path

import pytest

from sofia.platform.ui_launchers import (
    UILauncherInstallOptions, install_windows_launchers, install_xdg_launchers,
)


def test_xdg_launchers_and_autostart_are_per_user_and_core_neutral(tmp_path):
    home = tmp_path / "home"
    receipt = install_xdg_launchers(
        UILauncherInstallOptions(tray_autostart=True),
        environment={"HOME": str(home)}, executable=Path("/usr/bin/python3"),
    )

    assert receipt.platform == "linux-xdg"
    assert len(receipt.installed) == 4
    assert len(receipt.autostart) == 1
    for raw in receipt.installed:
        content = Path(raw).read_text(encoding="utf-8")
        assert "sofia.platform.launcher" in content
        assert "sofia.db" not in content
        assert "credential" not in content.casefold()
    tray = home / ".config/autostart/companion-runtime-tray.desktop"
    assert tray.is_file()
    assert not (home / ".config/autostart/companion-runtime-desktop.desktop").exists()

    disabled = install_xdg_launchers(
        UILauncherInstallOptions(), environment={"HOME": str(home)},
        executable=Path("/usr/bin/python3"),
    )
    assert disabled.autostart == ()
    assert not tray.exists()


def test_xdg_launcher_refuses_symlink_redirection(tmp_path):
    home = tmp_path / "home"
    applications = home / ".local/share/applications"
    applications.mkdir(parents=True)
    target = tmp_path / "outside.desktop"
    target.write_text("do not overwrite", encoding="utf-8")
    (applications / "companion-runtime-desktop.desktop").symlink_to(target)

    with pytest.raises(PermissionError, match="unsafe"):
        install_xdg_launchers(
            UILauncherInstallOptions(), environment={"HOME": str(home)},
            executable=Path("/usr/bin/python3"),
        )
    assert target.read_text(encoding="utf-8") == "do not overwrite"


def test_windows_shortcuts_and_startup_are_current_user_only(tmp_path):
    calls = []
    startup = []

    def run(argv, **kwargs):
        calls.append((argv, kwargs))

    receipt = install_windows_launchers(
        UILauncherInstallOptions(
            tray_autostart=True, desktop_autostart=False,
            desktop_shortcuts=True,
        ),
        environment={
            "APPDATA": str(tmp_path / "AppData/Roaming"),
            "USERPROFILE": str(tmp_path / "User"),
        },
        executable=Path("C:/Python/python.exe"), run=run,
        powershell_path="powershell.exe",
        configure_startup=lambda **values: startup.append(values),
    )

    assert receipt.platform == "windows"
    assert len(receipt.installed) == 8
    assert receipt.autostart == ("tray",)
    assert len(calls) == 8
    assert all("Microsoft/Windows/Start Menu/Programs/Sofía" in call[0][5]
               or "/Desktop/" in call[0][5] for call in calls)
    assert all("sofia.platform.launcher" in call[0][7] for call in calls)
    assert startup == [{
        "tray_enabled": True, "desktop_enabled": False,
        "executable": Path("C:/Python/python.exe"),
    }]
