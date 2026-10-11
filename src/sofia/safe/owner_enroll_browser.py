"""Attended Windows Hello first registration; supervised later FIDO2 registrations.

This process only binds to 127.0.0.1, cannot run in a service session, and
requires the operator's interactive approval for the initial Venus trust root.
No API endpoint can self-enroll a key by supplying a display name.
"""
from __future__ import annotations

import ctypes
from contextlib import closing
from datetime import datetime, timezone
from hashlib import sha256
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
from queue import Empty, Queue
import secrets
import socket
import sys
from threading import Lock, Thread
from urllib.parse import parse_qs, urlsplit
import webbrowser

from sofia.safe.owner_registration import parse_registration, persist_enrollment
from sofia.safe.owner_webauthn import OwnerWebAuthnVerifier, _b64, _unb64


_HTML = """<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sofía owner credential registration</title>
<body><main><h1>Register Sofía owner credential</h1>
<pre id="details">__REVIEW__</pre>
<p>The first credential uses Windows Hello. Add and backup security keys only
after verifying an already enrolled owner credential.</p>
<button id="enroll">Begin supervised registration</button>
<pre id="status">No credential registered.</pre></main>
<script>
const options=__OPTIONS__;
const status=document.getElementById('status');
const decode=s=>Uint8Array.from(atob(s.replace(/-/g,'+').replace(/_/g,'/')
  .padEnd(Math.ceil(s.length/4)*4,'=')),c=>c.charCodeAt(0));
const encode=b=>btoa(String.fromCharCode(...new Uint8Array(b)))
  .replace(/\\+/g,'-').replace(/\\//g,'_').replace(/=+$/,'');
document.getElementById('enroll').addEventListener('click',async()=>{
 const button=document.getElementById('enroll');button.disabled=true;
 try{
  if(!window.isSecureContext || !window.PublicKeyCredential) throw Error('WebAuthn unavailable');
  let existing=null;
  if(options.owner_proof){
   const x=options.owner_proof;
   const att=await navigator.credentials.get({publicKey:{
     rpId:options.rp_id,challenge:decode(x.challenge),
     allowCredentials:x.allow_credentials.map(id=>({
       id:decode(id),type:'public-key'})),
     userVerification:'required',timeout:90000}});
   if(!att) throw Error('Owner verification was canceled');
   existing={credential_id:att.id,
     client_data_json:encode(att.response.clientDataJSON),
     authenticator_data:encode(att.response.authenticatorData),
     signature:encode(att.response.signature)};
  }
  const publicKey={
   challenge:decode(options.registration_challenge),
   rp:{id:options.rp_id,name:'Sofía Ada Lyra'},
   user:{id:decode(options.user_id),name:'sofia-owner',displayName:'Sofía Owner'},
   pubKeyCredParams:[{type:'public-key',alg:-7}],
   timeout:90000,attestation:'none',
   authenticatorSelection:{
     authenticatorAttachment:options.kind==='platform'?'platform':'cross-platform',
     userVerification:'required',residentKey:'required'}
  };
  const result=await navigator.credentials.create({publicKey});
  if(!result || result.type!=='public-key') throw Error('No registered credential');
  if(result.authenticatorAttachment !== (options.kind==='platform'?'platform':'cross-platform'))
   throw Error('Authenticator attachment differs from reviewed enrollment type');
  const payload={
   credential_id:result.id,
   client_data_json:encode(result.response.clientDataJSON),
   attestation_object:encode(result.response.attestationObject),
   attachment:result.authenticatorAttachment,owner_proof:existing};
  const response=await fetch(options.finish,{method:'POST',
    headers:{'Content-Type':'application/json'},cache:'no-store',
    body:JSON.stringify(payload)});
  if(!response.ok) throw Error('Sofía rejected this registration');
  status.textContent='Credential saved with canonical SAFE audit. Close this window.';
 }catch(error){status.textContent='Not enrolled: '+error.message;}
});
</script></body></html>"""


def require_venus_interactive_windows() -> None:
    """Bootstrap authority must originate from an attended Venus user session."""
    if os.name != "nt" or sys.platform != "win32":
        raise PermissionError("attended owner enrollment requires Windows on Venus")
    if socket.gethostname().split(".", 1)[0].casefold() != "venus":
        raise PermissionError("owner credential bootstrap must run on Venus")
    if not sys.stdin.isatty():
        raise PermissionError("owner enrollment requires an interactive terminal")
    session_id = ctypes.c_ulong()
    pid = ctypes.windll.kernel32.GetCurrentProcessId()
    ok = ctypes.windll.kernel32.ProcessIdToSessionId(
        ctypes.c_ulong(pid), ctypes.byref(session_id)
    )
    if not ok or session_id.value == 0:
        raise PermissionError("service/session-0 enrollment is forbidden")


def enroll_attended(
    state_path: Path | str, *, kind: str, existing_credential_id: str | None = None,
    timeout_seconds: int = 120, open_browser=None,
) -> str:
    """Perform one attended WebAuthn create and persist only after verification.

    First enrollment is a Windows Hello platform credential on Venus. Subsequent
    registration requires an owner assertion for this exact registration session.
    Host admission is mandatory. Isolated tests patch the platform guard.
    """
    require_venus_interactive_windows()
    if kind not in ("platform", "security_key"):
        raise ValueError("unknown owner credential role")
    if type(timeout_seconds) is not int or not 15 <= timeout_seconds <= 120:
        raise ValueError("registration timeout must be 15..120 seconds")
    registration_challenge = _b64(secrets.token_bytes(32))
    registration_digest = sha256(registration_challenge.encode("ascii")).hexdigest()
    user_id = _b64(secrets.token_bytes(32))
    token = secrets.token_urlsafe(32)
    finished: Queue[str | Exception] = Queue(maxsize=1)
    admission = Lock()
    attempted = [False]
    shared: dict[str, object] = {}
    first = existing_credential_id is None
    if first and kind != "platform":
        raise PermissionError("only supervised Windows Hello may bootstrap first trust")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def _valid(self):
            path = urlsplit(self.path)
            return (
                self.headers.get("Host") == f"localhost:{self.server.server_port}"
                and path.path in ("/", "/complete")
                and parse_qs(path.query).get("token") == [token]
            )

        def _answer(self, status: int, data: bytes, mime="text/plain"):
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy",
                             "default-src 'none'; script-src 'unsafe-inline'; connect-src 'self'")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if not self._valid() or urlsplit(self.path).path != "/":
                return self._answer(404, b"Not found")
            self._answer(200, shared["html"], "text/html; charset=utf-8")

        def do_POST(self):
            if (
                not self._valid() or urlsplit(self.path).path != "/complete"
                or self.headers.get("Origin") != shared["origin"]
                or self.headers.get_content_type() != "application/json"
            ):
                return self._answer(403, b"Forbidden")
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            if not 0 < length <= 32768:
                return self._answer(413, b"Invalid payload")
            with admission:
                if attempted[0]:
                    return self._answer(409, b"Already attempted")
                attempted[0] = True
            try:
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict) or set(body) != {
                    "credential_id","client_data_json","attestation_object",
                    "attachment","owner_proof"
                }:
                    raise PermissionError("malformed enrollment payload")
                attachment = "platform" if kind == "platform" else "cross-platform"
                if body["attachment"] != attachment:
                    raise PermissionError("wrong reviewed authenticator attachment")
                credential_id, public_der, counter = parse_registration(
                    client_data_json=body["client_data_json"],
                    attestation_object=body["attestation_object"],
                    expected_challenge=registration_challenge,
                    expected_origin=shared["origin"], rp_id="localhost",
                )
                if body["credential_id"] != credential_id:
                    raise PermissionError("client and CTAP credential IDs differ")
                event_id = None
                if not first:
                    auth = body["owner_proof"]
                    if not isinstance(auth, dict) or set(auth) != {
                        "credential_id","client_data_json",
                        "authenticator_data","signature"
                    }:
                        raise PermissionError("missing authenticated existing-owner approval")
                    proof = shared["verifier"].verify(
                        challenge=shared["owner_proof"]["challenge"],
                        credential_id=auth["credential_id"],
                        action_fingerprint=shared["fingerprint"],
                        client_data_json=auth["client_data_json"],
                        authenticator_data=auth["authenticator_data"],
                        signature=auth["signature"],
                        security_key_required=False,
                    )
                    event_id = proof["authentication_event_id"]
                persist_enrollment(
                    shared["verifier"], credential_id=credential_id,
                    public_key_der=public_der, count=counter, kind=kind,
                    first=first, authorizing_event_id=event_id,
                    registration_challenge_digest=registration_digest,
                )
                finished.put_nowait(credential_id)
                self._answer(200, b'{"status":"enrolled"}', "application/json")
            except Exception as exc:
                finished.put_nowait(exc)
                self._answer(403, b'{"status":"denied"}', "application/json")

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    worker = None
    try:
        origin = f"http://localhost:{server.server_port}"
        verifier = OwnerWebAuthnVerifier(state_path, rp_id="localhost", origin=origin)
        with closing(verifier._db()) as db:
            total = db.execute("SELECT COUNT(*) FROM safe_owner_credential").fetchone()[0]
        if first != (total == 0):
            raise PermissionError(
                "first enrollment is irreversible; later enrollment requires an existing signer"
            )
        fingerprint = sha256(
            ("owner.enroll:" + kind + ":" + registration_digest).encode("ascii")
        ).hexdigest()
        proof = None
        if not first:
            proof = verifier.issue(
                credential_id=existing_credential_id,
                action_fingerprint=fingerprint,
                ttl_seconds=timeout_seconds,
            )
        options = {
            "kind":kind, "rp_id":"localhost",
            "registration_challenge":registration_challenge, "user_id":user_id,
            "finish":"/complete?token=" + token, "owner_proof":proof,
        }
        review = json.dumps({
            "type":"FIRST Windows Hello owner trust" if first else "ADD owner credential",
            "kind":kind, "registration_challenge_digest":registration_digest,
            "existing_owner_proof_required":not first,
            "hardware_attestation":"not available with fmt none",
        }, indent=2, sort_keys=True)
        page = (_HTML.replace("__OPTIONS__", json.dumps(options).replace("<", "\\u003c"))
                .replace("__REVIEW__", escape(review, quote=True)))
        shared.update({
            "html":page.encode("utf-8"), "origin":origin,
            "verifier":verifier,"owner_proof":proof,"fingerprint":fingerprint,
        })
        worker = Thread(
            target=server.serve_forever,
            name="sofia-owner-enrollment-local", daemon=True,
        )
        worker.start()
        opener = open_browser or webbrowser.open
        if opener(origin + "/?token=" + token) is False:
            raise RuntimeError("browser did not open")
        try:
            result = finished.get(timeout=timeout_seconds)
        except Empty as exc:
            raise PermissionError("owner registration timed out") from exc
        if isinstance(result, Exception):
            raise PermissionError("WebAuthn owner registration refused") from result
        return result
    finally:
        if worker is not None:
            server.shutdown()
        server.server_close()
        if worker is not None:
            worker.join(timeout=2)
