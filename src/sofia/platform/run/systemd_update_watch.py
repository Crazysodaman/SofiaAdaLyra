"""Render independent Debian update watcher systemd units, without installing them.

This is deliberately a read-only GitHub/release-evidence watcher. It cannot
restart Sofía or activate a release. A separately trusted deployment service
must own compatibility, idle drain, fencing and reversible activation.
"""
from __future__ import annotations

import argparse
from pathlib import PurePosixPath
import re
import sys

_SAFE = re.compile(r"^/[A-Za-z0-9._/+@-]+$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")


def _absolute(value: str) -> str:
    p = PurePosixPath(value)
    if (
        not p.is_absolute() or str(p) == "/"
        or ".." in p.parts or _SAFE.fullmatch(str(p)) is None
    ):
        raise ValueError("update watcher paths must be absolute and safe")
    return str(p)


def render_service(
    *,
    python_path: str = "/opt/sofia/.venv/bin/python",
    trusted_key_file: str | None = None,
    signer_key_id: str | None = None,
) -> str:
    python_path = _absolute(python_path)
    if (trusted_key_file is None) != (signer_key_id is None):
        raise ValueError("trusted public key and signer ID must be configured together")
    trust = ""
    if trusted_key_file is not None:
        if _IDENTIFIER.fullmatch(signer_key_id) is None:
            raise ValueError("invalid release signer ID")
        trust = (
            " --trusted-release-key " + _absolute(trusted_key_file)
            + " --signer-key-id " + signer_key_id
        )
    return f"""[Unit]
Description=Sofía independent read-only GitHub update watcher
Wants=network-online.target
After=network-online.target
# Update discovery is intentionally independent of sofia-runtime.service.

[Service]
Type=oneshot
DynamicUser=yes
StateDirectory=sofia-updater
StateDirectoryMode=0700
WorkingDirectory=/var/lib/sofia-updater
ExecStart={python_path} -m sofia.platform.run.github_update_watch --status-file /var/lib/sofia-updater/status.json --installed-revision-file /var/lib/sofia-updater/installed-revision --inbox /var/lib/sofia-updater/inbox{trust}
Environment=PYTHONDONTWRITEBYTECODE=1
Environment=GIT_TERMINAL_PROMPT=0
TimeoutStartSec=90
UMask=0077
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
PrivateDevices=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictSUIDSGID=true
LockPersonality=true
ReadWritePaths=/var/lib/sofia-updater
"""


def render_timer() -> str:
    return """[Unit]
Description=Check signed Sofía update availability independently

[Timer]
OnBootSec=5min
OnUnitActiveSec=15min
RandomizedDelaySec=2min
Persistent=true
Unit=sofia-update-watch.service

[Install]
WantedBy=timers.target
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render Sofía update watcher units")
    parser.add_argument("kind", choices=("service", "timer"))
    parser.add_argument("--python", default="/opt/sofia/.venv/bin/python")
    parser.add_argument("--trusted-key")
    parser.add_argument("--signer-key-id")
    args = parser.parse_args(argv)
    try:
        if args.kind == "service":
            print(render_service(
                python_path=args.python,
                trusted_key_file=args.trusted_key,
                signer_key_id=args.signer_key_id,
            ), end="")
        else:
            if args.trusted_key or args.signer_key_id:
                raise ValueError("timer doesn't use release signing arguments")
            print(render_timer(), end="")
    except ValueError as exc:
        print("Sofía update service unit refused: " + str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
