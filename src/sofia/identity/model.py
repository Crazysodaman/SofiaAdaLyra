from dataclasses import dataclass


@dataclass(frozen=True)
class SofiaIdentity:
    name: str