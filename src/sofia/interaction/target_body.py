from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


_DEFAULT_TARGET_REGIONS = (
    "head",
    "hair",
    "forehead",
    "face",
    "cheek",
    "mouth",
    "neck",
    "shoulder",
    "upper-arm",
    "forearm",
    "hand",
    "chest",
    "upper-back",
    "lower-back",
    "waist",
    "side",
    "hip",
    "thigh",
    "knee",
    "lower-leg",
    "foot",
    "buttocks",
    "groin",
)

_PRIVATE_TARGET_REGIONS = frozenset({
    "chest",
    "buttocks",
    "groin",
})


@dataclass(frozen=True, slots=True)
class TargetRegion:
    region_id: str
    private: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.region_id, str) or not self.region_id.strip():
            raise ValueError("target region_id must be nonempty")
        if type(self.private) is not bool:
            raise TypeError("private must be boolean")


class RepresentedTargetBody:
    """Abstract target-body vocabulary independent of any avatar skeleton.

    This is semantic targeting only. It does not assert a physical body,
    sensation, hit-test, or renderer rig.
    """

    def __init__(
        self,
        *,
        subject_id: str,
        region_ids: tuple[str, ...] = _DEFAULT_TARGET_REGIONS,
    ) -> None:
        if not isinstance(subject_id, str) or not subject_id.strip():
            raise ValueError("subject_id must be nonempty")
        if (
            not isinstance(region_ids, tuple)
            or not region_ids
            or len(set(region_ids)) != len(region_ids)
        ):
            raise ValueError("region_ids must be a distinct nonempty tuple")
        regions = {}
        for region_id in region_ids:
            if not isinstance(region_id, str) or not region_id.strip():
                raise ValueError("target region IDs must be nonempty strings")
            regions[region_id] = TargetRegion(
                region_id=region_id,
                private=region_id in _PRIVATE_TARGET_REGIONS,
            )
        self.subject_id = subject_id
        self.regions: Mapping[str, TargetRegion] = MappingProxyType(regions)

    def has_region(self, region_id: str) -> bool:
        return region_id in self.regions

    def require_region(self, region_id: str) -> TargetRegion:
        try:
            return self.regions[region_id]
        except KeyError as exc:
            raise ValueError(
                f"unknown target-body region: {region_id}"
            ) from exc
