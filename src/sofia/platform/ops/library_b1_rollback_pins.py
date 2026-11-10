"""D028 signed rollback pin evidence from canonical B1 installation history.

A private single-owner Library must never GC the only verified asset needed
to reinstall or roll back a previously accepted Platform release. This
adapter reads the ORIGINAL PlatformInstallationStore, independently verifies
the stored installed release's Ed25519 publisher signature and every asset,
and returns their precise CAS SHA-256 references.

This is NOT the whole retention authority. The installed service must still
hold its real B1 pin-revision lock and supply complete live stage/dependency/
in-flight/operator pin inventories to GovernedLibraryRetention. Missing
history, deleted release trees, revoked signers or torn reads fail CLOSED.
No new SQLite schema, grant, migration, destructive operation or Core state.
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import re

from sofia.platform.ops.library_retention_graph import LibraryRetentionDenied
from sofia.platform.ops.platform_installation import (
    PlatformInstallationStore, _decode_private_json,
    _verify_release_bytes, verify_installed,
)
from sofia.platform.ops.platform_release import PlatformReleaseVerifier
from sofia.platform.state.private_file import assert_no_redirected_components

_SHA = re.compile(r"[0-9a-f]{64}\Z")


class SignedB1RollbackAssetSource:
    """Internal exact B1 history/manifest resolver, never client-supplied."""

    def __init__(
        self, *, store: PlatformInstallationStore,
        verifier: PlatformReleaseVerifier,
        publisher_signer_current: Callable[[str], bool],
    ) -> None:
        if not isinstance(store, PlatformInstallationStore):
            raise LibraryRetentionDenied("canonical B1 installation ledger required")
        if not isinstance(verifier, PlatformReleaseVerifier):
            raise LibraryRetentionDenied("independent installed publisher verifier required")
        if not callable(publisher_signer_current):
            raise LibraryRetentionDenied("current installed publisher revocation required")
        self._store = store
        self._verifier = verifier
        self._signer = publisher_signer_current

    def __call__(self, manifest_sha256: str) -> tuple[str, ...]:
        if type(manifest_sha256) is not str or _SHA.fullmatch(manifest_sha256) is None:
            raise LibraryRetentionDenied("exact signed rollback manifest SHA required")
        if self._store.pending_attempts():
            raise LibraryRetentionDenied("unresolved B1 installation blocks retention decisions")
        checkpoint = self._store.checkpoint()
        generation = checkpoint.generation if checkpoint is not None else 0
        history = [
            row for row in self._store.history()
            if row["result"] == "SUCCEEDED"
            and row["manifest_sha256"] == manifest_sha256
        ]
        if not history or len(history) > 4096:
            raise LibraryRetentionDenied("no exact attested B1 rollback history")

        releases = sorted({row["release_id"] for row in history})
        digests: set[str] = set()
        for release_id in releases:
            receipt = self._store.receipt_for_release(release_id)
            if (receipt is None or receipt["result"] != "SUCCEEDED"
                    or receipt["manifest_sha256"] != manifest_sha256
                    or type(receipt["revision"]) is not int
                    or receipt["revision"] < 1):
                raise LibraryRetentionDenied("signed rollback receipt differs from installed B1 history")
            destination = Path(receipt["destination"]).absolute()
            assert_no_redirected_components(destination, include_leaf=True)
            # Exact B1 provenance and present publisher-trusted files, not
            # merely a matching filename or an unverified manifest JSON.
            verify_installed(
                destination, store=self._store, verifier=self._verifier,
                minimum_revision=receipt["revision"],
            )
            signed = _decode_private_json(destination / "release-signature.json")
            signer_key = signed.get("signer_key_id")
            if (type(signer_key) is not str or not signer_key
                    or self._signer(signer_key) is not True):
                raise LibraryRetentionDenied("installed rollback publisher revoked")
            manifest = _verify_release_bytes(
                destination, verifier=self._verifier,
                minimum_revision=receipt["revision"], expected_source_sha=None,
            )
            if (manifest.digest != manifest_sha256
                    or manifest.release_id != release_id
                    or manifest.revision != receipt["revision"]):
                raise LibraryRetentionDenied("installed B1 signed manifest differs from its receipt")
            references = [item.reference.sha256 for item in manifest.assets]
            if (not references or len(references) > 8192
                    or any(type(digest) is not str or _SHA.fullmatch(digest) is None
                           for digest in references)):
                raise LibraryRetentionDenied("incomplete signed B1 asset inventory")
            digests.update(references)
            if self._signer(signer_key) is not True:
                raise LibraryRetentionDenied("rollback publisher revoked during asset enumeration")

        after = self._store.checkpoint()
        after_generation = after.generation if after is not None else 0
        after_history = [
            (row["receipt_id"], row["release_id"], row["revision"])
            for row in self._store.history()
            if row["result"] == "SUCCEEDED"
            and row["manifest_sha256"] == manifest_sha256
        ]
        before_history = [
            (row["receipt_id"], row["release_id"], row["revision"])
            for row in history
        ]
        if (self._store.pending_attempts()
                or after_generation != generation
                or after_history != before_history):
            raise LibraryRetentionDenied("B1 signed rollback history changed during observation")
        return tuple(sorted(digests))
