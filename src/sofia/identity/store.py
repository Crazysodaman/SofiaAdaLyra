import json
from enum import Enum
from pathlib import Path
from uuid import UUID, uuid4

from sofia.identity.model import SofiaIdentity


class IdentityStoreError(Exception):
    """Raised when persisted identity data is invalid or unavailable."""


class IdentityBootstrapMode(str, Enum):
    """Controls whether this store may create canonical identity."""

    EXISTING_ONLY = "existing_only"
    FIRST_BOOTSTRAP = "first_bootstrap"


class IdentityStore:
    """
    Persists and loads Sofía's canonical identity.

    Normal runtimes are EXISTING_ONLY. A missing or incomplete identity must
    therefore fail closed instead of silently minting a second Sofía. Creation
    is permitted only through explicitly selected FIRST_BOOTSTRAP mode.
    """

    def __init__(
        self,
        identity_path: Path,
        *,
        bootstrap_mode: IdentityBootstrapMode = IdentityBootstrapMode.EXISTING_ONLY,
    ):
        if not isinstance(identity_path, Path):
            raise TypeError("IdentityStore identity_path must be a Path.")
        if not isinstance(bootstrap_mode, IdentityBootstrapMode):
            raise TypeError(
                "IdentityStore bootstrap_mode must be an "
                "IdentityBootstrapMode."
            )
        self.identity_path = identity_path
        self.bootstrap_mode = bootstrap_mode

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

    def bootstrap(
        self,
        *,
        name: str = "Sofía Ada Lyra",
        instance_id: UUID | None = None,
    ) -> SofiaIdentity:
        """Create canonical identity only in explicit first-bootstrap mode."""

        if self.bootstrap_mode is not IdentityBootstrapMode.FIRST_BOOTSTRAP:
            raise IdentityStoreError(
                "Canonical identity bootstrap is not authorized for this "
                "runtime."
            )
        if self.identity_path.exists():
            raise IdentityStoreError(
                "Canonical identity already exists; refusing second bootstrap."
            )
        identity = SofiaIdentity(
            name=name,
            instance_id=instance_id or uuid4(),
        )
        self.save(identity)
        return identity

    def load(self) -> SofiaIdentity:
        if not self.identity_path.exists():
            if self.bootstrap_mode is IdentityBootstrapMode.FIRST_BOOTSTRAP:
                return self.bootstrap()
            raise IdentityStoreError(
                "Canonical identity is missing. A normal or joining runtime "
                "must recover/verify the existing identity instead of creating "
                "a replacement."
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

        name = self._load_name(data)
        instance_id = self._load_instance_id(data)

        if instance_id is None:
            raise IdentityStoreError(
                "Canonical identity is missing instance_id. Refusing to mint "
                "a replacement identity from an incomplete record."
            )

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
