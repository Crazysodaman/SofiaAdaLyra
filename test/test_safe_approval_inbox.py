"""Durable owner approval inbox regressions (synthetic keys; no live host changes)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from base64 import urlsafe_b64encode
from hashlib import sha256
import json
import re
import sqlite3
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from sofia.safe.approval_inbox import ApprovalInbox
from sofia.safe.execution_approval import ExecutionApprovalVerifier
from sofia.safe.owner_webauthn import OwnerWebAuthnVerifier
from sofia.state.canonical_sqlite import bootstrap_canonical_sqlite

pytestmark = pytest.mark.pkg_safe


def _b64(data: bytes) -> str:
    return urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _signed_browser(private_key, credential_id: str, *, after_sign=None):
    """Simulates the hardware/browser in tests; production has no such bypass."""
    def visit(url: str):
        with urlopen(url, timeout=5) as response:
            page = response.read().decode("utf-8")
        assert "Sofía: approve one action" in page
        assert "fleet.enroll" in page
        found = re.search(r"const options=(\{.*?\});", page)
        assert found is not None
        options = json.loads(found.group(1))
        origin = urlsplit(url).scheme + "://" + urlsplit(url).netloc
        client = json.dumps({
            "type": "webauthn.get", "challenge": options["challenge"],
            "origin": origin, "crossOrigin": False,
        }).encode("utf-8")
        data = sha256(b"localhost").digest() + bytes([5]) + (1).to_bytes(4, "big")
        signature = private_key.sign(
            data + sha256(client).digest(), ec.ECDSA(hashes.SHA256()),
        )
        body = json.dumps({
            "credential_id": credential_id,
            "client_data_json": _b64(client),
            "authenticator_data": _b64(data),
            "signature": _b64(signature),
        }).encode("utf-8")
        target = Request(
            origin + options["finish"], data=body, method="POST",
            headers={"Origin": origin, "Content-Type": "application/json"},
        )
        with urlopen(target, timeout=5) as response:
            assert response.status == 200
        if after_sign is not None:
            after_sign()
        return True
    return visit


def _setup(tmp_path, monkeypatch):
    from sofia.safe import owner_browser, owner_enroll_browser

    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    monkeypatch.setattr(
        owner_browser, "require_owner_windows_account",
        lambda path: "S-1-5-21-FAKE-TEST-SID",
    )
    monkeypatch.setattr(
        owner_enroll_browser, "require_owner_windows_account",
        lambda path: "S-1-5-21-FAKE-TEST-SID",
    )
    verifier = OwnerWebAuthnVerifier(
        state, rp_id="localhost", origin="http://localhost:39872",
    )
    signer = ec.generate_private_key(ec.SECP256R1())
    credential_id = _b64(uuid4().bytes)
    der = signer.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    with sqlite3.connect(state) as db:
        db.execute(
            "INSERT INTO safe_owner_credential "
            "(credential_id,public_key_der,credential_kind,sign_count,enrolled_at) "
            "VALUES(?,?,?,?,?)",
            (credential_id, der, "security_key", 0, datetime.now(timezone.utc).isoformat()),
        )
    return state, ApprovalInbox(state), signer, credential_id


def test_request_is_durable_audited_and_never_an_execution_approval(tmp_path):
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    inbox = ApprovalInbox(state)
    args = {"host_id": "Artemis", "scope": ["service", "inspect"]}
    pending = inbox.create("fleet.enroll", args)
    args["scope"].append("MUTATED")
    restarted = ApprovalInbox(state)
    persisted = restarted.get(pending.request_id)
    assert persisted.parameters == {"host_id": "Artemis", "scope": ["service", "inspect"]}
    assert persisted.status == "pending"
    assert persisted.expires_at - persisted.created_at == timedelta(hours=24)
    assert persisted.approval_id is None
    assert restarted.notifications()[0].request_id == pending.request_id
    assert ExecutionApprovalVerifier(state).active_capabilities(
        now=datetime.now(timezone.utc),
    ) == ()
    assert restarted.audit.verify() == (True, None)


def test_expiry_and_crash_recovery_do_not_execute_or_approve(tmp_path):
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    inbox = ApprovalInbox(state)
    base = datetime(2026, 10, 15, tzinfo=timezone.utc)
    expired = inbox.create("fleet.enroll", {"host_id": "Artemis"}, now=base)
    live = inbox.create("fleet.enroll", {"host_id": "Venus"},
                        now=base + timedelta(hours=23))
    assert inbox.recover(now=base + timedelta(hours=24, seconds=1)) == 1
    assert inbox.get(expired.request_id).status == "expired"
    assert inbox.get(live.request_id).status == "pending"
    assert inbox.recover(now=base + timedelta(hours=24, seconds=1)) == 0
    with pytest.raises(PermissionError):
        inbox.approved_receipt(
            live.request_id, capability="fleet.enroll", parameters={"host_id": "Venus"},
        )
    assert inbox.audit.verify()[0]


def test_real_verified_webauthn_is_required_and_bound_to_exact_action(tmp_path, monkeypatch):
    state, inbox, signer, credential_id = _setup(tmp_path, monkeypatch)
    args = {"host_id": "Artemis", "purpose": "enrollment"}
    pending = inbox.create("fleet.enroll", args)
    with pytest.raises(PermissionError):
        inbox.approved_receipt(
            pending.request_id, capability="fleet.enroll", parameters=args,
        )
    approved = inbox.approve_attended(
        pending.request_id, credential_id=credential_id,
        open_browser=_signed_browser(signer, credential_id),
    )
    assert approved.status == "approved"
    assert approved.approval_id is not None
    assert approved.approval_expires_at - datetime.now(timezone.utc) < timedelta(seconds=601)
    assert inbox.approved_receipt(
        pending.request_id, capability="fleet.enroll", parameters=args,
    ) == approved.approval_id
    with pytest.raises(PermissionError, match="differs"):
        inbox.approved_receipt(
            pending.request_id, capability="fleet.enroll",
            parameters={"host_id": "Venus", "purpose": "enrollment"},
        )
    with pytest.raises(PermissionError, match="not pending"):
        inbox.approve_attended(
            pending.request_id, credential_id=credential_id,
            open_browser=lambda url: (_ for _ in ()).throw(AssertionError("replay")),
        )
    ExecutionApprovalVerifier(state).consume(
        approval_id=approved.approval_id, capability="fleet.enroll",
        parameters=args, now=datetime.now(timezone.utc),
    )
    with pytest.raises(PermissionError, match="invalid or consumed"):
        inbox.approved_receipt(
            pending.request_id, capability="fleet.enroll", parameters=args,
        )
    assert inbox.audit.verify()[0]


def test_review_does_not_start_without_authenticated_owner(tmp_path, monkeypatch):
    from sofia.safe import owner_enroll_browser
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    inbox = ApprovalInbox(state)
    pending = inbox.create("fleet.enroll", {"host_id": "Artemis"})
    monkeypatch.setattr(
        owner_enroll_browser, "require_owner_windows_account",
        lambda path: (_ for _ in ()).throw(PermissionError("wrong owner")),
    )
    with pytest.raises(PermissionError, match="wrong owner"):
        inbox.approve_attended(
            pending.request_id, credential_id=_b64(b"fake"),
            open_browser=lambda _: (_ for _ in ()).throw(AssertionError()),
        )
    assert inbox.get(pending.request_id).status == "pending"


def test_expired_review_lease_fences_late_approval(tmp_path, monkeypatch):
    state, inbox, signer, credential_id = _setup(tmp_path, monkeypatch)
    pending = inbox.create("fleet.enroll", {"host_id": "Artemis"})

    def after_sign():
        # Simulate a restart and late completion; original review token loses.
        assert inbox.recover(now=datetime.now(timezone.utc)
                             + timedelta(minutes=4)) == 1

    with pytest.raises(PermissionError, match="superseded"):
        inbox.approve_attended(
            pending.request_id, credential_id=credential_id,
            open_browser=_signed_browser(signer, credential_id, after_sign=after_sign),
        )
    recovered = ApprovalInbox(state)
    assert recovered.get(pending.request_id).status == "pending"
    assert recovered.get(pending.request_id).approval_id is None


def test_owner_denial_and_outbox_retry(tmp_path, monkeypatch):
    state, inbox, _signer, _credential_id = _setup(tmp_path, monkeypatch)
    req = inbox.create("fleet.enroll", {"host_id": "Artemis"})
    with pytest.raises(RuntimeError, match="offline"):
        inbox.deliver_notifications(lambda event: (_ for _ in ()).throw(
            RuntimeError("offline")
        ))
    assert len(inbox.notifications()) == 1
    assert inbox.deny_attended(req.request_id).status == "denied"
    with pytest.raises(PermissionError, match="not pending"):
        inbox.deny_attended(req.request_id)
    sent = []
    assert inbox.deliver_notifications(lambda event: sent.append(event)) == 2
    assert [e.event_type for e in sent] == ["requested", "denied"]
    assert inbox.deliver_notifications(lambda event: sent.append(event)) == 0
    assert not inbox.notifications()
    assert inbox.audit.verify()[0]


def test_missing_canonical_state_fails_closed_without_new_database(tmp_path):
    missing = tmp_path / "missing" / "sofia.db"
    with pytest.raises(FileNotFoundError):
        ApprovalInbox(missing)
    assert not missing.exists()


def test_low_risk_queue_and_non_finite_parameters_refused(tmp_path):
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    inbox = ApprovalInbox(state)
    with pytest.raises(ValueError, match="low-risk"):
        inbox.create("system.inspect", {})
    with pytest.raises(ValueError):
        inbox.create("fleet.enroll", {"oops": float("nan")})


def test_platform_passkey_cannot_approve_protected_inbox_action(tmp_path, monkeypatch):
    state, inbox, signer, credential_id = _setup(tmp_path, monkeypatch)
    with sqlite3.connect(state) as db:
        db.execute(
            "UPDATE safe_owner_credential SET credential_kind='platform' "
            "WHERE credential_id=?", (credential_id,),
        )
    req = inbox.create("fleet.enroll", {"host_id": "Artemis"})
    # The browser's real verifier must reject platform-only proof for L4.
    with pytest.raises(Exception):
        inbox.approve_attended(
            req.request_id, credential_id=credential_id,
            open_browser=_signed_browser(signer, credential_id),
        )
    assert inbox.get(req.request_id).status == "pending"
    assert inbox.get(req.request_id).approval_id is None
    assert not ExecutionApprovalVerifier(state).active_capabilities(
        now=datetime.now(timezone.utc),
    )


def test_owner_can_deny_inflight_review_without_late_authority(tmp_path, monkeypatch):
    state, inbox, signer, credential_id = _setup(tmp_path, monkeypatch)
    req = inbox.create("fleet.enroll", {"host_id": "Artemis"})

    def deny_while_browser_closing():
        inbox.deny_attended(req.request_id)

    with pytest.raises(PermissionError, match="superseded"):
        inbox.approve_attended(
            req.request_id, credential_id=credential_id,
            open_browser=_signed_browser(
                signer, credential_id, after_sign=deny_while_browser_closing,
            ),
        )
    assert inbox.get(req.request_id).status == "denied"
    assert inbox.get(req.request_id).approval_id is None
    assert inbox.audit.verify()[0]


def test_request_cannot_smuggle_unbound_approval_id(tmp_path):
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    inbox = ApprovalInbox(state)
    with pytest.raises(ValueError, match="approval_id"):
        inbox.create("fleet.enroll", {
            "host_id": "Artemis", "approval_id": "untrusted",
        })
