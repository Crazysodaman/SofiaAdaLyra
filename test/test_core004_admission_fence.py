"""CORE-004: real canonical SQLite admission fencing against late STOP/revoke.

The credential/STOP transition is deliberately injected *after* the gateway's
second authorization check but *before* canonical admission.  This reproduces
the previously uncovered race with a real disposable SofiaApplication and the
actual access/STOP SQLite stores, without an Ollama call or production state.
"""
from datetime import timedelta

import pytest

from sofia.platform.application import SofiaApplication
from sofia.platform.core_link import (
    CoreLinkClientAccessStore, CoreLinkConversationGateway,
)
from sofia.platform.safe.operator_stop import OperatorStopStore
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite
from sofia.core.conversation.lifelong import LifelongThreadStore
from test.test_core_link_conversation import (
    NOW, access, authorize, configuration, enrolled_store, request,
)


@pytest.mark.parametrize("intervening_change", ["revocation", "operator_stop"])
def test_core004_real_admission_denies_change_after_gateway_final_check(
    tmp_path, monkeypatch, intervening_change,
):
    state = tmp_path / "sofia.db"
    bootstrap_canonical_sqlite(state)
    app = SofiaApplication(configuration(tmp_path))
    app.start()
    gateway = None
    try:
        store = enrolled_store(state)
        gateway = CoreLinkConversationGateway(
            app,
            access_store=store,
            remote_platform_id="platform:canonical",
            remote_core_identity_id="core:sofia",
            generation_provider=lambda: 7,
            clock=lambda: NOW + timedelta(seconds=1),
        )
        service = gateway._service(access(), None)
        event_key = "core004:late-" + intervening_change
        event_id = gateway._event_id(access(), event_key)
        invoked = []

        class _TransitionBetweenPrecheckAndAdmission:
            def respond(self, *args, **kwargs):
                invoked.append("entered")
                if intervening_change == "revocation":
                    approval = authorize(
                        state,
                        capability="core-link.revoke",
                        parameters={
                            "client_id": access().client_id,
                            "expected_revision": 1,
                        },
                        now=NOW + timedelta(seconds=2),
                    )
                    store.revoke(
                        access().client_id,
                        expected_revision=1,
                        approval_id=approval,
                        now=NOW + timedelta(seconds=2),
                    )
                else:
                    OperatorStopStore(state).set(
                        active=True,
                        updated_by="Sparks",
                        reason="CORE-004 simulated emergency STOP",
                        at=NOW + timedelta(seconds=2),
                    )
                # The former implementation let this reach the model.
                # The canonical BEGIN IMMEDIATE admission now rejects it.
                return service.respond(*args, **kwargs)

        monkeypatch.setattr(
            gateway, "_service",
            lambda _access, _session_id: _TransitionBetweenPrecheckAndAdmission(),
        )
        with pytest.raises(
            PermissionError, match="(turn admission|not current at turn admission)",
        ):
            gateway.dispatch(
                certificate_public_key_sha256="a" * 64,
                request=request(
                    "conversation.send",
                    {
                        "session_id": service.session_id,
                        "content": "Never produce an answer after this transition",
                        "client_created_at": NOW.isoformat(),
                    },
                    idempotency_key=event_key,
                ),
            )
        assert invoked == ["entered"]
        assert (
            LifelongThreadStore(state).turn_status(
                event_id=event_id, principal=access().principal,
            )
            is None
        ), "unauthorized turn obtained durable canonical admission"
    finally:
        if gateway is not None:
            gateway.close()
        app.shutdown()


def test_core004_admission_allows_current_enrollment_and_stop_clear(tmp_path):
    state = tmp_path / "sofia.db"
    bootstrap_canonical_sqlite(state)
    app = SofiaApplication(configuration(tmp_path))
    app.start()
    gateway = None
    try:
        store = enrolled_store(state)
        gateway = CoreLinkConversationGateway(
            app, access_store=store, remote_platform_id="platform:canonical",
            remote_core_identity_id="core:sofia",
            generation_provider=lambda: 7,
            clock=lambda: NOW + timedelta(seconds=1),
        )
        service = gateway._service(access(), None)
        result = gateway.dispatch(
            certificate_public_key_sha256="a" * 64,
            request=request(
                "conversation.send",
                {
                    "session_id": service.session_id,
                    "content": "CORE-004 positive admission control",
                    "client_created_at": NOW.isoformat(),
                },
                idempotency_key="core004:positive",
            ),
        )
        assert result.status.value == "completed"
        assert result.payload["receipt"]["status"] == "completed"
    finally:
        if gateway is not None:
            gateway.close()
        app.shutdown()
