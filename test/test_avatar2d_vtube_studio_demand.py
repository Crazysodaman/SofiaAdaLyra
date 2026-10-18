"""On-demand Live2D host decisions depend on trusted public visual state."""
from __future__ import annotations

from dataclasses import replace

import pytest

from sofia.avatar.presentation import (
    AppearanceState, AudienceScope, AttireMode, PresentationProjection,
)
from sofia.avatar.vtube_studio_demand import (
    AvatarDemand, AvatarHostAction, decide_avatar_host_action,
    handle_avatar_demand,
)


@pytest.fixture
def public():
    return PresentationProjection(
        audience=AudienceScope.PUBLIC, source_revision=1,
        attire=AttireMode.CLOTHED, outfit_id="day.default",
        item_ids=("shirt",), appearance=AppearanceState(
            hairstyle="long layered", hair_color="deep crimson",
            tail_color="dark violet",
        ), private_fallback_used=False, reason="test",
    )


@pytest.fixture
def demand(public):
    return AvatarDemand(
        owner_enabled=True, visible_surface_requested=True,
        rig_verified_on_this_host=True, covered_outfit_verified=True,
        gaming_or_pressure_active=False, externally_stopped=False,
        presentation=public,
    )


def test_on_demand_launch_when_safe_model_and_visible_desired(demand):
    assert decide_avatar_host_action(
        demand, currently_owned=False,
    ) is AvatarHostAction.LAUNCH_OR_REUSE
    calls = []
    assert handle_avatar_demand(
        demand, currently_owned=False,
        launch=lambda: calls.append("launch") or {"result": "launched"},
        close_owned=lambda: pytest.fail("must not close needed avatar"),
    )["decision"] == "launch_or_reuse"
    assert calls == ["launch"]


@pytest.mark.parametrize("override", (
    {"owner_enabled": False},
    {"visible_surface_requested": False},
    {"rig_verified_on_this_host": False},
    {"covered_outfit_verified": False},
    {"gaming_or_pressure_active": True},
    {"externally_stopped": True},
))
def test_never_launch_without_preconditions(demand, override):
    changed = replace(demand, **override)
    assert decide_avatar_host_action(changed, currently_owned=False) is (
        AvatarHostAction.STAY_STOPPED
    )
    calls = []
    result = handle_avatar_demand(
        changed, currently_owned=True,
        launch=lambda: pytest.fail("must not launch unverified character"),
        close_owned=lambda: calls.append("close") or {"close_sent": True},
    )
    assert result["decision"] == "close_owned"
    assert calls == ["close"]


def test_private_or_uncovered_model_cannot_be_automatically_displayed(demand):
    private = replace(demand.presentation, audience=AudienceScope.PRIVATE)
    assert decide_avatar_host_action(
        replace(demand, presentation=private), currently_owned=False,
    ) is AvatarHostAction.STAY_STOPPED
    fallback = replace(demand.presentation, private_fallback_used=True)
    assert decide_avatar_host_action(
        replace(demand, presentation=fallback), currently_owned=False,
    ) is AvatarHostAction.STAY_STOPPED
    nude = replace(demand.presentation, attire=AttireMode.NUDE)
    assert decide_avatar_host_action(
        replace(demand, presentation=nude), currently_owned=False,
    ) is AvatarHostAction.STAY_STOPPED


def test_non_boolean_flags_fail_closed(demand):
    with pytest.raises(TypeError, match="owner_enabled"):
        replace(demand, owner_enabled=1)
    with pytest.raises(TypeError, match="ownership"):
        decide_avatar_host_action(demand, currently_owned=1)
