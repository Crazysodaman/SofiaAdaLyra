"""Loopback-only owner browser approval regressions, NOT executed during coding."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import re
import sqlite3
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4
from base64 import urlsafe_b64encode

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from sofia.safe.owner_browser import authorize_exact_action
from sofia.safe.execution_approval import ExecutionApprovalVerifier
from sofia.safe.owner_webauthn import OwnerWebAuthnVerifier
from sofia.state.canonical_sqlite import bootstrap_canonical_sqlite


def _b64(raw):
    return urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def test_browser_request_shows_exact_action_and_uses_signed_passkey(tmp_path):
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    key = ec.generate_private_key(ec.SECP256R1())
    credential = _b64(uuid4().bytes)
    # Host-trusted enrollment is synthetic here; production lacks this bypass.
    owner = OwnerWebAuthnVerifier(
        state, rp_id="localhost", origin="http://localhost:39872"
    )
    pub = key.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    with sqlite3.connect(state) as db:
        db.execute(
            "INSERT INTO safe_owner_credential "
            "(credential_id,public_key_der,credential_kind,sign_count,enrolled_at) "
            "VALUES(?,?,?,?,?)",
            (credential,pub,"security_key",0,datetime.now(timezone.utc).isoformat()),
        )

    exact = {"host_id": "Artemis", "effect": "restricted-enrollment"}

    def browser(url):
        with urlopen(url, timeout=5) as response:
            source = response.read().decode("utf-8")
        assert "fleet.enroll" in source
        assert "restricted-enrollment" in source
        data = re.search(r"const options=(\{.*?\});", source)
        assert data is not None
        options = json.loads(data.group(1))
        origin = urlsplit(url).scheme + "://" + urlsplit(url).netloc
        raw_client = json.dumps({
            "type": "webauthn.get", "challenge": options["challenge"],
            "origin": origin, "crossOrigin": False,
        }).encode()
        auth_data = sha256(b"localhost").digest() + bytes([5]) + (1).to_bytes(4, "big")
        signature = key.sign(
            auth_data + sha256(raw_client).digest(), ec.ECDSA(hashes.SHA256()),
        )
        payload = json.dumps({
            "credential_id":credential,
            "client_data_json":_b64(raw_client),
            "authenticator_data":_b64(auth_data),
            "signature":_b64(signature),
        }).encode()
        request = Request(
            origin + options["finish"],
            data=payload,
            method="POST",
            headers={"Origin":origin,"Content-Type":"application/json"},
        )
        with urlopen(request, timeout=5) as result:
            assert result.status == 200
        return True

    approval = authorize_exact_action(
        state, capability="fleet.enroll", parameters=exact,
        credential_id=credential, open_browser=browser,
        timeout_seconds=20,
    )
    assert ExecutionApprovalVerifier(state).matches_unconsumed(
        approval_id=approval.approval_id,
        capability="fleet.enroll", parameters=exact,
        now=datetime.now(timezone.utc),
    )


def test_browser_cannot_bootstrap_an_unknown_owner_credential(tmp_path):
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    opened = []
    with pytest.raises(PermissionError, match="enrolled"):
        authorize_exact_action(
            state, capability="fleet.enroll",
            parameters={"host_id": "Artemis"},
            credential_id=_b64(b"unregistered"),
            open_browser=lambda url: opened.append(url),
        )
    assert opened == []
