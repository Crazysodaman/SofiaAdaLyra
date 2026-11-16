"""Read-only enforcement for protected Core identity and Constitution state.

No method here creates, rewrites or exports protected state.  Every read is
gated by the Core access policy, and corrupt or substituted state fails closed
with a bounded error that contains no content, path or identity detail.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, TypeVar
from uuid import UUID

from sofia.core.constitution.store import (
    Constitution,
    ConstitutionIntegrityError,
    ConstitutionIntegrityVerifier,
    ConstitutionStore,
)
from sofia.core.identity.model import IdentityBootstrapMode
from sofia.core.identity.store import IdentityStore, IdentityStoreError
from sofia.core.security.boundary import (
    CoreAccessDenied,
    CoreAccessPolicy,
    CoreOperation,
    CoreProtectedResource,
)
from sofia.platform.state.private_file import assert_no_redirected_components


class ProtectedCoreStateError(RuntimeError):
    """Bounded failure for unreadable, corrupt or substituted protected state."""


@dataclass(frozen=True, slots=True)
class ProtectedIdentityView:
    """Owner-only identity projection; never returned to guest/unknown."""

    name: str
    instance_id: UUID


MemoryResult = TypeVar("MemoryResult")


class ProtectedCoreState:
    """Owner-gated strict reader for Core identity and Constitution files.

    ``expected_instance_id`` binds the canonical identity observed by the
    caller so a valid-but-substituted identity cannot silently pass.  Strict
    loading never creates a replacement identity and never rewrites a
    protected file.
    """

    def __init__(
        self,
        *,
        policy: CoreAccessPolicy,
        identity_path: Path,
        constitution_path: Path,
        constitution_hash_path: Path,
        expected_instance_id: UUID | None = None,
        required_audience_id: str | None = None,
    ) -> None:
        if not isinstance(policy, CoreAccessPolicy):
            raise TypeError("policy must be a CoreAccessPolicy")
        for label, value in (
            ("identity_path", identity_path),
            ("constitution_path", constitution_path),
            ("constitution_hash_path", constitution_hash_path),
        ):
            if not isinstance(value, Path):
                raise TypeError(f"{label} must be a Path")
            if not value.is_absolute():
                raise ValueError(f"{label} must be absolute")
            assert_no_redirected_components(value, include_leaf=True)
        if expected_instance_id is not None and not isinstance(
            expected_instance_id, UUID
        ):
            raise TypeError("expected_instance_id must be a UUID or None")
        if required_audience_id is not None and (
            not isinstance(required_audience_id, str)
            or not required_audience_id.strip()
        ):
            raise ValueError("required_audience_id must be None or nonempty text")

        self._policy = policy
        self._identity_path = identity_path
        self._constitution_path = constitution_path
        self._constitution_hash_path = constitution_hash_path
        self._expected_instance_id = expected_instance_id
        self._required_audience_id = required_audience_id

    def _require(
        self,
        principal: object,
        resource: CoreProtectedResource,
        operation: CoreOperation,
        *,
        required_audience: str | None = None,
        adult: bool = False,
    ):
        decision = self._policy.evaluate(
            principal, resource, operation,
            required_audience=required_audience, adult=adult,
        )
        if not decision.allowed:
            raise CoreAccessDenied(decision)
        return decision

    def read_identity(self, principal: object) -> ProtectedIdentityView:
        """Strictly load canonical identity for the authenticated owner."""
        self._require(
            principal, CoreProtectedResource.IDENTITY, CoreOperation.READ,
            required_audience=self._required_audience_id,
        )
        try:
            identity = IdentityStore(
                self._identity_path,
                bootstrap_mode=IdentityBootstrapMode.REQUIRE_EXISTING,
            ).load_strict(expected_instance_id=self._expected_instance_id)
        except (IdentityStoreError, OSError):
            raise ProtectedCoreStateError(
                "protected Core identity failed strict verification"
            ) from None
        return ProtectedIdentityView(
            name=identity.name,
            instance_id=identity.instance_id,
        )

    def read_constitution(self, principal: object) -> Constitution:
        """Strictly load and integrity-verify the authenticated owner's copy."""
        self._require(
            principal, CoreProtectedResource.CONSTITUTION, CoreOperation.READ,
            required_audience=self._required_audience_id,
        )
        try:
            return ConstitutionStore(
                self._constitution_path
            ).load_verified(
                ConstitutionIntegrityVerifier(self._constitution_hash_path)
            )
        except (ConstitutionIntegrityError, OSError):
            raise ProtectedCoreStateError(
                "protected Core Constitution failed integrity verification"
            ) from None

    def read_private_memory(
        self,
        principal: object,
        *,
        audience_id: str,
        loader: Callable[[], MemoryResult],
        adult: bool = False,
    ) -> MemoryResult:
        """Load owner-private memory through the existing memory owner only."""
        if not isinstance(audience_id, str) or not audience_id.strip():
            raise ValueError("audience_id must be nonempty text")
        if not callable(loader):
            raise TypeError("loader must be callable")
        self._require(
            principal, CoreProtectedResource.PRIVATE_MEMORY, CoreOperation.READ,
            required_audience=audience_id, adult=adult,
        )
        return loader()

    def owner_status(self, principal: object) -> dict[str, bool]:
        """Return owner-only health metadata without content or identifiers."""
        self._require(
            principal, CoreProtectedResource.DIAGNOSTICS, CoreOperation.READ,
            required_audience=self._required_audience_id,
        )
        try:
            IdentityStore(
                self._identity_path,
                bootstrap_mode=IdentityBootstrapMode.REQUIRE_EXISTING,
            ).load_strict(expected_instance_id=self._expected_instance_id)
            ConstitutionStore(
                self._constitution_path
            ).load_verified(
                ConstitutionIntegrityVerifier(self._constitution_hash_path)
            )
        except (IdentityStoreError, ConstitutionIntegrityError, OSError):
            raise ProtectedCoreStateError(
                "protected Core state failed strict verification"
            ) from None
        # The identity load exists only to prove strict verification; no
        # name, UUID, hash or content is projected into the status receipt.
        return {"identity_verified": True, "constitution_verified": True}
