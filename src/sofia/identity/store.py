import json
from pathlib import Path
from uuid import UUID, uuid4

from sofia.identity.model import SofiaIdentity


class IdentityStoreError(Exception):
    """Raised when persisted identity data is invalid."""


class IdentityStore:
    """
    Persists and loads Sofía's identity.

    The instance_id is generated exactly once for a new identity and
    persisted thereafter. This provides a stable logical identity across
    application restarts and processes.
    """

    def __init__(self, identity_path: Path):
        self.identity_path = identity_path

    def save(self, identity: SofiaIdentity) -> None:
        if not isinstance(identity, SofiaIdentity):
            raise TypeError(
                "IdentityStore identity must be a SofiaIdentity."
            )

        self.identity_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        data = {
            "name": identity.name,
            "instance_id": str(identity.instance_id),
        }

        try:
            self.identity_path.write_text(
                json.dumps(
                    data,
                    ensure_ascii=False,
                    indent=4,
                ),
                encoding="utf-8",
            )
        except OSError as exc:
            raise IdentityStoreError(
                "Identity data could not be saved."
            ) from exc

    def load(self) -> SofiaIdentity:
        if not self.identity_path.exists():
            identity = SofiaIdentity(
                name="Sofía Ada Lyra",
                instance_id=uuid4(),
            )

            self.save(identity)

            return identity

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

        name = self._load_name(data)

        instance_id = self._load_instance_id(data)

        if instance_id is None:
            instance_id = uuid4()

            identity = SofiaIdentity(
                name=name,
                instance_id=instance_id,
            )

            self.save(identity)

            return identity

        return SofiaIdentity(
            name=name,
            instance_id=instance_id,
        )

    @staticmethod
    def _load_name(data: dict) -> str:
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

        return name

    @staticmethod
    def _load_instance_id(
        data: dict,
    ) -> UUID | None:
        if "instance_id" not in data:
            return None

        value = data["instance_id"]

        if not isinstance(value, str):
            raise IdentityStoreError(
                "Identity instance_id must be a string."
            )

        try:
            return UUID(value)
        except ValueError as exc:
            raise IdentityStoreError(
                "Identity instance_id must be a valid UUID."
            ) from exc