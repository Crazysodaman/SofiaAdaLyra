from __future__ import annotations

from types import MethodType

from sofia.avatar.private_grant import PrivatePresentationGrantResolver
from sofia.safe.operator_stop import OperatorStopStore
from sofia.social.principals import local_sparks_principal


def test_private_grant_fails_closed_when_operator_stop_state_is_unreadable(
    tmp_path,
):
    state_path = tmp_path / "sofia.db"
    store = OperatorStopStore(state_path)

    def fail_current(self):
        raise RuntimeError("synthetic stop-store failure")

    store.current = MethodType(fail_current, store)
    resolver = PrivatePresentationGrantResolver(
        state_path=state_path,
        adult_verified=True,
        operator_stop_store=store,
    )

    assert resolver.resolve(
        principal=local_sparks_principal(),
        explicit_current_opt_in=True,
    ) is None
    assert resolver.last_error == "RuntimeError"


def test_private_grant_skips_stop_lookup_when_basic_eligibility_fails(
    tmp_path,
):
    state_path = tmp_path / "sofia.db"
    store = OperatorStopStore(state_path)
    calls = []

    def fail_if_called(self):
        calls.append("called")
        raise AssertionError("stop evidence should not be read")

    store.current = MethodType(fail_if_called, store)
    resolver = PrivatePresentationGrantResolver(
        state_path=state_path,
        adult_verified=False,
        operator_stop_store=store,
    )

    assert resolver.resolve(
        principal=local_sparks_principal(),
        explicit_current_opt_in=True,
    ) is None
    assert calls == []
    assert resolver.last_error is None
