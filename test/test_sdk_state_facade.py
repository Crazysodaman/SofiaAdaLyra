from datetime import datetime, timedelta, timezone
from hashlib import sha256

import pytest

from sofia.platform.state import PlatformSDKStateFacade
from sofia.platform.state.model import StateClass
from sofia.platform.state.namespaces import StateNamespaceSpec
from sofia.platform.state.plane import StatePlaneConflictError
from sofia.platform.state.platform import StatePlatformService
from sofia.platform.run import ComponentGenerationStore, LocalRunLeaseStore
from sofia.sdk import AuthorityProjection, ComponentEndpoint, ComponentKind


NOW = datetime(2026, 10, 24, tzinfo=timezone.utc)


def worker(generation=3):
    return ComponentEndpoint(
        "core.sofia", ComponentKind.CORE, sha256(b"core").hexdigest(),
        generation, "platform:test", "core:sofia",
    )


def authority(*scopes, audience="audience:private"):
    return AuthorityProjection(
        "principal:sparks", audience, "private", "grant:state", tuple(scopes),
        NOW + timedelta(minutes=5),
    )


def service(canonical_state_path):
    state = StatePlatformService(
        state_path=canonical_state_path,
        namespaces=(StateNamespaceSpec(
            "core.test", "CORE", StateClass.PROTECTED, True, True,
        ),),
    )
    return PlatformSDKStateFacade(
        state=state,
        generation_is_active=lambda endpoint: endpoint.generation == 3,
        authority_allows=lambda endpoint, auth, namespace, operation: (
            endpoint.core_identity_id == "core:sofia"
            and auth.principal_id == "principal:sparks"
        ),
        clock=lambda: NOW,
    )


def test_scoped_sdk_state_cas_survives_facade_reconstruction(canonical_state_path):
    facade = service(canonical_state_path)
    write = authority("state.write:core.test")
    created = facade.compare_and_set(
        worker=worker(), authority=write, namespace="core.test", key="self",
        expected_revision=None, value={"status": "present"},
    )
    assert created.revision == 1
    facade = service(canonical_state_path)
    read = facade.read_projection(
        worker=worker(), authority=authority("state.read:core.test"),
        namespace="core.test", key="self",
    )
    assert read is not None and read.value == {"status": "present"}
    updated = facade.compare_and_set(
        worker=worker(), authority=write, namespace="core.test", key="self",
        expected_revision=1, value={"status": "updated"},
    )
    assert updated.revision == 2
    with pytest.raises(StatePlaneConflictError):
        facade.compare_and_set(
            worker=worker(), authority=write, namespace="core.test", key="self",
            expected_revision=1, value={"status": "stale"},
        )


def test_facade_rejects_stale_generation_wrong_scope_and_audience(canonical_state_path):
    facade = service(canonical_state_path)
    with pytest.raises(PermissionError, match="generation"):
        facade.read_projection(
            worker=worker(2), authority=authority("state.read:core.test"),
            namespace="core.test", key="self",
        )
    with pytest.raises(PermissionError, match="exact state scope"):
        facade.read_projection(
            worker=worker(), authority=authority("cognition.respond"),
            namespace="core.test", key="self",
        )
    denied = PlatformSDKStateFacade(
        state=StatePlatformService(
            state_path=canonical_state_path,
            namespaces=(StateNamespaceSpec(
                "core.test", "CORE", StateClass.PROTECTED, True, True,
            ),),
        ),
        generation_is_active=lambda endpoint: True,
        authority_allows=lambda *args: False,
        clock=lambda: NOW,
    )
    with pytest.raises(PermissionError, match="denied"):
        denied.read_projection(
            worker=worker(), authority=authority("state.read:core.test"),
            namespace="core.test", key="self",
        )


def test_durable_generation_fence_revokes_state_facade(canonical_state_path):
    leases = LocalRunLeaseStore(canonical_state_path)
    lease = leases.acquire(
        owner_id="platform:supervisor", now=NOW, ttl_seconds=300,
    ).lease
    assert lease is not None
    generations = ComponentGenerationStore(
        state_path=canonical_state_path, lease_store=leases,
    )
    active = generations.stage(
        component_id="core.sofia", kind=ComponentKind.CORE,
        release_digest=sha256(b"core").hexdigest(),
        platform_instance_id="platform:test", core_identity_id="core:sofia",
        lease=lease, now=NOW, reason="reviewed",
    )
    generations.activate(active, lease=lease, now=NOW, reason="serve")
    state = StatePlatformService(
        state_path=canonical_state_path,
        namespaces=(StateNamespaceSpec(
            "core.test", "CORE", StateClass.PROTECTED, True, True,
        ),),
    )
    facade = PlatformSDKStateFacade(
        state=state, generation_is_active=generations.is_active,
        authority_allows=lambda *args: True, clock=lambda: NOW,
    )
    facade.compare_and_set(
        worker=active, authority=authority("state.write:core.test"),
        namespace="core.test", key="fenced", expected_revision=None,
        value={"accepted": True},
    )
    generations.begin_drain(
        active, lease=lease, now=NOW + timedelta(seconds=1), reason="replace",
    )
    with pytest.raises(PermissionError, match="generation"):
        facade.read_projection(
            worker=active, authority=authority("state.read:core.test"),
            namespace="core.test", key="fenced",
        )
