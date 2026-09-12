from dataclasses import dataclass


@dataclass(frozen=True)
class PersonalityProfile:
    name: str
    traits: tuple[str, ...] = ()
    communication_style: str = ""