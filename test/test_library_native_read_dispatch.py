"""D028 read-only Library catalog over the canonical native OS IPC dispatcher.

Source tests use disposable Ed25519 keys and synthetic OS principal strings.
They are NOT kernel-credential, enrolled installed-host or production-signing
evidence. The production listener supplies the OS identity independently.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

import pytest

from sofia.platform.run.library_read_dispatch import (
    InstalledSignedCatalogSource, LibraryReadDispatcher, LocalReadMultiplexer,
)
from sofia.platform.run.library_read_authority import CATALOG_OPERATION
from sofia.sdk.platform_library import UntrustedLibraryResponse
from test.library_fixture_support import make_signed_catalog_fixture

PEER = "unix:uid:1000:gid:1000"


def _request(now, *, target="enrolled-recipient", generation=3, revision=7,
             limit=32, kinds=None, cursor=None):
    data = {
        "schema": "aegis.platform.library.request.v1",
        "protocol": "1.0",
        "request_id": "request:123", "correlation_id": "corr:123",
        "operation": CATALOG_OPERATION,
        "target_platform_id": target,
        "expected_generation": generation, "expected_revision": revision,
        "idempotency_key": None,
        "created_at": (now - timedelta(seconds=1)).isoformat(),
        "deadline": (now + timedelta(seconds=25)).isoformat(),
        "parameters": {
            "limit": limit, "cursor": cursor,
            "kinds": [] if kinds is None else kinds,
        },
    }
    return json.dumps(data, separators=(",", ":"), sort_keys=True).encode()


@pytest.fixture
def review():
    envelope, sign, keys = make_signed_catalog_fixture()
    state = dict(
        platform_id="enrolled-recipient",
        generation=3, operator_stop=False, core_started=False,
        library_revision=7,
    )
    trust = dict(current=True)
    source = InstalledSignedCatalogSource(
        raw_signed_index=sign(),
        trusted_publisher_public_key=keys["trusted_publisher_public_key"],
        expected_publisher_key_sha256=keys["expected_publisher_key_sha256"],
        expected_source_platform_id="primary-library",
        expected_catalog_generation=3, minimum_catalog_revision=7,
        publisher_key_current=lambda _: trust["current"],
    )
    authorized = dict(value=True)
    module = dict(source=source)
    dispatch = LibraryReadDispatcher(
        current_status=lambda: dict(state),
        authorize_os_peer=lambda peer, op: (
            authorized["value"] and peer == PEER and op == CATALOG_OPERATION
        ),
        installed_signed_catalog=lambda: module["source"],
        clock=lambda: keys["now"],
    )
    return dispatch, state, authorized, module, trust, keys["now"]


def test_native_library_catalog_verifies_real_disposable_publisher_signature(review):
    dispatch, state, authorized, module, trust, now = review
    raw = _request(now)
    reply = dispatch.dispatch(raw, authenticated_peer=PEER, now=now)
    assert reply["outcome"] == "OK"
    assert reply["platform_id"] == "enrolled-recipient"
    assert reply["data"]["source"]["source_id"] == "primary-library"
    assert reply["data"]["catalog_revision"] == 7
    assert "installed" not in json.dumps(reply)
    from sofia.sdk.platform_library import UntrustedLibraryRequest
    request = UntrustedLibraryRequest.parse(
        raw, now=now, expected_target_platform_id="enrolled-recipient",
    )
    accepted = UntrustedLibraryResponse.parse(
        json.dumps(reply).encode(), expected=request, now=now,
    )
    assert accepted.outcome == "OK"


@pytest.mark.parametrize("peer", ["not-a-peer", "unix:uid:other:gid:1000", "windows:sid:forged"])
def test_unknown_native_peer_gets_eof_not_catalog_or_typed_denial(review, peer):
    dispatch, state, authorized, module, trust, now = review
    with pytest.raises(PermissionError, match="owner-enrolled"):
        dispatch.dispatch(_request(now), authenticated_peer=peer, now=now)


def test_denied_or_rotated_owner_enrollment_never_returns_signed_catalog(review):
    dispatch, state, authorized, module, trust, now = review
    authorized["value"] = False
    with pytest.raises(PermissionError, match="owner-enrolled"):
        dispatch.dispatch(_request(now), authenticated_peer=PEER, now=now)


def test_native_library_stop_and_generation_denials_are_typed_for_enrolled_peer(review):
    dispatch, state, authorized, module, trust, now = review
    state["operator_stop"] = True
    stopped = dispatch.dispatch(_request(now), authenticated_peer=PEER, now=now)
    assert stopped["outcome"] == "DENIED"
    assert stopped["data"] is None and stopped["denial"] == {"code": "STOPPED"}
    state["operator_stop"] = False
    state["generation"] = 4
    stale = dispatch.dispatch(_request(now), authenticated_peer=PEER, now=now)
    assert stale["outcome"] == "DENIED"
    assert stale["data"] is None
    assert stale["denial"]["code"] == "STALE_GENERATION"


def test_native_library_missing_installed_signed_index_is_unavailable(review):
    dispatch, state, authorized, module, trust, now = review
    module["source"] = None
    reply = dispatch.dispatch(_request(now), authenticated_peer=PEER, now=now)
    assert reply["denial"] == {"code": "UNAVAILABLE"}
    assert reply["data"] is None


def test_native_library_refuses_wrong_platform_and_revoked_publisher(review):
    dispatch, state, authorized, module, trust, now = review
    with pytest.raises(PermissionError, match="another installed"):
        dispatch.dispatch(
            _request(now, target="another-host"), authenticated_peer=PEER, now=now,
        )
    trust["current"] = False
    with pytest.raises(PermissionError, match="revoked"):
        dispatch.dispatch(_request(now), authenticated_peer=PEER, now=now)


def test_native_library_refuses_unreviewed_filters_and_missing_signed_revision(review):
    dispatch, state, authorized, module, trust, now = review
    unsupported = dispatch.dispatch(
        _request(now, kinds=["sdk"]), authenticated_peer=PEER, now=now,
    )
    assert unsupported["denial"] == {"code": "NOT_PERMITTED"}
    state["library_revision"] = 8
    revised = dispatch.dispatch(_request(now), authenticated_peer=PEER, now=now)
    assert revised["denial"] == {"code": "STALE_GENERATION"}


def test_native_library_rechecks_owner_grant_after_signed_verification(review):
    dispatch, state, authorized, module, trust, now = review
    old = module["source"]
    class RevokingCatalog:
        def __call__(self):
            authorized["value"] = False
            return old
    dispatch._catalog = RevokingCatalog()
    with pytest.raises(PermissionError, match="changed"):
        dispatch.dispatch(_request(now), authenticated_peer=PEER, now=now)


def test_native_multiplexer_preserves_old_management_read_contract(review):
    dispatch, state, authorized, module, trust, now = review
    class ExistingManagement:
        def __init__(self):
            self.calls = []
        def dispatch(self, raw, *, authenticated_peer, now):
            self.calls.append((raw, authenticated_peer, now))
            return {"prior": "intact"}
    management = ExistingManagement()
    mux = LocalReadMultiplexer(management=management, library=dispatch)
    library = mux.dispatch(
        _request(now), authenticated_peer=PEER, now=now,
    )
    assert library["outcome"] == "OK"
    assert management.calls == []
    ordinary = b'{"schema":"aegis.platform.management.read.v1"}'
    assert mux.dispatch(
        ordinary, authenticated_peer=PEER, now=now,
    ) == {"prior": "intact"}
    assert management.calls == [(ordinary, PEER, now)]


def test_native_library_malformed_or_duplicate_control_never_bypasses_decoder(review):
    dispatch, state, authorized, module, trust, now = review
    mux = LocalReadMultiplexer(
        management=type("Old", (), {"dispatch": lambda *_, **__: None})(),
        library=dispatch,
    )
    raw = _request(now)
    duplicate = raw.replace(
        b'"schema":', b'"schema":"forged","schema":', 1,
    )
    with pytest.raises(ValueError, match="duplicate"):
        mux.dispatch(duplicate, authenticated_peer=PEER, now=now)


@pytest.mark.parametrize("phase", ["observation", "serialization"])
def test_publisher_revoked_during_observation_cannot_release_catalog(review, monkeypatch, phase):
    dispatch, state, authorized, module, trust, now = review

    if phase == "observation":
        def observed_after_revocation():
            trust["current"] = False
            return now
        monkeypatch.setattr(dispatch, "_clock", observed_after_revocation)
    else:
        original_reply = dispatch._reply
        def serialized_after_revocation(*args, **kwargs):
            reply = original_reply(*args, **kwargs)
            trust["current"] = False
            return reply
        monkeypatch.setattr(dispatch, "_reply", serialized_after_revocation)

    with pytest.raises(PermissionError, match="publisher revoked"):
        dispatch.dispatch(_request(now), authenticated_peer=PEER, now=now)
