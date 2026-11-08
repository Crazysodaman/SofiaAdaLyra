"""Read-only, non-authoritative Settings projection for Aegis GUI/TUI.

Source: CanonicalSettingsService.snapshot(owners=...) after the Platform has
authenticated and authorized that exact client. This module never opens a
state database, reads secrets, approves a mutation or claims saved=effective.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Mapping

_FIELD = re.compile(r"^[a-z][a-z0-9_]{0,127}$")
_OWNERS = frozenset({"host", "core", "client"})
_APPLY = frozenset({
    "live", "next_operation", "component_restart", "platform_restart",
})
_SENSITIVE = re.compile(
    r"secret|token|password|credential|private|key|discord_.*id|owner.*id|auth",
    re.IGNORECASE,
)
_MAX_FIELDS = 256


@dataclass(frozen=True, slots=True)
class SettingsRow:
    field_id: str
    owner: str
    apply_class: str
    saved_value: str
    requires_apply: bool


@dataclass(frozen=True, slots=True)
class SettingsReadView:
    """Valid display projection, not proof of service identity or freshness."""

    revision: int
    effective_revision: int
    rows: tuple[SettingsRow, ...]
    source_trust: str = "UNVERIFIED"

    def needs_review(self, current: "SettingsReadView") -> bool:
        """Invalidate an editor when either revision has advanced."""
        return (self.source_trust != "VERIFIED"
                or current.source_trust != "VERIFIED"
                or current.revision != self.revision
                or current.effective_revision != self.effective_revision)


def _display_value(field_id: str, value: object) -> str:
    if _SENSITIVE.search(field_id):
        return "[REDACTED]"
    if value is None:
        return "(unset)"
    if type(value) is bool:
        return "Enabled" if value else "Disabled"
    if type(value) in (int, float):
        return str(value) if len(str(value)) <= 64 else "[VALUE TOO LONG]"
    if isinstance(value, str):
        # Terminal escape codes, control chars and newlines must never reach a
        # terminal or be passed into a GUI markup parser as trusted text.
        if len(value) > 160 or any(ord(c) < 32 or ord(c) == 127 for c in value):
            return "[TEXT HIDDEN]"
        return value
    return "[STRUCTURED VALUE]"


def project_settings_snapshot(raw: object) -> SettingsReadView:
    """Convert a Platform-owned scoped snapshot into a bounded display model.

    This is *not* an authentication check, permission check, source verifier,
    freshness guarantee or a client-side settings update implementation.
    """
    if not isinstance(raw, Mapping) or set(raw) != {
        "schema_version", "revision", "effective_revision", "values", "contracts",
    }:
        raise ValueError("invalid scoped settings snapshot")
    version, rev, effective = (
        raw["schema_version"], raw["revision"], raw["effective_revision"]
    )
    if type(version) is not int or version < 1:
        raise ValueError("invalid settings schema")
    if (type(rev) is not int or type(effective) is not int
            or rev < 0 or effective < 0 or effective > rev):
        raise ValueError("invalid settings revision")
    values, contracts = raw["values"], raw["contracts"]
    if (not isinstance(values, Mapping) or not isinstance(contracts, Mapping)
            or len(values) > _MAX_FIELDS or set(values) != set(contracts)):
        raise ValueError("unreviewed settings fields")
    rows = []
    for field_id in sorted(values):
        if not isinstance(field_id, str) or _FIELD.fullmatch(field_id) is None:
            raise ValueError("invalid settings field ID")
        contract = contracts[field_id]
        if (not isinstance(contract, Mapping)
                or set(contract) != {"owner", "apply_class"}
                or contract["owner"] not in _OWNERS
                or contract["apply_class"] not in _APPLY):
            raise ValueError("invalid settings contract")
        rows.append(SettingsRow(
            field_id=field_id,
            owner=contract["owner"],
            apply_class=contract["apply_class"],
            saved_value=_display_value(field_id, values[field_id]),
            requires_apply=effective < rev,
        ))
    return SettingsReadView(
        revision=rev, effective_revision=effective, rows=tuple(rows)
    )


def render_settings_lines(view: SettingsReadView) -> tuple[str, ...]:
    """Plain ASCII-only diagnostic fallback, never fake VERIFIED status."""
    status = f"Saved revision {view.revision} / applied {view.effective_revision}"
    return (
        "AEGIS SETTINGS (READ ONLY)",
        f"SOURCE TRUST: {view.source_trust}",
        status,
        *(
            f"[{row.owner}] {row.field_id}: {row.saved_value} "
            f"({row.apply_class}{', PENDING' if row.requires_apply else ''})"
            for row in view.rows
        ),
    )
