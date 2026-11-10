"""D028 durable partial transfer provenance cannot be adopted across peers.

Source, recipient, publisher manifest, RUN generation, catalog revision and
artifact class are all part of the owner-private on-disk resume binding.
No production host, package signature, owner proof or approval is made here.
"""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import os

import pytest

from sofia.platform.ops.library_chunk_receiver import (
    ChunkedArtifactReceiver, ChunkTransferRejected, PinnedChunkTransfer,
)

pytestmark = pytest.mark.skipif(
    os.name != "posix", reason="POSIX private metadata and immutable CAS modes",
)


def setup(tmp_path):
    raw = b"verified-owner-signed-bytes-" * 35
    pin = PinnedChunkTransfer(
        source_platform_id="source-installed",
        target_platform_id="recipient-installed",
        content_sha256=sha256(raw).hexdigest(),
        size_bytes=len(raw), generation=11,
        manifest_sha256="b" * 64, catalog_revision=3,
        artifact_kind="sdk", license_distribution="permitted",
        data_class="public",
    )
    receiver = ChunkedArtifactReceiver(tmp_path / "quarantine", max_bytes=len(raw))
    return raw, pin, receiver


def first_chunk(raw, pin, receiver):
    part = raw[:73]
    assert receiver.append_chunk(
        pin, offset=0, chunk=part,
        chunk_sha256=sha256(part).hexdigest(),
        authorize=lambda _: True,
    ) == len(part)
    return part


def test_restart_resumes_exact_private_transfer_and_removes_scope_on_complete(tmp_path):
    raw, pin, receiver = setup(tmp_path)
    first = first_chunk(raw, pin, receiver)
    scope = receiver.incoming / (pin.content_sha256 + ".scope")
    assert scope.is_file()
    assert scope.stat().st_mode & 0o077 == 0
    restarted = ChunkedArtifactReceiver(receiver.root, max_bytes=len(raw))
    assert restarted.received_bytes(pin, authorize=lambda _: True) == len(first)
    remaining = raw[len(first):]
    assert restarted.append_chunk(
        pin, offset=len(first), chunk=remaining,
        chunk_sha256=sha256(remaining).hexdigest(),
        authorize=lambda _: True,
    ) == len(raw)
    completed = restarted.finalize(pin, authorize=lambda _: True)
    assert completed.read_bytes() == raw
    assert not scope.exists()
    assert not list(restarted.incoming.iterdir())


@pytest.mark.parametrize("change", [
    {"source_platform_id": "unapproved-source"},
    {"target_platform_id": "different-recipient"},
    {"manifest_sha256": "a" * 64},
    {"generation": 12},
    {"catalog_revision": 4},
    {"artifact_kind": "module"},
    {"size_bytes": 9999},
])
def test_existing_partial_refuses_other_signed_scope_even_same_content_sha(
    tmp_path, change,
):
    raw, pin, receiver = setup(tmp_path)
    first_chunk(raw, pin, receiver)
    wrong = replace(pin, **change)
    restarted = ChunkedArtifactReceiver(receiver.root, max_bytes=len(raw))
    with pytest.raises(ChunkTransferRejected, match="scope"):
        restarted.received_bytes(wrong, authorize=lambda _: True)
    assert restarted.received_bytes(pin, authorize=lambda _: True) == 73


def test_orphan_old_partial_without_signed_scope_refused(tmp_path):
    raw, pin, receiver = setup(tmp_path)
    path = receiver.incoming / (pin.content_sha256 + ".part")
    path.write_bytes(raw[:41])
    path.chmod(0o600)
    with pytest.raises(ChunkTransferRejected, match="unbound legacy"):
        receiver.received_bytes(pin, authorize=lambda _: True)
    with pytest.raises(ChunkTransferRejected, match="unbound legacy"):
        receiver.append_chunk(
            pin, offset=41, chunk=raw[41:73],
            chunk_sha256=sha256(raw[41:73]).hexdigest(),
            authorize=lambda _: True,
        )
    assert path.read_bytes() == raw[:41]


def test_scope_tampering_is_denied_without_changing_partial_bytes(tmp_path):
    raw, pin, receiver = setup(tmp_path)
    first_chunk(raw, pin, receiver)
    scope = receiver.incoming / (pin.content_sha256 + ".scope")
    original = scope.read_bytes()
    scope.write_bytes(original.replace(b"source-installed", b"source-UNTRUSTED"))
    with pytest.raises(ChunkTransferRejected, match="scope"):
        receiver.received_bytes(pin, authorize=lambda _: True)
    assert (receiver.incoming / (pin.content_sha256 + ".part")).stat().st_size == 73


def test_scope_symlink_and_extra_storage_entries_fail_closed(tmp_path):
    raw, pin, receiver = setup(tmp_path)
    data = raw[:13]
    external = tmp_path / "external"
    external.write_bytes(b"unsafe")
    external.chmod(0o600)
    fake_scope = receiver.incoming / (pin.content_sha256 + ".scope")
    fake_scope.symlink_to(external)
    with pytest.raises((PermissionError, ChunkTransferRejected)):
        receiver.append_chunk(
            pin, offset=0, chunk=data, chunk_sha256=sha256(data).hexdigest(),
            authorize=lambda _: True,
        )
    fake_scope.unlink()
    extra = receiver.incoming / "unknown_file"
    extra.write_bytes(b"hidden")
    extra.chmod(0o600)
    with pytest.raises(ChunkTransferRejected, match="unexpected quarantine"):
        receiver.append_chunk(
            pin, offset=0, chunk=data, chunk_sha256=sha256(data).hexdigest(),
            authorize=lambda _: True,
        )


def test_private_scope_overhead_cannot_consume_content_quota(tmp_path):
    raw, pin, receiver = setup(tmp_path)
    assert receiver.max_bytes == len(raw)
    assert receiver.append_chunk(
        pin, offset=0, chunk=raw,
        chunk_sha256=sha256(raw).hexdigest(),
        authorize=lambda _: True,
    ) == len(raw)
    assert receiver.finalize(pin, authorize=lambda _: True).read_bytes() == raw



def test_quarantine_writer_is_single_owned_across_two_receiver_instances(tmp_path):
    raw, pin, receiver = setup(tmp_path)
    other = ChunkedArtifactReceiver(receiver.root, max_bytes=len(raw))
    fragment = raw[:73]
    # Cross-process lock also rejects a second handle in the same process.
    # A real process exit releases this OS lock, leaving the durable plan
    # metadata for independently re-authorized recovery.
    with receiver._writer_lock():
        with pytest.raises(RuntimeError, match="already owns"):
            other.append_chunk(
                pin, offset=0, chunk=fragment,
                chunk_sha256=sha256(fragment).hexdigest(),
                authorize=lambda _: True,
            )
        with pytest.raises(RuntimeError, match="already owns"):
            other.received_bytes(pin, authorize=lambda _: True)
    assert other.received_bytes(pin, authorize=lambda _: True) == 0
    assert other.append_chunk(
        pin, offset=0, chunk=fragment,
        chunk_sha256=sha256(fragment).hexdigest(),
        authorize=lambda _: True,
    ) == 73



def test_recover_crash_after_part_unlinked_preserves_verified_bytes(tmp_path):
    """A real interrupted CAS commit is recoverable, not deleted as failure."""
    raw, pin, receiver = setup(tmp_path)
    receiver.append_chunk(
        pin, offset=0, chunk=raw,
        chunk_sha256=sha256(raw).hexdigest(),
        authorize=lambda _: True,
    )
    part = receiver.incoming / (pin.content_sha256 + ".part")
    completed = receiver.completed / pin.content_sha256
    scope = receiver.incoming / (pin.content_sha256 + ".scope")
    # Exact crash window: link published, partial unlinked, original
    # transfer-scope metadata retained until final fsync/cleanup.
    os.link(part, completed)
    part.unlink()
    assert completed.stat().st_nlink == 1
    assert scope.is_file()
    restarted = ChunkedArtifactReceiver(receiver.root, max_bytes=len(raw))
    result = restarted.recover_interrupted_publication(
        pin, authorize=lambda _: True,
    )
    assert result == completed
    assert result.read_bytes() == raw
    assert not scope.exists()


def test_recovery_rejects_wrong_manifest_and_owner_revocation(tmp_path):
    raw, pin, receiver = setup(tmp_path)
    receiver.append_chunk(
        pin, offset=0, chunk=raw,
        chunk_sha256=sha256(raw).hexdigest(),
        authorize=lambda _: True,
    )
    part = receiver.incoming / (pin.content_sha256 + ".part")
    completed = receiver.completed / pin.content_sha256
    os.link(part, completed)
    part.unlink()
    restarted = ChunkedArtifactReceiver(receiver.root, max_bytes=len(raw))
    with pytest.raises(ChunkTransferRejected, match="scope"):
        restarted.recover_interrupted_publication(
            replace(pin, manifest_sha256="f" * 64),
            authorize=lambda _: True,
        )
    with pytest.raises(ChunkTransferRejected, match="SAFE"):
        restarted.recover_interrupted_publication(
            pin, authorize=lambda _: False,
        )
    assert completed.read_bytes() == raw


def test_recovery_rehashes_exact_completed_bytes_before_clearing_scope(tmp_path):
    raw, pin, receiver = setup(tmp_path)
    receiver.append_chunk(
        pin, offset=0, chunk=raw,
        chunk_sha256=sha256(raw).hexdigest(),
        authorize=lambda _: True,
    )
    part = receiver.incoming / (pin.content_sha256 + ".part")
    completed = receiver.completed / pin.content_sha256
    scope = receiver.incoming / (pin.content_sha256 + ".scope")
    os.link(part, completed)
    part.unlink()
    completed.write_bytes(b"x" * len(raw))
    restarted = ChunkedArtifactReceiver(receiver.root, max_bytes=len(raw))
    with pytest.raises(ChunkTransferRejected, match="content changed"):
        restarted.recover_interrupted_publication(
            pin, authorize=lambda _: True,
        )
    assert scope.is_file()
    assert completed.read_bytes() != raw


def test_recovery_refuses_unbound_foreign_completed_object(tmp_path):
    raw, pin, receiver = setup(tmp_path)
    completed = receiver.completed / pin.content_sha256
    completed.write_bytes(raw)
    completed.chmod(0o600)
    with pytest.raises(ChunkTransferRejected, match="unbound completed"):
        receiver.recover_interrupted_publication(
            pin, authorize=lambda _: True,
        )
    assert completed.read_bytes() == raw
