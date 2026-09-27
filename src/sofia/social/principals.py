from __future__ import annotations

from sofia.social.model import AudienceKind, PrincipalContext

SPARKS_PRINCIPAL_ID = "person:sparks"


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
