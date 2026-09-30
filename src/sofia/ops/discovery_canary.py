"""Read-only supervised mTLS discovery canary for one approved Fleet target.

Does not install, register, enroll, approve an endpoint, or write state.
Run from Venus with explicit target and existing controller TLS credentials.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from re import fullmatch
from uuid import UUID

from sofia.ops.agent_discovery import AgentDiscoveryTarget, MtlsAgentDiscoverySource
from sofia.ops.discovery import FleetDiscoveryCoordinator
from sofia.ops.fleet import FleetRegistry


def preview_candidate(source) -> dict:
    observations = source.discover()
    if not observations:
        return {
            "status": "no_verified_agent_observed",
            "persistent_changes": False,
        }
    if len(observations) != 1:
        raise ValueError("read-only canary expects exactly one agent observation")
    observation = observations[0]
    if (
        not observation.capabilities_verified
        or observation.observed_node_id is None
        or not observation.observed_public_key_sha256
        or not {"system.inspect", "ops.telemetry"}.issubset(
            observation.capability_names
        )
    ):
        raise ValueError(
            "mTLS canary requires verified identity and baseline capabilities"
        )
    # Use only an in-memory registry. Never touch production OPS state here.
    result = FleetDiscoveryCoordinator(FleetRegistry()).ingest(observations)
    return {
        "status": "verified_agent_observed_untrusted_candidate",
        "host_id": observation.host_id,
        "endpoint_host": observation.observed_endpoint_hostname,
        "endpoint_port": observation.observed_endpoint_port,
        "node_id": str(observation.observed_node_id),
        "server_public_key_sha256": observation.observed_public_key_sha256,
        "protocol_version": observation.installed_protocol_version,
        "platform": observation.platform,
        "architecture": observation.architecture,
        "capabilities_verified": observation.capabilities_verified,
        "capabilities": list(observation.capability_names),
        "candidate_created_in_memory": result.created_host_ids
        == (observation.host_id,),
        "candidate_trusted": False,
        "enrolled": False,
        "persistent_changes": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m sofia.ops.discovery_canary",
        description="Probe one explicitly approved Fleet endpoint; never enroll.",
    )
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=7443)
    parser.add_argument("--ca-file", default=os.environ.get("SOFIA_REMOTE_CA"))
    parser.add_argument(
        "--client-cert",
        default=os.environ.get("SOFIA_REMOTE_CLIENT_CERT"),
    )
    parser.add_argument(
        "--client-key",
        default=os.environ.get("SOFIA_REMOTE_CLIENT_KEY"),
    )
    parser.add_argument("--expected-node-id")
    parser.add_argument("--expected-name")
    parser.add_argument("--expected-server-key")
    parser.add_argument("--required-protocol", default="1.0")
    parser.add_argument("--timeout", type=float, default=5.0)
    args = parser.parse_args(argv)

    try:
        tls_paths = {
            "--ca-file": args.ca_file,
            "--client-cert": args.client_cert,
            "--client-key": args.client_key,
        }
        for flag, raw in tls_paths.items():
            if not raw or not Path(raw).is_file():
                raise ValueError(
                    f"{flag} must refer to an existing controller credential file"
                )
        if args.expected_node_id is not None:
            expected_node_id = UUID(args.expected_node_id)
        else:
            expected_node_id = None
        if args.expected_server_key is not None and fullmatch(
            r"[0-9a-f]{64}", args.expected_server_key
        ) is None:
            raise ValueError(
                "--expected-server-key must be a lowercase SHA-256 fingerprint"
            )
        source = MtlsAgentDiscoverySource(
            (
                AgentDiscoveryTarget(
                    hostname=args.host,
                    port=args.port,
                    inside_approved_scope=True,
                ),
            ),
            ca_file=Path(args.ca_file),
            client_certificate=Path(args.client_cert),
            client_private_key=Path(args.client_key),
            timeout_seconds=args.timeout,
            required_protocol_version=args.required_protocol,
        )
        result = preview_candidate(source)
        mismatches = []
        if result["status"] != "no_verified_agent_observed":
            if (
                expected_node_id is not None
                and result["node_id"] != str(expected_node_id)
            ):
                mismatches.append("node ID differs from operator expectation")
            if (
                args.expected_name is not None
                and result["host_id"] != args.expected_name
            ):
                mismatches.append("agent name differs from operator expectation")
            if (
                args.expected_server_key is not None
                and result["server_public_key_sha256"]
                != args.expected_server_key
            ):
                mismatches.append(
                    "server public-key fingerprint differs from operator expectation"
                )
        if mismatches:
            result["status"] = "operator_expected_identity_mismatch"
            result["mismatches"] = mismatches
        print(json.dumps(result, sort_keys=True))
        return 0 if result["status"] == (
            "verified_agent_observed_untrusted_candidate"
        ) else 3
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "canary_error",
                    "error_type": type(exc).__name__,
                    "detail": str(exc),
                    "persistent_changes": False,
                },
                sort_keys=True,
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
