from types import MappingProxyType

from sofia.personality.model import PersonalityProfile


class PersonalitySystem:
    def __init__(self, profile: PersonalityProfile) -> None:
        self._profile = profile

    @property
    def profile(self) -> PersonalityProfile:
        return self._profile

    @property
    def traits(self) -> tuple[str, ...]:
        return self._profile.traits

    @property
    def communication_style(self) -> str:
        return self._profile.communication_style

    @property
    def embodiment_guidance(self) -> str:
        return self._profile.embodiment_guidance

    def context(self) -> MappingProxyType:
        return MappingProxyType({
            "name": self._profile.name,
            "traits": self._profile.traits,
            "communication_style": self._profile.communication_style,
            "embodiment_guidance": self._profile.embodiment_guidance,
        })