"""Option A source regression scenarios; authored but NOT executed during coding."""
from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import sqlite3

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

from sofia.safe.owner_registration import parse_registration, persist_enrollment
from sofia.safe.owner_webauthn import OwnerWebAuthnVerifier
from sofia.state.canonical_sqlite import bootstrap_canonical_sqlite


NOW = datetime(2026, 10, 11, 16, tzinfo=timezone.utc)
ORIGIN = "http://localhost:39872"


def b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def cbor(v):
    def head(major, n):
        if n < 24:
            return bytes([major << 5 | n])
        if n < 256:
            return bytes([major << 5 | 24, n])
        if n < 65536:
            return bytes([major << 5 | 25]) + n.to_bytes(2, "big")
        return bytes([major << 5 | 26]) + n.to_bytes(4, "big")

    if type(v) is int:
        return head(0, v) if v >= 0 else head(1, -v - 1)
    if type(v) is bytes:
        return head(2, len(v)) + v
    if type(v) is str:
        raw = v.encode()
        return head(3, len(raw)) + raw
    if type(v) is dict:
        return head(5, len(v)) + b"".join(
            cbor(k) + cbor(value) for k, value in v.items()
        )
    raise TypeError("unsupported test CBOR type")


def registered_data(*, challenge="supervised-registration",
                    origin=ORIGIN, rp_id="localhost", flags=0x45,
                    duplicate_cose=False, credential=b"first-platform-credential"):
    key = ec.generate_private_key(ec.SECP256R1())
    public = key.public_key().public_numbers()
    cose = {
        1: 2, 3: -7, -1: 1,
        -2: public.x.to_bytes(32, "big"),
        -3: public.y.to_bytes(32, "big"),
    }
    cose_bytes = cbor(cose)
    if duplicate_cose:
        cose_bytes += cbor({1: 2})
    auth = (
        sha256(rp_id.encode()).digest() + bytes([flags])
        + (0).to_bytes(4, "big") + bytes(16)
        + len(credential).to_bytes(2, "big") + credential + cose_bytes
    )
    attestation = cbor({"fmt": "none", "attStmt": {}, "authData": auth})
    client = json.dumps({
        "type": "webauthn.create", "challenge": challenge,
        "origin": origin, "crossOrigin": False,
    }).encode()
    return key, {
        "client_data_json": b64(client),
        "attestation_object": b64(attestation),
        "expected_challenge": challenge,
        "expected_origin": ORIGIN,
        "rp_id": "localhost",
    }


def test_real_registration_parser_extracts_public_key_and_credential():
    _, registration = registered_data()
    credential, der, counter = parse_registration(**registration)
    assert credential == b64(b"first-platform-credential")
    assert der.startswith(b"0") and len(der) > 60
    assert counter == 0


@pytest.mark.parametrize("tamper", [
    {"origin":"http://other.invalid"},
    {"rp_id":"other.invalid"},
    {"flags":0x41},
    {"flags":0x05},
    {"duplicate_cose":True},
])
def test_registration_parser_refuses_mismatched_or_non_uv_evidence(tamper):
    _, registration = registered_data(**tamper)
    with pytest.raises(PermissionError):
        parse_registration(**registration)


def test_first_hello_once_then_second_key_requires_signed_platform_proof(
    tmp_path, monkeypatch,
):
    from sofia.safe import owner_enroll_browser

    monkeypatch.setattr(
        owner_enroll_browser, "require_venus_interactive_windows", lambda: None,
    )
    db_path = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    verifier = OwnerWebAuthnVerifier(
        db_path, rp_id="localhost", origin=ORIGIN,
    )
    platform_key, registered = registered_data()
    platform_id, platform_der, count = parse_registration(**registered)
    registration_digest = sha256(b"initial").hexdigest()
    persist_enrollment(
        verifier, credential_id=platform_id, public_key_der=platform_der,
        count=count, kind="platform", first=True,
        authorizing_event_id=None, registration_challenge_digest=registration_digest,
        at=NOW,
    )
    with pytest.raises(PermissionError, match="first enrollment"):
        persist_enrollment(
            verifier, credential_id=b64(b"alternate"),
            public_key_der=platform_der, count=0, kind="platform", first=True,
            authorizing_event_id=None,
            registration_challenge_digest=sha256(b"second").hexdigest(), at=NOW,
        )

    second_digest = sha256(b"second-challenge").hexdigest()
    purpose = sha256(
        ("owner.enroll:security_key:" + second_digest).encode()
    ).hexdigest()
    challenge = verifier.issue(
        credential_id=platform_id, action_fingerprint=purpose,
        now=NOW + timedelta(seconds=1),
    )
    raw = json.dumps({
        "type":"webauthn.get", "challenge":challenge["challenge"],
        "origin":ORIGIN, "crossOrigin":False,
    }).encode()
    auth = sha256(b"localhost").digest() + bytes([5]) + (1).to_bytes(4, "big")
    proof = verifier.verify(
        challenge=challenge["challenge"], credential_id=platform_id,
        action_fingerprint=purpose, client_data_json=b64(raw),
        authenticator_data=b64(auth),
        signature=b64(platform_key.sign(
            auth + sha256(raw).digest(), ec.ECDSA(hashes.SHA256()),
        )),
        security_key_required=False, now=NOW + timedelta(seconds=2),
    )
    physical_key, data2 = registered_data(
        credential=b"reviewed-cross-platform-key",
    )
    second_id, second_der, second_count = parse_registration(**data2)
    with pytest.raises(PermissionError, match="existing owner"):
        persist_enrollment(
            verifier, credential_id=second_id, public_key_der=second_der,
            count=second_count, kind="security_key", first=False,
            authorizing_event_id=None,
            registration_challenge_digest=second_digest, at=NOW + timedelta(seconds=3),
        )
    persist_enrollment(
        verifier, credential_id=second_id, public_key_der=second_der,
        count=second_count, kind="security_key", first=False,
        authorizing_event_id=proof["authentication_event_id"],
        registration_challenge_digest=second_digest, at=NOW + timedelta(seconds=3),
    )
    with sqlite3.connect(db_path) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM safe_owner_credential",
        ).fetchone()[0] == 2
        assert db.execute(
            "SELECT COUNT(*) FROM safe_owner_enrollment_authorization",
        ).fetchone()[0] == 1
    with pytest.raises(PermissionError, match="already spent"):
        persist_enrollment(
            verifier, credential_id=b64(b"another-key"),
            public_key_der=second_der, count=0, kind="security_key",
            first=False, authorizing_event_id=proof["authentication_event_id"],
            registration_challenge_digest=second_digest, at=NOW + timedelta(seconds=4),
        )


def test_production_host_guard_denies_non_windows_and_unattended(monkeypatch):
    from sofia.safe import owner_enroll_browser
    monkeypatch.setattr(owner_enroll_browser.os, "name", "posix", raising=False)
    with pytest.raises(PermissionError, match="Windows on Venus"):
        owner_enroll_browser.require_venus_interactive_windows()
