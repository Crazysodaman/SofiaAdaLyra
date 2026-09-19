from datetime import datetime, timezone

import pytest

from sofia.external.authentication import (
    CredentialReference,
    ExternalAuthentication,
    ExternalAuthenticationMethod,
    ExternalAuthenticationState,
)


def test_credential_reference_is_opaque_and_immutable() -> None:
    reference = CredentialReference(
        reference_id="vault://github/token",
        provider="vault",
    )

    assert reference.reference_id == "vault://github/token"
    assert reference.provider == "vault"

    with pytest.raises(Exception):
        reference.reference_id = "secret"


@pytest.mark.parametrize(
    "value",
    ["", "   ", None, 123],
)
def test_credential_reference_requires_non_empty_reference(
    value,
) -> None:
    with pytest.raises((TypeError, ValueError)):
        CredentialReference(reference_id=value)


def test_authentication_can_be_unconfigured() -> None:
    authentication = ExternalAuthentication(
        system_id="github",
        method=ExternalAuthenticationMethod.API_KEY,
        state=ExternalAuthenticationState.NOT_CONFIGURED,
    )

    assert not authentication.is_authenticated
    assert not authentication.has_credentials


def test_verified_authentication_requires_reference() -> None:
    with pytest.raises(ValueError):
        ExternalAuthentication(
            system_id="github",
            method=ExternalAuthenticationMethod.API_KEY,
            state=ExternalAuthenticationState.VERIFIED,
        )


def test_verified_authentication_exposes_no_secret() -> None:
    reference = CredentialReference(
        reference_id="vault://github/token",
    )

    authentication = ExternalAuthentication(
        system_id="github",
        method=ExternalAuthenticationMethod.API_KEY,
        state=ExternalAuthenticationState.VERIFIED,
        credential_reference=reference,
        observed_at=datetime.now(timezone.utc),
    )

    assert authentication.is_authenticated
    assert authentication.has_credentials
    assert authentication.credential_reference == reference
    assert not hasattr(authentication, "secret")
    assert not hasattr(authentication, "token")
    assert not hasattr(authentication, "password")
    assert not hasattr(authentication, "private_key")


def test_none_authentication_cannot_have_credentials() -> None:
    with pytest.raises(ValueError):
        ExternalAuthentication(
            system_id="github",
            method=ExternalAuthenticationMethod.NONE,
            state=ExternalAuthenticationState.NOT_CONFIGURED,
            credential_reference=CredentialReference(
                reference_id="vault://github/token",
            ),
        )


@pytest.mark.parametrize(
    "state",
    [
        ExternalAuthenticationState.EXPIRED,
        ExternalAuthenticationState.INVALID,
        ExternalAuthenticationState.UNKNOWN,
    ],
)
def test_non_verified_states_are_not_authenticated(state) -> None:
    authentication = ExternalAuthentication(
        system_id="github",
        method=ExternalAuthenticationMethod.API_KEY,
        state=state,
    )

    assert not authentication.is_authenticated


def test_authentication_requires_valid_system_id() -> None:
    with pytest.raises(TypeError):
        ExternalAuthentication(
            system_id=123,
            method=ExternalAuthenticationMethod.API_KEY,
            state=ExternalAuthenticationState.UNKNOWN,
        )

    with pytest.raises(ValueError):
        ExternalAuthentication(
            system_id="",
            method=ExternalAuthenticationMethod.API_KEY,
            state=ExternalAuthenticationState.UNKNOWN,
        )


def test_authentication_validates_enum_types() -> None:
    with pytest.raises(TypeError):
        ExternalAuthentication(
            system_id="github",
            method="api_key",
            state=ExternalAuthenticationState.UNKNOWN,
        )

    with pytest.raises(TypeError):
        ExternalAuthentication(
            system_id="github",
            method=ExternalAuthenticationMethod.API_KEY,
            state="verified",
        )