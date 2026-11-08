"""Read-only, non-authoritative Settings projection for Aegis GUI/TUI.

Source: CanonicalSettingsService.snapshot(owners=...) after the Platform has
authenticated and authorized that exact client. This module never opens a
state database, reads secrets, approves a mutation or claims saved=effective.
"""
from __future__ import annotations

from dataclasses import dataclass
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
    # None means the snapshot does not identify which fields are pending.
    requires_apply: bool | None


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
            requires_apply=None if effective < rev else False,
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
            f"({row.apply_class}{', APPLY UNKNOWN' if row.requires_apply is None else ''})"
            for row in view.rows
        ),
    )



@dataclass(frozen=True, slots=True)
class ModuleSettingsReadView:
    """Identity-bound module projection, not a current Platform grant."""

    module_id: str
    package_digest: str
    lifecycle: str
    lifecycle_revision: int
    revision: int
    effective_revision: int
    rows: tuple[SettingsRow, ...]

    def needs_review(self, current: "ModuleSettingsReadView") -> bool:
        """Require a new review on any module or settings incarnation change."""
        return (
            self.module_id != current.module_id
            or self.package_digest != current.package_digest
            or self.lifecycle != current.lifecycle
            or self.lifecycle_revision != current.lifecycle_revision
            or self.revision != current.revision
            or self.effective_revision != current.effective_revision
        )


def project_module_settings_snapshot(raw: object) -> ModuleSettingsReadView:
    """Safely display scoped ModuleSettingsService.snapshot without database access.

    Protected secret references are always hidden. The provided signed
    contract is parsed, but this view does not independently verify the
    package signature or supply any settings update authorization.
    """
    from sofia.sdk.module_settings import module_settings_contract_from_document

    fields = {
        "module_id", "package_digest", "lifecycle", "lifecycle_revision",
        "revision", "effective_revision", "values", "contract",
    }
    if not isinstance(raw, Mapping) or set(raw) != fields:
        raise ValueError("invalid module settings snapshot")
    module_id = raw["module_id"]
    digest = raw["package_digest"]
    lifecycle = raw["lifecycle"]
    if (not isinstance(module_id, str) or len(module_id) > 160
            or _FIELD.fullmatch(module_id.replace(".", "_").replace("-", "_")) is None
            or not isinstance(digest, str)
            or re.fullmatch(r"[0-9a-f]{64}", digest) is None
            or not isinstance(lifecycle, str)
            or re.fullmatch(r"[a-z_]{1,40}", lifecycle) is None):
        raise ValueError("invalid module settings identity")
    revisions = (
        raw["lifecycle_revision"], raw["revision"], raw["effective_revision"]
    )
    if (any(type(item) is not int or item < 0 for item in revisions)
            or revisions[0] == 0 or revisions[2] > revisions[1]):
        raise ValueError("invalid module settings revisions")
    contract = module_settings_contract_from_document(raw["contract"])
    values = raw["values"]
    if not isinstance(values, Mapping):
        raise ValueError("invalid module settings values")
    allowed = {field.field_id: field for field in contract.fields}
    if len(values) > 128 or any(key not in allowed for key in values):
        raise ValueError("unreviewed module settings fields")
    rows: list[SettingsRow] = []
    for field_id in sorted(values):
        field = allowed[field_id]
        value = values[field_id]
        if field.secret_reference:
            if value not in (None, "<protected-secret-reference>"):
                raise ValueError("unredacted module secret field refused")
            visible = "[REDACTED]"
        else:
            field.validate(value)
            visible = _display_value(field_id, value)
        rows.append(SettingsRow(
            field_id=field_id,
            owner="module",
            apply_class=field.apply_class.value,
            saved_value=visible,
            requires_apply=None if revisions[2] < revisions[1] else False,
        ))
    return ModuleSettingsReadView(
        module_id=module_id, package_digest=digest, lifecycle=lifecycle,
        lifecycle_revision=revisions[0], revision=revisions[1],
        effective_revision=revisions[2], rows=tuple(rows),
    )
