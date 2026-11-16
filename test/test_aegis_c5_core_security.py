"""Core-owned security boundary, protected-state and STOP continuity contracts.

All principals, files, approvals and STOP state here are disposable synthetic
fixtures under pytest temporary directories.  No production identity,
Constitution, credential or canonical Core database is read or written.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from uuid import UUID

import pytest

from sofia.core.constitution.store import (
    ConstitutionIntegrityError,
    ConstitutionIntegrityVerifier,
    ConstitutionStore,
)
from sofia.core.identity.store import IdentityStore, IdentityStoreError
from sofia.core.security import (
    CoreAccessDenial,
    CoreAccessDenied,
    CoreAccessPolicy,
    CoreOperation,
    CorePrincipalRole,
    CoreProtectedResource,
    CoreSecurityBoundary,
    ProtectedCoreState,
    ProtectedCoreStateError,
    assert_protected_core_path,
)
from sofia.core.social.model import AudienceKind, PrincipalContext
from sofia.core.social.principals import (
    SPARKS_PRINCIPAL_ID,
    local_sparks_principal,
    sofia_core_principal,
)
from sofia.platform.ops.restore_authority import ProtectedRestoreLedger
from sofia.platform.safe.execution_approval import (
    ExecutionApproval,
    ExecutionApprovalVerifier,
    execution_fingerprint,
)
from sofia.platform.safe.operator_stop import OperatorStopStore
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite
from test.aegis_p5_security_support import make_directory_redirect
from test.owner_auth_fixture import record_verified_owner_approval
from test.test_ops_backup_restore import (
    NOW as BACKUP_NOW,
    make_restore_authority,
    mint_replacement,
)

NOW = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)
IDENTITY_UUID = UUID("11111111-1111-4111-8111-111111111111")
OTHER_IDENTITY_UUID = UUID("22222222-2222-4222-8222-222222222222")
CONSTITUTION_TEXT = "# Synthetic Core Constitution\n\nOwner-only rule.\n"


def owner(audience_id: str = "local:text") -> PrincipalContext:
    return local_sparks_principal(audience_id)


def guest(
    *, name: str = "Sparks", audience_id: str = "local:text",
    kind: AudienceKind = AudienceKind.PRIVATE,
) -> PrincipalContext:
    return PrincipalContext(
        principal_id="guest:synthetic-intruder",
        audience_id=audience_id,
        audience_kind=kind,
        display_name=name,
    )


def shared_owner() -> PrincipalContext:
    return PrincipalContext(
        principal_id=SPARKS_PRINCIPAL_ID,
        audience_id="shared:synthetic-room",
        audience_kind=AudienceKind.SHARED,
        display_name="Sparks",
    )


def accept_test_principal(principal: object) -> bool:
    """Explicit test-only verifier for already synthetic authenticated fixtures."""
    return isinstance(principal, PrincipalContext)


def write_identity(
    path: Path, *, instance_id: UUID = IDENTITY_UUID,
    name: str = "Sofia Ada Lyra",
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"name": name, "instance_id": str(instance_id)}),
        encoding="utf-8",
    )
    return path


def write_constitution(
    root: Path, *, content: str = CONSTITUTION_TEXT,
) -> tuple[Path, Path]:
    root.mkdir(parents=True, exist_ok=True)
    document = root / "constitution.md"
    digest = root / "constitution.sha256"
    document.write_text(content, encoding="utf-8")
    digest.write_text(
        sha256(content.encode("utf-8")).hexdigest(), encoding="utf-8",
    )
    return document, digest


def protected_paths(
    tmp_path: Path, *, instance_id: UUID = IDENTITY_UUID,
) -> tuple[Path, Path, Path]:
    identity = write_identity(tmp_path / "protected" / "identity.json",
                              instance_id=instance_id)
    constitution, digest = write_constitution(tmp_path / "protected")
    return identity, constitution, digest


def protected_state(
    tmp_path: Path, *, expected_instance_id: UUID | None = IDENTITY_UUID,
    required_audience_id: str | None = None,
) -> ProtectedCoreState:
    identity, constitution, digest = protected_paths(
        tmp_path,
        instance_id=expected_instance_id or IDENTITY_UUID,
    )
    return ProtectedCoreState(
        policy=CoreAccessPolicy(),
        identity_path=identity,
        constitution_path=constitution,
        constitution_hash_path=digest,
        expected_instance_id=expected_instance_id,
        required_audience_id=required_audience_id,
    )


def stop_store(tmp_path: Path) -> tuple[OperatorStopStore, Path]:
    state = bootstrap_canonical_sqlite(tmp_path / "canonical" / "sofia.db")
    return OperatorStopStore(state), state


def assert_hidden(text: str, *secrets: str) -> None:
    for secret in secrets:
        assert secret not in text


# ---- Core permission enforcement -------------------------------------------


def test_authenticated_private_owner_is_owner():
    decision = CoreAccessPolicy().evaluate(
        owner(), CoreProtectedResource.IDENTITY, CoreOperation.READ,
    )
    assert decision.allowed is True
    assert decision.denial is CoreAccessDenial.NONE


def test_display_name_never_grants_owner_authority():
    policy = CoreAccessPolicy()
    for name in ("Sparks", "owner", "person:sparks", "Sofia Ada Lyra"):
        decision = policy.evaluate(
            guest(name=name),
            CoreProtectedResource.PRIVATE_MEMORY,
            CoreOperation.READ,
            required_audience="local:text",
        )
        assert decision.allowed is False
        assert decision.denial is CoreAccessDenial.ROLE


def test_core_self_assertion_is_never_owner_authority():
    decision = CoreAccessPolicy().evaluate(
        sofia_core_principal(), CoreProtectedResource.IDENTITY,
        CoreOperation.WRITE,
    )
    assert decision.allowed is False
    assert decision.denial is CoreAccessDenial.PRINCIPAL


def test_shared_audience_is_not_owner_even_with_owner_principal_id():
    decision = CoreAccessPolicy().evaluate(
        shared_owner(), CoreProtectedResource.IDENTITY, CoreOperation.READ,
    )
    assert decision.allowed is False
    assert decision.denial is CoreAccessDenial.ROLE


@pytest.mark.parametrize(
    "principal", [None, object(), "person:sparks", {"principal_id": SPARKS_PRINCIPAL_ID}],
)
def test_missing_or_malformed_principal_fails_closed(principal):
    decision = CoreAccessPolicy().evaluate(
        principal, CoreProtectedResource.CONSTITUTION, CoreOperation.READ,
    )
    assert decision.allowed is False
    assert decision.denial is CoreAccessDenial.PRINCIPAL


def test_private_memory_requires_the_exact_owner_audience(tmp_path):
    state = protected_state(tmp_path)
    loaded: list[str] = []
    with pytest.raises(CoreAccessDenied) as denied:
        state.read_private_memory(
            owner("local:text"),
            audience_id="discord:dm:999",
            loader=lambda: loaded.append("private"),
        )
    assert denied.value.decision.denial is CoreAccessDenial.AUDIENCE
    assert loaded == []


def test_owner_private_memory_and_adult_scope_can_be_read():
    policy = CoreAccessPolicy()
    assert policy.evaluate(
        owner(), CoreProtectedResource.PRIVATE_MEMORY, CoreOperation.READ,
        required_audience="local:text", adult=True,
    ).allowed is True
    assert policy.evaluate(
        guest(), CoreProtectedResource.PRIVATE_MEMORY, CoreOperation.READ,
        required_audience="local:text", adult=True,
    ).allowed is False


def test_adult_scope_is_refused_outside_a_private_audience():
    decision = CoreAccessPolicy().evaluate(
        shared_owner(), CoreProtectedResource.PRIVATE_MEMORY,
        CoreOperation.READ, adult=True,
    )
    assert decision.allowed is False
    assert decision.denial is CoreAccessDenial.ADULT


def test_required_protected_audience_rejects_owner_from_another_audience(
    tmp_path,
):
    state = protected_state(tmp_path, required_audience_id="local:text")
    with pytest.raises(CoreAccessDenied) as denied:
        state.read_identity(owner("discord:dm:42"))
    assert denied.value.decision.denial is CoreAccessDenial.AUDIENCE


def test_textual_or_model_proposed_authority_has_no_api_path():
    with pytest.raises(TypeError):
        CoreAccessPolicy().evaluate(
            guest(), CoreProtectedResource.IDENTITY, CoreOperation.WRITE,
            claimed_role="owner",
        )
    with pytest.raises(TypeError):
        CoreAccessPolicy().evaluate(
            guest(), CoreProtectedResource.IDENTITY, CoreOperation.WRITE,
            model_output={"authorized": True},
        )


def test_refusal_receipts_do_not_echo_display_name_or_identity():
    secret_name = "SYNTHETIC-OWNER-DISPLAY-SECRET"
    policy = CoreAccessPolicy()
    decision = policy.evaluate(
        guest(name=secret_name),
        CoreProtectedResource.PRIVATE_MEMORY,
        CoreOperation.READ,
    )
    assert_hidden(repr(decision), secret_name)
    with pytest.raises(CoreAccessDenied) as denied:
        policy.require(
            guest(name=secret_name),
            CoreProtectedResource.PRIVATE_MEMORY,
            CoreOperation.READ,
        )
    assert_hidden(str(denied.value), secret_name)


# ---- Protected identity, Constitution and private memory -------------------


def test_owner_can_strictly_read_identity_and_constitution(tmp_path):
    state = protected_state(tmp_path)
    identity = state.read_identity(owner())
    constitution = state.read_constitution(owner())
    assert identity.instance_id == IDENTITY_UUID
    assert constitution.content == CONSTITUTION_TEXT


def test_guest_and_unknown_never_reach_protected_file_readers(
    tmp_path, monkeypatch,
):
    from sofia.core.security import protected as module

    state = protected_state(tmp_path)

    class _UnreadableIdentity:
        def __init__(self, *args, **kwargs):
            pass

        def load_strict(self, **kwargs):
            raise AssertionError("protected identity must not be read")

    class _UnreadableConstitution:
        def __init__(self, *args, **kwargs):
            pass

        def load_verified(self, *args, **kwargs):
            raise AssertionError("protected constitution must not be read")

    monkeypatch.setattr(module, "IdentityStore", _UnreadableIdentity)
    monkeypatch.setattr(module, "ConstitutionStore", _UnreadableConstitution)
    for principal in (None, guest(), sofia_core_principal(), shared_owner()):
        with pytest.raises(CoreAccessDenied):
            state.read_identity(principal)
        with pytest.raises(CoreAccessDenied):
            state.read_constitution(principal)


def test_generic_diagnostics_are_denied(tmp_path):
    state = protected_state(tmp_path)
    with pytest.raises(CoreAccessDenied) as denied:
        state.owner_status(None)
    assert denied.value.decision.denial is CoreAccessDenial.PRINCIPAL


def test_owner_status_receipt_contains_no_protected_content(tmp_path):
    identity = write_identity(
        tmp_path / "protected" / "identity.json",
        name="SYNTHETIC-IDENTITY-SECRET",
    )
    constitution, digest = write_constitution(
        tmp_path / "protected",
        content="SYNTHETIC-CONSTITUTION-SECRET",
    )
    state = ProtectedCoreState(
        policy=CoreAccessPolicy(),
        identity_path=identity,
        constitution_path=constitution,
        constitution_hash_path=digest,
        expected_instance_id=IDENTITY_UUID,
    )
    status = state.owner_status(owner())
    assert status == {"identity_verified": True, "constitution_verified": True}
    assert_hidden(
        repr(status),
        "SYNTHETIC-IDENTITY-SECRET",
        "SYNTHETIC-CONSTITUTION-SECRET",
        str(IDENTITY_UUID),
    )


def test_private_memory_loader_only_runs_for_exact_owner_audience(tmp_path):
    state = protected_state(tmp_path, required_audience_id="local:text")
    assert state.read_private_memory(
        owner("local:text"),
        audience_id="local:text",
        loader=lambda: ("synthetic-private-record",),
    ) == ("synthetic-private-record",)
    calls: list[str] = []
    for principal, audience in (
        (guest(), "local:text"),
        (owner("local:text"), "discord:dm:999"),
        (shared_owner(), "shared:synthetic-room"),
        (None, "local:text"),
    ):
        with pytest.raises(CoreAccessDenied):
            state.read_private_memory(
                principal, audience_id=audience,
                loader=lambda: calls.append("loaded"),
            )
    assert calls == []


def test_corrupt_identity_fails_closed_without_rewrite(tmp_path):
    state = protected_state(tmp_path)
    path = tmp_path / "protected" / "identity.json"
    original = b"{not valid json"
    path.write_bytes(original)
    with pytest.raises(ProtectedCoreStateError) as failed:
        state.read_identity(owner())
    assert_hidden(str(failed.value), str(path), "Sofia Ada Lyra")
    assert path.read_bytes() == original


def test_substituted_identity_fails_closed_without_rewrite(tmp_path):
    state = protected_state(tmp_path, expected_instance_id=IDENTITY_UUID)
    path = tmp_path / "protected" / "identity.json"
    substituted = json.dumps({
        "name": "Sofia Ada Lyra",
        "instance_id": str(OTHER_IDENTITY_UUID),
    }).encode("utf-8")
    path.write_bytes(substituted)
    with pytest.raises(ProtectedCoreStateError):
        state.read_identity(owner())
    assert path.read_bytes() == substituted


def test_missing_identity_is_not_silently_regenerated(tmp_path):
    state = protected_state(tmp_path)
    path = tmp_path / "protected" / "identity.json"
    path.unlink()
    with pytest.raises(ProtectedCoreStateError):
        state.read_identity(owner())
    assert not path.exists()


def test_tampered_constitution_fails_closed_without_rewrite(tmp_path):
    state = protected_state(tmp_path)
    path = tmp_path / "protected" / "constitution.md"
    tampered = b"# Synthetic Core Constitution\n\nChanged rule.\n"
    path.write_bytes(tampered)
    with pytest.raises(ProtectedCoreStateError) as failed:
        state.read_constitution(owner())
    assert_hidden(str(failed.value), str(path), "Changed rule")
    assert path.read_bytes() == tampered


@pytest.mark.parametrize(
    "trusted_hash", ["a" * 63, "g" * 64, ""],
)
def test_corrupt_trusted_constitution_hash_fails_closed(tmp_path, trusted_hash):
    state = protected_state(tmp_path)
    (tmp_path / "protected" / "constitution.sha256").write_text(
        trusted_hash, encoding="utf-8",
    )
    with pytest.raises(ProtectedCoreStateError):
        state.read_constitution(owner())


def test_unreadable_constitution_fails_closed_without_creation(tmp_path):
    state = protected_state(tmp_path)
    (tmp_path / "protected" / "constitution.md").unlink()
    with pytest.raises(ProtectedCoreStateError):
        state.read_constitution(owner())
    assert not (tmp_path / "protected" / "constitution.md").exists()


def test_owner_status_fails_closed_on_protected_state_tamper(tmp_path):
    state = protected_state(tmp_path)
    (tmp_path / "protected" / "constitution.md").write_text(
        "tampered", encoding="utf-8",
    )
    with pytest.raises(ProtectedCoreStateError):
        state.owner_status(owner())


def test_identity_load_strict_never_creates_missing_state(tmp_path):
    path = tmp_path / "identity.json"
    with pytest.raises(IdentityStoreError):
        IdentityStore(path).load_strict()
    assert not path.exists()


def test_identity_load_strict_refuses_legacy_missing_instance_id(tmp_path):
    path = tmp_path / "identity.json"
    original = b'{"name": "Sofia Ada Lyra"}'
    path.write_bytes(original)
    with pytest.raises(IdentityStoreError):
        IdentityStore(path).load_strict()
    assert path.read_bytes() == original


def test_identity_load_strict_rejects_expected_identity_mismatch(tmp_path):
    path = write_identity(tmp_path / "identity.json")
    with pytest.raises(IdentityStoreError):
        IdentityStore(path).load_strict(expected_instance_id=OTHER_IDENTITY_UUID)


def test_constitution_load_verified_rejects_mismatch(tmp_path):
    constitution, digest = write_constitution(tmp_path)
    digest.write_text("0" * 64, encoding="utf-8")
    with pytest.raises(ConstitutionIntegrityError):
        ConstitutionStore(constitution).load_verified(
            ConstitutionIntegrityVerifier(digest)
        )


# ---- Protected path and redirect checks ------------------------------------


def test_protected_path_inside_root_is_accepted(tmp_path):
    root = tmp_path / "protected"
    root.mkdir()
    path = root / "identity.json"
    assert assert_protected_core_path(path, root=root) == path


def test_protected_path_outside_root_is_denied(tmp_path):
    root = tmp_path / "protected"
    root.mkdir()
    (tmp_path / "other").mkdir()
    with pytest.raises(PermissionError, match="outside"):
        assert_protected_core_path(tmp_path / "other" / "identity.json", root=root)


def test_relative_protected_path_is_denied():
    with pytest.raises(ValueError, match="absolute"):
        assert_protected_core_path(
            Path("protected") / "identity.json", root=Path("protected"),
        )


def test_redirected_protected_path_is_denied(tmp_path):
    actual = tmp_path / "actual"
    actual.mkdir()
    redirected = tmp_path / "redirected"
    make_directory_redirect(redirected, actual)
    with pytest.raises(PermissionError, match="redirection"):
        assert_protected_core_path(redirected / "identity.json", root=redirected)


def test_protected_state_constructor_refuses_redirected_identity(tmp_path):
    root = tmp_path / "protected"
    root.mkdir()
    constitution, digest = write_constitution(root)
    actual = tmp_path / "actual"
    actual.mkdir()
    redirect = tmp_path / "identity-redirect"
    make_directory_redirect(redirect, actual)
    with pytest.raises(PermissionError, match="redirection"):
        ProtectedCoreState(
            policy=CoreAccessPolicy(),
            identity_path=redirect / "identity.json",
            constitution_path=constitution,
            constitution_hash_path=digest,
        )


# ---- SAFE/STOP integration and current authority ---------------------------


def test_stop_between_plan_and_effect_denies_without_effect(tmp_path):
    stop, _ = stop_store(tmp_path)
    boundary = CoreSecurityBoundary(stop=stop, verify_principal=accept_test_principal)
    calls: list[str] = []
    plan = boundary.evaluate(
        owner(), CoreProtectedResource.PRIVATE_MEMORY, CoreOperation.WRITE,
    )
    assert plan.allowed is True
    stop.set(active=True, updated_by="Sparks", reason="synthetic C5 STOP")
    with pytest.raises(CoreAccessDenied) as denied:
        boundary.execute(
            principal=owner(),
            resource=CoreProtectedResource.PRIVATE_MEMORY,
            operation=CoreOperation.WRITE,
            effect=lambda: calls.append("effect"),
        )
    assert denied.value.decision.denial is CoreAccessDenial.OPERATOR_STOP
    assert calls == []


def test_stop_survives_boundary_restart(tmp_path):
    stop, state = stop_store(tmp_path)
    stop.set(active=True, updated_by="Sparks", reason="synthetic restart STOP")
    restarted = CoreSecurityBoundary(stop=OperatorStopStore(state), verify_principal=accept_test_principal)
    with pytest.raises(CoreAccessDenied) as denied:
        restarted.execute(
            principal=owner(),
            resource=CoreProtectedResource.CONSTITUTION,
            operation=CoreOperation.EXPORT,
            effect=lambda: "never",
        )
    assert denied.value.decision.denial is CoreAccessDenial.OPERATOR_STOP


def test_boundary_never_caches_prior_authorization(tmp_path):
    stop, _ = stop_store(tmp_path)
    boundary = CoreSecurityBoundary(stop=stop, verify_principal=accept_test_principal)
    calls: list[str] = []
    boundary.execute(
        principal=owner(),
        resource=CoreProtectedResource.PRIVATE_MEMORY,
        operation=CoreOperation.WRITE,
        effect=lambda: calls.append("first"),
    )
    stop.set(active=True, updated_by="Sparks", reason="synthetic cached STOP")
    with pytest.raises(CoreAccessDenied):
        boundary.execute(
            principal=owner(),
            resource=CoreProtectedResource.PRIVATE_MEMORY,
            operation=CoreOperation.WRITE,
            effect=lambda: calls.append("second"),
        )
    assert calls == ["first"]


def test_unreadable_stop_authority_fails_closed(tmp_path, monkeypatch):
    stop, _ = stop_store(tmp_path)
    boundary = CoreSecurityBoundary(stop=stop, verify_principal=accept_test_principal)

    def unavailable():
        raise FileNotFoundError("synthetic canonical state loss")

    monkeypatch.setattr(stop, "current", unavailable)
    calls: list[str] = []
    with pytest.raises(CoreAccessDenied) as denied:
        boundary.execute(
            principal=owner(),
            resource=CoreProtectedResource.IDENTITY,
            operation=CoreOperation.WRITE,
            effect=lambda: calls.append("effect"),
        )
    assert denied.value.decision.denial is CoreAccessDenial.OPERATOR_STOP
    assert calls == []


def test_public_boundary_cannot_be_constructed_without_a_verifier(tmp_path):
    stop, _ = stop_store(tmp_path)
    with pytest.raises(TypeError, match="verify_principal"):
        CoreSecurityBoundary(stop=stop)


def test_forged_local_owner_is_denied_unless_verifier_authenticates_it(tmp_path):
    stop, _ = stop_store(tmp_path)
    forged = local_sparks_principal()
    denied = CoreSecurityBoundary(
        stop=stop, verify_principal=lambda principal: False,
    )
    plan = denied.evaluate(
        forged, CoreProtectedResource.IDENTITY, CoreOperation.READ,
    )
    assert plan.allowed is False
    assert plan.role is CorePrincipalRole.UNKNOWN
    assert plan.denial is CoreAccessDenial.NOT_AUTHENTICATED

    calls: list[str] = []
    with pytest.raises(CoreAccessDenied) as refused:
        denied.execute(
            principal=forged,
            resource=CoreProtectedResource.PRIVATE_MEMORY,
            operation=CoreOperation.WRITE,
            effect=lambda: calls.append("forged-effect"),
        )
    assert refused.value.decision.role is CorePrincipalRole.UNKNOWN
    assert refused.value.decision.denial is CoreAccessDenial.NOT_AUTHENTICATED
    assert calls == []

    authenticated = CoreSecurityBoundary(
        stop=stop, verify_principal=lambda principal: principal == forged,
    )
    assert authenticated.evaluate(
        forged, CoreProtectedResource.IDENTITY, CoreOperation.READ,
    ).allowed is True


def test_verifier_exception_fails_closed_without_effect(tmp_path):
    stop, _ = stop_store(tmp_path)

    def unavailable(principal):
        raise RuntimeError("synthetic attestation store unavailable")

    boundary = CoreSecurityBoundary(stop=stop, verify_principal=unavailable)
    calls: list[str] = []
    with pytest.raises(CoreAccessDenied) as denied:
        boundary.execute(
            principal=owner(),
            resource=CoreProtectedResource.PRIVATE_MEMORY,
            operation=CoreOperation.WRITE,
            effect=lambda: calls.append("effect"),
        )
    assert denied.value.decision.role is CorePrincipalRole.UNKNOWN
    assert denied.value.decision.denial is CoreAccessDenial.NOT_AUTHENTICATED
    assert calls == []


def test_revoked_attestation_is_rechecked_immediately_before_the_effect(
    tmp_path,
):
    stop, _ = stop_store(tmp_path)
    answers = iter((True, False))

    def revoked_before_effect(principal):
        return next(answers, False)

    boundary = CoreSecurityBoundary(
        stop=stop, verify_principal=revoked_before_effect,
    )
    calls: list[str] = []
    with pytest.raises(CoreAccessDenied) as denied:
        boundary.execute(
            principal=owner(),
            resource=CoreProtectedResource.PRIVATE_MEMORY,
            operation=CoreOperation.WRITE,
            effect=lambda: calls.append("effect"),
        )
    assert denied.value.decision.denial is CoreAccessDenial.NOT_AUTHENTICATED
    assert calls == []


def _current_approval(
    state: Path, *, capability: str = "core.test.protected_effect",
) -> tuple[ExecutionApprovalVerifier, ExecutionApproval, dict]:
    parameters = {"value": "exact"}
    approval = ExecutionApproval(
        approval_id="approval:c5-synthetic",
        capability=capability,
        request_fingerprint=execution_fingerprint(capability, parameters),
        approved_by="Sparks",
        approved_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
    )
    verifier = ExecutionApprovalVerifier(state)
    record_verified_owner_approval(verifier, approval)
    return verifier, approval, parameters


def test_replayed_owner_approval_cannot_reauthorize_effect(tmp_path):
    stop, state = stop_store(tmp_path)
    boundary = CoreSecurityBoundary(stop=stop, verify_principal=accept_test_principal)
    verifier, approval, parameters = _current_approval(state)
    calls: list[str] = []

    def current() -> bool:
        return verifier.matches_unconsumed(
            approval_id=approval.approval_id,
            capability=approval.capability,
            parameters=parameters,
            now=NOW,
        )

    boundary.execute(
        principal=owner(),
        resource=CoreProtectedResource.PRIVATE_MEMORY,
        operation=CoreOperation.WRITE,
        authority_check=current,
        effect=lambda: calls.append("first"),
    )
    verifier.consume(
        approval_id=approval.approval_id,
        capability=approval.capability,
        parameters=parameters,
        now=NOW,
    )
    with pytest.raises(CoreAccessDenied) as denied:
        boundary.execute(
            principal=owner(),
            resource=CoreProtectedResource.PRIVATE_MEMORY,
            operation=CoreOperation.WRITE,
            authority_check=current,
            effect=lambda: calls.append("replayed"),
        )
    assert denied.value.decision.denial is CoreAccessDenial.AUTHORITY
    assert calls == ["first"]


def test_revoked_owner_credential_between_plan_and_effect_denies(tmp_path):
    stop, state = stop_store(tmp_path)
    boundary = CoreSecurityBoundary(stop=stop, verify_principal=accept_test_principal)
    verifier, approval, parameters = _current_approval(state)
    with sqlite3.connect(state) as db:
        db.execute(
            "UPDATE safe_owner_credential SET revoked_at=?",
            (NOW.isoformat(),),
        )
        db.commit()
    calls: list[str] = []
    with pytest.raises(CoreAccessDenied) as denied:
        boundary.execute(
            principal=owner(),
            resource=CoreProtectedResource.PRIVATE_MEMORY,
            operation=CoreOperation.WRITE,
            authority_check=lambda: verifier.matches_unconsumed(
                approval_id=approval.approval_id,
                capability=approval.capability,
                parameters=parameters,
                now=NOW,
            ),
            effect=lambda: calls.append("effect"),
        )
    assert denied.value.decision.denial is CoreAccessDenial.AUTHORITY
    assert calls == []


@pytest.mark.parametrize("principal", [guest(), None, sofia_core_principal()])
def test_guest_unknown_and_core_self_cannot_export_protected_state(
    tmp_path, principal,
):
    stop, _ = stop_store(tmp_path)
    boundary = CoreSecurityBoundary(stop=stop, verify_principal=accept_test_principal)
    calls: list[str] = []
    with pytest.raises(CoreAccessDenied) as denied:
        boundary.execute(
            principal=principal,
            resource=CoreProtectedResource.PRIVATE_MEMORY,
            operation=CoreOperation.EXPORT,
            effect=lambda: calls.append("effect"),
        )
    assert denied.value.decision.denial in {
        CoreAccessDenial.ROLE,
        CoreAccessDenial.PRINCIPAL,
        CoreAccessDenial.NOT_AUTHENTICATED,
    }
    assert calls == []


# ---- Backup and recovery trust ---------------------------------------------


class _Manifest:
    def __init__(self, backup_id: str, digest: str) -> None:
        self.backup_id = backup_id
        self.digest = digest


def _restore_target(tmp_path: Path) -> Path:
    return tmp_path / "restored" / "sofia.db"


def test_restore_requires_the_existing_authorized_receipt(tmp_path):
    ledger = make_restore_authority(tmp_path)
    target = _restore_target(tmp_path)
    with pytest.raises(PermissionError, match="not authorized"):
        ledger.require_replacement(
            target, _Manifest("backup:c5", "a" * 64), now=BACKUP_NOW,
        )


def test_restore_receipt_cannot_authorize_another_identity_generation(
    tmp_path,
):
    ledger = make_restore_authority(tmp_path)
    target = _restore_target(tmp_path)
    approved = _Manifest("backup:approved", "a" * 64)
    other = _Manifest("backup:other-generation", "b" * 64)
    mint_replacement(ledger, target, approved)
    assert ledger.require_replacement(
        target, approved, now=BACKUP_NOW,
    ) == "restore.replacement-1"
    with pytest.raises(PermissionError, match="not authorized"):
        ledger.require_replacement(target, other, now=BACKUP_NOW)


def test_restore_receipt_cannot_authorize_another_destination_home(tmp_path):
    ledger = make_restore_authority(tmp_path)
    approved = _Manifest("backup:approved-home", "c" * 64)
    mint_replacement(ledger, _restore_target(tmp_path), approved)
    with pytest.raises(PermissionError, match="not authorized"):
        ledger.require_replacement(
            tmp_path / "another-home" / "sofia.db", approved, now=BACKUP_NOW,
        )


def test_recovered_identity_from_another_generation_is_denied(tmp_path):
    state = protected_state(tmp_path, expected_instance_id=IDENTITY_UUID)
    write_identity(
        tmp_path / "protected" / "identity.json",
        instance_id=OTHER_IDENTITY_UUID,
    )
    with pytest.raises(ProtectedCoreStateError):
        state.read_identity(owner())


def test_restore_ledger_is_never_manufactured_in_place(tmp_path):
    from sofia.platform.ops.restore_authority import RestoreAuthorityUnavailable

    path = tmp_path / "missing" / "restore-authority.db"
    with pytest.raises(RestoreAuthorityUnavailable):
        ProtectedRestoreLedger(path)
    assert not path.exists()
