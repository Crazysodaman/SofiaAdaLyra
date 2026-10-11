"""Owner-authenticated mobile chat and sensor application boundary."""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from threading import RLock
import re
import sqlite3

from sofia.safe.permissions import PermissionStore
from sofia.social.model import AudienceKind, PrincipalContext
from sofia.social.store import SocialSessionStore
from sofia.social.principals import SPARKS_PRINCIPAL_ID
from sofia.avatar.private_grant import PrivatePresentationGrantResolver

from .model import MobileSensorReport
from .notifications import MobileNotificationStore
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
        self.notifications = MobileNotificationStore(self.state_path)
        self.permissions = PermissionStore(self.state_path)
        self.private_grants = PrivatePresentationGrantResolver(
            state_path=self.state_path
        )
        self._conversations = {}
        self._lock = RLock()
        self._social_sessions = SocialSessionStore(self.state_path)
        environment = getattr(self.application.runtime, "environment_service", None)
        if environment is not None and not any(
            provider.name == MobileSensorProvider.name
            for provider in environment.providers
        ):
            environment.register_provider(MobileSensorProvider(self.sensors))
        with closing(self._connect()) as db, db:
            # Keep the old single-mode table for verified, read-only migration.
            # A device may have a distinct PRIVATE and SHARED conversation.
            db.execute("""
                CREATE TABLE IF NOT EXISTS mobile_conversation_binding (
                    device_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL UNIQUE,
                    updated_at TEXT NOT NULL
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS mobile_conversation_binding_v2 (
                    device_id TEXT NOT NULL,
                    presentation_mode TEXT NOT NULL
                        CHECK(presentation_mode IN ('private','standard')),
                    session_id TEXT NOT NULL UNIQUE,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(device_id,presentation_mode)
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

    def _conversation(self, device_id: str, *, private_mode: bool):
        """Resume only the session belonging to the exact device AND audience.

        Legacy device-only sessions migrate if their CURRENT authenticated
        social binding matches the requested mode. An ambiguous or foreign
        legacy session is never reused for private conversation.
        """
        mode = "private" if private_mode else "standard"
        principal = self._principal(device_id, private_mode=private_mode)
        key = (device_id, mode)
        existing = self._conversations.get(key)
        if existing is not None:
            return existing
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT session_id FROM mobile_conversation_binding_v2 "
                "WHERE device_id=? AND presentation_mode=?",
                key,
            ).fetchone()
            if row is not None:
                session_id = row[0]
                current = self._social_sessions.get(session_id)
                if current is not None and (
                    current.principal_id != principal.principal_id
                    or current.audience_id != principal.audience_id
                    or current.audience_kind is not principal.audience_kind
                ):
                    raise PermissionError(
                        "stored mobile session changed its authenticated audience"
                    )
            else:
                legacy = db.execute(
                    "SELECT session_id FROM mobile_conversation_binding WHERE device_id=?",
                    (device_id,),
                ).fetchone()
                candidate = None if legacy is None else legacy[0]
                bound = None if candidate is None else self._social_sessions.get(candidate)
                session_id = candidate if (
                    bound is not None
                    and bound.principal_id == principal.principal_id
                    and bound.audience_id == principal.audience_id
                    and bound.audience_kind is principal.audience_kind
                ) else None

        try:
            conversation = self.application.open_channel_conversation(
                session_id=session_id
            )
        except (KeyError, ValueError):
            if row is not None:
                # Broken or deleted bound sessions are not silently replaced.
                raise
            conversation = self.application.open_channel_conversation()
        actual_session = conversation.session_id
        if not isinstance(actual_session, str) or not actual_session:
            raise RuntimeError("mobile conversation did not start")
        with closing(self._connect()) as db, db:
            db.execute(
                "INSERT INTO mobile_conversation_binding_v2 "
                "(device_id,presentation_mode,session_id,updated_at) "
                "VALUES(?,?,?,?) "
                "ON CONFLICT(device_id,presentation_mode) DO UPDATE SET "
                "session_id=excluded.session_id,updated_at=excluded.updated_at",
                (device_id, mode, actual_session, datetime.now(timezone.utc).isoformat()),
            )
        self._conversations[key] = conversation
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
            if private_mode and not self.permissions.private_adult_authority().private_chat:
                # Evaluate durable SAFE authority immediately before chat
                # dispatch, not before waiting on another device's turn.
                raise PermissionError("private mobile chat requires the host private-chat grant")
            conversation = self._conversation(device, private_mode=private_mode)
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
                self._conversation(device, private_mode=private_mode),
                response=None,
                principal=self._principal(device, private_mode=private_mode),
                private_mode=private_mode,
            )

    def main_history(
        self, *, device_id: object, private_mode: object = False,
        before: object = None, limit: object = 30,
    ) -> dict[str, object]:
        """Authenticated read of canonical Main, never cross-audience disclosure.

        Cursor is the linked timestamp and original source message ID.
        The phone cannot supply a principal or select another source audience.
        """
        device = self._device(device_id)
        if type(private_mode) is not bool:
            raise TypeError("private_mode must be a bool")
        if type(limit) is not int or not 1 <= limit <= 50:
            raise ValueError("Main page limit must be 1..50")
        cursor = None
        if before is not None:
            if not isinstance(before, dict) or set(before) != {
                "linked_at", "message_id",
            }:
                raise ValueError("Main cursor schema is invalid")
            raw_time, raw_id = before["linked_at"], before["message_id"]
            if not isinstance(raw_time, str) or not isinstance(raw_id, str):
                raise TypeError("Main cursor fields must be strings")
            if not 1 <= len(raw_time) <= 64 or not 1 <= len(raw_id) <= 160:
                raise ValueError("Main cursor fields exceed bounds")
            timestamp = datetime.fromisoformat(raw_time)
            if timestamp.tzinfo is None or timestamp.utcoffset() is None:
                raise ValueError("Main cursor timestamp must be timezone-aware")
            cursor = (timestamp, raw_id)

        principal = self._principal(device, private_mode=private_mode)
        if private_mode and not self.permissions.private_adult_authority().private_chat:
            raise PermissionError("private Main history requires the host private-chat grant")
        with self._lock:
            page = self.application.main_thread_page(
                principal=principal, before=cursor, limit=limit,
            )
        messages = [
            {
                "id": item.message.id,
                "role": item.message.role.value,
                "content": item.message.content,
                "created_at": item.message.created_at.isoformat(),
                "linked_at": item.linked_at.isoformat(),
            }
            for item in page
        ]
        first = page[0] if page else None
        return {
            "messages": messages,
            "next_before": (
                None if first is None else {
                    "linked_at": first.linked_at.isoformat(),
                    "message_id": first.message.id,
                }
            ),
            "has_more": len(page) == limit,
            "audience_kind": principal.audience_kind.value,
        }

    def claim_notification(
        self, *, device_id: object, private_mode: object = False
    ) -> dict[str, object]:
        device = self._device(device_id)
        if type(private_mode) is not bool:
            raise TypeError("private_mode must be a bool")
        authority = self.permissions.private_adult_authority()
        if authority.adult_external_delivery and not private_mode:
            return {
                "notification": None,
                "blocked_reason": "private_mode_required",
            }
        notification = self.notifications.claim_next(
            device_id=device,
            now=datetime.now(timezone.utc),
        )
        if notification is None:
            return {"notification": None}
        full_preview = bool(
            private_mode
            and authority.private_chat
            and authority.adult_external_delivery
        )
        return {
            "notification": {
                "id": notification.notification_id,
                "title": notification.title,
                "content": notification.content,
                "preview": (
                    notification.content
                    if full_preview
                    else "Sofía has something she wants to share with you."
                ),
                "full_preview_authorized": full_preview,
                "created_at": notification.created_at.isoformat(),
            }
        }

    def acknowledge_notification(
        self, *, device_id: object, notification_id: object
    ) -> dict[str, object]:
        device = self._device(device_id)
        if not isinstance(notification_id, str):
            raise TypeError("notification_id must be a string")
        self.notifications.acknowledge(
            notification_id,
            device_id=device,
            now=datetime.now(timezone.utc),
        )
        return {"acknowledged": True}

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
        expression_runtime = getattr(self.application, "expression_runtime", None)
        decision = (
            None if expression_runtime is None
            else expression_runtime.latest(principal)
        )
        output_receipts = (
            () if decision is None
            else expression_runtime.receipts(decision.decision_id)
        )
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
            "expression_output": None if decision is None else {
                "decision_id": decision.decision_id,
                "message_id": decision.message_id,
                "gesture": decision.gesture,
                "pose": decision.pose,
                "receipts": [
                    {
                        "output": item.output,
                        "status": item.status,
                        "acknowledged": item.acknowledged,
                        "backend": item.backend,
                        "occurred_at": item.occurred_at.isoformat(),
                    }
                    for item in output_receipts
                ],
            },
            "avatar": None if presentation is None else {
                "outfit_id": presentation.outfit_id,
                "source_revision": presentation.source_revision,
            },
        }
        if response is not None:
            result["response"] = response
        return result
