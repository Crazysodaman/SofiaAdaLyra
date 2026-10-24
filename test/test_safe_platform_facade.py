from datetime import datetime, timezone

from sofia.platform.safe.platform import PlatformSafeFacade, PolicyDenial
from sofia.core.social.model import AudienceKind, PrincipalContext


NOW = datetime(2026, 10, 23, 2, tzinfo=timezone.utc)
PRIVATE = PrincipalContext(
    "principal:sparks", "audience:desktop", AudienceKind.PRIVATE,
)


def facade(path, *, valid=True):
    return PlatformSafeFacade(
        path,
        principal_verifier=lambda principal, ref, now: valid and ref == "session:valid",
    )


def test_authenticated_read_only_policy_is_allowed_without_creating_authority(
    canonical_state_path,
):
    result = facade(canonical_state_path).evaluate(
        principal=PRIVATE, principal_attestation_ref="session:valid",
        capability="system.inspect", parameters={}, module_permission_ceiling=1,
        now=NOW,
    )
    assert result.allowed is True
    assert result.approval_must_be_consumed is False


def test_identity_audience_and_module_ceiling_fail_closed(canonical_state_path):
    service = facade(canonical_state_path, valid=False)
    denied = service.evaluate(
        principal=PRIVATE, principal_attestation_ref="forged",
        capability="system.inspect", parameters={}, module_permission_ceiling=5,
        now=NOW,
    )
    assert denied.denial is PolicyDenial.IDENTITY

    shared = PrincipalContext(
        "principal:sparks", "audience:discord", AudienceKind.SHARED,
    )
    denied = facade(canonical_state_path).evaluate(
        principal=shared, principal_attestation_ref="session:valid",
        capability="system.inspect", parameters={}, module_permission_ceiling=5,
        now=NOW,
    )
    assert denied.denial is PolicyDenial.AUDIENCE

    denied = facade(canonical_state_path).evaluate(
        principal=PRIVATE, principal_attestation_ref="session:valid",
        capability="service.restart", parameters={"service": "docker"},
        module_permission_ceiling=1, now=NOW,
    )
    assert denied.denial is PolicyDenial.MODULE_CEILING


def test_operator_stop_and_authority_changing_capabilities_are_denied(
    canonical_state_path,
):
    service = facade(canonical_state_path)
    service.operator_stop.set(
        active=True, updated_by="Sparks", reason="test emergency stop", at=NOW,
    )
    stopped = service.evaluate(
        principal=PRIVATE, principal_attestation_ref="session:valid",
        capability="system.inspect", parameters={}, module_permission_ceiling=5,
        now=NOW,
    )
    assert stopped.denial is PolicyDenial.OPERATOR_STOP

    # Use a fresh database because clearing STOP correctly requires the real
    # FIDO2 approval path and this test must not bypass it.


def test_unknown_protected_capability_requires_exact_approval(canonical_state_path):
    result = facade(canonical_state_path).evaluate(
        principal=PRIVATE, principal_attestation_ref="session:valid",
        capability="module.example.mutate", parameters={"target": "fixture"},
        module_permission_ceiling=4, now=NOW,
    )
    assert result.allowed is False
    assert result.denial is PolicyDenial.APPROVAL_REQUIRED


def test_never_self_authorized_capability_stays_denied_at_ceiling_five(
    canonical_state_path,
):
    result = facade(canonical_state_path).evaluate(
        principal=PRIVATE, principal_attestation_ref="session:valid",
        capability="permissions.grant", parameters={},
        module_permission_ceiling=5, now=NOW,
    )
    assert result.denial is PolicyDenial.NEVER_SELF_AUTHORIZED
