"""Mutual-TLS HTTPS transport for bounded remote fleet operations."""
from __future__ import annotations
from datetime import datetime
from http.client import HTTPSConnection
import json,ssl
from pathlib import Path
from typing import Callable,Any
from uuid import UUID

from sofia.distributed.capabilities import CapabilityInventory,RemoteCapability
from sofia.distributed.identity import NodeEnrollment
from sofia.distributed.model import NodeEndpoint,NodeTransport
from sofia.distributed.operations import RemoteOperationRequest,RemoteOperationResult,RemoteOutcome,RemoteTransport
from sofia.distributed.tls import public_key_fingerprint_from_der_certificate

class HttpsTransportError(RuntimeError): pass

class PinnedHttpsRemoteTransport(RemoteTransport):
    """Authenticated transport using CA validation + mutual TLS + SPKI pinning."""

    def __init__(
        self,
        endpoint_resolver:Callable[[UUID],NodeEndpoint|None],
        *,
        ca_file:Path|str,
        client_certificate:Path|str,
        client_private_key:Path|str,
        timeout_seconds:float=10.0,
    )->None:
        self._endpoint_resolver=endpoint_resolver
        self._ca_file=Path(ca_file)
        self._client_certificate=Path(client_certificate)
        self._client_private_key=Path(client_private_key)
        if timeout_seconds<=0: raise ValueError("timeout_seconds must be positive")
        self._timeout=timeout_seconds

    def _context(self)->ssl.SSLContext:
        context=ssl.create_default_context(ssl.Purpose.SERVER_AUTH,cafile=str(self._ca_file))
        context.minimum_version=ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(certfile=str(self._client_certificate),keyfile=str(self._client_private_key))
        return context

    def _endpoint(self,enrollment:NodeEnrollment)->NodeEndpoint:
        endpoint=self._endpoint_resolver(enrollment.node.node_id)
        if endpoint is None: raise HttpsTransportError("node has no active approved endpoint")
        if endpoint.transport is not NodeTransport.HTTPS:
            raise HttpsTransportError("approved node endpoint is not HTTPS")
        return endpoint

    def _request(self,enrollment:NodeEnrollment,method:str,path:str,payload:Any=None)->Any:
        endpoint=self._endpoint(enrollment)
        body=None if payload is None else json.dumps(payload,separators=(",",":")).encode("utf-8")
        headers={"Accept":"application/json"}
        if body is not None: headers["Content-Type"]="application/json"
        connection=HTTPSConnection(endpoint.hostname,endpoint.port,context=self._context(),timeout=self._timeout)
        try:
            connection.connect()
            sock=connection.sock
            if sock is None: raise HttpsTransportError("TLS socket unavailable")
            peer_cert=sock.getpeercert(binary_form=True)
            if not peer_cert: raise HttpsTransportError("peer did not present a certificate")
            actual=public_key_fingerprint_from_der_certificate(peer_cert)
            if actual!=enrollment.public_key_sha256:
                raise HttpsTransportError("peer TLS public key does not match enrolled node pin")
            connection.request(method,path,body=body,headers=headers)
            response=connection.getresponse()
            raw=response.read()
            if response.status<200 or response.status>=300:
                text=raw.decode("utf-8",errors="replace")[:500]
                raise HttpsTransportError(f"agent HTTP {response.status}: {text}")
            if not raw: return None
            try: return json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError,json.JSONDecodeError) as exc:
                raise HttpsTransportError("agent returned invalid JSON") from exc
        finally:
            connection.close()

    def authenticate(self,enrollment:NodeEnrollment)->bool:
        try:
            data=self._request(enrollment,"GET","/v1/identity")
        except HttpsTransportError:
            return False
        return isinstance(data,dict) and data.get("node_id")==str(enrollment.node.node_id)

    def discover(self,enrollment:NodeEnrollment)->CapabilityInventory:
        data=self._request(enrollment,"GET","/v1/capabilities")
        if not isinstance(data,dict): raise HttpsTransportError("invalid capability inventory response")
        if data.get("node_id")!=str(enrollment.node.node_id):
            raise HttpsTransportError("capability inventory node identity mismatch")
        try:
            observed_at=datetime.fromisoformat(data["observed_at"])
            capabilities=tuple(
                RemoteCapability(str(item["name"]),tuple(str(op) for op in item["operations"]))
                for item in data["capabilities"]
            )
            return CapabilityInventory(
                enrollment.node.node_id,observed_at,capabilities,str(data.get("source") or "https-agent"),
            )
        except (KeyError,TypeError,ValueError) as exc:
            raise HttpsTransportError("invalid capability inventory payload") from exc

    def execute(self,enrollment:NodeEnrollment,request:RemoteOperationRequest)->RemoteOperationResult:
        data=self._request(enrollment,"POST","/v1/operations",{
            "request_id":str(request.request_id),
            "node_id":str(request.node_id),
            "capability":request.capability,
            "operation":request.operation,
            "parameters":dict(request.parameters),
        })
        if not isinstance(data,dict): raise HttpsTransportError("invalid remote operation response")
        try:
            return RemoteOperationResult(
                request_id=UUID(data["request_id"]),
                node_id=UUID(data["node_id"]),
                outcome=RemoteOutcome(data["outcome"]),
                message=str(data.get("message","")),
            )
        except (KeyError,TypeError,ValueError) as exc:
            raise HttpsTransportError("invalid remote operation result payload") from exc
