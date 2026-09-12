from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Constitution:
    """
    Represents an immutable loaded version of Sofía's Constitution.
    """

    version: str
    content: str
    content_hash: str
    loaded_at: datetime