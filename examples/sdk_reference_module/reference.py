"""Aegis SDK golden reference: inert, bounded optional module example.

This source is a *reviewed developer sample*, not a dynamically executable
plugin loader or a signed production module. The Platform owns admission,
approval, settings persistence, worker lifecycle and capability registration.
No file/network/process/secret access or user-visible side effects.
"""
from __future__ import annotations

import re
from typing import Mapping

from sofia.sdk import (
    SDK_PROTOCOL_VERSION, ModuleSettingApplyClass, ModuleSettingField,
    ModuleSettingType, ModuleSettingsContract,
)
from sofia.platform.capability.model import Capability, CapabilityRequest

MODULE_ID = "dev.aegis.reference"
MODULE_VERSION = "0.1.0"
CAPABILITY_ID = "reference.ping"
PROFILE = "OBSERVE"
# Provisional admission resources, not a verified reservation.
RESOURCES = (("cpu_millicores", 50), ("ram_mib", 32), ("gpu_mib", 0))
_NONCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$")


def settings_contract() -> ModuleSettingsContract:
    """Signed manifest's typed settings; not permission to write state."""
    return ModuleSettingsContract(
        "sofia.module.settings.v1", 1, (
            ModuleSettingField(
                "display.mode", "Display mode", ModuleSettingType.ENUM,
                ModuleSettingApplyClass.LIVE, required=True,
                enum_values=("compact", "verbose"),
            ),
            ModuleSettingField(
                "demo.transport", "Example transport", ModuleSettingType.ENUM,
                ModuleSettingApplyClass.COMPONENT_RESTART,
                enum_values=("local", "isolated"),
            ),
        ),
    )


class ReferenceModule:
    """Disposable module behavior. The Platform creates/owns its lifecycle."""

    def __init__(self) -> None:
        self._display_mode = "compact"

    def capability_registrations(self):
        capability = Capability(
            CAPABILITY_ID, "Return a bounded, no-effect SDK ping receipt.",
        )

        def handle(request: CapabilityRequest) -> dict[str, object]:
            if (not isinstance(request, CapabilityRequest)
                    or request.capability != capability
                    or set(request.parameters) != {"nonce"}):
                raise ValueError("exact reference.ping request required")
            nonce = request.parameters["nonce"]
            if type(nonce) is not str or _NONCE.fullmatch(nonce) is None:
                raise ValueError("nonce must be a bounded opaque identifier")
            return {
                "schema": "aegis.sdk.reference.ping.v1",
                "module_id": MODULE_ID,
                "sdk_protocol": str(SDK_PROTOCOL_VERSION),
                "nonce": nonce,
                "display_mode": self._display_mode,
                "effect": "none",
                "data_persisted": False,
                "runtime_health_verified": False,
            }

        return ((capability, handle),)

    def apply_live_settings(
        self, module_id: str, package_digest: str,
        values: Mapping[str, object], changed_fields: tuple[str, ...],
    ) -> None:
        """Apply only a separately authorized Platform LIVE settings callback.

        A component-restart field is never applied by this handler.
        The canonical ModuleSettingsService validates revision and authority.
        """
        if module_id != MODULE_ID or type(package_digest) is not str or (
            len(package_digest) != 64
            or any(char not in "0123456789abcdef" for char in package_digest)
        ):
            raise ValueError("unexpected module package identity")
        if changed_fields != ("display.mode",):
            raise ValueError("only display.mode supports live apply")
        candidate = settings_contract().validate_partial(values)
        if "display.mode" not in candidate:
            raise ValueError("missing display.mode")
        self._display_mode = candidate["display.mode"]


def capability_registrations():
    """Convenience single-use registration for minimal SDK experiments."""
    return ReferenceModule().capability_registrations()
