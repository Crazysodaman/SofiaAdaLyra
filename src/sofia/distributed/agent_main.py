"""Explicit foreground entry point for Sofía's pinned mTLS fleet agent."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any
from uuid import UUID

from .agent import RemoteAgentConfig, RemoteAgentServer
from .agent_tools import create_default_agent_dispatcher
from .inference_service import (
    LocalOllamaInferenceService,
    RemoteInferencePolicy,
)


_REQUIRED = (
    "SOFIA_AGENT_NODE_ID",
    "SOFIA_AGENT_NODE_NAME",
    "SOFIA_AGENT_SERVER_CERT",
    "SOFIA_AGENT_SERVER_KEY",
    "SOFIA_AGENT_CLIENT_CA",
    "SOFIA_AGENT_CLIENT_PUBLIC_KEY_SHA256",
    "SOFIA_AGENT_LEDGER",
)

_CONFIG_KEYS = frozenset(
    {
        "node_id",
        "node_name",
        "listen_host",
        "listen_port",
        "server_certificate",
        "server_private_key",
        "client_ca_file",
        "expected_client_public_key_sha256",
        "ledger_path",
        "protocol_version",
        "inference_models",
        "inference_max_context_size",
        "inference_allow_tools",
    }
)


def _inference_models(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return tuple(
            item.strip()
            for item in value.split(",")
            if item.strip()
        )
    if isinstance(value, (list, tuple)):
        result = []
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise ValueError(
                    "inference_models must contain nonempty strings"
                )
            result.append(item.strip())
        return tuple(result)
    raise ValueError(
        "inference_models must be a list or comma-separated string"
    )


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


def _resolve_path(base: Path, value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} is required")
    path = Path(value)
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def configuration_from_environment() -> RemoteAgentConfig:
    for name in _REQUIRED:
        _required(name)
    return RemoteAgentConfig(
        node_id=UUID(_required("SOFIA_AGENT_NODE_ID")),
        node_name=_required("SOFIA_AGENT_NODE_NAME"),
        listen_host=os.environ.get("SOFIA_AGENT_LISTEN_HOST", "0.0.0.0").strip()
        or "0.0.0.0",
        listen_port=int(os.environ.get("SOFIA_AGENT_LISTEN_PORT", "7443")),
        server_certificate=Path(_required("SOFIA_AGENT_SERVER_CERT")),
        server_private_key=Path(_required("SOFIA_AGENT_SERVER_KEY")),
        client_ca_file=Path(_required("SOFIA_AGENT_CLIENT_CA")),
        expected_client_public_key_sha256=_required(
            "SOFIA_AGENT_CLIENT_PUBLIC_KEY_SHA256"
        ),
        ledger_path=Path(_required("SOFIA_AGENT_LEDGER")),
        protocol_version=os.environ.get(
            "SOFIA_AGENT_PROTOCOL_VERSION", "1.0"
        ).strip() or "1.0",
        inference_models=_inference_models(
            os.environ.get("SOFIA_AGENT_INFERENCE_MODELS", "")
        ),
        inference_max_context_size=int(
            os.environ.get(
                "SOFIA_AGENT_INFERENCE_MAX_CONTEXT_SIZE",
                "65536",
            )
        ),
        inference_allow_tools=os.environ.get(
            "SOFIA_AGENT_INFERENCE_ALLOW_TOOLS",
            "1",
        ).strip().casefold() not in {"0","false","off"},
    )


def configuration_from_file(path: Path | str) -> RemoteAgentConfig:
    target = Path(path).resolve()
    payload = json.loads(target.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("Fleet agent config must be a JSON object")

    unknown = set(payload) - _CONFIG_KEYS
    if unknown:
        raise ValueError(
            "Unsupported Fleet agent config keys: "
            + ", ".join(sorted(str(value) for value in unknown))
        )

    base = target.parent
    try:
        node_id = UUID(str(payload["node_id"]))
        node_name = str(payload["node_name"]).strip()
        server_certificate = _resolve_path(
            base, payload["server_certificate"], "server_certificate"
        )
        server_private_key = _resolve_path(
            base, payload["server_private_key"], "server_private_key"
        )
        client_ca_file = _resolve_path(
            base, payload["client_ca_file"], "client_ca_file"
        )
        ledger_path = _resolve_path(base, payload["ledger_path"], "ledger_path")
        expected_client_pin = str(
            payload["expected_client_public_key_sha256"]
        ).strip()
    except KeyError as exc:
        raise ValueError(f"Missing Fleet agent config key: {exc.args[0]}") from exc

    if not node_name:
        raise ValueError("node_name is required")

    listen_host = str(payload.get("listen_host", "0.0.0.0")).strip() or "0.0.0.0"
    listen_port = int(payload.get("listen_port", 7443))

    return RemoteAgentConfig(
        node_id=node_id,
        node_name=node_name,
        listen_host=listen_host,
        listen_port=listen_port,
        server_certificate=server_certificate,
        server_private_key=server_private_key,
        client_ca_file=client_ca_file,
        expected_client_public_key_sha256=expected_client_pin,
        ledger_path=ledger_path,
        protocol_version=str(payload.get("protocol_version", "1.0")).strip()
        or "1.0",
        inference_models=_inference_models(
            payload.get("inference_models", ())
        ),
        inference_max_context_size=int(
            payload.get("inference_max_context_size", 65536)
        ),
        inference_allow_tools=payload.get(
            "inference_allow_tools",
            True,
        ),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m sofia.distributed.agent_main")
    parser.add_argument(
        "--config",
        help="JSON Fleet-agent configuration file. Environment variables remain supported.",
    )
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="Validate configuration and exit without opening a listener.",
    )
    args = parser.parse_args(argv)

    try:
        config = (
            configuration_from_file(args.config)
            if args.config
            else configuration_from_environment()
        )
        if args.check_config:
            print(
                f"Fleet agent config valid: {config.node_name} "
                f"{config.node_id} {config.listen_host}:{config.listen_port}"
            )
            return 0

        config.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        inference = (
            None
            if not config.inference_models
            else LocalOllamaInferenceService(
                node_id=config.node_id,
                policy=RemoteInferencePolicy(
                    allowed_models=config.inference_models,
                    max_context_size=config.inference_max_context_size,
                    allow_tools=config.inference_allow_tools,
                ),
            )
        )
        server = RemoteAgentServer(
            config,
            create_default_agent_dispatcher(
                inference_models=config.inference_models,
            ),
            inference_handler=None if inference is None else inference.infer,
        )
        try:
            server.serve_forever()
        finally:
            server.close()
    except (
        json.JSONDecodeError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as exc:
        print(f"Sofía fleet agent refused startup: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
