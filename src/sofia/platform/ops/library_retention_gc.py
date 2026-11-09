"""D028-05 one-blob owner-governed GC over existing B1 CAS and SAFE.

No sweeping deletion, private-state purge or automatic pressure eviction.
The canonical installed Platform service must hold the B1/RUN pin-revision
lock supplied by hold_pin_revision while this executor also acquires the
same platform-cache lock used by OfflineArtifactCache imports.

No snapshot object or client UI is itself authority. Every mutation consumes
a separate exact one-use owner approval from the existing SAFE SQLite store,
and the pin graph is rebuilt under both locks immediately before unlink.
Unknown graph, pending install, symbolic link, hard link, corrupt cache,
revocation, STOP or mismatched revision => deny without deletion.
"""
from __future__ import annotations

from contextlib import AbstractContextManager
from datetime import datetime, timezone
from hashlib import sha256
import os
from pathlib import Path
import re
import stat
from typing import Callable

from sofia.platform.ops.library_retention_graph import (
    LibraryPinGraph, LibraryRetentionDenied, build_library_pin_graph,
)
from sofia.platform.ops.platform_install import OfflineArtifactCache
from sofia.platform.ops.platform_installation import PlatformInstallationStore
from sofia.platform.run.process_lock import StateProcessLock
from sofia.platform.safe.audit import AuditChain
from sofia.platform.safe.execution_approval import ExecutionApprovalVerifier
from sofia.platform.safe.operator_stop import OperatorStopStore
from sofia.platform.state.private_file import (
    assert_no_redirected_components, assert_owner_private_path,
)

GC_CAPABILITY = "platform.library.gc_one_verified_blob"
_SHA = re.compile(r"[0-9a-f]{64}\Z")


class GovernedLibraryRetention:
    """Internal B1/RUN/SAFE-backed retention executor, not client RPC."""

    def __init__(
        self, *, cache: OfflineArtifactCache, store: PlatformInstallationStore,
        canonical_safe_state: Path | str, platform_id: str,
        run_generation: int,
        independently_verified_assets_for_manifest: Callable[[str], tuple[str, ...]],
        read_current_live_pins: Callable[[], dict[str, tuple[str, ...]]],
        current_host_admit: Callable[[LibraryPinGraph], bool],
        hold_pin_revision: Callable[[], AbstractContextManager],
    ) -> None:
        if not isinstance(cache, OfflineArtifactCache):
            raise LibraryRetentionDenied("single canonical B1 CAS required")
        if not isinstance(store, PlatformInstallationStore):
            raise LibraryRetentionDenied("single canonical B1 install store required")
        for gate in (
            independently_verified_assets_for_manifest, read_current_live_pins,
            current_host_admit, hold_pin_revision,
        ):
            if not callable(gate):
                raise LibraryRetentionDenied("canonical B1/RUN retention authority missing")
        self.cache, self.store = cache, store
        self.safe = Path(canonical_safe_state).absolute()
        assert_no_redirected_components(self.safe, include_leaf=True)
        self.platform_id, self.run_generation = platform_id, run_generation
        self._assets = independently_verified_assets_for_manifest
        self._live = read_current_live_pins
        self._host = current_host_admit
        self._pin_lock = hold_pin_revision

    def _current(self) -> LibraryPinGraph:
        if OperatorStopStore(self.safe).current().active:
            raise LibraryRetentionDenied("operator STOP prevents retention effects")
        graph = build_library_pin_graph(
            store=self.store, platform_id=self.platform_id,
            run_generation=self.run_generation,
            independently_verified_assets_for_manifest=self._assets,
            read_current_live_pins=self._live,
        )
        if self._host(graph) is not True:
            raise LibraryRetentionDenied("current enrolled RUN/SAFE retention denied")
        return graph

    def _object(self, content_sha256: str) -> tuple[Path, int]:
        if type(content_sha256) is not str or _SHA.fullmatch(content_sha256) is None:
            raise LibraryRetentionDenied("exact immutable SHA256 object required")
        self.cache._check_root()
        path = self.cache.root / content_sha256
        assert_no_redirected_components(path, include_leaf=True)
        try:
            details = path.lstat()
        except FileNotFoundError as exc:
            raise LibraryRetentionDenied("selected verified CAS object unavailable") from exc
        if (not stat.S_ISREG(details.st_mode) or details.st_nlink != 1
                or details.st_size < 1 or details.st_size > self.cache.max_bytes):
            raise LibraryRetentionDenied("unsafe, linked or unbounded CAS object")
        assert_owner_private_path(path, directory=False)
        if self.cache.digest(path) != content_sha256:
            raise LibraryRetentionDenied("corrupt CAS content cannot be garbage collected")
        return path, details.st_size

    def preview(self, *, content_sha256: str) -> dict[str, object]:
        """No deletion, approval consumption or install-state inference."""
        graph = self._current()
        path, size = self._object(content_sha256)
        reasons = graph.pin_reasons(content_sha256)
        return {
            "schema": "aegis.platform.library.gc-preview.v1",
            "platform_id": graph.platform_id,
            "run_generation": graph.run_generation,
            "b1_generation": graph.b1_generation,
            "b1_revision_floor": graph.b1_revision_floor,
            "pin_graph_sha256": graph.fingerprint,
            "cache_root": str(self.cache.root),
            "content_sha256": content_sha256,
            "size_bytes": size,
            "pin_reasons": list(reasons),
            "deletion_eligible": not bool(reasons),
            "deletion_executed": False,
            "owner_approved": False,
        }

    def delete_one(
        self, *, content_sha256: str, expected_pin_graph_sha256: str,
        approval_id: str, now: datetime | None = None,
    ) -> dict[str, object]:
        """Recheck B1+SAFE under canonical locks, consume proof, delete one.

        The caller MUST pass the real B1 pin lock, not a fabricated context
        manager. This implementation intentionally cannot authenticate its
        own callback; ONLY the canonical installed service may expose it.
        If physical deletion succeeds but the audit commit fails, report
        OUTCOME_UNKNOWN and reconcile before any retry.
        """
        if (type(approval_id) is not str or not approval_id.strip()
                or type(expected_pin_graph_sha256) is not str
                or _SHA.fullmatch(expected_pin_graph_sha256) is None):
            raise LibraryRetentionDenied("exact owner proof and pinned B1 graph required")
        moment = datetime.now(timezone.utc) if now is None else now
        if not isinstance(moment, datetime) or moment.utcoffset() is None:
            raise LibraryRetentionDenied("aware one-use owner approval time required")
        cache_lock = StateProcessLock(
            self.cache.root / "cache", resource="platform-cache",
            lock_directory=self.cache.root,
        )
        # This lock must freeze B1 stage/activate/rollback/owner/dependency
        # pin revisions, independently of the cache single-writer lock.
        context = self._pin_lock()
        if not hasattr(context, "__enter__") or not hasattr(context, "__exit__"):
            raise LibraryRetentionDenied("canonical B1 pin revision lock unavailable")
        with context:
            with cache_lock:
                first = self.preview(content_sha256=content_sha256)
                if first["pin_graph_sha256"] != expected_pin_graph_sha256:
                    raise LibraryRetentionDenied("B1 pin graph changed before deletion")
                if not first["deletion_eligible"]:
                    raise LibraryRetentionDenied("active, staged or rollback CAS object pinned")
                # The signed approval fingerprint includes the B1 authority,
                # exact digest+length and current RUN generation; never a path
                # chosen by the client or a broad sweep grant.
                params = {
                    "platform_id": first["platform_id"],
                    "run_generation": first["run_generation"],
                    "b1_generation": first["b1_generation"],
                    "b1_revision_floor": first["b1_revision_floor"],
                    "pin_graph_sha256": first["pin_graph_sha256"],
                    "cache_root": first["cache_root"],
                    "b1_store": str(self.store.path),
                    "content_sha256": content_sha256,
                    "size_bytes": first["size_bytes"],
                }
                verifier = ExecutionApprovalVerifier(self.safe)
                audit = AuditChain(self.safe)
                approval = verifier.consume(
                    approval_id=approval_id, capability=GC_CAPABILITY,
                    parameters=params, now=moment,
                )
                # Revocation/STOP or stale B1 pin state after owner proof
                # must deny, even though the one-use approval is consumed.
                second = self.preview(content_sha256=content_sha256)
                if (second["pin_graph_sha256"] != first["pin_graph_sha256"]
                        or second["size_bytes"] != first["size_bytes"]
                        or not second["deletion_eligible"]):
                    raise LibraryRetentionDenied("retention authority changed after approval")
                path, size = self._object(content_sha256)
                flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
                fd = os.open(path, flags)
                try:
                    before = os.fstat(fd)
                    current = path.lstat()
                    if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
                            or (before.st_dev, before.st_ino, before.st_size)
                            != (current.st_dev, current.st_ino, current.st_size)
                            or before.st_size != size):
                        raise LibraryRetentionDenied("CAS inode changed before unlink")
                    digest = sha256()
                    with os.fdopen(fd, "rb", closefd=False) as reader:
                        while block := reader.read(65536):
                            digest.update(block)
                    if digest.hexdigest() != content_sha256:
                        raise LibraryRetentionDenied("CAS object mutated during GC verification")
                    after = os.fstat(fd)
                    if ((after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                            != (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)):
                        raise LibraryRetentionDenied("CAS object changed during GC read")
                finally:
                    os.close(fd)
                # Last-minute STOP/host gate check before the irreversible
                # unlink. Canonical B1 pin lock freezes graph revisions.
                last = self.preview(content_sha256=content_sha256)
                if last["pin_graph_sha256"] != expected_pin_graph_sha256:
                    raise LibraryRetentionDenied("pin graph changed at GC commit")
                os.unlink(path)
                if os.name != "nt":
                    directory = os.open(
                        self.cache.root,
                        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
                    )
                    try:
                        os.fsync(directory)
                    finally:
                        os.close(directory)
                try:
                    audit_hash = audit.append(
                        actor_id=approval.approved_by,
                        event_type="library.cache.gc.completed",
                        payload={
                            **params, "deletion_verified": not path.exists(),
                            "approval_id": approval_id,
                        },
                        occurred_at=moment,
                        event_id="library-gc:" + approval_id,
                    )
                except Exception as exc:
                    raise RuntimeError(
                        "GC OUTCOME_UNKNOWN: CAS deletion may have succeeded; "
                        "reconcile B1 pins, audit and object existence before retry"
                    ) from exc
                return {
                    **last, "deletion_executed": True,
                    "owner_approved": True,
                    "cache_state": "REMOVED",
                    "audit_event_hash": audit_hash,
                    "install_executed": False,
                }
