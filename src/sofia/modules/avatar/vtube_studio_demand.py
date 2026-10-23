"""Trusted-demand boundary for an opt-in Live2D / VTube Studio avatar session.

This headless policy is deliberately independent of the model/Steam/Tk UI.
A desktop USER-SESSION coordinator passes the actual public appearance,
covered wardrobe, model installation status and gaming activity, then calls
the on-demand VTS host launcher or owner-safe closer. No LLM reply or
private art can independently request an unreviewed model on screen.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .presentation import AudienceScope, AttireMode, PresentationProjection


class AvatarHostAction(str, Enum):
    LAUNCH_OR_REUSE = "launch_or_reuse"
    CLOSE_OWNED = "close_owned"
    STAY_STOPPED = "stay_stopped"


@dataclass(frozen=True, slots=True)
class AvatarDemand:
    """Facts supplied by the trusted local avatar controller, not by the LLM."""
    owner_enabled: bool
    visible_surface_requested: bool
    rig_verified_on_this_host: bool
    covered_outfit_verified: bool
    gaming_or_pressure_active: bool
    externally_stopped: bool
    presentation: PresentationProjection

    def __post_init__(self) -> None:
        for name in (
            "owner_enabled", "visible_surface_requested",
            "rig_verified_on_this_host", "covered_outfit_verified",
            "gaming_or_pressure_active", "externally_stopped",
        ):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"{name} must be a trusted boolean")
        if not isinstance(self.presentation, PresentationProjection):
            raise TypeError("trusted canonical presentation required")


def decide_avatar_host_action(
    demand: AvatarDemand, *, currently_owned: bool,
) -> AvatarHostAction:
    """Decide when avatar use warrants launching a new desktop application.

    A pre-existing user-opened VTube Studio instance is never owned by
    Sofía and therefore never a target for CLOSE_OWNED.
    """
    if not isinstance(demand, AvatarDemand) or type(currently_owned) is not bool:
        raise TypeError("trusted demand and ownership required")
    safe_public_view = (
        demand.presentation.audience is AudienceScope.PUBLIC
        and demand.presentation.attire is AttireMode.CLOTHED
        and not demand.presentation.private_fallback_used
        and demand.covered_outfit_verified
    )
    should_show = all((
        demand.owner_enabled,
        demand.visible_surface_requested,
        demand.rig_verified_on_this_host,
        safe_public_view,
        not demand.gaming_or_pressure_active,
        not demand.externally_stopped,
    ))
    if should_show:
        return AvatarHostAction.LAUNCH_OR_REUSE
    return (
        AvatarHostAction.CLOSE_OWNED
        if currently_owned else AvatarHostAction.STAY_STOPPED
    )


def handle_avatar_demand(
    demand: AvatarDemand, *, currently_owned: bool,
    launch, close_owned,
) -> dict:
    """Apply the selected action only via provided local user-session callbacks.

    The real UI must later wire this to on-demand launcher after Live2D rig
    has been visually accepted. No import, background polling or auto-start
    occurs by defining this helper.
    """
    action = decide_avatar_host_action(demand, currently_owned=currently_owned)
    if action is AvatarHostAction.LAUNCH_OR_REUSE:
        result = launch()
        return {"decision": action.value, "host_result": result}
    if action is AvatarHostAction.CLOSE_OWNED:
        result = close_owned()
        return {"decision": action.value, "host_result": result}
    return {"decision": action.value, "host_result": None}
