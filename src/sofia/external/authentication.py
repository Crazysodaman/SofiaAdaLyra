from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ExternalAuthenticationMethod(str, Enum):
    NONE = "none"
    API_KEY = "api_key"
    BEARER_TOKEN = "bearer_token"
    BASIC = "basic"
    OAUTH2 = "oauth2"
    SSH_KEY = "ssh_key"
    CERTIFICATE = "certificate"
    OTHER = "other"


class ExternalAuthenticationState(str, Enum):
    NOT_CONFIGURED = "not_configured"
    AVAILABLE = "available"
    VERIFIED = "verified"
    EXPIRED = "expired"
    INVALID = "invalid"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class CredentialReference:
    """
    Opaque reference to authentication material.

    The reference identifies credential material managed outside Sofía's
    ordinary external-system models. It must never contain the secret
    itself.
    """

    reference_id: str
    provider: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.reference_id, str):
            raise TypeError("reference_id must be a string.")

        if not self.reference_id.strip():
            raise ValueError("reference_id must not be empty.")

        if self.provider is not None:
            if not isinstance(self.provider, str):
                raise TypeError("provider must be a string or None.")

            if not self.provider.strip():
                raise ValueError("provider must not be empty.")


@dataclass(frozen=True)
class ExternalAuthentication:
    """
    Authentication state for one external system.

    This model describes whether authentication material is configured
    or verified. It does not contain passwords, tokens, keys, secrets,
    or authorization decisions.
    """

    system_id: str
    method: ExternalAuthenticationMethod
    state: ExternalAuthenticationState
    credential_reference: CredentialReference | None = None
    observed_at: object | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.system_id, str):
            raise TypeError("system_id must be a string.")

        if not self.system_id.strip():
            raise ValueError("system_id must not be empty.")

        if not isinstance(
            self.method,
            ExternalAuthenticationMethod,
        ):
            raise TypeError(
                "method must be an ExternalAuthenticationMethod."
            )

        if not isinstance(
            self.state,
            ExternalAuthenticationState,
        ):
            raise TypeError(
                "state must be an ExternalAuthenticationState."
            )

        if (
            self.credential_reference is not None
            and not isinstance(
                self.credential_reference,
                CredentialReference,
            )
        ):
            raise TypeError(
                "credential_reference must be a "
                "CredentialReference or None."
            )

        if (
            self.state
            in {
                ExternalAuthenticationState.AVAILABLE,
                ExternalAuthenticationState.VERIFIED,
            }
            and self.credential_reference is None
        ):
            raise ValueError(
                "Configured authentication state requires a "
                "credential reference."
            )

        if (
            self.method is ExternalAuthenticationMethod.NONE
            and self.credential_reference is not None
        ):
            raise ValueError(
                "NONE authentication must not contain a "
                "credential reference."
            )

    @property
    def is_authenticated(self) -> bool:
        return self.state is ExternalAuthenticationState.VERIFIED

    @property
    def has_credentials(self) -> bool:
        return self.credential_reference is not None