"""Explicit foreground entry point for Sofía's pinned mTLS fleet agent."""
from __future__ import annotations
import os,sys
from pathlib import Path
from uuid import UUID

from .agent import RemoteAgentConfig,RemoteAgentServer
from .agent_tools import create_default_agent_dispatcher

_REQUIRED=(
    "SOFIA_AGENT_NODE_ID","SOFIA_AGENT_NODE_NAME","SOFIA_AGENT_SERVER_CERT",
    "SOFIA_AGENT_SERVER_KEY","SOFIA_AGENT_CLIENT_CA",
    "SOFIA_AGENT_CLIENT_PUBLIC_KEY_SHA256","SOFIA_AGENT_LEDGER",
)

def _required(name:str)->str:
    value=os.environ.get(name,"").strip()
    if not value: raise ValueError(f"{name} is required")
    return value

def configuration_from_environment()->RemoteAgentConfig:
    for name in _REQUIRED: _required(name)
    return RemoteAgentConfig(
        node_id=UUID(_required("SOFIA_AGENT_NODE_ID")),
        node_name=_required("SOFIA_AGENT_NODE_NAME"),
        listen_host=os.environ.get("SOFIA_AGENT_LISTEN_HOST","0.0.0.0").strip() or "0.0.0.0",
        listen_port=int(os.environ.get("SOFIA_AGENT_LISTEN_PORT","7443")),
        server_certificate=Path(_required("SOFIA_AGENT_SERVER_CERT")),
        server_private_key=Path(_required("SOFIA_AGENT_SERVER_KEY")),
        client_ca_file=Path(_required("SOFIA_AGENT_CLIENT_CA")),
        expected_client_public_key_sha256=_required("SOFIA_AGENT_CLIENT_PUBLIC_KEY_SHA256"),
        ledger_path=Path(_required("SOFIA_AGENT_LEDGER")),
    )

def main()->int:
    try:
        config=configuration_from_environment()
        server=RemoteAgentServer(config,create_default_agent_dispatcher())
        try:
            server.serve_forever()
        finally:
            server.close()
    except (OSError,RuntimeError,TypeError,ValueError) as exc:
        print(f"Sofía fleet agent refused startup: {exc}",file=sys.stderr)
        return 2
    return 0

if __name__=="__main__":
    raise SystemExit(main())
