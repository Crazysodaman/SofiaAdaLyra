from pathlib import Path

from sofia.capability.model import (
    Capability,
    CapabilityRequest,
    CapabilityResultKind,
)
from sofia.capability.system import CapabilitySystem


def make_capability() -> Capability:
    return Capability(
        name="test.inspect",
        description="Test inspection capability.",
    )


def make_request(
    requested_scope=None,
) -> CapabilityRequest:
    return CapabilityRequest(
        capability=make_capability(),
        parameters={},
        requested_scope=requested_scope,
        rationale="Inspect the test target.",
    )


def test_capability_request_does_not_contain_authority():
    request = make_request()

    assert not hasattr(request, "authority")
    assert not hasattr(request, "authorization")


def test_capability_does_not_contain_authority():
    capability = make_capability()

    assert not hasattr(capability, "authority")
    assert not hasattr(capability, "authorization")


def test_capability_availability_does_not_imply_authorization():
    executed = False

    def handler(request):
        nonlocal executed
        executed = True
        return {"observed": True}

    system = CapabilitySystem(
        authorization_checker=lambda request: False,
    )

    system.register(make_capability(), handler)

    result = system.execute(make_request())

    assert result.kind is CapabilityResultKind.UNAUTHORIZED
    assert executed is False


def test_cognition_request_does_not_bypass_authorization():
    executed = False

    def handler(request):
        nonlocal executed
        executed = True
        return {"observed": True}

    system = CapabilitySystem(
        authorization_checker=lambda request: False,
    )

    system.register(make_capability(), handler)

    request = make_request()

    result = system.execute(request)

    assert result.kind is CapabilityResultKind.UNAUTHORIZED
    assert executed is False


def test_capability_cannot_grant_itself_authorization():
    def handler(request):
        assert not hasattr(request, "authority")
        assert not hasattr(request, "authorization")
        return {"observed": True}

    system = CapabilitySystem(
        authorization_checker=lambda request: False,
    )

    system.register(make_capability(), handler)

    result = system.execute(make_request())

    assert result.kind is CapabilityResultKind.UNAUTHORIZED
    assert result.evidence is None


def test_unauthorized_result_contains_no_evidence():
    system = CapabilitySystem(
        authorization_checker=lambda request: False,
    )

    system.register(
        make_capability(),
        lambda request: {"observed": True},
    )

    result = system.execute(make_request())

    assert result.kind is CapabilityResultKind.UNAUTHORIZED
    assert result.evidence is None


def test_authorization_checker_receives_requested_scope():
    observed = []

    def authorize(request):
        observed.append(request.requested_scope)
        return True

    system = CapabilitySystem(
        authorization_checker=authorize,
    )

    system.register(
        make_capability(),
        lambda request: {"observed": True},
    )

    requested_scope = Path("scope")

    result = system.execute(
        make_request(
            requested_scope=requested_scope,
        )
    )

    assert result.kind is CapabilityResultKind.SUCCESS
    assert observed == [requested_scope]


def test_authorization_checker_can_reject_requested_scope():
    executed = False

    def handler(request):
        nonlocal executed
        executed = True
        return {"observed": True}

    def authorize(request):
        return request.requested_scope == Path("authorized")

    system = CapabilitySystem(
        authorization_checker=authorize,
    )

    system.register(
        make_capability(),
        handler,
    )

    result = system.execute(
        make_request(
            requested_scope=Path("outside"),
        )
    )

    assert result.kind is CapabilityResultKind.UNAUTHORIZED
    assert result.evidence is None
    assert executed is False


def test_requested_scope_is_not_authority():
    executed = False

    def handler(request):
        nonlocal executed
        executed = True
        return {"observed": True}

    system = CapabilitySystem(
        authorization_checker=lambda request: False,
    )

    system.register(
        make_capability(),
        handler,
    )

    result = system.execute(
        make_request(
            requested_scope=Path("pretend-authorized"),
        )
    )

    assert result.kind is CapabilityResultKind.UNAUTHORIZED
    assert result.evidence is None
    assert executed is False


def test_authorized_requested_scope_reaches_handler():
    executed_scope = None

    def handler(request):
        nonlocal executed_scope
        executed_scope = request.requested_scope
        return {"observed": True}

    authorized_scope = Path("authorized")

    system = CapabilitySystem(
        authorization_checker=lambda request: (
            request.requested_scope == authorized_scope
        ),
    )

    system.register(
        make_capability(),
        handler,
    )

    result = system.execute(
        make_request(
            requested_scope=authorized_scope,
        )
    )

    assert result.kind is CapabilityResultKind.SUCCESS
    assert result.evidence == {"observed": True}
    assert executed_scope == authorized_scope