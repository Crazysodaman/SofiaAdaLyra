"""Host-side operator commands for secure fleet enrollment, endpoints and grants."""
from __future__ import annotations
import argparse
from datetime import datetime,timedelta,timezone
from pathlib import Path
from uuid import UUID,uuid4

from sofia.config import create_default_configuration
from sofia.distributed.authorization import RemoteGrant
from sofia.distributed.durable import DurableRemoteAuthorization
from sofia.distributed.endpoint_policy import ApprovedEndpoint
from sofia.distributed.endpoint_policy_durable import DurableEndpointPolicy
from sofia.distributed.identity import NodeEnrollment
from sofia.distributed.identity_durable import DurableNodeIdentityRegistry
from sofia.distributed.model import DistributedNode,NodeEndpoint,NodeTransport
from sofia.distributed.tls import public_key_fingerprint_from_pem_certificate

def _paths(state_path:Path)->dict[str,Path]:
    base=state_path.parent
    return {
        "identity":base/"remote-identities.db",
        "endpoint":base/"remote-endpoints.db",
        "grant":base/"remote-grants.db",
    }

def enroll_node(state_path:Path,*,node_id:UUID,name:str,server_certificate:Path,approved_by:str="Sparks")->NodeEnrollment:
    pin=public_key_fingerprint_from_pem_certificate(server_certificate)
    enrollment=NodeEnrollment(DistributedNode(node_id,name),pin,datetime.now(timezone.utc),approved_by)
    paths=_paths(state_path); store=DurableNodeIdentityRegistry(paths["identity"])
    try: store.enroll(enrollment)
    finally: store.close()
    return enrollment

def approve_endpoint(state_path:Path,*,node_id:UUID,hostname:str,port:int,approved_by:str="Sparks")->NodeEndpoint:
    endpoint=NodeEndpoint(hostname,port,NodeTransport.HTTPS)
    paths=_paths(state_path); store=DurableEndpointPolicy(paths["endpoint"])
    try: store.approve(ApprovedEndpoint(node_id,endpoint,approved_by))
    finally: store.close()
    return endpoint

def grant_operation(state_path:Path,*,node_id:UUID,capability:str,operation:str,hours:float,approved_by:str="Sparks")->RemoteGrant:
    if hours<=0: raise ValueError("grant hours must be positive")
    grant=RemoteGrant(uuid4(),node_id,capability,operation,approved_by,datetime.now(timezone.utc)+timedelta(hours=hours))
    paths=_paths(state_path); store=DurableRemoteAuthorization(paths["grant"])
    try: store.add_approved_grant(grant)
    finally: store.close()
    return grant

def revoke_grant(state_path:Path,grant_id:UUID)->None:
    paths=_paths(state_path); store=DurableRemoteAuthorization(paths["grant"])
    try: store.revoke(grant_id)
    finally: store.close()

def retire_node(state_path:Path,node_id:UUID)->None:
    paths=_paths(state_path)
    identities=DurableNodeIdentityRegistry(paths["identity"])
    endpoints=DurableEndpointPolicy(paths["endpoint"])
    grants=DurableRemoteAuthorization(paths["grant"])
    try:
        identities.retire(node_id)
        endpoints.revoke(node_id)
        grants.revoke_node(node_id)
    finally:
        identities.close(); endpoints.close(); grants.close()

def fingerprint_certificate(path:Path)->str:
    return public_key_fingerprint_from_pem_certificate(path)

def _state_path(raw:str|None)->Path:
    if raw: return Path(raw)
    return Path(create_default_configuration().state_path)

def main(argv:list[str]|None=None)->int:
    parser=argparse.ArgumentParser(prog="python -m sofia.distributed.operator")
    parser.add_argument("--state-path")
    sub=parser.add_subparsers(dest="command",required=True)

    fp=sub.add_parser("fingerprint-cert"); fp.add_argument("certificate")

    en=sub.add_parser("enroll")
    en.add_argument("--node-id",required=True); en.add_argument("--name",required=True)
    en.add_argument("--server-cert",required=True); en.add_argument("--approved-by",default="Sparks")

    ep=sub.add_parser("endpoint")
    ep.add_argument("--node-id",required=True); ep.add_argument("--hostname",required=True)
    ep.add_argument("--port",type=int,default=7443); ep.add_argument("--approved-by",default="Sparks")

    gr=sub.add_parser("grant")
    gr.add_argument("--node-id",required=True); gr.add_argument("--capability",required=True)
    gr.add_argument("--operation",required=True); gr.add_argument("--hours",type=float,default=24.0)
    gr.add_argument("--approved-by",default="Sparks")

    rg=sub.add_parser("revoke-grant"); rg.add_argument("--grant-id",required=True)
    rt=sub.add_parser("retire"); rt.add_argument("--node-id",required=True)

    args=parser.parse_args(argv); state=_state_path(args.state_path)
    if args.command=="fingerprint-cert":
        print(fingerprint_certificate(Path(args.certificate))); return 0
    if args.command=="enroll":
        item=enroll_node(state,node_id=UUID(args.node_id),name=args.name,server_certificate=Path(args.server_cert),approved_by=args.approved_by)
        print(f"enrolled {item.node.name} {item.node.node_id} pin={item.public_key_sha256}"); return 0
    if args.command=="endpoint":
        item=approve_endpoint(state,node_id=UUID(args.node_id),hostname=args.hostname,port=args.port,approved_by=args.approved_by)
        print(f"approved {args.node_id} https://{item.hostname}:{item.port}"); return 0
    if args.command=="grant":
        item=grant_operation(state,node_id=UUID(args.node_id),capability=args.capability,operation=args.operation,hours=args.hours,approved_by=args.approved_by)
        print(f"grant {item.grant_id} {item.capability}/{item.operation} expires={item.expires_at.isoformat()}"); return 0
    if args.command=="revoke-grant":
        revoke_grant(state,UUID(args.grant_id)); print("grant revoked"); return 0
    if args.command=="retire":
        retire_node(state,UUID(args.node_id)); print("node retired, endpoint revoked, grants revoked"); return 0
    return 2

if __name__=="__main__":
    raise SystemExit(main())
