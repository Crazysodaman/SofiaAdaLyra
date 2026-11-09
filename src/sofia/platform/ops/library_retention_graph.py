"""D028-05 conservative B1 cache pin graph, no deletion or new authority.

The existing B1 PlatformInstallationStore remains the installed-release
authority. The installed service must supply independently verified asset
digests for *every* successful installation in history, not only the active
release, and a complete current stage/dependency/in-flight/operator pin
inventory while holding its canonical pin-revision lock.

A fabricated snapshot or a screen-derived inventory is NEVER an owner grant.
The resulting immutable fingerprint supports exact one-use GC approval and
stale-revision refusal in the separate local executor. Missing/inconsistent
provenance always denies deletion, including when the cache appears full.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from hashlib import sha256
import json
import re

from sofia.platform.ops.platform_installation import PlatformInstallationStore

_SHA = re.compile(r"[0-9a-f]{64}\Z")
_PLATFORM = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:@-]{0,159}\Z")
_MAX = 2**53 - 1
PIN_REASONS = frozenset({
    "ACTIVE", "STAGED", "INSTALLED_DEPENDENCY",
    "ROLLBACK_RETAINED", "IN_FLIGHT_VERIFICATION", "OPERATOR_PIN",
})
LIVE_PIN_REASONS = frozenset(PIN_REASONS - {"ROLLBACK_RETAINED"})


class LibraryRetentionDenied(PermissionError):
    """Unknown or stale B1 authority cannot authorize GC."""


def _validate_digests(items, *, allow_empty: bool) -> tuple[str, ...]:
    if (type(items) not in (tuple, list)
            or len(items) > 10000
            or (not allow_empty and not items)
            or any(type(value) is not str or _SHA.fullmatch(value) is None
                   for value in items)):
        raise LibraryRetentionDenied("complete bounded signed CAS digest inventory required")
    if len(set(items)) != len(items):
        raise LibraryRetentionDenied("duplicate signed CAS digest in pin source")
    return tuple(sorted(items))


@dataclass(frozen=True, slots=True)
class LibraryPinGraph:
    platform_id: str
    run_generation: int
    b1_generation: int
    b1_revision_floor: int
    installed_manifest_sha256: tuple[str, ...]
    pins: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        if type(self.platform_id) is not str or _PLATFORM.fullmatch(self.platform_id) is None:
            raise LibraryRetentionDenied("canonical Platform identity required")
        for field, minimum in (("run_generation", 1), ("b1_generation", 0),
                               ("b1_revision_floor", 0)):
            value = getattr(self, field)
            if type(value) is not int or not minimum <= value <= _MAX:
                raise LibraryRetentionDenied("bounded current generation and revision required")
        if _validate_digests(self.installed_manifest_sha256, allow_empty=True) != self.installed_manifest_sha256:
            raise LibraryRetentionDenied("installed manifest history must be canonical sorted")
        if type(self.pins) is not tuple or len(self.pins) > 20000:
            raise LibraryRetentionDenied("bounded immutable pin graph required")
        if tuple(sorted(set(self.pins))) != self.pins:
            raise LibraryRetentionDenied("pin graph must be unique and deterministically ordered")
        for entry in self.pins:
            if (type(entry) is not tuple or len(entry) != 2
                    or type(entry[0]) is not str
                    or _SHA.fullmatch(entry[0]) is None
                    or type(entry[1]) is not str
                    or entry[1] not in PIN_REASONS):
                raise LibraryRetentionDenied("unreviewed cache retention pin")

    @property
    def fingerprint(self) -> str:
        payload = {
            "schema": "aegis.platform.library.pin-graph.v1",
            "platform_id": self.platform_id,
            "run_generation": self.run_generation,
            "b1_generation": self.b1_generation,
            "b1_revision_floor": self.b1_revision_floor,
            "installed_manifest_sha256": list(self.installed_manifest_sha256),
            "pins": [list(item) for item in self.pins],
        }
        return sha256(json.dumps(
            payload, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        ).encode("utf-8")).hexdigest()

    def pin_reasons(self, content_sha256: str) -> tuple[str, ...]:
        if type(content_sha256) is not str or _SHA.fullmatch(content_sha256) is None:
            raise LibraryRetentionDenied("exact CAS digest required")
        return tuple(reason for digest, reason in self.pins if digest == content_sha256)


def build_library_pin_graph(
    *, store: PlatformInstallationStore,
    platform_id: str,
    run_generation: int,
    independently_verified_assets_for_manifest: Callable[[str], tuple[str, ...]],
    read_current_live_pins: Callable[[], Mapping[str, tuple[str, ...]]],
) -> LibraryPinGraph:
    """Read all B1 installation history and current live pins fail-closed.

    The installed Platform service must hold its *real* B1+RUN pin revision
    lock while calling this. The manifest lookup must verify signed publisher
    bytes and current retained rollback provenance, never a Hub self-claim.
    This function does not verify a caller-supplied closure's authority.
    """
    if not isinstance(store, PlatformInstallationStore):
        raise LibraryRetentionDenied("single canonical B1 installation store required")
    if not callable(independently_verified_assets_for_manifest) or not callable(read_current_live_pins):
        raise LibraryRetentionDenied("complete independently verified pin sources required")
    if store.pending_attempts():
        raise LibraryRetentionDenied("unresolved B1 installation attempt pins unknown")
    checkpoint = store.checkpoint()
    b1_generation = checkpoint.generation if checkpoint is not None else 0
    b1_floor = checkpoint.minimum_accepted_revision if checkpoint is not None else 0
    history = store.history()
    installed = sorted({
        row["manifest_sha256"] for row in history if row["result"] == "SUCCEEDED"
    })
    if len(installed) > 4096:
        raise LibraryRetentionDenied("unbounded installed manifest history")
    manifests = _validate_digests(installed, allow_empty=True)
    pins: set[tuple[str, str]] = set()
    for manifest_sha256 in manifests:
        assets = _validate_digests(
            independently_verified_assets_for_manifest(manifest_sha256),
            allow_empty=False,
        )
        # Historical successful installations MUST protect exact rollback
        # material, even when the installed release is not active today.
        pins.update((digest, "ROLLBACK_RETAINED") for digest in assets)
    live = read_current_live_pins()
    if type(live) is not dict or set(live) != LIVE_PIN_REASONS:
        raise LibraryRetentionDenied("incomplete installed/staged/dependency pin inventory")
    for reason in sorted(LIVE_PIN_REASONS):
        pins.update((digest, reason) for digest in _validate_digests(
            live[reason], allow_empty=True,
        ))
    # A torn B1 read cannot claim safe retention. The external lock is still
    # mandatory because a later generation may race the following checks.
    after = store.checkpoint()
    after_generation = after.generation if after is not None else 0
    after_floor = after.minimum_accepted_revision if after is not None else 0
    if (store.pending_attempts() or after_generation != b1_generation
            or after_floor != b1_floor
            or sorted({row["manifest_sha256"] for row in store.history()
                       if row["result"] == "SUCCEEDED"}) != installed):
        raise LibraryRetentionDenied("B1 pin graph changed during read")
    return LibraryPinGraph(
        platform_id=platform_id, run_generation=run_generation,
        b1_generation=b1_generation, b1_revision_floor=b1_floor,
        installed_manifest_sha256=manifests,
        pins=tuple(sorted(pins)),
    )
