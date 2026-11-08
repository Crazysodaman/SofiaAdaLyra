"""Strict, authority-free AG-D028 Library v1 wire syntax.

Not a Hub, network client, signer, downloader, installer, enrollment or SAFE
authorization. Only the Rust-owned Platform service may dispatch a reviewed
operation after native/remote mutual identity and current SAFE/STOP checks.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import math
import re
import unicodedata
from typing import Mapping

LIBRARY_REQUEST_SCHEMA = "aegis.platform.library.request.v1"
LIBRARY_RESPONSE_SCHEMA = "aegis.platform.library.response.v1"
LIBRARY_PROTOCOL = "1.0"
MAX_LIBRARY_CONTROL_BYTES = 32 * 1024
MAX_SAFE_INTEGER = 2**53 - 1
_REQUEST_KEYS = frozenset((
    "schema", "protocol", "request_id", "correlation_id", "operation",
    "target_platform_id", "expected_generation", "expected_revision",
    "idempotency_key", "created_at", "deadline", "parameters",
))
_RESPONSE_KEYS = frozenset((
    "schema", "protocol", "request_id", "correlation_id", "operation",
    "platform_id", "platform_generation", "state_revision", "observed_at",
    "outcome", "data", "denial",
))
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TIME = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$"
)
_READ = frozenset({
    "library.catalog.snapshot.v1",
    "library.inventory.snapshot.v1",
    "library.sources.snapshot.v1",
    "library.transfer.status.v1",
    "library.history.snapshot.v1",
    "library.plan.acquire.v1",  # pure reviewed proposal, never queues work
})
_DENIALS = frozenset({
    "NOT_PERMITTED", "REVOKED", "STOPPED", "STALE_GENERATION",
    "EXPIRED", "UNAVAILABLE",
})
_KINDS = frozenset({
    "platform_release", "sdk", "core_runtime", "core_definition",
    "module", "model", "asset", "rollback",
})
_SOURCES = frozenset({
    "LOCAL_VERIFIED_CACHE", "OFFLINE_MEDIA", "OWNER_SELECTED_HUB",
    "AUTHORIZED_PEER", "OFFICIAL_REMOTE",
})
_STATUSES = frozenset({"CURRENT", "STALE", "UNAVAILABLE"})
_JOB_STATES = frozenset({
    "QUEUED", "DOWNLOADING", "PAUSED", "VERIFYING", "COMPLETE",
    "FAILED", "CANCELLED", "OUTCOME_UNKNOWN",
})
_PRIVATE_NAMES = (
    "secret", "password", "credential", "authorization",
    "owner_proof", "private_key", "access_token", "refresh_token",
    "api_key", "sofia.db", "peer_sid", "peer_uid",
)
_CATALOG_DATA = frozenset({
    "catalog_revision", "catalog_generation", "catalog_fresh_until",
    "target_platform_id", "source", "page", "items",
})
_ITEM = frozenset({
    "artifact_id", "kind", "version", "revision", "manifest_digest",
    "content_digest", "size_bytes", "publisher", "signer_key_id",
    "signature_scheme", "signature_receipt_ref", "target_os_arch",
    "sdk_range", "abi_range", "license_distribution",
    "data_class", "distribution_allowed",
})
_TRANSFER_DATA = frozenset({
    "job_id", "artifact_content_digest", "target_platform_id",
    "source_platform_id", "source_kind", "received_bytes",
    "verified_bytes", "total_bytes", "state", "failure",
    "last_observed_at", "restart_cursor", "receipt_ref",
})


def _unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
    out: dict[str, object] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate Library control key")
        out[key] = value
    return out


def _object(value: object, fields: frozenset[str]) -> Mapping[str, object]:
    if type(value) is not dict or set(value) != fields:
        raise ValueError("missing or unreviewed Library fields")
    return value


def _id(value: object) -> str:
    if (type(value) is not str or _ID.fullmatch(value) is None
            or "://" in value or value.startswith("/") or ".." in value):
        raise ValueError("invalid Library opaque identifier")
    return value


def _int(value: object, minimum: int = 0) -> int:
    if type(value) is not int or not minimum <= value <= MAX_SAFE_INTEGER:
        raise ValueError("nonportable Library integer")
    return value


def _time(value: object) -> datetime:
    if type(value) is not str or _TIME.fullmatch(value) is None:
        raise ValueError("Library timestamp must be bounded RFC3339")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("invalid Library timestamp") from error
    if result.utcoffset() is None:
        raise ValueError("Library timestamp requires timezone")
    return result.astimezone(timezone.utc)


def _safe(value: object, depth: int = 0) -> None:
    if depth > 8:
        raise ValueError("Library projection nested too deeply")
    if type(value) is dict:
        if len(value) > 256:
            raise ValueError("Library projection has excessive keys")
        for key, member in value.items():
            if (type(key) is not str or not key or not key.isascii()
                    or len(key) > 160 or any(part in key.lower() for part in _PRIVATE_NAMES)
                    or key.lower() in {"__proto__", "constructor", "prototype"}):
                raise ValueError("unsafe Library projection key")
            _safe(member, depth + 1)
    elif type(value) is list:
        if len(value) > 128:
            raise ValueError("Library array exceeds control bounds")
        for member in value:
            _safe(member, depth + 1)
    elif type(value) is str:
        if (len(value) > 4096
                or any(unicodedata.category(char) in {"Cc", "Cs"} for char in value)):
            raise ValueError("unsafe Library string")
    elif type(value) is int:
        _int(value, -MAX_SAFE_INTEGER)
    elif type(value) is float:
        if not math.isfinite(value) or abs(value) > MAX_SAFE_INTEGER:
            raise ValueError("unportable Library number")
    elif value is None or type(value) is bool:
        return
    else:
        raise ValueError("unsupported Library projection")


def _decode(raw: bytes) -> Mapping[str, object]:
    if type(raw) is not bytes or not raw or len(raw) > MAX_LIBRARY_CONTROL_BYTES:
        raise ValueError("Library control bytes exceed bound")
    try:
        value = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_unique,
            parse_constant=lambda _: (_ for _ in ()).throw(
                ValueError("nonfinite Library control number")
            ),
        )
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise ValueError("invalid Library JSON") from error
    if type(value) is not dict:
        raise ValueError("Library envelope must be an object")
    _safe(value)
    return value


def _catalog(data: Mapping[str, object], request: "UntrustedLibraryRequest", now: datetime) -> None:
    _object(data, _CATALOG_DATA)
    _int(data["catalog_revision"])
    _int(data["catalog_generation"], 1)
    freshness = _time(data["catalog_fresh_until"])
    if data["target_platform_id"] != request.target_platform_id:
        raise PermissionError("catalog target differs from authenticated request")
    source = _object(data["source"], frozenset({
        "kind", "source_id", "last_observed_at", "status",
    }))
    if source["kind"] not in _SOURCES or source["status"] not in _STATUSES:
        raise ValueError("unsupported Library source projection")
    _id(source["source_id"])
    last = _time(source["last_observed_at"])
    if last > now or (source["status"] == "CURRENT" and freshness <= now):
        raise PermissionError("Library source claimed fresh after expiry")
    page = _object(data["page"], frozenset({"limit", "next_cursor", "cursor_state"}))
    if (_int(page["limit"], 1) > 128
            or page["cursor_state"] not in {"CURRENT", "STALE", "LOST"}):
        raise ValueError("invalid Library catalog page")
    if page["next_cursor"] is not None:
        _id(page["next_cursor"])
    if type(data["items"]) is not list or len(data["items"]) > page["limit"]:
        raise ValueError("unbounded Library catalog page")
    for item in data["items"]:
        _object(item, _ITEM)
        if item["kind"] not in _KINDS:
            raise ValueError("unsupported artifact type")
        for name in (
            "artifact_id", "version", "publisher", "signer_key_id",
            "signature_receipt_ref", "target_os_arch", "sdk_range", "abi_range",
        ):
            _id(item[name])
        for name in ("manifest_digest", "content_digest"):
            if type(item[name]) is not str or _SHA256.fullmatch(item[name]) is None:
                raise ValueError("invalid signed content digest syntax")
        _int(item["revision"], 1)
        _int(item["size_bytes"], 1)
        if (item["signature_scheme"] not in {"ed25519", "ecdsa-p256"}
                or item["license_distribution"] not in {
                    "permitted", "restricted", "non_redistributable", "unknown"
                } or item["data_class"] not in {"public", "protected", "private"}
                or type(item["distribution_allowed"]) is not bool):
            raise ValueError("invalid artifact provenance or distribution metadata")
        if (item["license_distribution"] != "permitted"
                or item["data_class"] != "public") and item["distribution_allowed"]:
            raise PermissionError("restricted Library bytes offered as distributable")


def _transfer(data: Mapping[str, object], request: "UntrustedLibraryRequest", now: datetime) -> None:
    _object(data, _TRANSFER_DATA)
    for field in ("job_id", "target_platform_id", "source_platform_id", "receipt_ref"):
        _id(data[field])
    if data["target_platform_id"] != request.target_platform_id:
        raise PermissionError("transfer status target differs from request")
    if data["source_kind"] not in _SOURCES:
        raise ValueError("unknown transfer source")
    if not isinstance(data["artifact_content_digest"], str) or _SHA256.fullmatch(
        data["artifact_content_digest"]
    ) is None:
        raise ValueError("unverified digest syntax")
    total = _int(data["total_bytes"], 1)
    received = _int(data["received_bytes"])
    verified = _int(data["verified_bytes"])
    if received > total or verified > received:
        raise ValueError("inconsistent transfer progress")
    if data["state"] not in _JOB_STATES:
        raise ValueError("unsupported transfer state")
    if data["state"] == "COMPLETE" and verified != total:
        raise ValueError("transfer completion is not independent verification")
    if data["failure"] is not None and data["failure"] not in {
        "CONFLICT", "QUOTA_EXCEEDED", "REJECTED", "UNAVAILABLE", "INTERRUPTED",
    }:
        raise ValueError("unreviewed transfer failure")
    if _time(data["last_observed_at"]) > now:
        raise PermissionError("transfer observation from future")
    if data["restart_cursor"] is not None:
        _id(data["restart_cursor"])


@dataclass(frozen=True, slots=True)
class UntrustedLibraryRequest:
    """Syntax only; no principal, role, audience or owner grant is carried."""

    request_id: str
    correlation_id: str
    operation: str
    target_platform_id: str
    expected_generation: int
    expected_revision: int
    created_at: str
    deadline: str

    @classmethod
    def parse(cls, raw: bytes, *, now: datetime) -> "UntrustedLibraryRequest":
        doc = _object(_decode(raw), _REQUEST_KEYS)
        if doc["schema"] != LIBRARY_REQUEST_SCHEMA or doc["protocol"] != LIBRARY_PROTOCOL:
            raise ValueError("unsupported Library protocol version")
        for name in ("request_id", "correlation_id", "target_platform_id"):
            _id(doc[name])
        generation = _int(doc["expected_generation"], 1)
        revision = _int(doc["expected_revision"])
        if doc["operation"] not in _READ:
            raise PermissionError("effectful Library operation cannot use read preview")
        if doc["idempotency_key"] is not None:
            raise PermissionError("read Library operation cannot carry effect idempotency")
        if not isinstance(now, datetime) or now.utcoffset() is None:
            raise ValueError("aware Library receiver time required")
        moment = now.astimezone(timezone.utc)
        created = _time(doc["created_at"])
        deadline = _time(doc["deadline"])
        if (created > moment or created < moment - timedelta(seconds=60)
                or deadline <= moment or deadline <= created
                or deadline > created + timedelta(seconds=60)):
            raise PermissionError("stale or future Library request")
        params = doc["parameters"]
        if doc["operation"] == "library.catalog.snapshot.v1":
            _object(params, frozenset({"limit", "cursor", "kinds"}))
            if _int(params["limit"], 1) > 128:
                raise ValueError("catalog limit exceeds bound")
            if params["cursor"] is not None:
                _id(params["cursor"])
            if type(params["kinds"]) is not list or len(params["kinds"]) > 8:
                raise ValueError("catalog kinds exceed bound")
            if len(set(params["kinds"])) != len(params["kinds"]) or any(
                kind not in _KINDS for kind in params["kinds"]
            ):
                raise ValueError("unsupported catalog filter")
        elif doc["operation"] == "library.transfer.status.v1":
            _object(params, frozenset({"job_id"}))
            _id(params["job_id"])
        else:
            # Freeze other read projections only after B/C/D fields are signed.
            if params != {}:
                raise PermissionError("Library projection parameters not yet reviewed")
        return cls(
            doc["request_id"], doc["correlation_id"], doc["operation"],
            doc["target_platform_id"], generation, revision,
            doc["created_at"], doc["deadline"],
        )


@dataclass(frozen=True, slots=True)
class UntrustedLibraryResponse:
    """Never treats Hub assertions as publisher signature or installation."""

    request_id: str
    correlation_id: str
    operation: str
    platform_id: str
    generation: int
    revision: int
    observed_at: str
    outcome: str
    data: Mapping[str, object] | None
    denial_code: str | None

    @classmethod
    def parse(
        cls, raw: bytes, *, expected: UntrustedLibraryRequest, now: datetime,
    ) -> "UntrustedLibraryResponse":
        if not isinstance(expected, UntrustedLibraryRequest):
            raise TypeError("typed outstanding Library request required")
        if not isinstance(now, datetime) or now.utcoffset() is None:
            raise ValueError("aware Library client clock required")
        doc = _object(_decode(raw), _RESPONSE_KEYS)
        if (doc["schema"] != LIBRARY_RESPONSE_SCHEMA
                or doc["protocol"] != LIBRARY_PROTOCOL
                or doc["request_id"] != expected.request_id
                or doc["correlation_id"] != expected.correlation_id
                or doc["operation"] != expected.operation
                or doc["platform_id"] != expected.target_platform_id
                or _int(doc["platform_generation"], 1) != expected.expected_generation
                or _int(doc["state_revision"]) != expected.expected_revision):
            raise PermissionError("Library correlation, revision or generation mismatch")
        moment = now.astimezone(timezone.utc)
        observed = _time(doc["observed_at"])
        created = _time(expected.created_at)
        deadline = _time(expected.deadline)
        if (observed < created or observed > moment or observed >= deadline
                or moment >= deadline or moment - observed > timedelta(seconds=5)):
            raise PermissionError("Library response stale, future or replayed")
        if doc["outcome"] == "DENIED":
            if (doc["data"] is not None
                    or type(doc["denial"]) is not dict
                    or set(doc["denial"]) != {"code"}
                    or doc["denial"]["code"] not in _DENIALS):
                raise ValueError("invalid scoped Library denial")
            code = doc["denial"]["code"]
            data = None
        elif doc["outcome"] == "OK":
            if doc["denial"] is not None or type(doc["data"]) is not dict:
                raise ValueError("Library success must have typed data only")
            data = doc["data"]
            if expected.operation == "library.catalog.snapshot.v1":
                _catalog(data, expected, moment)
            elif expected.operation == "library.transfer.status.v1":
                _transfer(data, expected, moment)
            else:
                # An unreviewed result must not become a trusted UI state.
                raise PermissionError("Library successful projection not yet frozen")
            code = None
        else:
            raise ValueError("unsupported Library response outcome")
        return cls(
            expected.request_id, expected.correlation_id, expected.operation,
            expected.target_platform_id, expected.expected_generation,
            expected.expected_revision, doc["observed_at"],
            doc["outcome"], data, code,
        )
