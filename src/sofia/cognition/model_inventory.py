"""Read-only model discovery grounded in Ollama's actual local API.

Production owner Settings invokes this on demand. It never pulls, loads,
switches providers, admits licenses, or treats advertised abilities as tested.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from typing import Mapping

from sofia.config.cognitive_models import CognitiveModelSelection
from sofia.state.canonical_sqlite import CanonicalSQLiteGuard


@dataclass(frozen=True, slots=True)
class ModelInventoryObservation:
    host_id: str
    model: str
    provider: str
    configured_roles: tuple[str, ...]
    installed: bool | None
    observed_at: datetime
    provider_version: str | None = None
    digest: str | None = None
    size_bytes: int | None = None
    quantization: str | None = None
    advertised_context_length: int | None = None
    advertised_capabilities: tuple[str, ...] = ()
    license_sha256: str | None = None
    license_excerpt: str | None = None
    details_error: str | None = None

    def __post_init__(self):
        if not self.host_id or not self.model or not self.provider:
            raise ValueError("inventory requires host, model and provider")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("inventory time must be timezone-aware")
        if self.installed is not None and type(self.installed) is not bool:
            raise TypeError("installed must be observed bool or unknown")
        if any(role not in {"primary", "secondary"} for role in self.configured_roles):
            raise ValueError("unknown configured role")


def _string(value, *, limit=240) -> str | None:
    if not isinstance(value, str):
        return None
    clean = value.strip()
    return clean[:limit] if clean else None


def _positive_size(value) -> int | None:
    return value if type(value) is int and 0 < value < (1 << 64) else None


def _configured_roles(selection: CognitiveModelSelection) -> dict[str, tuple[str, ...]]:
    roles: dict[str, list[str]] = {}
    for role, provider in (
        ("primary", selection.primary), ("secondary", selection.secondary),
    ):
        if provider is None:
            continue
        roles.setdefault(provider.model, []).append(role)
    return {name: tuple(values) for name, values in roles.items()}


def collect_local_model_inventory(
    *,
    selection: CognitiveModelSelection,
    backend,
    host_id: str,
    at: datetime,
) -> tuple[ModelInventoryObservation, ...]:
    """Bounded Ollama /tags + /version + /show inventory, with honest unknowns."""
    if not isinstance(selection, CognitiveModelSelection):
        raise TypeError("effective model selection required")
    if not isinstance(host_id, str) or not host_id.strip() or len(host_id) > 200:
        raise ValueError("verified host ID required")
    if not isinstance(at, datetime) or at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("observation time must be timezone-aware")

    # A model service outage is an error, not evidence that no models exist.
    tags = backend.models()
    if not isinstance(tags, Mapping) or not isinstance(tags.get("models"), list):
        raise ValueError("Ollama returned no valid installed-model inventory")
    entries = tags["models"]
    if len(entries) > 64:
        raise ValueError("installed-model inventory exceeds reviewed 64-model bound")

    version = None
    try:
        reported = backend.version()
        if isinstance(reported, Mapping):
            version = _string(reported.get("version"), limit=100)
    except Exception:
        # A missing optional /version endpoint does not erase observed tags.
        pass

    by_name: dict[str, Mapping] = {}
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise ValueError("Ollama returned an invalid model metadata row")
        name = _string(entry.get("name") or entry.get("model"), limit=300)
        if name is None:
            raise ValueError("Ollama listed a model without a valid name")
        if name in by_name:
            raise ValueError("Ollama returned duplicate installed-model identity")
        by_name[name] = entry

    configured = _configured_roles(selection)
    providers = {selection.primary.model: selection.primary.provider}
    if selection.secondary is not None:
        providers[selection.secondary.model] = selection.secondary.provider
    # Include configured Ollama role models missing from /tags. Non-Ollama
    # roles are explicitly unknown to this Ollama-only observer.
    names = sorted(set(by_name) | set(configured))
    result = []
    for name in names:
        entry = by_name.get(name)
        provider = providers.get(name, "ollama")
        details = entry.get("details") if entry is not None else None
        details = details if isinstance(details, Mapping) else {}
        quant = _string(details.get("quantization_level"), limit=120)
        digest = _string(entry.get("digest"), limit=200) if entry else None
        size = _positive_size(entry.get("size")) if entry else None
        caps = ()
        context_limit = None
        license_digest = None
        license_excerpt = None
        detail_error = None
        if entry is not None:
            try:
                shown = backend.show(name)
                if not isinstance(shown, Mapping):
                    raise ValueError("model /show returned a non-object")
                raw_caps = shown.get("capabilities")
                if isinstance(raw_caps, list):
                    caps = tuple(sorted({
                        value
                        for item in raw_caps[:64]
                        if (value := _string(item, limit=100)) is not None
                    }))
                model_info = shown.get("model_info")
                if isinstance(model_info, Mapping):
                    limits = [
                        value for key, value in list(model_info.items())[:128]
                        if isinstance(key, str)
                        and key.endswith(".context_length")
                        and (value := _positive_size(value)) is not None
                    ]
                    context_limit = max(limits) if limits else None
                license_value = shown.get("license")
                if isinstance(license_value, str):
                    license_text = license_value
                elif (
                    isinstance(license_value, list)
                    and all(isinstance(item, str) for item in license_value)
                ):
                    license_text = "\n".join(license_value)
                else:
                    license_text = ""
                if license_text:
                    license_digest = sha256(license_text.encode("utf-8")).hexdigest()
                    license_excerpt = license_text[:240]
                show_details = shown.get("details")
                if quant is None and isinstance(show_details, Mapping):
                    quant = _string(show_details.get("quantization_level"), limit=120)
            except Exception as exc:
                detail_error = type(exc).__name__

        installed = (entry is not None) if provider == "ollama" else None
        result.append(ModelInventoryObservation(
            host_id=host_id, model=name, provider=provider,
            configured_roles=configured.get(name, ()),
            installed=installed, observed_at=at,
            provider_version=version if provider == "ollama" else None,
            digest=digest, size_bytes=size, quantization=quant,
            advertised_context_length=context_limit,
            advertised_capabilities=caps,
            license_sha256=license_digest,
            license_excerpt=license_excerpt,
            details_error=detail_error,
        ))
    return tuple(result)


class ModelInventoryStore:
    """Latest bounded observed model facts in the existing canonical DB."""

    def __init__(self, state_path: Path | str):
        self.path = Path(state_path)
        self._guard = CanonicalSQLiteGuard(self.path)
        with closing(self._guard.connect(timeout=10)) as db, db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS cognition_model_inventory(
                    host_id TEXT NOT NULL,
                    model TEXT NOT NULL,
                    snapshot_json TEXT NOT NULL,
                    PRIMARY KEY(host_id, model)
                )"""
            )

    def replace_host(
        self, *, host_id: str,
        observations: tuple[ModelInventoryObservation, ...],
    ) -> None:
        if not isinstance(host_id, str) or not host_id.strip():
            raise ValueError("host_id required")
        if not isinstance(observations, tuple) or len(observations) > 66:
            raise ValueError("bounded model inventory required")
        if any(
            not isinstance(item, ModelInventoryObservation)
            or item.host_id != host_id for item in observations
        ):
            raise ValueError("inventory rows must belong to the observed host")
        with closing(self._guard.connect(timeout=10)) as db, db:
            db.execute("PRAGMA busy_timeout=10000")
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "DELETE FROM cognition_model_inventory WHERE host_id=?",
                (host_id,),
            )
            for item in observations:
                payload = asdict(item)
                payload["observed_at"] = item.observed_at.astimezone(
                    timezone.utc
                ).isoformat()
                db.execute(
                    "INSERT INTO cognition_model_inventory VALUES(?,?,?)",
                    (host_id, item.model,
                     json.dumps(payload, sort_keys=True, ensure_ascii=False)),
                )

    def readable(self, *, host_id: str) -> str:
        with closing(self._guard.connect(timeout=10)) as db:
            rows = db.execute(
                "SELECT snapshot_json FROM cognition_model_inventory "
                "WHERE host_id=? ORDER BY model LIMIT 66",
                (host_id,),
            ).fetchall()
        if not rows:
            return "No successful read-only inventory yet. Use Refresh local model inventory."
        lines = [
            "Observed local model metadata only. Capabilities are ADVERTISED,",
            "NOT VERIFIED. Licenses are NOT accepted by discovery.",
        ]
        for (raw,) in rows:
            item = json.loads(raw)
            installed = item.get("installed")
            state = (
                "installed" if installed is True
                else "not installed" if installed is False
                else "not observable through Ollama"
            )
            lines.extend((
                f"Model: {item['model']} | {state} | "
                f"role(s): {', '.join(item['configured_roles']) or 'unconfigured'}",
                f"  Provider: {item['provider']} "
                f"version: {item['provider_version'] or 'unknown'} "
                f"digest: {item['digest'] or 'unknown'}",
                f"  Bytes: {item['size_bytes'] or 'unknown'} "
                f"quantization: {item['quantization'] or 'unknown'} "
                f"context advertised: {item['advertised_context_length'] or 'unknown'}",
                f"  Capabilities advertised: {', '.join(item['advertised_capabilities']) or 'unknown'} "
                f"(not verified); details: {item['details_error'] or 'observed'}",
                f"  License SHA-256: {item['license_sha256'] or 'unknown'} "
                f"(terms require human review)",
                f"  Observed: {item['observed_at']}",
            ))
        return "\n".join(lines)
