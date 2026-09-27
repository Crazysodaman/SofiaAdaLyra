from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from uuid import NAMESPACE_URL, uuid5

from sofia.habits.patterns import HabitPattern
from sofia.state.json_repository import JsonStateRepository
from sofia.state.namespaces import HABIT_EXPECTATION
from sofia.state.plane import StatePlane


class ExpectationStatus(str, Enum):
    PENDING = "pending"
    FULFILLED = "fulfilled"
    MISSED = "missed"
    UNCERTAIN = "uncertain"
    UNOBSERVABLE = "unobservable"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class HabitExpectation:
    expectation_id: str
    pattern_id: str
    principal_id: str
    audience_id: str
    window_start_utc: datetime
    window_end_utc: datetime
    local_window_start: datetime
    local_window_end: datetime
    timezone: str
    confidence_snapshot: float
    status: ExpectationStatus
    created_at: datetime
    resolved_at: datetime | None
    resolution_evidence_ref: str | None

    def __post_init__(self) -> None:
        for name in (
            "expectation_id", "pattern_id", "principal_id",
            "audience_id", "timezone",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be nonempty")
        for name in (
            "window_start_utc", "window_end_utc",
            "local_window_start", "local_window_end", "created_at",
        ):
            value = getattr(self, name)
            if not isinstance(value, datetime):
                raise TypeError(f"{name} must be a datetime")
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{name} must be timezone-aware")
        if self.window_end_utc <= self.window_start_utc:
            raise ValueError("expectation UTC window is invalid")
        if self.local_window_end <= self.local_window_start:
            raise ValueError("expectation local window is invalid")
        if not 0.0 <= self.confidence_snapshot <= 1.0:
            raise ValueError("confidence_snapshot must be in [0, 1]")
        if not isinstance(self.status, ExpectationStatus):
            raise TypeError("status must be ExpectationStatus")
        if self.status is ExpectationStatus.PENDING:
            if self.resolved_at is not None or self.resolution_evidence_ref is not None:
                raise ValueError("pending expectation cannot carry a resolution")
        else:
            if (
                self.resolved_at is None
                or self.resolved_at.tzinfo is None
                or self.resolved_at.utcoffset() is None
            ):
                raise ValueError("resolved expectation requires resolved_at")
            if self.resolution_evidence_ref is not None and (
                not isinstance(self.resolution_evidence_ref, str)
                or not self.resolution_evidence_ref.strip()
            ):
                raise ValueError("resolution_evidence_ref must be nonempty or None")


class HabitExpectationStore:
    def __init__(self, state_plane: StatePlane) -> None:
        if not isinstance(state_plane, StatePlane):
            raise TypeError("state_plane must be a StatePlane")
        self._repo = JsonStateRepository(state_plane, HABIT_EXPECTATION)

    @staticmethod
    def _value(item: HabitExpectation) -> dict:
        return {
            "expectation_id": item.expectation_id,
            "pattern_id": item.pattern_id,
            "principal_id": item.principal_id,
            "audience_id": item.audience_id,
            "window_start_utc": item.window_start_utc.isoformat(),
            "window_end_utc": item.window_end_utc.isoformat(),
            "local_window_start": item.local_window_start.isoformat(),
            "local_window_end": item.local_window_end.isoformat(),
            "timezone": item.timezone,
            "confidence_snapshot": item.confidence_snapshot,
            "status": item.status.value,
            "created_at": item.created_at.isoformat(),
            "resolved_at": (
                item.resolved_at.isoformat()
                if item.resolved_at is not None
                else None
            ),
            "resolution_evidence_ref": item.resolution_evidence_ref,
        }

    @staticmethod
    def _decode(value: dict) -> HabitExpectation:
        resolved_at = value.get("resolved_at")
        return HabitExpectation(
            expectation_id=value["expectation_id"],
            pattern_id=value["pattern_id"],
            principal_id=value["principal_id"],
            audience_id=value["audience_id"],
            window_start_utc=datetime.fromisoformat(value["window_start_utc"]),
            window_end_utc=datetime.fromisoformat(value["window_end_utc"]),
            local_window_start=datetime.fromisoformat(value["local_window_start"]),
            local_window_end=datetime.fromisoformat(value["local_window_end"]),
            timezone=value["timezone"],
            confidence_snapshot=float(value["confidence_snapshot"]),
            status=ExpectationStatus(value["status"]),
            created_at=datetime.fromisoformat(value["created_at"]),
            resolved_at=(
                None if resolved_at is None
                else datetime.fromisoformat(resolved_at)
            ),
            resolution_evidence_ref=value.get("resolution_evidence_ref"),
        )

    def get(
        self,
        expectation_id: str,
        *,
        principal_id: str,
        audience_id: str,
    ) -> HabitExpectation | None:
        item = self._repo.get(
            expectation_id,
            principal_id=principal_id,
            audience=audience_id,
        )
        return None if item is None else self._decode(item[0])

    def put(self, item: HabitExpectation, *, source: str) -> HabitExpectation:
        if not isinstance(item, HabitExpectation):
            raise TypeError("item must be HabitExpectation")
        self._repo.put(
            item.expectation_id,
            self._value(item),
            principal_id=item.principal_id,
            audience=item.audience_id,
            updated_at=item.resolved_at or item.created_at,
            source=source,
        )
        return item

    def list(
        self,
        *,
        principal_id: str,
        audience_id: str,
    ) -> tuple[HabitExpectation, ...]:
        rows = self._repo.list(
            principal_id=principal_id,
            audience=audience_id,
        )
        return tuple(sorted(
            (self._decode(value) for value, _ in rows),
            key=lambda item: (
                item.window_start_utc,
                item.expectation_id,
            ),
        ))


class HabitExpectationEngine:
    """Create and resolve expectations without changing habit confidence."""

    def __init__(self, store: HabitExpectationStore) -> None:
        if not isinstance(store, HabitExpectationStore):
            raise TypeError("store must be HabitExpectationStore")
        self._store = store

    @staticmethod
    def _utc(value: datetime) -> datetime:
        if (
            not isinstance(value, datetime)
            or value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ValueError("expectation timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    def create(
        self,
        *,
        pattern: HabitPattern,
        window_start_utc: datetime,
        window_end_utc: datetime,
        local_window_start: datetime,
        local_window_end: datetime,
        timezone_name: str,
        created_at: datetime,
    ) -> HabitExpectation:
        if not isinstance(pattern, HabitPattern):
            raise TypeError("pattern must be HabitPattern")
        start = self._utc(window_start_utc)
        end = self._utc(window_end_utc)
        created = self._utc(created_at)
        if end <= start:
            raise ValueError("expectation window is invalid")
        if pattern.lifecycle.value in ("retired", "suppressed"):
            raise ValueError("retired/suppressed patterns cannot create expectations")
        expectation_id = str(uuid5(
            NAMESPACE_URL,
            f"sofia-expectation:{pattern.pattern_id}:{start.isoformat()}:"
            f"{end.isoformat()}:{timezone_name}",
        ))
        item = HabitExpectation(
            expectation_id=expectation_id,
            pattern_id=pattern.pattern_id,
            principal_id=pattern.principal_id,
            audience_id=pattern.audience_id,
            window_start_utc=start,
            window_end_utc=end,
            local_window_start=local_window_start,
            local_window_end=local_window_end,
            timezone=timezone_name,
            confidence_snapshot=pattern.confidence,
            status=ExpectationStatus.PENDING,
            created_at=created,
            resolved_at=None,
            resolution_evidence_ref=None,
        )
        existing = self._store.get(
            expectation_id,
            principal_id=pattern.principal_id,
            audience_id=pattern.audience_id,
        )
        if existing is not None:
            return existing
        return self._store.put(
            item,
            source=f"habit-pattern:{pattern.pattern_id}",
        )

    def resolve(
        self,
        expectation: HabitExpectation,
        *,
        status: ExpectationStatus,
        resolved_at: datetime,
        evidence_ref: str | None,
    ) -> HabitExpectation:
        if not isinstance(expectation, HabitExpectation):
            raise TypeError("expectation must be HabitExpectation")
        if expectation.status is not ExpectationStatus.PENDING:
            return expectation
        if status is ExpectationStatus.PENDING:
            raise ValueError("resolution status cannot remain pending")
        if status in (
            ExpectationStatus.FULFILLED,
            ExpectationStatus.MISSED,
        ) and (
            not isinstance(evidence_ref, str)
            or not evidence_ref.strip()
        ):
            raise ValueError(
                "fulfilled/missed expectations require evidence"
            )
        current = self._utc(resolved_at)
        updated = replace(
            expectation,
            status=status,
            resolved_at=current,
            resolution_evidence_ref=evidence_ref,
        )
        return self._store.put(
            updated,
            source=evidence_ref or f"expectation:{status.value}",
        )
