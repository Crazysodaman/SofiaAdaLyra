"""Operator CLI for Sofía's canonical permission store."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
from uuid import uuid4

from sofia.safe.owner_browser import authorize_exact_action

from sofia.platform.config import production_state_path
from sofia.safe.permissions import (
    PermissionLevel,
    PermissionStore,
    capability_permission_policy,
    explicitly_classified_capabilities,
    grantable_capabilities,
    standing_grant_parameters,
    private_authority_parameters,
)


def _state_path(raw: str | None) -> Path:
    return Path(raw) if raw else Path(production_state_path())


def _json_object(raw: str) -> dict:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("--scope-json must be valid JSON") from exc
    if not isinstance(value, dict):
        raise ValueError("--scope-json must decode to an object")
    return value


def _switch(raw: str | None, current: bool) -> bool:
    if raw is None:
        return current
    return raw == "on"


def _print_grants(store: PermissionStore, *, active_only: bool) -> None:
    rows = []
    for grant in store.grants(active_only=active_only):
        policy = capability_permission_policy(grant.capability)
        rows.append({
            "grant_id": grant.grant_id,
            "capability": grant.capability,
            "level": int(policy.level),
            "scope": grant.scope,
            "granted_by": grant.granted_by,
            "granted_at": grant.granted_at.isoformat(),
            "expires_at": (
                None if grant.expires_at is None else grant.expires_at.isoformat()
            ),
            "revoked_at": (
                None if grant.revoked_at is None else grant.revoked_at.isoformat()
            ),
            "active": grant.active,
        })
    print(json.dumps(rows, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m sofia.safe.permissions_cli"
    )
    parser.add_argument("--state-path")
    sub = parser.add_subparsers(dest="command", required=True)

    list_cmd = sub.add_parser("list")
    list_cmd.add_argument("--active-only", action="store_true")

    show_cmd = sub.add_parser("show")
    show_cmd.add_argument("capability")

    sub.add_parser("levels")

    grant_cmd = sub.add_parser("grant")
    grant_cmd.add_argument("capability", choices=grantable_capabilities())
    grant_cmd.add_argument("--scope-json", default="{}")
    grant_cmd.add_argument("--expires-minutes", type=int)
    grant_cmd.add_argument("--granted-by", default="Sparks")
    grant_cmd.add_argument("--credential-id", required=True,
                           help="Enrolled FIDO2 key for a durable grant")

    revoke_cmd = sub.add_parser("revoke")
    revoke_cmd.add_argument("grant_id")
    revoke_cmd.add_argument("--revoked-by", default="Sparks")
    revoke_cmd.add_argument("--credential-id", required=True,
                            help="Enrolled FIDO2 key to revoke a standing grant")

    private = sub.add_parser("private")
    private_sub = private.add_subparsers(
        dest="private_command",
        required=True,
    )
    private_sub.add_parser("show")
    private_set = private_sub.add_parser("set")
    for flag in (
        "private-chat",
        "adult-chat",
        "adult-avatar",
        "adult-external-delivery",
    ):
        private_set.add_argument(
            f"--{flag}",
            choices=("on", "off"),
        )
    private_set.add_argument("--updated-by", default="Sparks")
    private_set.add_argument("--credential-id", required=True,
                             help="Enrolled FIDO2 key for Level-5 authority")

    args = parser.parse_args(argv)

    try:
        store = PermissionStore(_state_path(args.state_path))

        if args.command == "list":
            _print_grants(store, active_only=args.active_only)
            return 0

        if args.command == "show":
            policy = capability_permission_policy(args.capability)
            print(json.dumps({
                "capability": policy.capability,
                "level": int(policy.level),
                "level_name": policy.level.name.lower(),
                "privacy": policy.privacy.value,
                "standing_grant_allowed": policy.standing_grant_allowed,
                "description": policy.description,
                "explicitly_classified": (
                    args.capability in explicitly_classified_capabilities()
                ),
            }, indent=2, sort_keys=True))
            return 0

        if args.command == "levels":
            grouped = {
                str(int(level)): sorted(
                    capability
                    for capability in explicitly_classified_capabilities()
                    if capability_permission_policy(capability).level is level
                )
                for level in PermissionLevel
            }
            print(json.dumps(grouped, indent=2, sort_keys=True))
            return 0

        if args.command == "grant":
            scope = _json_object(args.scope_json)
            expires_at = None
            if args.expires_minutes is not None:
                if args.expires_minutes <= 0:
                    raise ValueError("--expires-minutes must be positive")
                expires_at = (
                    datetime.now(timezone.utc)
                    + timedelta(minutes=args.expires_minutes)
                )
            grant_id = str(uuid4())
            approved = authorize_exact_action(
                store.path, capability="safe.permission.standing.grant",
                parameters=standing_grant_parameters(
                    args.capability, scope=scope, grant_id=grant_id,
                    expires_at=expires_at,
                ),
                credential_id=args.credential_id, expires_seconds=120,
            )
            grant = store.grant(
                args.capability,
                scope=scope,
                granted_by=args.granted_by,
                expires_at=expires_at,
                grant_id=grant_id,
                approval_id=approved.approval_id,
            )
            print(json.dumps({
                "grant_id": grant.grant_id,
                "capability": grant.capability,
                "scope": grant.scope,
                "expires_at": (
                    None if grant.expires_at is None
                    else grant.expires_at.isoformat()
                ),
            }, indent=2, sort_keys=True))
            return 0

        if args.command == "revoke":
            approved = authorize_exact_action(
                store.path, capability="safe.permission.standing.revoke",
                parameters={"grant_id": args.grant_id},
                credential_id=args.credential_id, expires_seconds=120,
            )
            grant = store.revoke(
                args.grant_id,
                revoked_by=args.revoked_by,
                approval_id=approved.approval_id,
            )
            print(json.dumps({
                "grant_id": grant.grant_id,
                "capability": grant.capability,
                "revoked_at": (
                    None if grant.revoked_at is None
                    else grant.revoked_at.isoformat()
                ),
            }, indent=2, sort_keys=True))
            return 0

        if args.command == "private":
            current = store.private_adult_authority()
            if args.private_command == "show":
                print(json.dumps({
                    "private_chat": current.private_chat,
                    "adult_chat": current.adult_chat,
                    "adult_avatar": current.adult_avatar,
                    "adult_external_delivery": current.adult_external_delivery,
                    "updated_by": current.updated_by,
                    "updated_at": (
                        None if current.updated_at is None
                        else current.updated_at.isoformat()
                    ),
                }, indent=2, sort_keys=True))
                return 0

            flags = private_authority_parameters(
                private_chat=_switch(args.private_chat, current.private_chat),
                adult_chat=_switch(args.adult_chat, current.adult_chat),
                adult_avatar=_switch(args.adult_avatar, current.adult_avatar),
                adult_external_delivery=_switch(
                    args.adult_external_delivery,
                    current.adult_external_delivery,
                ),
            )
            approved = authorize_exact_action(
                store.path, capability="safe.permission.private_authority.change",
                parameters=flags, credential_id=args.credential_id,
                expires_seconds=120,
            )
            updated = store.set_private_adult_authority(
                **flags, updated_by=args.updated_by,
                approval_id=approved.approval_id,
            )
            print(json.dumps({
                "private_chat": updated.private_chat,
                "adult_chat": updated.adult_chat,
                "adult_avatar": updated.adult_avatar,
                "adult_external_delivery": updated.adult_external_delivery,
                "updated_by": updated.updated_by,
                "updated_at": (
                    None if updated.updated_at is None
                    else updated.updated_at.isoformat()
                ),
            }, indent=2, sort_keys=True))
            return 0

        raise RuntimeError("unhandled permission command")
    except (
        KeyError,
        OSError,
        PermissionError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as exc:
        print(
            f"Permission command refused: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
