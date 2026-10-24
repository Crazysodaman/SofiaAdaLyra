from __future__ import annotations

from sofia.core.social.model import AudienceKind, PrincipalContext

SPARKS_PRINCIPAL_ID = "person:sparks"
SOFIA_PRINCIPAL_ID = "sofia"


def sofia_core_principal() -> PrincipalContext:
    """Host-authenticated identity for Core-originated non-effect proposals.

    This context is never an owner identity and grants no execution authority.
    Platform still independently admits every installation or effect.
    """
    return PrincipalContext(
        principal_id=SOFIA_PRINCIPAL_ID,
        audience_id="system:core",
        audience_kind=AudienceKind.SYSTEM,
        display_name="Sofía",
    )


def local_sparks_principal(
    audience_id: str = "local:text",
) -> PrincipalContext:
    return PrincipalContext(
        principal_id=SPARKS_PRINCIPAL_ID,
        audience_id=audience_id,
        audience_kind=AudienceKind.PRIVATE,
        display_name="Sparks",
    )


def discord_sparks_principal(channel_id: int) -> PrincipalContext:
    if type(channel_id) is not int or channel_id <= 0:
        raise ValueError("channel_id must be a positive integer")
    return PrincipalContext(
        principal_id=SPARKS_PRINCIPAL_ID,
        audience_id=f"discord:dm:{channel_id}",
        audience_kind=AudienceKind.PRIVATE,
        display_name="Sparks",
    )

def remote_sparks_principal(
    client_public_key_sha256: str,
) -> PrincipalContext:
    if (
        not isinstance(client_public_key_sha256, str)
        or len(client_public_key_sha256) != 64
        or any(character not in "0123456789abcdefABCDEF" for character in client_public_key_sha256)
    ):
        raise ValueError("client_public_key_sha256 must be a SHA-256 digest")
    return PrincipalContext(
        principal_id=SPARKS_PRINCIPAL_ID,
        audience_id=f"remote-chat:{client_public_key_sha256[:16].lower()}",
        audience_kind=AudienceKind.PRIVATE,
        display_name="Sparks",
    )
