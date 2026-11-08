"""D028 receiver tests on a disposable local private store only."""
import hashlib
import os
from pathlib import Path

import pytest

from sofia.platform.ops.library_chunk_receiver import (
    ChunkedArtifactReceiver, ChunkTransferRejected, PinnedChunkTransfer,
)

pytestmark = [
    pytest.mark.pkg_ops,
    pytest.mark.pkg_safe,
    pytest.mark.skipif(os.name != "posix", reason="strict Unix owner-private file modes"),
]


def _setup(tmp_path):
    data = b"alpha-beta-gamma" * 19
    transfer = PinnedChunkTransfer(
        "source-1", "target-1", hashlib.sha256(data).hexdigest(), len(data), 1,
        hashlib.sha256(b"manifest").hexdigest(), 1, "module", "permitted", "public",
    )
    return data, transfer, ChunkedArtifactReceiver(tmp_path / "library", max_bytes=1024 * 1024)


def test_resume_verify_and_publish(tmp_path):
    data, pin, receiver = _setup(tmp_path)
    approve = lambda _pin: True
    n = receiver.append_chunk(
        pin, offset=0, chunk=data[:25],
        chunk_sha256=hashlib.sha256(data[:25]).hexdigest(), authorize=approve,
    )
    assert receiver.received_bytes(pin, authorize=approve) == n == 25
    restarted = ChunkedArtifactReceiver(tmp_path / "library", max_bytes=1024 * 1024)
    assert restarted.append_chunk(
        pin, offset=n, chunk=data[n:],
        chunk_sha256=hashlib.sha256(data[n:]).hexdigest(), authorize=approve,
    ) == len(data)
    assert restarted.finalize(pin, authorize=approve).read_bytes() == data


def test_revoked_grant_denies_before_write(tmp_path):
    data, pin, receiver = _setup(tmp_path)
    with pytest.raises(ChunkTransferRejected):
        receiver.append_chunk(
            pin, offset=0, chunk=data,
            chunk_sha256=hashlib.sha256(data).hexdigest(),
            authorize=lambda _pin: False,
        )
    assert not list(receiver.incoming.iterdir())


def test_corrupt_chunk_and_wrong_resume_cursor_deny(tmp_path):
    data, pin, receiver = _setup(tmp_path)
    with pytest.raises(ChunkTransferRejected):
        receiver.append_chunk(
            pin, offset=0, chunk=data, chunk_sha256="0" * 64,
            authorize=lambda _pin: True,
        )
    with pytest.raises(ChunkTransferRejected):
        receiver.append_chunk(
            pin, offset=1, chunk=data,
            chunk_sha256=hashlib.sha256(data).hexdigest(),
            authorize=lambda _pin: True,
        )


def test_full_size_wrong_final_digest_denied(tmp_path):
    data, pin, receiver = _setup(tmp_path)
    bad = b"x" * len(data)
    receiver.append_chunk(
        pin, offset=0, chunk=bad,
        chunk_sha256=hashlib.sha256(bad).hexdigest(),
        authorize=lambda _pin: True,
    )
    with pytest.raises(ChunkTransferRejected):
        receiver.finalize(pin, authorize=lambda _pin: True)
    assert not list(receiver.completed.iterdir())


def test_symlinked_incoming_data_is_rejected(tmp_path):
    _data, pin, receiver = _setup(tmp_path)
    external = tmp_path / "other"
    external.write_bytes(b"bad")
    (receiver.incoming / (pin.content_sha256 + ".part")).symlink_to(external)
    with pytest.raises(ChunkTransferRejected):
        receiver.received_bytes(pin, authorize=lambda _pin: True)

def test_mid_write_revoke_truncates_unapproved_chunk(tmp_path):
    data, pin, receiver = _setup(tmp_path)
    outcomes = iter((True, True, False))
    with pytest.raises(ChunkTransferRejected):
        receiver.append_chunk(
            pin, offset=0, chunk=data,
            chunk_sha256=hashlib.sha256(data).hexdigest(),
            authorize=lambda _: next(outcomes),
        )
    assert receiver.received_bytes(pin, authorize=lambda _: True) == 0


def test_global_quota_blocks_unrelated_pending_bytes(tmp_path):
    data, pin, receiver = _setup(tmp_path)
    other = b"y" * 19
    alternate = PinnedChunkTransfer(
        "source-2", "target-1", hashlib.sha256(other).hexdigest(), len(other), 1,
        hashlib.sha256(b"manifest").hexdigest(), 1, "module", "permitted", "public",
    )
    receiver.max_bytes = len(data)
    receiver.append_chunk(
        pin, offset=0, chunk=data,
        chunk_sha256=hashlib.sha256(data).hexdigest(),
        authorize=lambda _: True,
    )
    with pytest.raises(ChunkTransferRejected):
        receiver.append_chunk(
            alternate, offset=0, chunk=other,
            chunk_sha256=hashlib.sha256(other).hexdigest(),
            authorize=lambda _: True,
        )


def test_non_distributable_and_private_content_is_denied():
    with pytest.raises(ValueError):
        PinnedChunkTransfer(
            "source", "target", "0" * 64, 1, 1, "1" * 64, 1,
            "module", "non_redistributable", "public",
        )
    with pytest.raises(ValueError):
        PinnedChunkTransfer(
            "source", "target", "0" * 64, 1, 1, "1" * 64, 1,
            "module", "permitted", "private",
        )


def test_replaced_after_hash_cannot_be_published(tmp_path, monkeypatch):
    """The published CAS inode must be the exact inode SHA-256 verified."""
    data, pin, receiver = _setup(tmp_path)
    approve = lambda _: True
    receiver.append_chunk(
        pin, offset=0, chunk=data,
        chunk_sha256=hashlib.sha256(data).hexdigest(), authorize=approve,
    )
    part = receiver.incoming / (pin.content_sha256 + ".part")
    replacement = receiver.incoming / "replacement"
    replacement.write_bytes(b"z" * len(data))
    replacement.chmod(0o600)
    original_link = os.link

    def swap_before_link(source, destination, **kwargs):
        assert Path(source) == part
        os.replace(replacement, part)
        return original_link(source, destination, **kwargs)

    monkeypatch.setattr(os, "link", swap_before_link)
    with pytest.raises(ChunkTransferRejected, match="published object failed identity"):
        receiver.finalize(pin, authorize=approve)
    assert not list(receiver.completed.iterdir())


def test_redirected_library_root_denied_before_creation(tmp_path):
    """A symlink ancestor must not redirect any CAS write outside the root."""
    external = tmp_path / "external"
    external.mkdir()
    redir = tmp_path / "redirect"
    redir.symlink_to(external, target_is_directory=True)
    with pytest.raises((PermissionError, ChunkTransferRejected)):
        ChunkedArtifactReceiver(redir / "library", max_bytes=1024)
    assert not (external / "library").exists()


@pytest.mark.parametrize("bad_id", ["peer\nforged", "peer name", "/root", "..", "peer\x00null"])
def test_transfer_rejects_control_character_peer_ids(bad_id):
    with pytest.raises(ValueError, match="platform identities"):
        PinnedChunkTransfer(
            source_platform_id=bad_id, target_platform_id="target-1",
            content_sha256="a" * 64, size_bytes=5, generation=1,
            manifest_sha256="b" * 64, catalog_revision=1,
            artifact_kind="module", license_distribution="permitted",
            data_class="public",
        )
