"""Operator-facing authenticated probe for one enrolled Fleet node.

This command never creates enrollment, endpoint approval, or authority.
It consumes the existing durable NET records and exact active grants.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sofia.config import create_default_configuration
from sofia.distributed.durable import DurableRemoteAuthorization
from sofia.distributed.endpoint_policy_durable import DurableEndpointPolicy
from sofia.distributed.https_transport import PinnedHttpsRemoteTransport
from sofia.distributed.identity_durable import DurableNodeIdentityRegistry
from sofia.distributed.operations import RemoteOperationRequest
from sofia.distributed.remote_control import DurableRemoteControl


def _paths(state_path: Path) -> dict[str, Path]:
    base = state_path.parent
    return {
        "identity": base / "remote-identities.db",
        "endpoint": base / "remote-endpoints.db",
        "grant": base / "remote-grants.db",
        "ledger": base / "remote-request-ledger.db",
    }


def _state_path(raw: str | None) -> Path:
    return Path(raw) if raw else Path(create_default_configuration().state_path)


def _scalar(raw: str) -> str | int | float | bool | None:
    lowered = raw.casefold()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"null", "none"}:
        return None
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        return raw


def _parameters(items: list[str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for item in items:
        if "=" not in item:
            raise ValueError("parameters must use key=value")
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError("parameter key required")
        if key in result:
            raise ValueError(f"duplicate parameter: {key}")
        result[key] = _scalar(value)
    return result


class FleetNodeProbe:
    def __init__(
        self,
        *,
        state_path: Path,
        node_id: UUID,
        ca_file: Path,
        client_certificate: Path,
        client_private_key: Path,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.state_path = Path(state_path)
        self.node_id = node_id
        self.paths = _paths(self.state_path)

        identities = DurableNodeIdentityRegistry(self.paths["identity"])
        endpoints = DurableEndpointPolicy(self.paths["endpoint"])
        try:
            enrollment = identities.get(node_id)
            endpoint = endpoints.get(node_id)
        finally:
            identities.close()
            endpoints.close()

        if enrollment is None:
            raise LookupError("node is not actively enrolled")
        if endpoint is None:
            raise LookupError("node has no active approved endpoint")

        self.enrollment = enrollment
        self.endpoint = endpoint
        self.transport = PinnedHttpsRemoteTransport(
            lambda requested: self.endpoint if requested == self.node_id else None,
            ca_file=ca_file,
            client_certificate=client_certificate,
            client_private_key=client_private_key,
            timeout_seconds=timeout_seconds,
        )

    def authenticate(self) -> bool:
        return self.transport.authenticate(self.enrollment)

    def capabilities(self):
        if not self.authenticate():
            raise PermissionError("Fleet peer authentication failed")
        return self.transport.discover(self.enrollment)

    def invoke(
        self,
        *,
        capability: str,
        operation: str,
        parameters: dict[str, Any],
        max_inventory_age_seconds: float = 60.0,
    ):
        now = datetime.now(timezone.utc)
        authorization = DurableRemoteAuthorization(self.paths["grant"])
        try:
            grant = authorization.find_active(
                node_id=self.node_id,
                capability=capability,
                operation=operation,
                now=now,
            )
        finally:
            authorization.close()

        if grant is None:
            raise PermissionError(
                f"no active exact grant for {capability}/{operation}"
            )

        request = RemoteOperationRequest(
            request_id=uuid4(),
            node_id=self.node_id,
            grant_id=grant.grant_id,
            capability=capability,
            operation=operation,
            parameters=parameters,
        )
        control = DurableRemoteControl(
            transport=self.transport,
            identity_path=self.paths["identity"],
            endpoint_path=self.paths["endpoint"],
            authorization_path=self.paths["grant"],
            ledger_path=self.paths["ledger"],
            max_inventory_age=timedelta(seconds=max_inventory_age_seconds),
        )
        try:
            return control.invoke(
                self.enrollment,
                self.endpoint,
                request,
                now=now,
            )
        finally:
            control.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m sofia.distributed.fleet_probe")
    parser.add_argument("--state-path")
    parser.add_argument("--node-id", required=True)
    parser.add_argument("--ca-file", required=True)
    parser.add_argument("--client-cert", required=True)
    parser.add_argument("--client-key", required=True)
    parser.add_argument("--timeout", type=float, default=10.0)

    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("identity")
    sub.add_parser("capabilities")

    invoke = sub.add_parser("invoke")
    invoke.add_argument("--capability", required=True)
    invoke.add_argument("--operation", required=True)
    invoke.add_argument("--parameter", action="append", default=[])
    invoke.add_argument("--max-inventory-age", type=float, default=60.0)

    args = parser.parse_args(argv)

    try:
        probe = FleetNodeProbe(
            state_path=_state_path(args.state_path),
            node_id=UUID(args.node_id),
            ca_file=Path(args.ca_file),
            client_certificate=Path(args.client_cert),
            client_private_key=Path(args.client_key),
            timeout_seconds=args.timeout,
        )

        if args.command == "identity":
            authenticated = probe.authenticate()
            print(
                json.dumps(
                    {
                        "authenticated": authenticated,
                        "node_id": str(probe.enrollment.node.node_id),
                        "name": probe.enrollment.node.name,
                        "endpoint": (
                            f"https://{probe.endpoint.hostname}:{probe.endpoint.port}"
                        ),
                    },
                    sort_keys=True,
                )
            )
            return 0 if authenticated else 3

        if args.command == "capabilities":
            inventory = probe.capabilities()
            print(
                json.dumps(
                    {
                        "node_id": str(inventory.node_id),
                        "observed_at": inventory.observed_at.isoformat(),
                        "source": inventory.source,
                        "capabilities": [
                            {
                                "name": capability.name,
                                "operations": list(capability.operations),
                            }
                            for capability in inventory.capabilities
                        ],
                    },
                    sort_keys=True,
                )
            )
            return 0

        result = probe.invoke(
            capability=args.capability,
            operation=args.operation,
            parameters=_parameters(args.parameter),
            max_inventory_age_seconds=args.max_inventory_age,
        )
        print(
            json.dumps(
                {
                    "request_id": str(result.request_id),
                    "node_id": str(result.node_id),
                    "outcome": result.outcome.value,
                    "message": result.message,
                },
                sort_keys=True,
            )
        )
        return 0
    except Exception as exc:
        print(f"Fleet probe failed: {type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
