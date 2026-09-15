from sofia.capability.model import (
    Capability,
    CapabilityRequest,
    CapabilityResultKind,
)
from sofia.capability.system import (
    CapabilityResolutionError,
    CapabilitySystem,
)


def make_capability() -> Capability:
    return Capability(
        name="test.inspect",
        description="Test inspection capability.",
    )


def make_request() -> CapabilityRequest:
    return CapabilityRequest(
        capability=make_capability(),
        parameters={"target": "example"},
        requested_scope=None,
        rationale="Inspect the example.",
    )


def test_capability_can_be_registered():
    system = CapabilitySystem(
        authorization_checker=lambda request: True,
    )

    capability = make_capability()

    system.register(
        capability,
        lambda request: {"observed": True},
    )

    assert system.resolve("test.inspect") is capability


def test_duplicate_capability_registration_is_rejected():
    system = CapabilitySystem(
        authorization_checker=lambda request: True,
    )

    capability = make_capability()

    system.register(
        capability,
        lambda request: {"observed": True},
    )

    try:
        system.register(
            capability,
            lambda request: {"observed": False},
        )
    except ValueError as exc:
        assert "already registered" in str(exc)
    else:
        raise AssertionError("Expected duplicate registration to fail.")


def test_unknown_capability_cannot_be_resolved():
    system = CapabilitySystem(
        authorization_checker=lambda request: True,
    )

    try:
        system.resolve("does.not.exist")
    except CapabilityResolutionError as exc:
        assert "does.not.exist" in str(exc)
    else:
        raise AssertionError("Expected resolution to fail.")


def test_unknown_capability_returns_unavailable_result():
    system = CapabilitySystem(
        authorization_checker=lambda request: True,
    )

    request = make_request()

    result = system.execute(request)

    assert result.kind is CapabilityResultKind.UNAVAILABLE
    assert result.evidence is None


def test_unauthorized_request_does_not_execute_capability():
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
    assert result.evidence is None
    assert executed is False


def test_authorized_request_executes_capability_once():
    executions = 0

    def handler(request):
        nonlocal executions
        executions += 1
        return {"observed": True}

    system = CapabilitySystem(
        authorization_checker=lambda request: True,
    )

    system.register(make_capability(), handler)

    result = system.execute(make_request())

    assert result.kind is CapabilityResultKind.SUCCESS
    assert result.evidence == {"observed": True}
    assert executions == 1


def test_authorization_is_checked_before_execution():
    events = []

    def authorize(request):
        events.append("authorize")
        return True

    def handler(request):
        events.append("execute")
        return {"observed": True}

    system = CapabilitySystem(
        authorization_checker=authorize,
    )

    system.register(make_capability(), handler)

    result = system.execute(make_request())

    assert result.kind is CapabilityResultKind.SUCCESS
    assert events == ["authorize", "execute"]


def test_missing_authorization_checker_denies_execution():
    executed = False

    def handler(request):
        nonlocal executed
        executed = True
        return {"observed": True}

    system = CapabilitySystem()

    system.register(make_capability(), handler)

    result = system.execute(make_request())

    assert result.kind is CapabilityResultKind.UNAUTHORIZED
    assert result.evidence is None
    assert executed is False


def test_capability_failure_becomes_structured_result():
    def handler(request):
        raise RuntimeError("inspection exploded")

    system = CapabilitySystem(
        authorization_checker=lambda request: True,
    )

    system.register(make_capability(), handler)

    result = system.execute(make_request())

    assert result.kind is CapabilityResultKind.FAILED
    assert result.evidence is None
    assert "inspection exploded" in result.error