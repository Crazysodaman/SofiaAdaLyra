"""Owner-authenticated mobile chat and sensor application boundary."""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from threading import RLock
import re
import sqlite3

from sofia.state.canonical_sqlite import CanonicalSQLiteGuard
from sofia.conversation.lifelong import LifelongThreadStore
from sofia.safe.permissions import PermissionStore
from sofia.social.model import AudienceKind, PrincipalContext
from sofia.social.store import SocialSessionStore
from sofia.social.principals import SPARKS_PRINCIPAL_ID
from sofia.avatar.private_grant import PrivatePresentationGrantResolver

from .pairing import MobileDeviceCredentialStore
from .main_seen import MobileMainSeenStore
from .model import MobileSensorReport
from .notifications import MobileNotificationStore
from .sensors import MobileSensorProvider, MobileSensorStore


_DEVICE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}")
_REQUEST = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{7,127}")


class MobileDeliveryConflict(RuntimeError):
    """Request ID was already used for another payload or conversation."""


class MobileDeliveryUncertain(RuntimeError):
    """The host cannot prove an earlier turn did not execute; never replay."""


class MobileCredentialRevoked(PermissionError):
    """The enrolled credential stopped being valid before actual execution."""


class MobileRouteNotFound(LookupError):
    """No authenticated mobile operation is registered for this route."""



class MobileCompanionGateway:
    """Serialize one private owner channel per paired phone."""

    def __init__(self, application, *, state_path: Path | str) -> None:
        if not callable(getattr(application, "open_channel_conversation", None)):
            raise TypeError("application must open channel conversations")
        self.application = application
        self.state_path = Path(state_path)
        self._guard = CanonicalSQLiteGuard(self.state_path)
        # Validate the one configured writer database BEFORE any
        # convenience/sensor layer can seed tables or directories.
        self.credentials = MobileDeviceCredentialStore(self.state_path)
        self.sensors = MobileSensorStore(self.state_path)
        self.notifications = MobileNotificationStore(self.state_path)
        self.main_seen = MobileMainSeenStore(self.state_path)
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
            db.execute("""
                CREATE TABLE IF NOT EXISTS mobile_turn_receipt (
                    request_id TEXT PRIMARY KEY,
                    device_id TEXT NOT NULL,
                    presentation_mode TEXT NOT NULL
                        CHECK(presentation_mode IN ('private','standard')),
                    content_sha256 TEXT NOT NULL,
                    status TEXT NOT NULL
                        CHECK(status IN ('processing','completed','uncertain')),
                    response_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            db.execute("""
                CREATE INDEX IF NOT EXISTS mobile_turn_receipt_device
                ON mobile_turn_receipt(device_id,presentation_mode,created_at)
            """)
            # V2 is preserved as read-only generation-one migration evidence.
            # V3 owns the durable *versioned* device-session relationship.
            db.execute("""
                CREATE TABLE IF NOT EXISTS mobile_conversation_binding_v3 (
                    device_id TEXT NOT NULL,
                    presentation_mode TEXT NOT NULL CHECK(
                        presentation_mode IN ('private','standard')
                    ),
                    credential_generation INTEGER NOT NULL CHECK(
                        credential_generation >= 1
                    ),
                    session_id TEXT NOT NULL UNIQUE,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(device_id,presentation_mode,credential_generation)
                )
            """)
            receipt_fields = {
                row[1] for row in db.execute(
                    "PRAGMA table_info(mobile_turn_receipt)"
                ).fetchall()
            }
            if "credential_generation" not in receipt_fields:
                db.execute(
                    "ALTER TABLE mobile_turn_receipt ADD COLUMN "
                    "credential_generation INTEGER NOT NULL DEFAULT 1"
                )
            if "server_sequence" not in receipt_fields:
                db.execute(
                    "ALTER TABLE mobile_turn_receipt ADD COLUMN "
                    "server_sequence INTEGER"
                )
            if "server_received_at" not in receipt_fields:
                db.execute(
                    "ALTER TABLE mobile_turn_receipt ADD COLUMN "
                    "server_received_at TEXT"
                )
            db.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS mobile_turn_authoritative_order
                ON mobile_turn_receipt(
                    device_id,presentation_mode,credential_generation,
                    server_sequence
                ) WHERE server_sequence IS NOT NULL
            """)

    def _connect(self) -> sqlite3.Connection:
        db = self._guard.connect(timeout=10)
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _device(value: object) -> str:
        if not isinstance(value, str) or _DEVICE.fullmatch(value) is None:
            raise ValueError("invalid mobile device_id")
        return value

    def dispatch_authenticated(
        self, *, credential: str, operation: str,
        payload: dict[str, object],
    ) -> dict[str, object]:
        """Recheck a mobile credential inside the *actual* owner-thread turn.

        HTTP authentication before enqueue is insufficient: the desktop worker
        can be busy while an operator revokes or rotates the pairing secret.
        The bearer travels only through the in-process command queue, never
        through an LLM prompt or durable work receipt. All public mobile
        operations pass through the same authority boundary.
        """
        if not isinstance(credential, str) or not isinstance(operation, str):
            raise TypeError("authenticated operation requires a credential and path")
        if not isinstance(payload, dict):
            raise TypeError("mobile payload must be a JSON object")
        with self._lock:
            device = self.credentials.authenticate(credential)
            if device is None:
                raise MobileCredentialRevoked(
                    "mobile credential revoked or rotated before dispatch"
                )
            if payload.get("device_id") != device:
                raise PermissionError("mobile bearer and device identity disagree")
            if operation == "/v1/mobile/sensors":
                # The existing typed sensor parser enforces its own schema.
                return self.ingest_sensors(payload)
            if operation == "/v1/mobile/chat":
                if set(payload) != {
                    "device_id", "message", "private_mode", "request_id"
                }:
                    raise ValueError("chat payload fields are invalid")
                return self.chat(
                    device_id=device, message=payload["message"],
                    private_mode=payload["private_mode"],
                    request_id=payload["request_id"],
                )
            if operation == "/v1/mobile/state":
                if set(payload) != {"device_id", "private_mode"}:
                    raise ValueError("state payload fields are invalid")
                return self.state(
                    device_id=device, private_mode=payload["private_mode"],
                )
            if operation == "/v1/mobile/main/page":
                if set(payload) != {
                    "device_id", "private_mode", "before", "limit"
                }:
                    raise ValueError("Main page payload fields are invalid")
                return self.main_history(
                    device_id=device, private_mode=payload["private_mode"],
                    before=payload["before"], limit=payload["limit"],
                )
            if operation == "/v1/mobile/threads":
                if set(payload) != {"device_id", "private_mode", "limit"}:
                    raise ValueError("thread list payload fields are invalid")
                return self.visible_thread_headers(
                    device_id=device,
                    private_mode=payload["private_mode"],
                    limit=payload["limit"],
                )
            if operation == "/v1/mobile/thread/page":
                if set(payload) != {
                    "device_id", "private_mode", "thread_id", "before", "limit"
                }:
                    raise ValueError("thread page payload fields are invalid")
                return self.project_thread_history(
                    device_id=device, private_mode=payload["private_mode"],
                    thread_id=payload["thread_id"],
                    before=payload["before"], limit=payload["limit"],
                )
            if operation == "/v1/mobile/main/seen":
                if set(payload) != {
                    "device_id", "private_mode", "canonical_sequence",
                    "turn_position", "message_id"
                }:
                    raise ValueError("Main seen payload fields are invalid")
                return self.acknowledge_main_seen(
                    device_id=device, private_mode=payload["private_mode"],
                    canonical_sequence=payload["canonical_sequence"],
                    turn_position=payload["turn_position"],
                    message_id=payload["message_id"],
                    credential=credential,
                )
            if operation == "/v1/mobile/notifications/claim":
                if set(payload) != {"device_id", "private_mode"}:
                    raise ValueError("notification claim fields are invalid")
                return self.claim_notification(
                    device_id=device, private_mode=payload["private_mode"],
                )
            if operation == "/v1/mobile/notifications/ack":
                if set(payload) != {"device_id", "notification_id"}:
                    raise ValueError("notification ack fields are invalid")
                return self.acknowledge_notification(
                    device_id=device, notification_id=payload["notification_id"],
                )
            raise MobileRouteNotFound("unknown authenticated mobile operation")

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
        generation = self.credentials.active_generation(device_id) or 1
        principal = self._principal(device_id, private_mode=private_mode)
        key = (device_id, mode, generation)
        existing = self._conversations.get(key)
        if existing is not None:
            return existing
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT session_id FROM mobile_conversation_binding_v3 "
                "WHERE device_id=? AND presentation_mode=? "
                "AND credential_generation=?",
                key,
            ).fetchone()
            if row is None and generation == 1:
                row = db.execute(
                    "SELECT session_id FROM mobile_conversation_binding_v2 "
                    "WHERE device_id=? AND presentation_mode=?",
                    (device_id, mode),
                ).fetchone()
            if row is not None:
                session_id = row[0]
                current = self._social_sessions.get(session_id)
                if current is None:
                    # Older deployments could persist a device/session record
                    # without binding its audience until the first chat.
                    # An EMPTY session can safely be bound now; a populated
                    # unbound session has unknowable ownership and is denied.
                    has_messages = db.execute(
                        "SELECT 1 FROM conversation_messages WHERE session_id=? LIMIT 1",
                        (session_id,),
                    ).fetchone()
                    if has_messages is not None:
                        raise PermissionError(
                            "populated mobile session has no authenticated audience"
                        )
                elif (
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
                ).fetchone() if generation == 1 else None
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
        # Establish the principal first, including a newly created empty
        # session. This prevents a later restart from resuming a populated
        # session with unknown ownership.
        self._social_sessions.bind(session_id=actual_session, principal=principal)
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            now_stamp = datetime.now(timezone.utc).isoformat()
            db.execute(
                "INSERT OR IGNORE INTO mobile_conversation_binding_v3 "
                "(device_id,presentation_mode,credential_generation,session_id,updated_at) "
                "VALUES(?,?,?,?,?)",
                (device_id, mode, generation, actual_session, now_stamp),
            )
            stored = db.execute(
                "SELECT session_id FROM mobile_conversation_binding_v3 "
                "WHERE device_id=? AND presentation_mode=? "
                "AND credential_generation=?", key,
            ).fetchone()
            if stored is None or stored[0] != actual_session:
                raise RuntimeError(
                    "another gateway already owns this generation's session"
                )
            if generation == 1:
                # Backward-compatible V2 record for legacy generation-one
                # mobile clients, never assign old records to a new pairing.
                db.execute(
                    "INSERT OR IGNORE INTO mobile_conversation_binding_v2 "
                    "(device_id,presentation_mode,session_id,updated_at) "
                    "VALUES(?,?,?,?)",
                    (device_id, mode, actual_session, now_stamp),
                )
                prior = db.execute(
                    "SELECT session_id FROM mobile_conversation_binding_v2 "
                    "WHERE device_id=? AND presentation_mode=?",
                    (device_id, mode),
                ).fetchone()
                if prior is None or prior[0] != actual_session:
                    raise RuntimeError("legacy session binding changed concurrently")
        self._conversations[key] = conversation
        return conversation

    def _principal(self, device_id: str, *, private_mode: bool):
        digest = sha256(device_id.encode("utf-8")).hexdigest()[:20]
        mode = "private" if private_mode else "standard"
        generation = self.credentials.active_generation(device_id) or 1
        # Generation one preserves existing authenticated mobile audience
        # history. A re-paired device must not inherit a prior bearer epoch's
        # private memories or its previously linked social sessions.
        audience = f"mobile:{mode}:{digest}"
        if generation > 1:
            audience += f":g{generation}"
        return PrincipalContext(
            principal_id=SPARKS_PRINCIPAL_ID,
            audience_id=audience,
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
        request_id: object,
    ) -> dict[str, object]:
        """At-most-once *dispatch* for a mobile request, including restarts.

        A processing receipt whose process crashed cannot establish whether
        the model/conversation already persisted a turn. Retain it as
        uncertain and explicitly reject replay instead of guessing success.
        """
        device = self._device(device_id)
        if type(private_mode) is not bool:
            raise TypeError("private_mode must be a bool")
        if not isinstance(message, str) or not message.strip() or len(message) > 12_000:
            raise ValueError("mobile message must be 1..12000 characters")
        if not isinstance(request_id, str) or _REQUEST.fullmatch(request_id) is None:
            raise ValueError("mobile request_id must be a bounded stable identifier")
        content = message.strip()
        mode = "private" if private_mode else "standard"
        digest = sha256(content.encode("utf-8")).hexdigest()
        generation = self.credentials.active_generation(device) or 1
        with self._lock:
            if private_mode and not self.permissions.private_adult_authority().private_chat:
                raise PermissionError("private mobile chat requires the host private-chat grant")
            now = datetime.now(timezone.utc).isoformat()
            with closing(self._connect()) as db, db:
                db.execute("BEGIN IMMEDIATE")
                existing = db.execute(
                    "SELECT device_id,presentation_mode,content_sha256,status,"
                    "response_json,credential_generation "
                    "FROM mobile_turn_receipt WHERE request_id=?",
                    (request_id,),
                ).fetchone()
                if existing is not None:
                    if (
                        tuple(existing[:3]) != (device, mode, digest)
                        or existing[5] != generation
                    ):
                        raise MobileDeliveryConflict("request ID was reused with a different scope or message")
                    if existing[3] == "completed" and existing[4] is not None:
                        return json.loads(existing[4])
                    raise MobileDeliveryUncertain(
                        "a prior mobile delivery is not independently settled"
                    )
                # A local phone clock is never used for causality. Allocate
                # one monotonically increasing admission sequence while this
                # canonical SQLite writer transaction is held. Uncertain
                # attempts keep their sequence, never backfilled or reused.
                sequence = int(db.execute(
                    "SELECT COALESCE(MAX(server_sequence),0)+1 "
                    "FROM mobile_turn_receipt "
                    "WHERE device_id=? AND presentation_mode=? "
                    "AND credential_generation=?",
                    (device, mode, generation),
                ).fetchone()[0])
                db.execute(
                    "INSERT INTO mobile_turn_receipt "
                    "(request_id,device_id,presentation_mode,content_sha256,"
                    "status,response_json,created_at,updated_at,"
                    "credential_generation,server_sequence,server_received_at) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (request_id, device, mode, digest, "processing", None,
                     now, now, generation, sequence, now),
                )

            # Do NOT hold an open SQLite writer transaction over model work.
            # The durable processing claim prevents replay on a second host
            # even if the first host disappears before finalization.
            try:
                conversation = self._conversation(device, private_mode=private_mode)
                principal = self._principal(device, private_mode=private_mode)
                response = conversation.respond(
                    content, principal=principal,
                    channel=("mobile-private" if private_mode else "mobile-standard"),
                    source_event_id=(
                        f"mobile:{device}:{generation}:{request_id}"
                    ),
                )
                canonical = getattr(conversation, "last_turn_receipt", None)
                canonical = canonical if isinstance(canonical, dict) else {}
                result = self._state_payload(
                    conversation, response=response.content,
                    principal=principal, private_mode=private_mode,
                )
                result["delivery_receipt"] = {
                    "request_id": request_id,
                    "origin_device_id": device,
                    "presentation_mode": mode,
                    "credential_generation": generation,
                    "server_received_at": now,
                    "canonical_sequence": sequence,
                    "main_sequence": canonical.get("canonical_sequence"),
                    "logical_status": "completed",
                }
                encoded = json.dumps(result, ensure_ascii=False, sort_keys=True)
                if len(encoded.encode("utf-8")) > 256_000:
                    raise ValueError("mobile delivery response exceeds durable receipt bound")
            except BaseException:
                with closing(self._connect()) as db, db:
                    db.execute(
                        "UPDATE mobile_turn_receipt SET status='uncertain',updated_at=? "
                        "WHERE request_id=? AND status='processing'",
                        (datetime.now(timezone.utc).isoformat(), request_id),
                    )
                raise
            with closing(self._connect()) as db, db:
                changed = db.execute(
                    "UPDATE mobile_turn_receipt SET status='completed',"
                    "response_json=?,updated_at=? "
                    "WHERE request_id=? AND status='processing' "
                    "AND device_id=? AND presentation_mode=? AND content_sha256=? "
                    "AND credential_generation=?",
                    (encoded, datetime.now(timezone.utc).isoformat(),
                     request_id, device, mode, digest, generation),
                )
                if changed.rowcount != 1:
                    raise MobileDeliveryUncertain(
                        "delivery receipt changed before it could be committed"
                    )
            return result

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
        principal = self._principal(device, private_mode=private_mode)
        if private_mode and not self.permissions.private_adult_authority().private_chat:
            raise PermissionError("private Main history requires the host private-chat grant")
        return self._canonical_history_page(
            device=device, principal=principal, private_mode=private_mode,
            before=before, limit=limit,
            page_reader=lambda cursor, page_limit:
                self.application.main_thread_page(
                    principal=principal, before=cursor, limit=page_limit,
                ),
        )

    def _canonical_history_page(
        self, *, device: str, principal: PrincipalContext,
        private_mode: bool, before: object, limit: int, page_reader,
    ) -> dict[str, object]:
        """One source-owned, source-audience-authorized bounded history pager."""
        cursor = None
        if before is not None:
            if not isinstance(before, dict) or set(before) not in ({
                "linked_at", "message_id",
            }, {
                "canonical_sequence", "turn_position", "message_id",
            }):
                raise ValueError("Main cursor schema is invalid")
            raw_id = before["message_id"]
            if not isinstance(raw_id, str) or not 1 <= len(raw_id) <= 160:
                raise ValueError("Main cursor message ID is invalid")
            if "canonical_sequence" in before:
                sequence, position = (
                    before["canonical_sequence"], before["turn_position"]
                )
                if type(sequence) is not int or sequence < 1:
                    raise ValueError("Main canonical sequence is invalid")
                if type(position) is not int or position not in {0, 1}:
                    raise ValueError("Main turn position is invalid")
                cursor = (sequence, position, raw_id)
            else:
                raw_time = before["linked_at"]
                if not isinstance(raw_time, str) or not 1 <= len(raw_time) <= 64:
                    raise ValueError("Main legacy cursor timestamp is invalid")
                timestamp = datetime.fromisoformat(raw_time)
                if timestamp.tzinfo is None or timestamp.utcoffset() is None:
                    raise ValueError("Main cursor timestamp must be timezone-aware")
                cursor = (timestamp, raw_id)

        with self._lock:
            # Each request carries a stable keyset cursor; narrowing a large
            # page must never discard or skip historical canonical messages.
            page_limit = limit
            while True:
                try:
                    page = page_reader(cursor, page_limit)
                except ValueError as exc:
                    if (
                        page_limit <= 1
                        or "lifelong page exceeds the 256-KiB display budget"
                        not in str(exc)
                    ):
                        raise
                    page_limit = max(1, page_limit // 2)
                    continue
                messages = [
                    {
                        "id": item.message.id,
                        "role": item.message.role.value,
                        "content": item.message.content,
                        "created_at": item.message.created_at.isoformat(),
                        "linked_at": item.linked_at.isoformat(),
                        "canonical_sequence": item.canonical_sequence,
                        "turn_position": item.turn_position,
                    }
                    for item in page
                ]
                # HttpsURLConnection has a 256-KB bounded reply reader.
                # Include serialized JSON escapes and leave framing room.
                if len(json.dumps(messages).encode("utf-8")) <= 192_000:
                    break
                if page_limit <= 1:
                    raise ValueError(
                        "one Main message exceeds the mobile display budget"
                    )
                page_limit = max(1, page_limit // 2)
        first = page[0] if page else None
        active_generation = self.credentials.active_generation(device)
        return {
            "messages": messages,
            "next_before": (
                None if first is None else (
                    {
                        "canonical_sequence": first.canonical_sequence,
                        "turn_position": first.turn_position,
                        "message_id": first.message.id,
                    }
                    if first.canonical_sequence is not None
                    else {
                        "linked_at": first.linked_at.isoformat(),
                        "message_id": first.message.id,
                    }
                )
            ),
            "has_more": len(page) == page_limit,
            "last_seen": (
                None if active_generation is None else self.main_seen.current(
                    device_id=device, private_mode=private_mode,
                    generation=active_generation,
                )
            ),
            "audience_id": principal.audience_id,
            "audience_kind": principal.audience_kind.value,
            "cross_channel_mirroring": False,
        }

    def visible_thread_headers(
        self, *, device_id: object, private_mode: object = False,
        limit: object = 30,
    ) -> dict[str, object]:
        """List only project titles with visible original source messages.

        The owner principal alone does not grant a different transport access
        to project titles or content from another source audience.
        """
        device = self._device(device_id)
        if type(private_mode) is not bool:
            raise TypeError("private_mode must be a bool")
        if type(limit) is not int or not 1 <= limit <= 50:
            raise ValueError("thread list limit must be 1..50")
        principal = self._principal(device, private_mode=private_mode)
        if private_mode and not self.permissions.private_adult_authority().private_chat:
            raise PermissionError("private thread list requires host private-chat grant")
        with self._lock:
            source = LifelongThreadStore(self.state_path)
            headers = source.list_threads(owner=principal, limit=limit)
            visible = []
            for header in headers:
                if header.kind != "main" and not source.visible_events(
                    thread_id=header.thread_id, principal=principal, limit=1,
                ):
                    continue
                visible.append({
                    "thread_id": header.thread_id,
                    "kind": header.kind,
                    "name": header.name,
                    "created_at": header.created_at.isoformat(),
                })
        return {
            "threads": visible,
            "audience_id": principal.audience_id,
            "audience_kind": principal.audience_kind.value,
            "cross_channel_mirroring": False,
        }

    def project_thread_history(
        self, *, device_id: object, private_mode: object,
        thread_id: object, before: object = None, limit: object = 30,
    ) -> dict[str, object]:
        """Read an existing project thread, never create or route a turn."""
        if not isinstance(thread_id, str) or not 8 <= len(thread_id) <= 128:
            raise ValueError("bounded project thread ID required")
        if type(limit) is not int or not 1 <= limit <= 50:
            raise ValueError("project page limit must be 1..50")
        device = self._device(device_id)
        if type(private_mode) is not bool:
            raise TypeError("private_mode must be a bool")
        if private_mode and not self.permissions.private_adult_authority().private_chat:
            raise PermissionError("private project history requires host grant")
        principal = self._principal(device, private_mode=private_mode)
        with self._lock:
            source = LifelongThreadStore(self.state_path)
            eligible = source.thread_for(
                owner=principal, thread_id=thread_id,
            )
            if eligible is None or eligible.kind != "project":
                raise PermissionError("project thread does not belong to owner")
            # Owner-wide metadata access does not imply that this Android
            # audience may observe its title or transcript.
            if not source.visible_events(
                thread_id=thread_id, principal=principal, limit=1,
            ):
                raise PermissionError(
                    "project has no visible originals for this audience"
                )
            # Delegate shared cursor validation and byte-budget logic to the
            # exact same canonical Main pager instead of a shadow reader.
            page = self._canonical_history_page(
                device=device, principal=principal,
                private_mode=private_mode,
                before=before, limit=limit,
                page_reader=lambda cursor, page_limit:
                    source.visible_message_page(
                        thread_id=thread_id, principal=principal,
                        before=cursor, limit=page_limit,
                    ),
            )
            # Exhausted keyset pages are normal: return an empty page, not
            # a spurious permission denial after authenticated paging.
            page["thread_id"] = thread_id
            page["kind"] = "project"
            page["name"] = eligible.name
            page["last_seen"] = None
            return page

    def acknowledge_main_seen(
        self, *, device_id: object, private_mode: object,
        canonical_sequence: object, turn_position: object,
        message_id: object, credential: str,
    ) -> dict[str, object]:
        device = self._device(device_id)
        if type(private_mode) is not bool:
            raise TypeError("private_mode must be bool")
        if private_mode and not self.permissions.private_adult_authority().private_chat:
            raise PermissionError("private Main read receipt requires host grant")
        if self.credentials.authenticate(credential) != device:
            raise MobileCredentialRevoked("device bearer revoked before Main read")
        fingerprint = self.credentials._digest(credential)
        if fingerprint is None:
            raise MobileCredentialRevoked("valid device bearer required")
        generation = self.credentials.active_generation(device)
        if generation is None:
            raise PermissionError("active paired mobile device required")
        with self._lock:
            return self.main_seen.acknowledge(
                device_id=device, private_mode=private_mode,
                generation=generation,
                principal=self._principal(device, private_mode=private_mode),
                canonical_sequence=canonical_sequence,
                turn_position=turn_position, message_id=message_id,
                credential_sha256=fingerprint,
            )

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
        visible_content = (
            notification.content if full_preview
            else "Sofía has something she wants to share with you."
        )
        return {
            "notification": {
                # Original ACT IDs may contain source project references.
                # Send only a stable random, non-semantic delivery handle.
                "id": self.notifications.delivery_handle(
                    notification.notification_id
                ),
                "title": notification.title if full_preview else "Sofía",
                # Never send the unapproved notification body to Android
                # while merely masking its lock-screen preview.
                "content": visible_content,
                "preview": visible_content,
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
        internal_id = self.notifications.resolve_delivery_handle(
            notification_id
        )
        self.notifications.acknowledge(
            internal_id,
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
            "audience_id": principal.audience_id,
            "audience_kind": principal.audience_kind.value,
            "cross_channel_mirroring": False,
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
