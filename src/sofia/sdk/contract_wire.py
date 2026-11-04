"""Strict, authority-free wire validation for cross-language SDK contracts.

The existing typed contracts remain authoritative.  This module adds framing
rules needed before constructing them: bounded UTF-8 JSON, duplicate-key
rejection, canonical encoding, protocol compatibility, and optional dispatch
context checks.  It does not authenticate a principal or grant authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json
import re
from typing import Mapping

from .contracts import ComponentRequestEnvelope, ComponentResponseEnvelope


MAX_MESSAGE_BYTES = 64 * 1024
SUPPORTED_PROTOCOL = "1.0"
_PAYLOAD_TYPE = re.compile(r"^[a-z][a-z0-9_.-]{0,127}\.v[1-9][0-9]*$")


class ContractWireError(ValueError):
    """Stable conformance error with a language-neutral category."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ContractWireError("duplicate_key", f"duplicate JSON key: {key}")
        result[key] = value
    return result


def loads_strict(raw: bytes) -> object:
    if not isinstance(raw, bytes):
        raise TypeError("contract message must be bytes")
    if len(raw) > MAX_MESSAGE_BYTES:
        raise ContractWireError("oversized", "contract message exceeds 64 KiB")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ContractWireError("malformed_json", "contract message is not UTF-8") from exc
    try:
        return json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ContractWireError("malformed_json", f"non-finite JSON: {value}")
            ),
        )
    except ContractWireError:
        raise
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ContractWireError("malformed_json", "contract message is invalid JSON") from exc


def canonical_json_bytes(value: object) -> bytes:
    def check(item: object) -> None:
        if item is None or type(item) in {str, bool}:
            return
        if type(item) is int:
            if not -(2**63) <= item <= 2**64 - 1:
                raise ContractWireError("malformed_json", "canonical integer is out of range")
            return
        if isinstance(item, list):
            for child in item:
                check(child)
            return
        if isinstance(item, Mapping) and all(isinstance(key, str) for key in item):
            for child in item.values():
                check(child)
            return
        raise ContractWireError(
            "malformed_json", "canonical v1 JSON permits bounded integers, not fractions"
        )

    check(value)
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError, UnicodeError) as exc:
        raise ContractWireError("malformed_json", "value is not finite JSON") from exc


def canonical_sha256(value: object) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


@dataclass(frozen=True, slots=True)
class DispatchContext:
    now: datetime
    expected_destination_generation: int
    expected_audience_id: str


def _require_protocol(document: object) -> Mapping[str, object]:
    if not isinstance(document, Mapping):
        raise ContractWireError("invalid_contract", "contract document must be an object")
    if document.get("protocol") != SUPPORTED_PROTOCOL:
        raise ContractWireError("unsupported_protocol", "unsupported SDK protocol")
    return document


def _require_u64_generation(endpoint: object) -> None:
    if not isinstance(endpoint, Mapping):
        return
    generation = endpoint.get("generation")
    if type(generation) is not int or not 1 <= generation <= 18_446_744_073_709_551_615:
        raise ContractWireError("invalid_contract", "generation must fit unsigned 64-bit")


def decode_request(
    raw: bytes,
    *,
    context: DispatchContext | None = None,
    payload: object | None = None,
) -> ComponentRequestEnvelope:
    document = _require_protocol(loads_strict(raw))
    _require_u64_generation(document.get("source"))
    _require_u64_generation(document.get("destination"))
    if not isinstance(document.get("payload_type"), str) or _PAYLOAD_TYPE.fullmatch(
        document["payload_type"]
    ) is None:
        raise ContractWireError("unsupported_schema", "unsupported payload schema")
    try:
        request = ComponentRequestEnvelope.from_payload(document)
    except (TypeError, ValueError) as exc:
        raise ContractWireError("invalid_contract", "component request is invalid") from exc
    if payload is not None and canonical_sha256(payload) != request.payload_digest:
        raise ContractWireError("digest_mismatch", "payload digest does not match canonical payload")
    if context is not None:
        if request.authority.audience_id != context.expected_audience_id:
            raise ContractWireError("wrong_audience", "authority audience does not match dispatch")
        try:
            request.require_dispatchable(
                now=context.now,
                expected_destination_generation=context.expected_destination_generation,
            )
        except PermissionError as exc:
            code = "wrong_generation" if "generation" in str(exc) else "expired"
            raise ContractWireError(code, str(exc)) from exc
        except TimeoutError as exc:
            raise ContractWireError("expired", str(exc)) from exc
    return request


def decode_response(raw: bytes) -> ComponentResponseEnvelope:
    document = _require_protocol(loads_strict(raw))
    _require_u64_generation(document.get("responder"))
    try:
        return ComponentResponseEnvelope.from_payload(document)
    except (TypeError, ValueError) as exc:
        raise ContractWireError("invalid_contract", "component response is invalid") from exc
