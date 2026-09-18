from sofia.capability.gateway import (
    CapabilityGateway,
)
from sofia.capability.model import (
    Capability,
    CapabilityResultKind,
)
from sofia.capability.proposal import (
    CapabilityProposal,
)
from sofia.capability.system import (
    CapabilitySystem,
)


def make_capability() -> Capability:
    return Capability(
        name="test.inspect",
        description="Test inspection capability.",
    )


def make_proposal() -> CapabilityProposal:
    return CapabilityProposal(
        capability_name="test.inspect",
        parameters={"target": "example"},
        rationale="Inspect the example.",
        requested_scope=None,
    )


def test_gateway_requires_capability_system():
    try:
        CapabilityGateway(object())
    except TypeError as exc:
        assert "CapabilitySystem" in str(exc)
    else:
        raise AssertionError(
            "Expected invalid capability system to fail."
        )


def test_gateway_requires_capability_proposal():
    system = CapabilitySystem(
        authorization_checker=lambda request: True,
    )

    gateway = CapabilityGateway(system)

    try:
        gateway.execute(object())
    except TypeError as exc:
        assert "CapabilityProposal" in str(exc)
    else:
        raise AssertionError(
            "Expected invalid proposal to fail."
        )


def test_gateway_returns_unavailable_for_unknown_capability():
    system = CapabilitySystem(
        authorization_checker=lambda request: True,
    )

    gateway = CapabilityGateway(system)

    result = gateway.execute(
        CapabilityProposal(
            capability_name="does.not.exist",
            parameters={},
            rationale="Attempt to use an unknown capability.",
        )
    )

    assert result.kind is CapabilityResultKind.UNAVAILABLE
    assert result.capability == "does.not.exist"
    assert result.evidence is None


def test_gateway_maps_proposal_to_canonical_request():
    observed = {}

    capability = make_capability()

    def authorize(request):
        observed["capability"] = request.capability
        observed["parameters"] = request.parameters
        observed["scope"] = request.requested_scope
        observed["rationale"] = request.rationale
        return True

    system = CapabilitySystem(
        authorization_checker=authorize,
    )

    system.register(
        capability,
        lambda request: {"observed": True},
    )

    gateway = CapabilityGateway(system)

    proposal = CapabilityProposal(
        capability_name=capability.name,
        parameters={"target": "example"},
        requested_scope="test-scope",
        rationale="Inspect the requested target.",
    )

    result = gateway.execute(proposal)

    assert result.kind is CapabilityResultKind.SUCCESS
    assert observed["capability"] is capability
    assert observed["parameters"] == {
        "target": "example",
    }
    assert observed["scope"] == "test-scope"
    assert observed["rationale"] == (
        "Inspect the requested target."
    )


def test_gateway_delegates_authorization_to_capability_system():
    executions = 0
    authorization_calls = 0

    def authorize(request):
        nonlocal authorization_calls
        authorization_calls += 1
        return False

    def handler(request):
        nonlocal executions
        executions += 1
        return {"observed": True}

    system = CapabilitySystem(
        authorization_checker=authorize,
    )

    system.register(
        make_capability(),
        handler,
    )

    gateway = CapabilityGateway(system)

    result = gateway.execute(
        make_proposal()
    )

    assert result.kind is CapabilityResultKind.UNAUTHORIZED
    assert result.evidence is None
    assert authorization_calls == 1
    assert executions == 0


def test_gateway_returns_capability_evidence():
    evidence = {
        "files": 3,
        "observed": True,
    }

    system = CapabilitySystem(
        authorization_checker=lambda request: True,
    )

    system.register(
        make_capability(),
        lambda request: evidence,
    )

    gateway = CapabilityGateway(system)

    result = gateway.execute(
        make_proposal()
    )

    assert result.kind is CapabilityResultKind.SUCCESS
    assert result.evidence == evidence


def test_gateway_does_not_bypass_capability_system_authorization():
    executions = 0

    def handler(request):
        nonlocal executions
        executions += 1
        return {"executed": True}

    system = CapabilitySystem(
        authorization_checker=lambda request: False,
    )

    system.register(
        make_capability(),
        handler,
    )

    gateway = CapabilityGateway(system)

    result = gateway.execute(
        make_proposal()
    )

    assert result.kind is CapabilityResultKind.UNAUTHORIZED
    assert executions == 0


def test_gateway_uses_registered_capability_identity():
    registered = make_capability()
    observed = {}

    def handler(request):
        observed["capability"] = request.capability
        return {"observed": True}

    system = CapabilitySystem(
        authorization_checker=lambda request: True,
    )

    system.register(
        registered,
        handler,
    )

    gateway = CapabilityGateway(system)

    result = gateway.execute(
        CapabilityProposal(
            capability_name=registered.name,
            parameters={},
            rationale="Execute the registered capability.",
        )
    )

    assert result.kind is CapabilityResultKind.SUCCESS
    assert observed["capability"] is registered


def test_gateway_has_no_direct_execution_handler():
    system = CapabilitySystem(
        authorization_checker=lambda request: True,
    )

    gateway = CapabilityGateway(system)

    assert not hasattr(gateway, "register")
    assert not hasattr(gateway, "resolve")