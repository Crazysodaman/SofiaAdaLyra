"""Owner-authenticated mobile chat and sensor application boundary."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from threading import RLock
import re
import sqlite3

from sofia.safe.permissions import PermissionStore
from sofia.social.model import AudienceKind, PrincipalContext
from sofia.social.principals import SPARKS_PRINCIPAL_ID
from sofia.avatar.private_grant import PrivatePresentationGrantResolver

from .model import MobileSensorReport
from .sensors import MobileSensorProvider, MobileSensorStore


_DEVICE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}")


class MobileCompanionGateway:
    """Serialize one private owner channel per paired phone."""

    def __init__(self, application, *, state_path: Path | str) -> None:
        if not callable(getattr(application, "open_channel_conversation", None)):
            raise TypeError("application must open channel conversations")
        self.application = application
        self.state_path = Path(state_path)
        self.sensors = MobileSensorStore(self.state_path)
        self.permissions = PermissionStore(self.state_path)
        self.private_grants = PrivatePresentationGrantResolver(
            state_path=self.state_path
        )
        self._conversations = {}
        self._lock = RLock()
        environment = getattr(self.application.runtime, "environment_service", None)
        if environment is not None and not any(
            provider.name == MobileSensorProvider.name
            for provider in environment.providers
        ):
            environment.register_provider(MobileSensorProvider(self.sensors))
        with self._connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS mobile_conversation_binding (
                    device_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL UNIQUE,
                    updated_at TEXT NOT NULL
                )
            """)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.state_path, timeout=10)
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _device(value: object) -> str:
        if not isinstance(value, str) or _DEVICE.fullmatch(value) is None:
            raise ValueError("invalid mobile device_id")
        return value

    def ingest_sensors(self, payload: object) -> dict[str, object]:
        report = MobileSensorReport.from_payload(payload)
        received = datetime.now(timezone.utc)
        self.sensors.record(report, received_at=received)
        environment = getattr(self.application.runtime, "environment_service", None)
        if environment is not None:
            environment.invalidate()
        return {
            "accepted": True,
            "observed_at": report.observed_at.isoformat(),
            "received_at": received.isoformat(),
        }

    def _conversation(self, device_id: str):
        existing = self._conversations.get(device_id)
        if existing is not None:
            return existing
        with self._connect() as db:
            row = db.execute(
                "SELECT session_id FROM mobile_conversation_binding WHERE device_id=?",
                (device_id,),
            ).fetchone()
        session_id = None if row is None else row[0]
        try:
            conversation = self.application.open_channel_conversation(
                session_id=session_id
            )
        except KeyError:
            conversation = self.application.open_channel_conversation()
        actual_session = conversation.session_id
        if actual_session is None:
            raise RuntimeError("mobile conversation did not start")
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO mobile_conversation_binding(device_id,session_id,updated_at)
                VALUES(?,?,?) ON CONFLICT(device_id) DO UPDATE SET
                    session_id=excluded.session_id, updated_at=excluded.updated_at
                """,
                (device_id, actual_session, datetime.now(timezone.utc).isoformat()),
            )
        self._conversations[device_id] = conversation
        return conversation

    @staticmethod
    def _principal(device_id: str, *, private_mode: bool):
        digest = sha256(device_id.encode("utf-8")).hexdigest()[:20]
        mode = "private" if private_mode else "standard"
        return PrincipalContext(
            principal_id=SPARKS_PRINCIPAL_ID,
            audience_id=f"mobile:{mode}:{digest}",
            audience_kind=(
                AudienceKind.PRIVATE if private_mode else AudienceKind.SHARED
            ),
            display_name="Sparks",
        )

    def chat(
        self,
        *,
        device_id: object,
        message: object,
        private_mode: object = False,
    ) -> dict[str, object]:
        device = self._device(device_id)
        if type(private_mode) is not bool:
            raise TypeError("private_mode must be a bool")
        if not isinstance(message, str) or not message.strip() or len(message) > 12_000:
            raise ValueError("mobile message must be 1..12000 characters")
        with self._lock:
            conversation = self._conversation(device)
            principal = self._principal(device, private_mode=private_mode)
            response = conversation.respond(
                message.strip(),
                principal=principal,
                channel=("mobile-private" if private_mode else "mobile-standard"),
            )
            return self._state_payload(
                conversation,
                response=response.content,
                principal=principal,
                private_mode=private_mode,
            )

    def state(
        self, *, device_id: object, private_mode: object = False
    ) -> dict[str, object]:
        device = self._device(device_id)
        if type(private_mode) is not bool:
            raise TypeError("private_mode must be a bool")
        with self._lock:
            return self._state_payload(
                self._conversation(device),
                response=None,
                principal=self._principal(device, private_mode=private_mode),
                private_mode=private_mode,
            )

    def _state_payload(
        self,
        conversation,
        *,
        response: str | None,
        principal,
        private_mode: bool,
    ) -> dict[str, object]:
        now = datetime.now(timezone.utc)
        state = conversation.current_emotional_state(now=now)
        expression = conversation.current_expression_plan
        grant = self.private_grants.resolve(
            principal=principal,
            explicit_current_opt_in=private_mode,
        )
        presentation = self.application.runtime.avatar_projection_for(
            principal=principal,
            private_grant=grant,
        )
        authority = self.permissions.private_adult_authority()
        result: dict[str, object] = {
            "as_of": now.isoformat(),
            "session_id": conversation.session_id,
            "private_owner_channel": True,
            "private_mode": private_mode,
            "adult_chat_enabled": (
                private_mode and authority.private_chat and authority.adult_chat
            ),
            "adult_avatar_enabled": (
                private_mode and authority.private_chat and authority.adult_avatar
            ),
            "emotion": {
                "tone": state.tone,
                "active": [
                    {"name": item.name, "intensity": item.intensity}
                    for item in state.active
                ],
            },
            "expression": None if expression is None else {
                "primary": expression.primary,
                "alternates": list(expression.alternates),
                "pose": expression.pose,
                "intensity": expression.intensity,
            },
            "avatar": None if presentation is None else {
                "outfit_id": presentation.outfit_id,
                "source_revision": presentation.source_revision,
            },
        }
        if response is not None:
            result["response"] = response
        return result
