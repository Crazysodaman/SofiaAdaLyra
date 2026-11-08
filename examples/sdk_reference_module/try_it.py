"""Run the Aegis reference capability in a disposable local SDK sandbox.

Run: python -m examples.sdk_reference_module.try_it

This demo does NOT install a package, enroll a Core, authenticate a real user,
or launch a worker. The authorization checker is a TEST DOUBLE only, never
suitable for production. See test_sdk_reference_module.py for the real
signature-verified lifecycle harness and settings/receipt checks.
"""
from __future__ import annotations

import json

from sofia.platform.capability import CapabilitySystem
from sofia.platform.capability.model import CapabilityRequest

from .reference import ReferenceModule, CAPABILITY_ID


def run_demo() -> dict[str, object]:
    """Exercise request -> Platform authorization -> capability -> unplug."""
    module = ReferenceModule()
    # Only for this disposable, no-effect example. Real Aegis uses SAFE.
    system = CapabilitySystem(
        authorization_checker=lambda request: request.rationale == "local-sdk-demo"
    )
    registrations = module.capability_registrations()
    system.register_batch(registrations)

    capability = system.resolve(CAPABILITY_ID)
    success = system.execute(CapabilityRequest(
        capability=capability,
        parameters={"nonce": "my-first-module"},
        requested_scope=None,
        rationale="local-sdk-demo",
    ))
    refused = system.execute(CapabilityRequest(
        capability=capability,
        parameters={"nonce": "my-first-module"},
        requested_scope=None,
        rationale="deliberately-not-approved",
    ))
    system.unregister_batch(registrations)
    unplugged = system.execute(CapabilityRequest(
        capability=capability,
        parameters={"nonce": "my-first-module"},
        requested_scope=None,
        rationale="local-sdk-demo",
    ))
    return {
        "module": "dev.aegis.reference",
        "approved_request": success.kind.value,
        "response": success.evidence,
        "unauthorized_request": refused.kind.value,
        "after_unplug": unplugged.kind.value,
        "effect": "none",
        "production_authorization": False,
    }


def main() -> None:
    print(json.dumps(run_demo(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
