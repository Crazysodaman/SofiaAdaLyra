"""Hash-pinned offline Linux Fleet-agent bootstrap bundle.

The rendered script is intended for an already authorized root/provisioning
boundary.  It does not discover credentials, enroll trust, or use the network.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import PurePosixPath
import re


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def _absolute(path: str, label: str) -> str:
    value = PurePosixPath(path)
    if not value.is_absolute() or ".." in value.parts or any(
        character in path for character in "\r\n\x00'\"`$"
    ):
        raise ValueError(f"{label} must be a safe absolute POSIX path")
    return str(value)


@dataclass(frozen=True, slots=True)
class LinuxBootstrapBundle:
    wheel_name: str
    wheel_sha256: str
    python_name: str
    python_sha256: str
    agent_config_name: str
    install_root: str
    service_name: str = "sofia-fleet-agent"

    def __post_init__(self) -> None:
        for value, label in (
            (self.wheel_name, "wheel_name"), (self.python_name, "python_name"),
            (self.agent_config_name, "agent_config_name"),
            (self.service_name, "service_name"),
        ):
            if _NAME.fullmatch(value) is None:
                raise ValueError(f"{label} must be a safe filename/identifier")
        if _SHA256.fullmatch(self.wheel_sha256) is None or _SHA256.fullmatch(
            self.python_sha256
        ) is None:
            raise ValueError("Linux bootstrap artifacts require SHA-256")
        _absolute(self.install_root, "install_root")

    def render(self) -> str:
        """Render offline atomic-release staging with a rollback symlink."""
        root = _absolute(self.install_root, "install_root")
        return f'''#!/bin/sh
set -eu
STAGE="${{1:?offline stage directory required}}"
RELEASE_ID="${{2:?release identifier required}}"
case "$RELEASE_ID" in (*[!A-Za-z0-9_.-]*|'') echo "invalid release identifier" >&2; exit 2;; esac
ROOT='{root}'
RELEASE="$ROOT/releases/$RELEASE_ID"
WHEEL="$STAGE/{self.wheel_name}"
PYTHON="$STAGE/{self.python_name}"
CONFIG="$STAGE/{self.agent_config_name}"
printf '%s  %s\\n' '{self.wheel_sha256}' "$WHEEL" | sha256sum -c -
printf '%s  %s\\n' '{self.python_sha256}' "$PYTHON" | sha256sum -c -
test -f "$CONFIG"
test ! -e "$RELEASE"
mkdir -p "$RELEASE" "$ROOT/releases" "$ROOT/receipts"
cp "$PYTHON" "$RELEASE/{self.python_name}"
chmod 0755 "$RELEASE/{self.python_name}"
cp "$WHEEL" "$RELEASE/{self.wheel_name}"
cp "$CONFIG" "$RELEASE/{self.agent_config_name}"
"$RELEASE/{self.python_name}" -m venv "$RELEASE/.venv"
"$RELEASE/.venv/bin/python" -m pip install --no-index --no-deps "$RELEASE/{self.wheel_name}"
"$RELEASE/.venv/bin/python" -m sofia.distributed.agent_main --config "$RELEASE/{self.agent_config_name}" --check-config
PREVIOUS=""
if test -L "$ROOT/current"; then PREVIOUS="$(readlink "$ROOT/current")"; fi
ln -s "$RELEASE" "$ROOT/current.next"
mv -Tf "$ROOT/current.next" "$ROOT/current"
printf '%s\\n' "$PREVIOUS" > "$ROOT/rollback-target"
systemctl restart '{self.service_name}'
systemctl is-active --quiet '{self.service_name}'
printf '{{"status":"succeeded","release_id":"%s","wheel_sha256":"{self.wheel_sha256}","previous":"%s"}}\\n' "$RELEASE_ID" "$PREVIOUS" > "$ROOT/receipts/$RELEASE_ID.json"
'''

    def verify_receipt(self, payload: str, *, release_id: str) -> dict:
        try:
            value = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValueError("Linux bootstrap receipt is not valid JSON") from exc
        if (
            not isinstance(value, dict)
            or value.get("status") != "succeeded"
            or value.get("release_id") != release_id
            or value.get("wheel_sha256") != self.wheel_sha256
        ):
            raise RuntimeError("Linux bootstrap receipt does not match approved release")
        return value


def render_linux_rollback(*, install_root: str, service_name: str = "sofia-fleet-agent") -> str:
    root = _absolute(install_root, "install_root")
    if _NAME.fullmatch(service_name) is None:
        raise ValueError("service_name must be canonical")
    return f'''#!/bin/sh
set -eu
ROOT='{root}'
TARGET="$(cat "$ROOT/rollback-target")"
test -n "$TARGET" && test -d "$TARGET"
CURRENT="$(readlink "$ROOT/current")"
ln -s "$TARGET" "$ROOT/current.rollback"
mv -Tf "$ROOT/current.rollback" "$ROOT/current"
systemctl restart '{service_name}'
if ! systemctl is-active --quiet '{service_name}'; then
  ln -s "$CURRENT" "$ROOT/current.failed-rollback"
  mv -Tf "$ROOT/current.failed-rollback" "$ROOT/current"
  systemctl restart '{service_name}' || true
  exit 1
fi
'''
