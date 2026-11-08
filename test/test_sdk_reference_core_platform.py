"""Conformance for disposable Core and Platform SDK reference fixtures.

These are in-process test doubles, not authenticated IPC or host acceptance.
They demonstrate accurate SDK request binding and denied/unavailable outcomes.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest

from sofia.sdk import (
    ComponentOutcome, ComponentRequestEnvelope,
    ComponentResponseEnvelope, ProtocolVersion,
)
from examples.sdk_reference_core.core import ReferenceCore
from examples.sdk_reference_platform.platform import (
    ReferencePlatform, ReferenceSession,
)
from examples.sdk_reference_system.try_it import (
    NOW, demo_endpoints, run_demo,
)
from examples.sdk_reference_system.wire import payload_digest


def sandbox():
    platform_ep, a_ep, b_ep = demo_endpoints()
    platform = ReferencePlatform(platform_ep)
    a = ReferenceCore(a_ep)
    b = ReferenceCore(b_ep)
    session_a = platform.open_test_session(a_ep, now=NOW)
    session_b = platform.open_test_session(b_ep, now=NOW)
    return platform, a, b, session_a, session_b


def ping(core, platform, session, request_id, nonce="sample", *, when=NOW):
    return core.build_ping(
        platform=platform.endpoint,
        projected_authority=session.authority,
        request_id=request_id,
        nonce=nonce, now=when,
    )


def test_runnable_reference_system_is_unprivileged_and_multi_core():
    expected = run_demo()
    assert expected == {
        "demo": "aegis.sdk.core-platform-module.v1",
        "first_core": "succeeded_reported_unverified",
        "second_core_before_grant": "denied",
        "second_core_after_grant": "succeeded_reported_unverified",
        "module_unplugged": "unavailable",
        "available_capabilities_after_unplug": [],
        "independent_verified_effect": False,
        "production_authentication": False,
        "real_worker": False,
        "persistent_state": False,
    }


def test_two_cores_are_isolated_and_module_unplug_does_not_close_them():
    platform, a, b, sa, sb = sandbox()
    platform.plug_reference_module()
    platform.test_only_grant(sa)

    req_a, payload_a = ping(a, platform, sa, "req:a:1")
    ra, data_a = platform.dispatch(
        session=sa, request=req_a, payload=payload_a, now=NOW,
    )
    assert a.read_ping(req_a, ra, data_a)["outcome"] == (
        ComponentOutcome.SUCCEEDED_REPORTED_UNVERIFIED.value
    )
    assert data_a["result"]["module_id"] == "dev.aegis.reference"

    req_b, payload_b = ping(b, platform, sb, "req:b:1")
    rb, data_b = platform.dispatch(
        session=sb, request=req_b, payload=payload_b, now=NOW,
    )
    assert b.read_ping(req_b, rb, data_b)["outcome"] == "denied"
    assert data_b is None

    platform.test_only_grant(sb)
    req_b2, payload_b2 = ping(b, platform, sb, "req:b:2")
    rb2, data_b2 = platform.dispatch(
        session=sb, request=req_b2, payload=payload_b2, now=NOW,
    )
    assert b.read_ping(req_b2, rb2, data_b2)["outcome"] == (
        "succeeded_reported_unverified"
    )

    platform.test_only_revoke(sa)
    req_a2, payload_a2 = ping(a, platform, sa, "req:a:2")
    ra2, data_a2 = platform.dispatch(
        session=sa, request=req_a2, payload=payload_a2, now=NOW,
    )
    assert a.read_ping(req_a2, ra2, data_a2)["outcome"] == "denied"

    platform.unplug_reference_module()
    assert platform.available_capabilities == ()
    req_b3, payload_b3 = ping(b, platform, sb, "req:b:3")
    rb3, data_b3 = platform.dispatch(
        session=sb, request=req_b3, payload=payload_b3, now=NOW,
    )
    assert b.read_ping(req_b3, rb3, data_b3)["outcome"] == "unavailable"

    platform.plug_reference_module()
    req_b4, payload_b4 = ping(b, platform, sb, "req:b:4")
    rb4, data_b4 = platform.dispatch(
        session=sb, request=req_b4, payload=payload_b4, now=NOW,
    )
    assert b.read_ping(req_b4, rb4, data_b4)["outcome"] == (
        "succeeded_reported_unverified"
    )
    assert sa in platform._sessions and sb in platform._sessions


def test_caller_fields_do_not_impersonate_active_core_or_platform():
    platform, a, b, sa, sb = sandbox()
    platform.plug_reference_module()
    platform.test_only_grant(sa)
    request, payload = ping(a, platform, sa, "req:a:identity")

    # A structurally identical but unregistered Python session is not accepted.
    lookalike = ReferenceSession(sa.source, sa.authority)
    with pytest.raises(PermissionError, match="no current"):
        platform.dispatch(
            session=lookalike, request=request, payload=payload, now=NOW,
        )

    forged_core = replace(request, source=sb.source)
    with pytest.raises(PermissionError, match="does not match"):
        platform.dispatch(
            session=sa, request=forged_core, payload=payload, now=NOW,
        )

    forged_projection = replace(
        request, authority=replace(request.authority, principal_id="core:other"),
    )
    with pytest.raises(PermissionError, match="does not match"):
        platform.dispatch(
            session=sa, request=forged_projection, payload=payload, now=NOW,
        )

    wrong_generation = replace(
        request, destination=replace(request.destination, generation=2),
    )
    with pytest.raises(PermissionError, match="does not match"):
        platform.dispatch(
            session=sa, request=wrong_generation, payload=payload, now=NOW,
        )

    wrong_protocol = replace(request, protocol=ProtocolVersion(2, 0))
    with pytest.raises(PermissionError, match="does not match"):
        platform.dispatch(
            session=sa, request=wrong_protocol, payload=payload, now=NOW,
        )

    forged_scope = replace(
        request, authority=replace(request.authority, scopes=("aegis.admin",)),
    )
    with pytest.raises(PermissionError, match="does not match"):
        platform.dispatch(
            session=sa, request=forged_scope, payload=payload, now=NOW,
        )

    with pytest.raises(PermissionError, match="digest mismatch"):
        platform.dispatch(
            session=sa, request=request, payload={"nonce": "changed"}, now=NOW,
        )


def test_expiry_replay_future_time_stop_and_close_fail_closed():
    platform, a, _, session, _ = sandbox()
    platform.plug_reference_module()
    platform.test_only_grant(session)
    request, payload = ping(a, platform, session, "req:a:once")
    answer, _ = platform.dispatch(
        session=session, request=request, payload=payload, now=NOW,
    )
    assert answer.outcome is ComponentOutcome.SUCCEEDED_REPORTED_UNVERIFIED
    with pytest.raises(PermissionError, match="replayed"):
        platform.dispatch(
            session=session, request=request, payload=payload, now=NOW,
        )

    future, future_payload = ping(
        a, platform, session, "req:a:future", when=NOW + timedelta(seconds=10),
    )
    with pytest.raises(PermissionError, match="before creation"):
        platform.dispatch(
            session=session, request=future, payload=future_payload, now=NOW,
        )

    expiring, exp_payload = ping(a, platform, session, "req:a:expired")
    with pytest.raises(PermissionError, match="expired"):
        platform.dispatch(
            session=session, request=expiring, payload=exp_payload,
            now=NOW + timedelta(seconds=121),
        )

    platform.test_only_stop(True)
    stopped, stopped_payload = ping(a, platform, session, "req:a:stopped")
    stop_reply, no_data = platform.dispatch(
        session=session, request=stopped, payload=stopped_payload, now=NOW,
    )
    assert stop_reply.outcome is ComponentOutcome.DENIED
    assert no_data is None
    platform.test_only_stop(False)
    platform.close_test_session(session)
    new, new_payload = ping(a, platform, session, "req:a:closed")
    with pytest.raises(PermissionError, match="no current"):
        platform.dispatch(
            session=session, request=new, payload=new_payload, now=NOW,
        )


def test_wire_round_trip_and_forged_success_rejected_by_dummy_core():
    platform, a, _, session, _ = sandbox()
    platform.plug_reference_module()
    platform.test_only_grant(session)
    request, payload = ping(a, platform, session, "req:a:wire")
    restored_request = ComponentRequestEnvelope.from_payload(request.to_payload())
    assert restored_request == request

    response, reply_data = platform.dispatch(
        session=session, request=request, payload=payload, now=NOW,
    )
    restored_response = ComponentResponseEnvelope.from_payload(
        response.to_payload()
    )
    assert restored_response == response
    assert a.read_ping(restored_request, restored_response, reply_data)[
        "verified"
    ] is False

    fake_verified = replace(
        response, outcome=ComponentOutcome.SUCCEEDED_VERIFIED,
        evidence_refs=("evidence:synthetic-not-independent",),
    )
    with pytest.raises(ValueError, match="cannot prove"):
        a.read_ping(request, fake_verified, reply_data)

    altered = {"result": {"module_id": "stolen"}}
    with pytest.raises(ValueError, match="digest"):
        a.read_ping(request, response, altered)
    forged_responder = replace(
        response, responder=replace(response.responder, generation=2),
    )
    with pytest.raises(ValueError, match="not bound"):
        a.read_ping(request, forged_responder, reply_data)


def test_bounded_json_digests_never_grant_permission():
    assert len(payload_digest({"nonce": "test"})) == 64
    with pytest.raises(ValueError, match="bounded object"):
        payload_digest({str(i): i for i in range(17)})
    with pytest.raises(ValueError, match="finite JSON"):
        payload_digest({"x": float("nan")})
    with pytest.raises(ValueError, match="4096"):
        payload_digest({"x": "z" * 4097})


def test_core_replacement_keeps_platform_and_other_core_alive():
    """Source-level Core generation fencing, not an OS process restart proof."""
    platform, a, b, sa, sb = sandbox()
    platform.plug_reference_module()
    platform.test_only_grant(sa)
    platform.test_only_grant(sb)

    # Core A disconnects; its old session cannot keep accessing capabilities.
    old_req, old_payload = ping(a, platform, sa, "req:a:old-generation")
    platform.close_test_session(sa)
    with pytest.raises(PermissionError, match="no current"):
        platform.dispatch(
            session=sa, request=old_req, payload=old_payload, now=NOW,
        )

    # Core B and the module keep working without replacing the Platform.
    b_req, b_payload = ping(b, platform, sb, "req:b:still-alive")
    b_response, b_data = platform.dispatch(
        session=sb, request=b_req, payload=b_payload, now=NOW,
    )
    assert b.read_ping(b_req, b_response, b_data)["outcome"] == (
        "succeeded_reported_unverified"
    )

    # Core A reconnects with a newer identity generation and fresh test grant.
    next_a_endpoint = replace(a.endpoint, generation=2)
    next_a = ReferenceCore(next_a_endpoint)
    next_session = platform.open_test_session(next_a_endpoint, now=NOW)
    platform.test_only_grant(next_session)
    next_req, next_payload = ping(
        next_a, platform, next_session, "req:a:new-generation",
    )
    next_response, next_data = platform.dispatch(
        session=next_session, request=next_req,
        payload=next_payload, now=NOW,
    )
    assert next_a.read_ping(next_req, next_response, next_data)["outcome"] == (
        "succeeded_reported_unverified"
    )
    assert sa not in platform._sessions
    assert sb in platform._sessions
    assert platform.available_capabilities == ("reference.ping",)
