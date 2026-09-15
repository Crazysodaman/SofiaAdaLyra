import pytest

from sofia.capability.model import (
    Capability,
    CapabilityRequest,
    CapabilityResult,
    CapabilityResultKind,
)


def test_capability_requires_name():
    with pytest.raises(ValueError):
        Capability(
            name="",
            description="Filesystem inspection",
        )


def test_capability_requires_description():
    with pytest.raises(ValueError):
        Capability(
            name="filesystem.inspect",
            description="",
        )


def test_capability_is_immutable():
    capability = Capability(
        name="filesystem.inspect",
        description="Read-only filesystem inspection.",
    )

    with pytest.raises(AttributeError):
        capability.name = "filesystem.write"


def test_capability_request_requires_capability():
    capability = Capability(
        name="filesystem.inspect",
        description="Read-only filesystem inspection.",
    )

    request = CapabilityRequest(
        capability=capability,
        parameters={},
        requested_scope=None,
        rationale="Inspect the project.",
    )

    assert request.capability is capability


def test_capability_request_is_immutable():
    capability = Capability(
        name="filesystem.inspect",
        description="Read-only filesystem inspection.",
    )

    request = CapabilityRequest(
        capability=capability,
        parameters={},
        requested_scope=None,
        rationale="Inspect the project.",
    )

    with pytest.raises(AttributeError):
        request.rationale = "Changed"


def test_capability_request_requires_rationale():
    capability = Capability(
        name="filesystem.inspect",
        description="Read-only filesystem inspection.",
    )

    with pytest.raises(ValueError):
        CapabilityRequest(
            capability=capability,
            parameters={},
            requested_scope=None,
            rationale="",
        )


def test_capability_result_represents_success():
    result = CapabilityResult(
        capability="filesystem.inspect",
        kind=CapabilityResultKind.SUCCESS,
        evidence={"observed": True},
        error=None,
    )

    assert result.kind is CapabilityResultKind.SUCCESS
    assert result.evidence == {"observed": True}
    assert result.error is None


def test_capability_result_can_represent_unauthorized():
    result = CapabilityResult(
        capability="filesystem.inspect",
        kind=CapabilityResultKind.UNAUTHORIZED,
        evidence=None,
        error="Operation was not authorized.",
    )

    assert result.kind is CapabilityResultKind.UNAUTHORIZED
    assert result.evidence is None
    assert result.error == "Operation was not authorized."


def test_capability_result_is_immutable():
    result = CapabilityResult(
        capability="filesystem.inspect",
        kind=CapabilityResultKind.SUCCESS,
        evidence={"observed": True},
        error=None,
    )

    with pytest.raises(AttributeError):
        result.error = "Nope"