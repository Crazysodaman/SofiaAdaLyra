from datetime import datetime, timedelta, timezone
from hashlib import sha256

import pytest

from sofia.sdk import (
    AuthorityProjection,
    ComponentEndpoint,
    ComponentKind,
    ComponentOutcome,
    ComponentRequestEnvelope,
    ComponentResponseEnvelope,
    ProtocolVersion,
    ProtocolVersionRange,
    negotiate_protocol,
)
from sofia.platform.distributed.inference import RemoteInferenceRequest
from sofia.platform.config.model import ProviderConfiguration
from sofia.core.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveRole
from uuid import uuid4


NOW = datetime(2026, 10, 24, tzinfo=timezone.utc)
DIGEST = sha256(b"release").hexdigest()
PAYLOAD = sha256(b"payload").hexdigest()


def endpoint(kind=ComponentKind.CORE, generation=4):
    return ComponentEndpoint(
        component_id="core.sofia" if kind is ComponentKind.CORE else "platform.host",
        kind=kind,
        release_digest=DIGEST,
        generation=generation,
        platform_instance_id="platform:test",
        core_identity_id="core:sofia" if kind is ComponentKind.CORE else None,
    )


def authority(expires=NOW + timedelta(minutes=5)):
    return AuthorityProjection(
        principal_id="principal:sparks",
        audience_id="audience:private",
        audience_kind="private",
        authority_ref="grant:test",
        scopes=("cognition.respond",),
        expires_at=expires,
    )


def request(destination_generation=4):
    return ComponentRequestEnvelope(
        protocol=ProtocolVersion(1, 0),
        request_id="request:test",
        correlation_id="correlation:test",
        idempotency_key="idempotency:test",
        source=endpoint(ComponentKind.PLATFORM, 9),
        destination=endpoint(ComponentKind.CORE, destination_generation),
        authority=authority(),
        payload_type="sofia.core.cognition.request.v1",
        payload_digest=PAYLOAD,
        created_at=NOW,
        deadline=NOW + timedelta(minutes=2),
    )


def test_protocol_negotiates_highest_overlap_and_rejects_incompatible():
    assert negotiate_protocol(
        ProtocolVersionRange(ProtocolVersion(1, 0), ProtocolVersion(1, 4)),
        ProtocolVersionRange(ProtocolVersion(1, 2), ProtocolVersion(1, 3)),
    ) == ProtocolVersion(1, 3)
    with pytest.raises(RuntimeError, match="major"):
        negotiate_protocol(
            ProtocolVersionRange(ProtocolVersion(1, 0), ProtocolVersion(1, 1)),
            ProtocolVersionRange(ProtocolVersion(2, 0), ProtocolVersion(2, 1)),
        )


def test_core_endpoint_requires_distinct_identity_and_digest():
    with pytest.raises(ValueError, match="core_identity_id"):
        ComponentEndpoint("core.sofia", ComponentKind.CORE, DIGEST, 1, "platform:test")
    with pytest.raises(ValueError, match="SHA-256"):
        ComponentEndpoint(
            "core.sofia", ComponentKind.CORE, "unverified", 1,
            "platform:test", "core:sofia",
        )


def test_request_fails_closed_for_expiry_and_stale_generation():
    original = request()
    restored = ComponentRequestEnvelope.from_payload(original.to_payload())
    assert restored == original
    restored.require_dispatchable(now=NOW + timedelta(seconds=1), expected_destination_generation=4)
    with pytest.raises(PermissionError, match="stale"):
        request().require_dispatchable(now=NOW, expected_destination_generation=5)
    with pytest.raises(TimeoutError, match="deadline"):
        request().require_dispatchable(
            now=NOW + timedelta(minutes=3), expected_destination_generation=4
        )
    with pytest.raises(ValueError, match="exceeds projected authority"):
        ComponentRequestEnvelope(
            protocol=ProtocolVersion(1, 0), request_id="request:test",
            correlation_id="correlation:test", idempotency_key="idempotency:test",
            source=endpoint(ComponentKind.PLATFORM, 9), destination=endpoint(),
            authority=authority(NOW + timedelta(seconds=30)),
            payload_type="sofia.core.cognition.request.v1", payload_digest=PAYLOAD,
            created_at=NOW, deadline=NOW + timedelta(minutes=2),
        )


def test_authority_projection_is_not_a_grant_and_requires_scope():
    with pytest.raises(ValueError, match="nonempty"):
        AuthorityProjection(
            "principal:sparks", "audience:private", "private", "grant:test", (),
            NOW + timedelta(minutes=1),
        )
    with pytest.raises(PermissionError, match="expired"):
        authority(NOW + timedelta(seconds=1)).require_current(
            now=NOW + timedelta(seconds=1)
        )


def test_verified_success_requires_evidence_and_unknown_does_not():
    with pytest.raises(ValueError, match="requires independent evidence"):
        ComponentResponseEnvelope(
            ProtocolVersion(1, 0), "request:test", "correlation:test", endpoint(),
            ComponentOutcome.SUCCEEDED_VERIFIED, None, None, (), NOW,
        )
    unknown = ComponentResponseEnvelope(
        ProtocolVersion(1, 0), "request:test", "correlation:test", endpoint(),
        ComponentOutcome.OUTCOME_UNKNOWN, None, None, (), NOW,
    )
    assert unknown.outcome is ComponentOutcome.OUTCOME_UNKNOWN
    verified = ComponentResponseEnvelope(
        ProtocolVersion(1, 0), "request:test", "correlation:test", endpoint(),
        ComponentOutcome.SUCCEEDED_VERIFIED,
        "sofia.core.cognition.response.v1", PAYLOAD, ("receipt:verified",), NOW,
    )
    assert verified.evidence_refs == ("receipt:verified",)
    assert ComponentResponseEnvelope.from_payload(verified.to_payload()) == verified
    injected = verified.to_payload()
    injected["grant"] = "forged"
    with pytest.raises(ValueError, match="exactly"):
        ComponentResponseEnvelope.from_payload(injected)


def test_existing_remote_inference_wire_is_bound_to_common_sdk_protocol():
    remote = RemoteInferenceRequest(
        request_id=uuid4(), node_id=uuid4(), grant_id=uuid4(),
        provider=ProviderConfiguration(provider="ollama", model="exact:model"),
        request=CognitiveRequest(messages=(
            CognitiveMessage(CognitiveRole.USER, "bounded test"),
        )),
    )
    assert remote.sdk_protocol == ProtocolVersion(1, 0)
    restored = RemoteInferenceRequest.from_payload(remote.to_payload())
    assert restored.sdk_protocol == remote.sdk_protocol
