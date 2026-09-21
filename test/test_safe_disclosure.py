from datetime import datetime, timedelta, timezone
import pytest
from sofia.safe import Artifact, Disclose, GrantRecord, Sensitivity, evaluate

NOW = datetime(2026, 9, 21, 20, tzinfo=timezone.utc)


def artifact(**kw):
    fields = dict(artifact_id="note-1", revision=3, owner_id="sparks",
                  sensitivity=Sensitivity.SHARED, source_ids=("message-2",))
    fields.update(kw)
    return Artifact(**fields)


def grant(**kw):
    fields = dict(grant_id="approved-1", artifact_id="note-1", artifact_revision=3,
                  owner_id="sparks", recipient_id="sparks", issued_at=NOW-timedelta(minutes=1),
                  expires_at=NOW+timedelta(minutes=1))
    fields.update(kw)
    return GrantRecord(**fields)


def check(item=None, **kw):
    fields = dict(viewer_id="sparks", owner_id="sparks", now=NOW, trusted_actor=True,
                  verified_grant=grant(), trusted_grant_origin=True)
    fields.update(kw)
    return evaluate(item or artifact(), **fields)


def test_exact_grant_only_eligible_not_authorized():
    assert check() is Disclose.ELIGIBLE_FOR_TRUSTED_ENFORCEMENT


def test_private_reflection_never_published_even_with_grant():
    assert check(artifact(sensitivity=Sensitivity.PRIVATE_REFLECTION)) is Disclose.DENIED


def test_personal_still_requires_explicit_grant():
    assert check(artifact(sensitivity=Sensitivity.PERSONAL), verified_grant=None) is Disclose.NEEDS_TRUSTED_GRANT


def test_shared_without_grant_not_displayed():
    assert check(verified_grant=None) is Disclose.NEEDS_TRUSTED_GRANT


def test_forged_grant_origin_no_permission():
    assert check(trusted_grant_origin=False) is Disclose.NEEDS_TRUSTED_GRANT


def test_unknown_actor_denied():
    assert check(trusted_actor=False) is Disclose.DENIED


def test_other_person_denied_even_if_claimed_grant():
    assert check(viewer_id="other") is Disclose.DENIED


def test_different_owner_denied():
    assert check(artifact(owner_id="other")) is Disclose.DENIED


@pytest.mark.parametrize("change", [dict(artifact_id="other"), dict(artifact_revision=2), dict(owner_id="other"), dict(recipient_id="other")])
def test_wrong_grant_scope_denied(change):
    assert check(verified_grant=grant(**change)) is Disclose.DENIED


def test_revoked_grant_denied():
    assert check(revoked_grant_ids=frozenset({"approved-1"})) is Disclose.DENIED


def test_just_expired_grant_denied():
    assert check(now=NOW+timedelta(minutes=1)) is Disclose.DENIED


def test_not_yet_valid_grant_denied():
    assert check(now=NOW-timedelta(minutes=2)) is Disclose.DENIED


def test_exact_boundary_issue_time_is_valid():
    assert check(now=NOW-timedelta(minutes=1)) is Disclose.ELIGIBLE_FOR_TRUSTED_ENFORCEMENT


@pytest.mark.parametrize("bad", [dict(artifact_id=""), dict(owner_id=" "), dict(revision=0), dict(revision=True), dict(sensitivity="shared"), dict(source_ids=()), dict(source_ids=("",)), dict(source_ids=("x", "x"))])
def test_invalid_artifact_rejected(bad):
    with pytest.raises((ValueError, TypeError)):
        artifact(**bad)


@pytest.mark.parametrize("bad", [dict(grant_id=" "), dict(artifact_revision=0), dict(artifact_revision=True), dict(recipient_id=""), dict(issued_at=datetime(2026, 9, 21)), dict(expires_at=NOW-timedelta(minutes=2))])
def test_invalid_grant_rejected(bad):
    with pytest.raises(ValueError):
        grant(**bad)


def test_naive_now_rejected():
    with pytest.raises(ValueError):
        check(now=datetime(2026, 9, 21))


def test_invalid_viewer_rejected():
    with pytest.raises(ValueError):
        check(viewer_id="")


def test_invalid_trust_flag_rejected():
    with pytest.raises(TypeError):
        check(trusted_actor="yes")


def test_invalid_revocation_type_rejected():
    with pytest.raises(TypeError):
        check(revoked_grant_ids={"approved-1"})


def test_no_publish_or_read_side_effect_api():
    import sofia.safe as module
    assert not hasattr(module, "publish") and not hasattr(module, "send")
