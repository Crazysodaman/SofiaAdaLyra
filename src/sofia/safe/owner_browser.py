"""One-shot localhost WebAuthn ceremony for explicit human-approved execution.

No network interface or unattended scheduler exposure. A challenge never becomes
authority without a signed, user-verified assertion and existing SAFE approval.
Initial credential enrollment is a separate authenticated operator operation.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from html import escape
import json
from pathlib import Path
from queue import Empty, Queue
import secrets
from threading import Lock, Thread
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4
import webbrowser

from sofia.safe.execution_approval import (
    ExecutionApproval, ExecutionApprovalVerifier, execution_fingerprint,
)
from sofia.safe.owner_webauthn import OwnerWebAuthnVerifier
from sofia.safe.permissions import capability_permission_policy, PermissionLevel


_PAGE = """<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sofía secure owner approval</title>
<body><main><h1>Sofía: approve one action</h1>
<p>Review the exact action and target below. No standing permission is granted.</p>
<pre id="action">__ACTION__</pre>
<button id="approve">Verify using passkey or security key</button>
<pre id="status">No approval has been issued.</pre></main>
<script>
const options=__OPTIONS__;
const status=document.getElementById('status');
const fromBase64=s=>Uint8Array.from(atob(s.replace(/-/g,'+').replace(/_/g,'/')
  .padEnd(Math.ceil(s.length/4)*4,'=')),c=>c.charCodeAt(0));
const toBase64=b=>btoa(String.fromCharCode(...new Uint8Array(b)))
  .replace(/\\+/g,'-').replace(/\\//g,'_').replace(/=+$/,'');
document.getElementById('approve').addEventListener('click',async()=>{
  const button=document.getElementById('approve'); button.disabled=true;
  try {
    if(!window.isSecureContext || !navigator.credentials) throw new Error('WebAuthn unavailable');
    const credential=await navigator.credentials.get({publicKey:{
      challenge:fromBase64(options.challenge),rpId:options.rp_id,
      allowCredentials:options.allow_credentials.map(id=>({
        id:fromBase64(id),type:'public-key'})),
      userVerification:'required',timeout:90000}});
    if(!credential) throw new Error('No authenticator assertion returned');
    const body={
      credential_id:credential.id,
      client_data_json:toBase64(credential.response.clientDataJSON),
      authenticator_data:toBase64(credential.response.authenticatorData),
      signature:toBase64(credential.response.signature)};
    const response=await fetch(options.finish,{method:'POST',headers:{
      'Content-Type':'application/json'},body:JSON.stringify(body),cache:'no-store'});
    if(!response.ok) throw new Error('SAFE denied owner authentication');
    status.textContent='Verified. You may close this window.';
  } catch(error){status.textContent='Approval refused: '+error.message;}
});
</script></body></html>"""


def authorize_exact_action(
    state_path: Path | str, *, capability: str, parameters: dict,
    credential_id: str, expires_seconds: int = 120,
    timeout_seconds: int = 120,
    open_browser=None,
) -> ExecutionApproval:
    """Browser-mediated approval for an already enrolled local credential.

    Only browser interaction can perform the WebAuthn assertion. Never accept
    a caller-supplied 'verified=True', supplied username or approval receipt.
    """
    if type(expires_seconds) is not int or not 30 <= expires_seconds <= 900:
        raise ValueError("approval TTL must be 30..900 seconds")
    if type(timeout_seconds) is not int or not 15 <= timeout_seconds <= 120:
        raise ValueError("browser ceremony timeout must be 15..120 seconds")
    exact = execution_fingerprint(capability, parameters)
    protected = (
        capability_permission_policy(capability).level >= PermissionLevel.PROTECTED
    )
    nonce = secrets.token_urlsafe(32)
    done: Queue[ExecutionApproval | Exception] = Queue(maxsize=1)
    admission = Lock()
    consumed = [False]
    holder: dict[str, object] = {}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args) -> None:
            return

        def _valid_request(self) -> bool:
            path = urlsplit(self.path)
            expected = f"localhost:{self.server.server_port}"
            return (
                self.headers.get("Host") == expected
                and path.path in ("/", "/finish")
                and parse_qs(path.query).get("token") == [nonce]
            )

        def _respond(self, status: int, data: bytes, mime: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy",
                             "default-src 'none'; script-src 'unsafe-inline'")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:
            if not self._valid_request() or urlsplit(self.path).path != "/":
                self._respond(404, b"Not found", "text/plain")
                return
            self._respond(200, holder["page"], "text/html; charset=utf-8")

        def do_POST(self) -> None:
            if (
                not self._valid_request() or urlsplit(self.path).path != "/finish"
                or self.headers.get("Origin") != holder["origin"]
                or self.headers.get_content_type() != "application/json"
            ):
                self._respond(403, b"Forbidden", "text/plain")
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                size = 0
            if size <= 0 or size > 32768:
                self._respond(413, b"Invalid payload", "text/plain")
                return
            with admission:
                if consumed[0]:
                    self._respond(409, b"Already attempted", "text/plain")
                    return
                consumed[0] = True
            try:
                assertion = json.loads(self.rfile.read(size))
                if not isinstance(assertion, dict) or set(assertion) != {
                    "credential_id", "client_data_json", "authenticator_data", "signature"
                }:
                    raise PermissionError("malformed assertion")
                now = datetime.now(timezone.utc)
                evidence = holder["verifier"].verify(
                    challenge=holder["challenge"]["challenge"],
                    credential_id=assertion["credential_id"],
                    client_data_json=assertion["client_data_json"],
                    authenticator_data=assertion["authenticator_data"],
                    signature=assertion["signature"],
                    action_fingerprint=exact, security_key_required=protected, now=now,
                )
                approval = ExecutionApproval(
                    approval_id=str(uuid4()), capability=capability,
                    request_fingerprint=exact, approved_by="Sparks",
                    approved_at=now, expires_at=now + timedelta(seconds=expires_seconds),
                )
                ExecutionApprovalVerifier(state_path).record(
                    approval,
                    authentication_event_id=evidence["authentication_event_id"],
                )
                done.put_nowait(approval)
                self._respond(200, b'{"status":"verified"}', "application/json")
            except (OSError, TypeError, ValueError, RuntimeError, PermissionError) as exc:
                done.put_nowait(exc)
                self._respond(403, b'{"status":"denied"}', "application/json")

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    worker = None
    try:
        origin = f"http://localhost:{server.server_port}"
        verifier = OwnerWebAuthnVerifier(
            state_path, rp_id="localhost", origin=origin,
        )
        challenge = verifier.issue(
            credential_id=credential_id, action_fingerprint=exact,
            ttl_seconds=min(120, timeout_seconds),
        )
        options = {**challenge, "finish": "/finish?token=" + nonce}
        review = json.dumps(
            {"capability": capability, "parameters": parameters,
             "action_fingerprint": exact},
            sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False,
        )
        page = (
            _PAGE.replace("__OPTIONS__", json.dumps(options).replace("<", "\\u003c"))
            .replace("__ACTION__", escape(review, quote=True))
        )
        holder.update({"page": page.encode("utf-8"), "verifier": verifier,
                       "challenge": challenge, "origin": origin})
        worker = Thread(target=server.serve_forever, name="sofia-owner-auth-local",
                        daemon=True)
        worker.start()
        url = origin + "/?token=" + nonce
        opener = open_browser or webbrowser.open
        if opener(url) is False:
            raise RuntimeError("could not open local WebAuthn browser")
        try:
            result = done.get(timeout=timeout_seconds)
        except Empty as exc:
            raise PermissionError("owner WebAuthn ceremony timed out") from exc
        if isinstance(result, Exception):
            raise PermissionError("owner authentication denied") from result
        return result
    finally:
        if worker is not None:
            server.shutdown()
        server.server_close()
        if worker is not None:
            worker.join(timeout=2)
