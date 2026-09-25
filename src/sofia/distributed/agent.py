"""Pinned mutual-TLS remote fleet agent with typed operations only."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json,sqlite3,ssl
from math import isfinite
from re import fullmatch
from threading import RLock
from pathlib import Path
from typing import Any,Callable,Mapping
from uuid import UUID

from sofia.distributed.capabilities import RemoteCapability
from sofia.distributed.operations import RemoteOutcome
from sofia.distributed.tls import public_key_fingerprint_from_der_certificate

AgentHandler=Callable[[Mapping[str,Any]],Any]
_FORBIDDEN_PARAMETERS=frozenset({"command","commands","cmd","shell","script","executable","argv","arguments","password","token","secret","private_key"})

def _bounded_parameters(parameters:dict[str,Any])->dict[str,Any]:
    clean={}
    for key,value in parameters.items():
        if not isinstance(key,str) or not key.strip() or len(key)>128:
            raise ValueError("invalid remote parameter key")
        if key.lower() in _FORBIDDEN_PARAMETERS:
            raise ValueError("arbitrary execution and secret parameters are forbidden")
        if type(value) not in (str,int,float,bool,type(None)):
            raise TypeError("remote agent accepts bounded JSON scalar parameters only")
        if type(value) is float and not isfinite(value):
            raise ValueError("nonfinite remote parameters are forbidden")
        clean[key]=value
    return clean


@dataclass(frozen=True)
class RemoteAgentConfig:
    node_id:UUID
    node_name:str
    listen_host:str
    listen_port:int
    server_certificate:Path
    server_private_key:Path
    client_ca_file:Path
    expected_client_public_key_sha256:str
    ledger_path:Path
    def __post_init__(self):
        if not self.node_name.strip(): raise ValueError("node_name required")
        if not 1<=self.listen_port<=65535: raise ValueError("listen_port out of range")
        if fullmatch(r"[0-9a-f]{64}",self.expected_client_public_key_sha256) is None: raise ValueError("client public-key pin must be lowercase SHA-256")

class RemoteAgentDispatcher:
    def __init__(self)->None:
        self._handlers:dict[tuple[str,str],AgentHandler]={}
    def register(self,capability:str,operation:str,handler:AgentHandler)->None:
        key=(capability,operation)
        if key in self._handlers: raise ValueError(f"duplicate remote operation: {capability}/{operation}")
        if not capability.strip() or not operation.strip(): raise ValueError("capability and operation required")
        self._handlers[key]=handler
    def inventory(self)->tuple[RemoteCapability,...]:
        grouped:dict[str,list[str]]={}
        for capability,operation in self._handlers:
            grouped.setdefault(capability,[]).append(operation)
        return tuple(RemoteCapability(name,tuple(sorted(ops))) for name,ops in sorted(grouped.items()))
    def execute(self,capability:str,operation:str,parameters:Mapping[str,Any])->Any:
        try: handler=self._handlers[(capability,operation)]
        except KeyError as exc: raise PermissionError("remote operation is not registered") from exc
        return handler(parameters)

class AgentRequestLedger:
    def __init__(self,path:Path)->None:
        path.parent.mkdir(parents=True,exist_ok=True)
        self._db=sqlite3.connect(path,timeout=5.0,check_same_thread=False)
        self._lock=RLock()
        self._db.execute("PRAGMA busy_timeout = 5000")
        self._db.execute("""CREATE TABLE IF NOT EXISTS agent_request (
            request_id TEXT PRIMARY KEY,
            node_id TEXT NOT NULL,
            capability TEXT NOT NULL,
            operation TEXT NOT NULL,
            state TEXT NOT NULL,
            outcome TEXT,
            message TEXT
        )""")
        self._db.commit()
    def reserve(self,request_id:UUID,node_id:UUID,capability:str,operation:str)->tuple[str,str|None,str|None]|None:
        with self._lock:
            row=self._db.execute(
                "SELECT node_id,capability,operation,state,outcome,message FROM agent_request WHERE request_id=?",
                (str(request_id),),
            ).fetchone()
            if row is not None:
                if row[0]!=str(node_id) or row[1]!=capability or row[2]!=operation:
                    raise PermissionError("request ID is already bound to a different remote operation")
                return (row[3],row[4],row[5])
            try:
                with self._db:
                    self._db.execute(
                        "INSERT INTO agent_request(request_id,node_id,capability,operation,state) VALUES(?,?,?,?,?)",
                        (str(request_id),str(node_id),capability,operation,"reserved"),
                    )
            except sqlite3.IntegrityError:
                row=self._db.execute(
                    "SELECT node_id,capability,operation,state,outcome,message FROM agent_request WHERE request_id=?",
                    (str(request_id),),
                ).fetchone()
                if row is None:
                    raise
                if row[0]!=str(node_id) or row[1]!=capability or row[2]!=operation:
                    raise PermissionError("request ID is already bound to a different remote operation")
                return (row[3],row[4],row[5])
            return None
    def finish(self,request_id:UUID,outcome:RemoteOutcome,message:str)->None:
        with self._lock:
            with self._db:
                cursor=self._db.execute(
                    "UPDATE agent_request SET state='final',outcome=?,message=? WHERE request_id=? AND state='reserved'",
                    (outcome.value,message[:1000],str(request_id)),
                )
                if cursor.rowcount!=1: raise RuntimeError("agent request is not reserved")
    def close(self)->None:
        with self._lock: self._db.close()

class RemoteAgentServer:
    def __init__(self,config:RemoteAgentConfig,dispatcher:RemoteAgentDispatcher)->None:
        self.config=config; self.dispatcher=dispatcher; self.ledger=AgentRequestLedger(config.ledger_path)
        owner=self
        class Handler(BaseHTTPRequestHandler):
            server_version="SofiaFleetAgent/1"
            def log_message(self,format,*args): return
            def _authorized_peer(self)->bool:
                cert=self.connection.getpeercert(binary_form=True)
                if not cert: return False
                return public_key_fingerprint_from_der_certificate(cert)==owner.config.expected_client_public_key_sha256
            def _json(self,status:int,payload:Any)->None:
                body=json.dumps(payload,separators=(",",":"),default=str).encode("utf-8")
                self.send_response(status); self.send_header("Content-Type","application/json")
                self.send_header("Content-Length",str(len(body))); self.end_headers(); self.wfile.write(body)
            def _read_json(self)->dict[str,Any]:
                raw_length=self.headers.get("Content-Length","0")
                try: length=int(raw_length)
                except ValueError as exc: raise ValueError("invalid Content-Length") from exc
                if length<0 or length>65536: raise ValueError("request body too large")
                raw=self.rfile.read(length)
                data=json.loads(raw.decode("utf-8")) if raw else {}
                if not isinstance(data,dict): raise ValueError("JSON object required")
                return data
            def do_GET(self):
                if not self._authorized_peer(): self._json(403,{"error":"unauthorized peer"}); return
                if self.path=="/v1/identity":
                    self._json(200,{"node_id":str(owner.config.node_id),"name":owner.config.node_name}); return
                if self.path=="/v1/capabilities":
                    self._json(200,{
                        "node_id":str(owner.config.node_id),
                        "observed_at":datetime.now(timezone.utc).isoformat(),
                        "source":"sofia-pinned-mtls-agent",
                        "capabilities":[{"name":c.name,"operations":list(c.operations)} for c in owner.dispatcher.inventory()],
                    }); return
                self._json(404,{"error":"not found"})
            def do_POST(self):
                if not self._authorized_peer(): self._json(403,{"error":"unauthorized peer"}); return
                if self.path!="/v1/operations": self._json(404,{"error":"not found"}); return
                try:
                    payload=self._read_json()
                    request_id=UUID(payload["request_id"]); node_id=UUID(payload["node_id"])
                    capability=str(payload["capability"]); operation=str(payload["operation"])
                    parameters=payload.get("parameters",{})
                    if node_id!=owner.config.node_id: raise PermissionError("wrong node")
                    if not isinstance(parameters,dict): raise ValueError("parameters must be object")
                    parameters=_bounded_parameters(parameters)
                    existing=owner.ledger.reserve(request_id,node_id,capability,operation)
                    if existing is not None:
                        state,outcome,message=existing
                        if state=="final" and outcome:
                            self._json(200,{"request_id":str(request_id),"node_id":str(node_id),"outcome":outcome,"message":message or ""})
                        else:
                            self._json(409,{"request_id":str(request_id),"node_id":str(node_id),"outcome":RemoteOutcome.UNKNOWN.value,"message":"request already reserved; outcome unknown"})
                        return
                    try:
                        result=owner.dispatcher.execute(capability,operation,parameters)
                        message=json.dumps(result,default=str,ensure_ascii=False) if result is not None else "ok"
                        outcome=RemoteOutcome.REPORTED_SUCCESS
                    except Exception as exc:
                        message=f"{type(exc).__name__}: {exc}"
                        outcome=RemoteOutcome.REPORTED_FAILURE
                    owner.ledger.finish(request_id,outcome,message)
                    self._json(200,{"request_id":str(request_id),"node_id":str(node_id),"outcome":outcome.value,"message":message})
                except (KeyError,TypeError,ValueError,PermissionError) as exc:
                    self._json(400,{"error":f"{type(exc).__name__}: {exc}"})
        self._server=ThreadingHTTPServer((config.listen_host,config.listen_port),Handler)
        context=ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.minimum_version=ssl.TLSVersion.TLSv1_2
        context.verify_mode=ssl.CERT_REQUIRED
        context.load_verify_locations(cafile=str(config.client_ca_file))
        context.load_cert_chain(certfile=str(config.server_certificate),keyfile=str(config.server_private_key))
        self._server.socket=context.wrap_socket(self._server.socket,server_side=True)
    def serve_forever(self)->None: self._server.serve_forever()
    def close(self)->None:
        self._server.shutdown(); self._server.server_close(); self.ledger.close()
