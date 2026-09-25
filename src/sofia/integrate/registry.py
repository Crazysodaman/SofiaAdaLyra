from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Protocol
from .model import AdapterManifest, ToolInvocation, ToolReceipt
from .schema import validate_object

class AdapterRegistrationError(RuntimeError): pass

class Adapter(Protocol):
    manifest: AdapterManifest
    def invoke(self, arguments: dict[str, Any]) -> Any: ...

class AdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, Adapter] = {}

    def register(self, adapter: Adapter) -> None:
        manifest = adapter.manifest
        old = self._adapters.get(manifest.tool_id)
        if old is not None and old.manifest.version != manifest.version:
            raise AdapterRegistrationError("tool_id already registered at another version")
        self._adapters[manifest.tool_id] = adapter

    def manifest(self, tool_id: str) -> AdapterManifest | None:
        adapter = self._adapters.get(tool_id)
        return None if adapter is None else adapter.manifest

    def tool_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._adapters))

    def invoke(self, request: ToolInvocation) -> ToolReceipt:
        adapter = self._adapters.get(request.tool_id)
        if adapter is None:
            raise KeyError(f"unknown tool: {request.tool_id}")
        if not request.authorized:
            raise PermissionError("tool invocation requires authority outside the registry")

        validate_object(adapter.manifest.input_schema, dict(request.arguments))
        started = datetime.now(timezone.utc)
        try:
            output = adapter.invoke(dict(request.arguments))
            validate_object(adapter.manifest.output_schema, output)
            ok = True
            error = None
        except Exception as exc:
            output = None
            ok = False
            error = f"{type(exc).__name__}: {exc}"
        finished = datetime.now(timezone.utc)
        return ToolReceipt(
            request.invocation_id,
            request.tool_id,
            adapter.manifest.version,
            started,
            finished,
            ok,
            output,
            error,
        )
