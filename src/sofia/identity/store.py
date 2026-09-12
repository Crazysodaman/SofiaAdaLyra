import json
from pathlib import Path

from sofia.identity.model import SofiaIdentity


class IdentityStoreError(Exception):
    """Raised when persisted identity data is invalid."""


class IdentityStore:
    """
    Persists and loads Sofía's identity.
    """

    def __init__(self, identity_path: Path):
        self.identity_path = identity_path

    def save(self, identity: SofiaIdentity) -> None:
        self.identity_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        data = {
            "name": identity.name,
        }

        self.identity_path.write_text(
            json.dumps(
                data,
                ensure_ascii=False,
                indent=4,
            ),
            encoding="utf-8",
        )

    def load(self) -> SofiaIdentity:
        if not self.identity_path.exists():
            return SofiaIdentity(
                name="Sofía Ada Lyra",
            )

        try:
            data = json.loads(
                self.identity_path.read_text(
                    encoding="utf-8",
                )
            )
        except (OSError, json.JSONDecodeError) as exc:
            raise IdentityStoreError(
                "Identity data could not be loaded."
            ) from exc

        if not isinstance(data, dict):
            raise IdentityStoreError(
                "Identity data must be a JSON object."
            )

        if "name" not in data:
            raise IdentityStoreError(
                "Identity data is missing the name."
            )

        name = data["name"]

        if not isinstance(name, str):
            raise IdentityStoreError(
                "Identity name must be a string."
            )

        if not name.strip():
            raise IdentityStoreError(
                "Identity name cannot be empty."
            )

        return SofiaIdentity(
            name=name,
        )