"""D028 recipient SAFE/STOP adapter wiring, synthetic controls only.

This proves exact argument forwarding and refusal. It is not an installed
service grant or live owner-secret enrollment test.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from sofia.platform.ops.library_chunk_receiver import PinnedChunkTransfer
from test.test_library_tls_chunk_transport import _transfer
from sofia.platform.safe.permissions import LIBRARY_PEER_SCOPE


def _adapter(monkeypatch):
    import sofia.platform.run.library_peer_gate as gate

    class FakePermissions:
        pass

    class FakeStop:
        pass

    monkeypatch.setattr(gate, "PermissionStore", FakePermissions)
    monkeypatch.setattr(gate, "OperatorStopStore", FakeStop)

    data = b"some-owner-reviewed-public-content"
    original = _transfer(data)
    recipient = gate.CurrentRecipientPeerAuthorizer(
        permissions=FakePermissions(), stop=FakeStop(),
        current_status=lambda: {"platform_id": original.target_platform_id,
                                "generation": original.generation},
        signed_transfer=original,
    )
    return gate, recipient, original


def test_adapter_forwards_exact_selected_scope_to_existing_safe_gate(monkeypatch):
    gate, recipient, transfer = _adapter(monkeypatch)
    seen = []
    def admit(**kwargs):
        seen.append(kwargs)
        return "a" * 64
    monkeypatch.setattr(gate, "admit_owner_enrolled_library_chunk", admit)
    assert recipient(object(), "a" * 64, transfer, 0, 11) is True
    assert len(seen) == 1
    request = seen[0]
    assert request["source_platform_id"] == transfer.source_platform_id
    assert request["target_platform_id"] == transfer.target_platform_id
    assert request["manifest_digest"] == transfer.manifest_sha256
    assert request["content_digest"] == transfer.content_sha256
    assert request["catalog_revision"] == transfer.catalog_revision
    assert request["expected_generation"] == transfer.generation
    assert request["offset"] == 0 and request["length"] == 11
    assert request["total_bytes"] == transfer.size_bytes


def test_adapter_denies_different_transfer_before_invoking_safe(monkeypatch):
    gate, recipient, transfer = _adapter(monkeypatch)
    invoked = []
    monkeypatch.setattr(
        gate, "admit_owner_enrolled_library_chunk",
        lambda **_: invoked.append(True),
    )
    other = PinnedChunkTransfer(
        source_platform_id=transfer.source_platform_id,
        target_platform_id=transfer.target_platform_id,
        content_sha256="f" * 64, size_bytes=transfer.size_bytes,
        generation=transfer.generation, manifest_sha256=transfer.manifest_sha256,
        catalog_revision=transfer.catalog_revision,
        artifact_kind=transfer.artifact_kind,
        license_distribution="permitted", data_class="public",
    )
    with pytest.raises(PermissionError, match="different signed transfer"):
        recipient(object(), "a" * 64, other, 0, 11)
    assert not invoked


def test_adapter_denies_broker_fingerprint_mismatch(monkeypatch):
    gate, recipient, transfer = _adapter(monkeypatch)
    monkeypatch.setattr(
        gate, "admit_owner_enrolled_library_chunk",
        lambda **_: "b" * 64,
    )
    with pytest.raises(PermissionError, match="fingerprint disagrees"):
        recipient(object(), "a" * 64, transfer, 0, 11)


def test_adapter_does_not_translate_unknown_grant_to_success(monkeypatch):
    gate, recipient, transfer = _adapter(monkeypatch)
    def deny(**_):
        raise PermissionError("no current owner SAFE grant")
    monkeypatch.setattr(gate, "admit_owner_enrolled_library_chunk", deny)
    with pytest.raises(PermissionError, match="no current owner SAFE"):
        recipient(object(), "a" * 64, transfer, 0, 11)



def test_exact_scope_builder_matches_canonical_grant_fields(monkeypatch):
    gate, _recipient, transfer = _adapter(monkeypatch)
    now = datetime.now(timezone.utc)
    scope = gate.selected_peer_grant_scope(
        transfer=transfer,
        enrolled_peer_certificate_sha256="a" * 64,
        max_chunk_bytes=min(1024, transfer.size_bytes),
        now=now, expires_at=now + timedelta(minutes=10),
    )
    assert set(scope) == LIBRARY_PEER_SCOPE
    assert scope["content_digest"] == transfer.content_sha256
    assert scope["manifest_digest"] == transfer.manifest_sha256
    assert scope["max_total_bytes"] == transfer.size_bytes
    assert scope["certificate_sha256"] == "a" * 64


def test_scope_builder_refuses_overbroad_or_unreviewed_grants(monkeypatch):
    gate, _recipient, transfer = _adapter(monkeypatch)
    now = datetime.now(timezone.utc)
    cases = (
        ("a" * 64, 1024 * 1024 + 1, now + timedelta(minutes=10)),
        ("a" * 64, 1024, now + timedelta(hours=2)),
        ("not-enrolled", 1024, now + timedelta(minutes=10)),
    )
    for cert, maximum, deadline in cases:
        with pytest.raises(PermissionError):
            gate.selected_peer_grant_scope(
                transfer=transfer,
                enrolled_peer_certificate_sha256=cert,
                max_chunk_bytes=maximum,
                now=now, expires_at=deadline,
            )
