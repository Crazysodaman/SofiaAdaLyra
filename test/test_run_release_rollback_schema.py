"""A release rollback must be compatible with today's data schemas.

The test deliberately isolates the mutation ordering: failure occurs before
canonical release-store rollback or audit event emission.
"""
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from sofia.platform.run.release import ReleaseManager, ReleaseManagerError, directory_sha256


def test_incompatible_old_release_cannot_rollback_canonical_state(tmp_path):
    old_root = tmp_path / "releases" / "old"
    old_root.mkdir(parents=True)
    (old_root / "payload").write_bytes(b"original signed artifact")
    old_manifest = SimpleNamespace(artifact_sha256=directory_sha256(old_root))
    mutations = []

    class Store:
        def active(self):
            return {"release_id": "new", "previous_release_id": "old"}
        def candidate(self, release_id):
            assert release_id == "old"
            return old_manifest
        def rollback_to_previous(self, **kwargs):
            mutations.append("rollback")

    class Audit:
        def append(self, **kwargs):
            mutations.append("audit")

    manager = object.__new__(ReleaseManager)
    manager.store = Store()
    manager.audit = Audit()
    manager.releases_dir = tmp_path / "releases"

    def refuse_incompatible(manifest):
        assert manifest is old_manifest
        raise ReleaseManagerError("previous schema is unsupported")

    manager._verify_compatibility = refuse_incompatible

    with pytest.raises(ReleaseManagerError, match="unsupported"):
        manager.rollback_failed_release(
            failed_release_id="new",
            reason="new schema cannot be read by old wheel",
            now=datetime.now(timezone.utc),
        )
    assert mutations == []
