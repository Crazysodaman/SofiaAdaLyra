"""Strict-X.509 Windows Fleet rekey/bootstrap canary.

This operator-approved workflow creates a fresh versioned Fleet PKI, prepares
an Artemis bundle from an existing non-secret config template, redeploys the
Windows Fleet agent through the typed CIM bootstrap path, creates a fresh
controller trust database, and performs the first authenticated identity probe.

Failed/older PKI and controller databases are never overwritten or silently
retired by this command.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
from uuid import UUID, uuid4

from sofia.distributed.endpoint_policy import ApprovedEndpoint
from sofia.distributed.endpoint_policy_durable import DurableEndpointPolicy
from sofia.distributed.fleet_probe import FleetNodeProbe
from sofia.distributed.identity import NodeEnrollment
from sofia.distributed.identity_durable import DurableNodeIdentityRegistry
from sofia.distributed.model import DistributedNode, NodeEndpoint, NodeTransport
from sofia.distributed.pki import bootstrap_pair
from sofia.distributed.tls import public_key_fingerprint_from_pem_certificate

from .bootstrap import (
    AgentPackage,
    BootstrapCandidate,
    FleetBootstrapExecutor,
    FleetBootstrapPlanner,
    InstallAuthority,
)
from .windows_bootstrap import WindowsCimBootstrapInstaller, sha256_file


def _local_root() -> Path:
    raw = os.environ.get("LOCALAPPDATA", "").strip()
    if not raw:
        raise RuntimeError("LOCALAPPDATA is required for local Fleet trust material")
    return Path(raw) / "SofiaAdaLyra"


def _fresh_directory(parent: Path, prefix: str) -> Path:
    parent.mkdir(parents=True, exist_ok=True)
    for _ in range(10):
        candidate = parent / f"{prefix}-{uuid4().hex[:12]}"
        if not candidate.exists():
            return candidate
    raise RuntimeError("could not allocate fresh Fleet state directory")


def _prepare_bundle(
    *,
    template_config: Path,
    output_directory: Path,
    pki_result: dict[str, str],
    listen_port: int,
) -> tuple[Path, dict[str, object]]:
    payload = json.loads(template_config.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("Fleet agent template config must be a JSON object")

    payload["listen_port"] = listen_port
    payload["server_certificate"] = "certs/artemis-server.pem"
    payload["server_private_key"] = "certs/artemis-server-key.pem"
    payload["client_ca_file"] = "certs/fleet-ca.pem"
    payload["expected_client_public_key_sha256"] = pki_result[
        "controller_public_key_sha256"
    ]

    certs = output_directory / "certs"
    state = output_directory / "state"
    certs.mkdir(parents=True, exist_ok=False)
    state.mkdir(parents=True, exist_ok=False)
    (output_directory / "agent.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    shutil.copy2(pki_result["ca_certificate"], certs / "fleet-ca.pem")
    shutil.copy2(
        pki_result["server_certificate"],
        certs / "artemis-server.pem",
    )
    shutil.copy2(
        pki_result["server_private_key"],
        certs / "artemis-server-key.pem",
    )
    return output_directory, payload


def _enroll_fresh_controller(
    *,
    state_path: Path,
    node_id: UUID,
    node_name: str,
    server_certificate: Path,
    endpoint_hostname: str,
    endpoint_port: int,
    approved_by: str,
) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    server_pin = public_key_fingerprint_from_pem_certificate(server_certificate)

    identities = DurableNodeIdentityRegistry(state_path.parent / "remote-identities.db")
    try:
        identities.enroll(
            NodeEnrollment(
                DistributedNode(node_id, node_name),
                server_pin,
                datetime.now(timezone.utc),
                approved_by,
            )
        )
    finally:
        identities.close()

    endpoints = DurableEndpointPolicy(state_path.parent / "remote-endpoints.db")
    try:
        endpoints.approve(
            ApprovedEndpoint(
                node_id,
                NodeEndpoint(endpoint_hostname, endpoint_port, NodeTransport.HTTPS),
                approved_by,
            )
        )
    finally:
        endpoints.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m sofia.ops.windows_rekey_bootstrap"
    )
    parser.add_argument("--approve", action="store_true")
    parser.add_argument("--host", required=True)
    parser.add_argument("--node-id", required=True)
    parser.add_argument("--credential-user", required=True)
    parser.add_argument("--template-config", required=True)
    parser.add_argument("--wheel", required=True)
    parser.add_argument("--stage-dir", required=True)
    parser.add_argument("--remote-stage-path", required=True)
    parser.add_argument("--endpoint-host", required=True)
    parser.add_argument("--server-dns", action="append", default=[])
    parser.add_argument("--server-ip", action="append", default=[])
    parser.add_argument("--listen-port", type=int, default=9999)
    parser.add_argument("--controller-name", default="Venus")
    parser.add_argument("--approved-by", default="Sparks")
    args = parser.parse_args(argv)

    if not args.approve:
        print("Fleet strict rekey refused: --approve is required.")
        return 2

    try:
        node_id = UUID(args.node_id)
        local_root = _local_root()
        pki_root = _fresh_directory(local_root, "fleet-pki-strict")
        bundle_root = _fresh_directory(local_root, "artemis-deploy-strict")
        controller_root = _fresh_directory(local_root, "fleet-controller-strict")
        state_path = controller_root / "state.db"

        result = bootstrap_pair(
            output_directory=pki_root,
            server_name=args.host,
            server_dns_names=tuple(args.server_dns) or (args.host, f"{args.host}.local"),
            server_ip_addresses=tuple(args.server_ip),
            controller_name=args.controller_name,
        )
        bundle, payload = _prepare_bundle(
            template_config=Path(args.template_config),
            output_directory=bundle_root,
            pki_result=result,
            listen_port=args.listen_port,
        )

        wheel = Path(args.wheel).resolve()
        package = AgentPackage(
            "sofia-fleet-agent",
            "0.1.0",
            sha256_file(wheel),
            str(wheel),
        )
        candidate = BootstrapCandidate(
            host_id=args.host,
            platform="windows",
            architecture="x86_64",
            discovery_source="operator-approved-strict-x509-rekey",
            inside_approved_scope=True,
            trusted_bootstrap_available=True,
        )
        plan = FleetBootstrapPlanner().plan(
            candidate,
            package,
            authority=InstallAuthority.OPERATOR_APPROVED,
        )
        installer = WindowsCimBootstrapInstaller(
            host=args.host,
            credential_user=args.credential_user,
            bundle_directory=bundle,
            wheel_path=wheel,
            controller_stage_directory=Path(args.stage_dir),
            remote_stage_path=args.remote_stage_path,
            node_id=node_id,
            listen_port=args.listen_port,
        )
        FleetBootstrapExecutor().execute(plan, installer)

        server_cert = Path(result["server_certificate"])
        _enroll_fresh_controller(
            state_path=state_path,
            node_id=node_id,
            node_name=args.host,
            server_certificate=server_cert,
            endpoint_hostname=args.endpoint_host,
            endpoint_port=args.listen_port,
            approved_by=args.approved_by,
        )

        probe = FleetNodeProbe(
            state_path=state_path,
            node_id=node_id,
            ca_file=Path(result["ca_certificate"]),
            client_certificate=Path(result["controller_certificate"]),
            client_private_key=Path(result["controller_private_key"]),
        )
        authenticated = probe.authenticate()
        if not authenticated:
            raise RuntimeError("strict-X.509 Artemis identity probe did not authenticate")

        print(
            json.dumps(
                {
                    "status": "authenticated",
                    "host": args.host,
                    "node_id": str(node_id),
                    "endpoint": f"https://{args.endpoint_host}:{args.listen_port}",
                    "controller_state": str(controller_root),
                    "pki_root": str(pki_root),
                    "server_public_key_sha256": result["server_public_key_sha256"],
                    "controller_public_key_sha256": result[
                        "controller_public_key_sha256"
                    ],
                    "agent_listen_port": payload["listen_port"],
                },
                sort_keys=True,
            )
        )
        return 0
    except Exception as exc:
        print(f"Fleet strict rekey failed: {type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
