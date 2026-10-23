"""Deferred screen SAFE classification tests, no platform picker or pixels.

A declared capability describes a policy, NEVER proves that its executable
provider is installed, that a target was selected, or that an OS consent
ceremony occurred.
"""
import pytest

from sofia.platform.safe.permissions import (
    PermissionLevel, PrivacyClass, automatic_capabilities,
    capability_permission_policy, explicitly_classified_capabilities,
    grantable_capabilities,
)

pytestmark = pytest.mark.pkg_interact


@pytest.mark.parametrize("capability", [
    "screen.discover", "screen.capture_once", "screen.watch_scoped",
])
def test_screen_target_knowledge_is_never_an_automatic_read(capability):
    policy=capability_permission_policy(capability)
    assert policy.level is PermissionLevel.PROTECTED
    assert policy.privacy is PrivacyClass.PROTECTED_PRIVATE
    assert policy.standing_grant_allowed is False
    assert capability in explicitly_classified_capabilities()
    assert capability not in automatic_capabilities()
    assert capability not in grantable_capabilities()


@pytest.mark.parametrize("capability", [
    "screen.remote_view", "screen.act_exact",
])
def test_sharing_and_gui_execution_are_never_model_self_authorized(capability):
    policy=capability_permission_policy(capability)
    assert policy.level is PermissionLevel.NEVER_SELF_AUTHORIZED
    assert policy.privacy is PrivacyClass.PROTECTED_PRIVATE
    assert policy.standing_grant_allowed is False
    assert capability in explicitly_classified_capabilities()
    assert capability not in automatic_capabilities()
    assert capability not in grantable_capabilities()


def test_unknown_screen_name_cannot_fall_back_to_autonomous_permission():
    policy=capability_permission_policy("screen.capture_all_silently")
    assert policy.level is PermissionLevel.PROTECTED
    assert policy.standing_grant_allowed is False
