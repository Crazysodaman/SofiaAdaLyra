import json
from pathlib import Path

from sofia.personality.model import PersonalityProfile
from sofia.state.atomic_file import atomic_write_text


class PersonalityStoreError(Exception):
    """Raised when personality persistence fails."""


class PersonalityStore:
    """
    Persists Sofía's personality profile.

    The store is responsible only for serialization and persistence.
    It does not contain personality behavior or runtime logic.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def save(self, profile: PersonalityProfile) -> None:
        if not isinstance(profile, PersonalityProfile):
            raise TypeError(
                "PersonalityStore profile must be a PersonalityProfile."
            )

        data = {
            "name": profile.name,
            "traits": list(profile.traits),
            "communication_style": profile.communication_style,
            "embodiment_guidance": profile.embodiment_guidance,
        }

        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_text(
                self._path,
                json.dumps(
                    data,
                    indent=2,
                    ensure_ascii=False,
                )
                + "\n",
            )
        except OSError as exc:
            raise PersonalityStoreError(
                "Failed to save personality profile."
            ) from exc

    def load(self) -> PersonalityProfile:
        try:
            data = json.loads(
                self._path.read_text(encoding="utf-8-sig")
            )
        except FileNotFoundError as exc:
            raise PersonalityStoreError(
                "Personality profile file does not exist."
            ) from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise PersonalityStoreError(
                "Failed to load personality profile."
            ) from exc

        if not isinstance(data, dict):
            raise PersonalityStoreError(
                "Personality profile data must be a JSON object."
            )

        try:
            name = data["name"]
            traits = data["traits"]
            communication_style = data["communication_style"]
        except KeyError as exc:
            raise PersonalityStoreError(
                "Personality profile is missing a required field."
            ) from exc

        embodiment_guidance = data.get(
            "embodiment_guidance",
            "",
        )

        if not isinstance(name, str):
            raise PersonalityStoreError(
                "Personality profile name must be a string."
            )

        if not isinstance(traits, list):
            raise PersonalityStoreError(
                "Personality profile traits must be a list."
            )

        if not all(isinstance(trait, str) for trait in traits):
            raise PersonalityStoreError(
                "Personality profile traits must contain strings."
            )

        if not isinstance(communication_style, str):
            raise PersonalityStoreError(
                "Personality profile communication_style must be a string."
            )

        if not isinstance(embodiment_guidance, str):
            raise PersonalityStoreError(
                "Personality profile embodiment_guidance must be a string."
            )

        try:
            return PersonalityProfile(
                name=name,
                traits=tuple(traits),
                communication_style=communication_style,
                embodiment_guidance=embodiment_guidance,
            )
        except (TypeError, ValueError) as exc:
            raise PersonalityStoreError(
                "Personality profile contains invalid data."
            ) from exc