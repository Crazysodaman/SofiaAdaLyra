"""Independent deterministic SDK Validation Core worker.

The worker imports only the Python standard library plus public ``sofia.sdk``
facades. It must not import ``sofia.core``, ``sofia.application`` or Platform
authority internals. Any operation that the SDK does not expose is recorded in
``SDK_GAPS.md`` instead of being reached through a private import.
"""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import sys
from typing import Any

from sofia.sdk import (
    AegisIdentity,
    IdentityKind,
    ProtocolVersion,
    ProtocolVersionRange,
    SDK_PROTOCOL_VERSION,
    negotiate_protocol,
)
from sofia.sdk.core_definition import CoreDefinition

PACKAGE_DIR = Path(__file__).resolve().parent
COMPONENT = "sdk-validation-core"
COMPONENT_VERSION = "0.1.0"
WORKER_SCHEMA = "aegis.sdk-validation.worker.v1"
HISTORY_SCHEMA = "aegis.sdk-validation.history.v1"
SCOPE_SCHEMA = "aegis.sdk-validation.scope.v1"
PRIVATE_SCOPE = "core.private.sdk-validation"
ENGINE = "DETERMINISTIC_TEST_ENGINE"
MODEL_STATUS = "MODEL_NOT_LOADED"
SUPPORTED_PROTOCOL = ProtocolVersionRange(
    SDK_PROTOCOL_VERSION, SDK_PROTOCOL_VERSION
)
MAX_LINE_BYTES = 8192
MAX_TEXT_CHARS = 4000
MAX_HISTORY_TURNS = 1000
RUNTIME_RELEASE_PATH = "assets/runtime_release.json"
STATE_FILE = "history.json"
FORBIDDEN_MODULE_PREFIXES = ("sofia.core", "sofia.application", "sofia.platform")


class ProtocolError(Exception):
    """A bounded protocol outcome that must not terminate the worker."""

    def __init__(self, code: str, op: str | None, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.op = op
        self.detail = detail


def _canonical(document: Any) -> str:
    return json.dumps(
        document, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    )


def _file_digest(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"cannot load provisioning file {path.name}") from exc


def _validate_asset(package_dir: Path, reference: Any) -> None:
    candidate = (package_dir / reference.path).resolve()
    if not candidate.is_relative_to(package_dir):
        raise RuntimeError("Core asset path escapes the example package")
    if not candidate.is_file():
        raise RuntimeError(f"missing Core asset {reference.path}")
    if candidate.stat().st_size != reference.size_bytes:
        raise RuntimeError(f"Core asset size differs for {reference.path}")
    if _file_digest(candidate) != reference.sha256:
        raise RuntimeError(f"Core asset digest differs for {reference.path}")


def load_provisioning(package_dir: Path = PACKAGE_DIR) -> tuple[
    AegisIdentity, CoreDefinition, dict[str, object]
]:
    identity = AegisIdentity.from_payload(_load_json(package_dir / "identity.json"))
    if identity.kind is not IdentityKind.CORE:
        raise RuntimeError("SDK Validation Core identity must be a Core")
    definition = CoreDefinition.from_payload(
        _load_json(package_dir / "definition.json")
    )
    if definition.identity != identity:
        raise RuntimeError("definition identity differs from identity.json")
    scope = _load_json(package_dir / "scope.json")
    if (
        not isinstance(scope, dict)
        or scope.get("schema") != SCOPE_SCHEMA
        or scope.get("audience_kind") != "private"
        or scope.get("scope") != PRIVATE_SCOPE
        or scope.get("identity_id") != identity.canonical_uuid
        or scope.get("identity_serial") != identity.serial
        or scope.get("definition_revision") != definition.revision
        or scope.get("definition_digest") != definition.digest
        or scope.get("runtime_release_sha256")
        != definition.runtime_release_sha256
        or scope.get("test_only") is not True
        or scope.get("contains_sofia_assets") is not False
        or scope.get("contains_owner_secrets") is not False
    ):
        raise RuntimeError("private test scope does not match the definition")
    _validate_asset(package_dir, definition.constitution)
    _validate_asset(package_dir, definition.personality)
    release = package_dir / RUNTIME_RELEASE_PATH
    if not release.is_file():
        raise RuntimeError("missing runtime release manifest")
    if _file_digest(release) != definition.runtime_release_sha256:
        raise RuntimeError("runtime release digest differs from the definition")
    return identity, definition, scope


def deterministic_reply(text: str, turn: int) -> str:
    digest = sha256(text.encode("utf-8")).hexdigest()[:16]
    return f"SDK-VC/1 turn={turn} sha256={digest} chars={len(text)}"


def loaded_sofia_modules() -> list[str]:
    return sorted(
        name for name in sys.modules
        if name == "sofia" or name.startswith("sofia.")
    )


class HistoryStore:
    """Worker-private durable history; never a Platform state writer."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory.resolve()
        self.path = self.directory / STATE_FILE
        self.turns: list[dict[str, object]] = []
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        document = _load_json(self.path)
        if (
            not isinstance(document, dict)
            or set(document) != {"schema", "turns"}
            or document["schema"] != HISTORY_SCHEMA
            or not isinstance(document["turns"], list)
            or len(document["turns"]) > MAX_HISTORY_TURNS
        ):
            raise RuntimeError("invalid SDK Validation Core history state")
        expected_turn = 1
        loaded: list[dict[str, object]] = []
        for item in document["turns"]:
            if (
                not isinstance(item, dict)
                or set(item) != {"turn", "user", "core"}
                or item["turn"] != expected_turn
                or not isinstance(item["user"], str)
                or not isinstance(item["core"], str)
                or len(item["user"]) > MAX_TEXT_CHARS
                or len(item["core"]) > MAX_TEXT_CHARS
            ):
                raise RuntimeError("invalid SDK Validation Core history entry")
            loaded.append(item)
            expected_turn += 1
        self.turns = loaded

    def append(self, user: str, core: str) -> int:
        turn = len(self.turns) + 1
        if turn > MAX_HISTORY_TURNS:
            raise ProtocolError(
                "history_full", "chat", "history turn limit reached"
            )
        self.turns.append({"turn": turn, "user": user, "core": core})
        self._save()
        return turn

    def _save(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        raw = _canonical(
            {"schema": HISTORY_SCHEMA, "turns": self.turns}
        ).encode("utf-8")
        temporary = self.path.with_name(self.path.name + ".tmp")
        with temporary.open("wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, self.path)


class Worker:
    def __init__(
        self,
        identity: AegisIdentity,
        definition: CoreDefinition,
        scope: dict[str, object],
        state_dir: Path,
    ) -> None:
        self.identity = identity
        self.definition = definition
        self.scope = scope
        self.store = HistoryStore(state_dir)
        self.started = False
        self.stopped = False

    def _common(self) -> dict[str, object]:
        return {
            "component": COMPONENT,
            "component_version": COMPONENT_VERSION,
            "identity": self.identity.to_payload(),
            "identity_serial": self.identity.serial,
            "definition_revision": self.definition.revision,
            "definition_digest": self.definition.digest,
            "scope": PRIVATE_SCOPE,
            "audience_kind": self.scope["audience_kind"],
            "engine": ENGINE,
            "model_status": MODEL_STATUS,
        }

    def hello(self, request: dict[str, object]) -> dict[str, object]:
        requested = request.get("protocol")
        if requested is None:
            negotiated = SDK_PROTOCOL_VERSION
        elif not isinstance(requested, str):
            raise ProtocolError(
                "invalid_protocol", "hello", "protocol must be text"
            )
        else:
            try:
                peer = ProtocolVersion.parse(requested)
                negotiated = negotiate_protocol(
                    SUPPORTED_PROTOCOL,
                    ProtocolVersionRange(peer, peer),
                )
            except (ValueError, RuntimeError) as exc:
                raise ProtocolError(
                    "incompatible_protocol", "hello",
                    "peer protocol is not supported",
                ) from exc
        return {
            "status": "ok",
            "op": "hello",
            "schema": WORKER_SCHEMA,
            **self._common(),
            "protocol": str(negotiated),
            "sdk_protocol": str(SDK_PROTOCOL_VERSION),
            "protocol_range": {
                "minimum": str(SUPPORTED_PROTOCOL.minimum),
                "maximum": str(SUPPORTED_PROTOCOL.maximum),
            },
            "state": "ready" if self.started else "idle",
            "turn_count": len(self.store.turns),
            "loaded_sofia_modules": loaded_sofia_modules(),
        }

    def start(self) -> dict[str, object]:
        self.started = True
        return {
            "status": "ok",
            "op": "start",
            **self._common(),
            "state": "ready",
            "turn_count": len(self.store.turns),
        }

    def chat(self, request: dict[str, object]) -> dict[str, object]:
        if not self.started:
            raise ProtocolError(
                "not_started", "chat", "start must be acknowledged first"
            )
        text = request.get("text")
        if not isinstance(text, str):
            raise ProtocolError(
                "invalid_text", "chat", "text must be a string"
            )
        if not text.strip():
            raise ProtocolError("empty_text", "chat", "text must not be empty")
        if len(text) > MAX_TEXT_CHARS:
            raise ProtocolError(
                "text_too_large", "chat", "text exceeds the character limit"
            )
        turn = self.store.append(text, deterministic_reply(
            text, len(self.store.turns) + 1
        ))
        return {
            "status": "ok",
            "op": "chat",
            **self._common(),
            "turn": turn,
            "reply": self.store.turns[-1]["core"],
            "turn_count": len(self.store.turns),
        }

    def history(self) -> dict[str, object]:
        if not self.started:
            raise ProtocolError(
                "not_started", "history", "start must be acknowledged first"
            )
        return {
            "status": "ok",
            "op": "history",
            "schema": HISTORY_SCHEMA,
            "identity": self.identity.to_payload(),
            "turns": list(self.store.turns),
            "count": len(self.store.turns),
        }

    def health(self) -> dict[str, object]:
        return {
            "status": "ok",
            "op": "health",
            "schema": WORKER_SCHEMA,
            **self._common(),
            "state": "ready" if self.started else "idle",
            "started": self.started,
            "stopped": self.stopped,
            "turn_count": len(self.store.turns),
            "loaded_sofia_modules": loaded_sofia_modules(),
        }

    def stop(self) -> dict[str, object]:
        self.stopped = True
        return {
            "status": "ok",
            "op": "stop",
            "schema": WORKER_SCHEMA,
            "identity": self.identity.to_payload(),
            "state": "stopped",
            "turn_count": len(self.store.turns),
        }

    def handle(self, request: object) -> dict[str, object]:
        if not isinstance(request, dict):
            raise ProtocolError(
                "invalid_request", None, "request must be a JSON object"
            )
        op = request.get("op")
        if not isinstance(op, str) or not op:
            raise ProtocolError(
                "invalid_request", None, "request requires a string op"
            )
        allowed = {
            "hello": {"op", "protocol"},
            "start": {"op"},
            "chat": {"op", "text"},
            "history": {"op"},
            "health": {"op"},
            "stop": {"op"},
        }
        if op not in allowed:
            raise ProtocolError("unknown_op", op, "unsupported operation")
        if set(request) - allowed[op]:
            raise ProtocolError(
                "invalid_request", op, "request contains unexpected fields"
            )
        if op == "hello":
            return self.hello(request)
        if op == "start":
            return self.start()
        if op == "chat":
            return self.chat(request)
        if op == "history":
            return self.history()
        if op == "health":
            return self.health()
        return self.stop()


def _error_response(
    code: str, op: str | None, detail: str
) -> dict[str, object]:
    return {
        "status": "error",
        "op": op,
        "error": code,
        "detail": detail,
    }


def _write(stream: Any, document: dict[str, object]) -> None:
    stream.write(_canonical(document) + "\n")
    stream.flush()


def serve(worker: Worker, stdin: Any, stdout: Any) -> int:
    while True:
        raw = stdin.readline(MAX_LINE_BYTES + 2)
        if raw == b"":
            return 0
        ended = raw.endswith(b"\n")
        content = raw[:-1] if ended else raw
        if len(content) > MAX_LINE_BYTES:
            if not ended:
                while True:
                    remainder = stdin.readline(MAX_LINE_BYTES + 2)
                    if not remainder or remainder.endswith(b"\n"):
                        break
            _write(stdout, _error_response(
                "message_too_large", None,
                "request line exceeds the byte limit",
            ))
            continue
        if not content:
            _write(stdout, _error_response(
                "invalid_json", None, "empty request line"
            ))
            continue
        try:
            request = json.loads(content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            _write(stdout, _error_response(
                "invalid_json", None, "request is not valid UTF-8 JSON"
            ))
            continue
        op = request.get("op") if isinstance(request, dict) else None
        try:
            response = worker.handle(request)
        except ProtocolError as exc:
            _write(stdout, _error_response(exc.code, exc.op, exc.detail))
            continue
        except Exception:
            _write(stdout, _error_response(
                "internal_error",
                op if isinstance(op, str) else None,
                "worker could not process the request",
            ))
            continue
        _write(stdout, response)
        if response.get("status") == "ok" and response.get("op") == "stop":
            return 0


def _state_directory(arguments: list[str]) -> tuple[Path, list[str]]:
    if "--state-dir" in arguments:
        index = arguments.index("--state-dir")
        try:
            value = arguments[index + 1]
        except IndexError as exc:
            raise SystemExit("--state-dir requires a path") from exc
        if not value:
            raise SystemExit("--state-dir requires a path")
        remaining = arguments[:index] + arguments[index + 2:]
        return Path(value), remaining
    fallback = os.environ.get("SDK_VALIDATION_CORE_STATE")
    return (
        Path(fallback) if fallback else PACKAGE_DIR / "state",
        list(arguments),
    )


def main(arguments: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if arguments is None else arguments)
    state_dir, args = _state_directory(args)
    identity, definition, scope = load_provisioning()
    if args == ["--check-imports"]:
        loaded = loaded_sofia_modules()
        _write(sys.stdout, {
            "status": "ok",
            "check": "imports",
            "identity_id": identity.canonical_uuid,
            "definition_digest": definition.digest,
            "loaded_sofia_modules": loaded,
            "sofia_core_loaded": any(
                name == "sofia.core" or name.startswith("sofia.core.")
                for name in loaded
            ),
            "forbidden_prefixes_loaded": [
                name for name in loaded
                if name.startswith(FORBIDDEN_MODULE_PREFIXES)
            ],
        })
        return 0
    if args:
        raise SystemExit(f"unsupported arguments: {args!r}")
    worker = Worker(identity, definition, scope, state_dir)
    return serve(worker, sys.stdin.buffer, sys.stdout)


if __name__ == "__main__":
    raise SystemExit(main())
