"""No Docker socket, Portainer credentials, container start or restart authority."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Mapping
import re
from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.platform.capability.model import Capability, CapabilityRequest

MODULE_ID = "MOD-IT-CONTAINERS"
MODULE_VERSION = "0.1.0"
CAPABILITY_ID = "it.containers.interpret_inventory.v1"
PROFILE = "OBSERVE"
RESOURCES = (("cpu_millicores", 50), ("ram_mib", 32), ("gpu_mib", 0))
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$")
_FIELDS = frozenset({"source_ref", "container_ref", "observed_at", "state", "health", "restart_count"})
_STATES = frozenset({"running", "stopped", "paused", "restarting", "unknown"})
_HEALTH = frozenset({"healthy", "unhealthy", "starting", "unknown"})


def inspect_containers(items: list[Mapping[str, object]], *, now: datetime, max_age_seconds: int = 300) -> dict[str, object]:
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("timezone-aware now required")
    if type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 86400:
        raise ValueError("invalid freshness limit")
    if type(items) is not list or not 1 <= len(items) <= 128:
        raise ValueError("expected 1..128 inventory items")
    seen = set()
    rows = []
    for item in items:
        if not isinstance(item, Mapping) or set(item) != _FIELDS:
            raise ValueError("container schema mismatch")
        source, container = item["source_ref"], item["container_ref"]
        if any(not isinstance(s, str) or not _ID.fullmatch(s) for s in (source, container)) or (source, container) in seen:
            raise ValueError("invalid or duplicated container identity")
        seen.add((source, container))
        if item["state"] not in _STATES or item["health"] not in _HEALTH:
            raise ValueError("invalid container state/health")
        restart = item["restart_count"]
        if type(restart) is not int or not 0 <= restart <= 1000000000:
            raise ValueError("invalid restart counter")
        try:
            when = datetime.fromisoformat(item["observed_at"])
            if when.tzinfo is None or when.utcoffset() is None:
                raise ValueError("timezone missing")
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid container timestamp") from exc
        age = (now.astimezone(timezone.utc) - when.astimezone(timezone.utc)).total_seconds()
        freshness = "future" if age < -5 else "stale" if age > max_age_seconds else "fresh"
        if freshness != "fresh":
            condition = "unknown"
        elif item["state"] in {"stopped", "restarting"} or item["health"] == "unhealthy":
            condition = "degraded"
        elif item["state"] == "running" and item["health"] == "healthy":
            condition = "observed_healthy"
        else:
            condition = "unknown"
        rows.append({"source_ref": source, "container_ref": container, "freshness": freshness, "condition": condition, "restart_count": restart if freshness == "fresh" else None})
    return {"schema": "sofia.it.containers.report.v1", "module_id": MODULE_ID, "sdk_protocol": str(SDK_PROTOCOL_VERSION), "containers": rows, "evidence_class": "supplied_unverified", "effect": "none"}


def capability_registrations():
    cap = Capability(CAPABILITY_ID, "Review approved container state observations without Docker or Portainer access.")
    def handler(request: CapabilityRequest):
        if request.capability != cap or set(request.parameters) != {"items"}:
            raise ValueError("invalid capability request")
        return inspect_containers(request.parameters["items"], now=datetime.now(timezone.utc))
    return ((cap, handler),)
