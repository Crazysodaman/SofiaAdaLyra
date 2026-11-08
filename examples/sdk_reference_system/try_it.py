"""Run the three-piece SDK development bench with no live services.

PowerShell: python -m examples.sdk_reference_system.try_it
Linux:      python -m examples.sdk_reference_system.try_it

Only ephemeral in-process simulation. No real authentication, signed install,
canonical writer, Core inference, process worker or external effects.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json

from sofia.sdk import ComponentEndpoint, ComponentKind

from examples.sdk_reference_core.core import ReferenceCore
from examples.sdk_reference_platform.platform import ReferencePlatform

NOW = datetime(2026, 11, 8, 12, 0, tzinfo=timezone.utc)


def demo_endpoints() -> tuple[ComponentEndpoint, ComponentEndpoint, ComponentEndpoint]:
    """Example release digests are placeholders, NOT verified signed releases."""
    platform = ComponentEndpoint(
        "platform:reference", ComponentKind.PLATFORM,
        "a" * 64, 1, "platform:reference",
    )
    core_a = ComponentEndpoint(
        "core:reference-a", ComponentKind.CORE,
        "b" * 64, 1, "platform:reference", "core:reference-a",
    )
    core_b = ComponentEndpoint(
        "core:reference-b", ComponentKind.CORE,
        "c" * 64, 1, "platform:reference", "core:reference-b",
    )
    return platform, core_a, core_b


def run_demo() -> dict[str, object]:
    platform_endpoint, a_endpoint, b_endpoint = demo_endpoints()
    platform = ReferencePlatform(platform_endpoint)
    a, b = ReferenceCore(a_endpoint), ReferenceCore(b_endpoint)

    platform.plug_reference_module()
    a_session = platform.open_test_session(a_endpoint, now=NOW)
    b_session = platform.open_test_session(b_endpoint, now=NOW)
    platform.test_only_grant(a_session)

    a_request, a_payload = a.build_ping(
        platform=platform_endpoint,
        projected_authority=a_session.authority,
        nonce="a-001", request_id="req:a-1", now=NOW,
    )
    a_reply, a_data = platform.dispatch(
        session=a_session, request=a_request, payload=a_payload, now=NOW,
    )
    a_result = a.read_ping(a_request, a_reply, a_data)

    b_request, b_payload = b.build_ping(
        platform=platform_endpoint,
        projected_authority=b_session.authority,
        nonce="b-001", request_id="req:b-1", now=NOW,
    )
    denied, denied_data = platform.dispatch(
        session=b_session, request=b_request, payload=b_payload, now=NOW,
    )
    b_denied = b.read_ping(b_request, denied, denied_data)

    platform.test_only_grant(b_session)
    b_request2, b_payload2 = b.build_ping(
        platform=platform_endpoint,
        projected_authority=b_session.authority,
        nonce="b-002", request_id="req:b-2", now=NOW,
    )
    accepted, accepted_data = platform.dispatch(
        session=b_session, request=b_request2, payload=b_payload2, now=NOW,
    )
    b_result = b.read_ping(b_request2, accepted, accepted_data)

    platform.unplug_reference_module()
    unplug_request, unplug_payload = a.build_ping(
        platform=platform_endpoint,
        projected_authority=a_session.authority,
        nonce="a-003", request_id="req:a-3", now=NOW,
    )
    unavailable, unavailable_data = platform.dispatch(
        session=a_session, request=unplug_request,
        payload=unplug_payload, now=NOW,
    )
    a_unplugged = a.read_ping(unplug_request, unavailable, unavailable_data)

    return {
        "demo": "aegis.sdk.core-platform-module.v1",
        "first_core": a_result["outcome"],
        "second_core_before_grant": b_denied["outcome"],
        "second_core_after_grant": b_result["outcome"],
        "module_unplugged": a_unplugged["outcome"],
        "available_capabilities_after_unplug": list(platform.available_capabilities),
        "independent_verified_effect": False,
        "production_authentication": False,
        "real_worker": False,
        "persistent_state": False,
    }


def main() -> None:
    print(json.dumps(run_demo(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
