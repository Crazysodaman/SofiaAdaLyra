"""Filesystem-safe mapping for canonical Sofía identifiers.

Canonical identifiers such as ``project:e757...`` or ``request:bcc...`` are
valid database keys but are not valid Windows path components because they
legally contain ``:``.  Rather than scattering ad-hoc ``str.replace`` calls
wherever an identifier becomes a directory or file name, every such site
routes the identifier through :func:`path_component`.

The original canonical identifier is never modified; it continues to be the
value persisted in SQLite.  Only the on-disk representation is derived.
"""
from __future__ import annotations

from hashlib import sha256

__all__ = ["path_component"]

_PREFIX = "id-"
_SEPARATORS = ("/", "\\")
_TRAVERSAL = frozenset({".", ".."})


def path_component(identifier: str) -> str:
    """Return a deterministic, filesystem-safe component for an identifier.

    The result is a lowercase hexadecimal SHA-256 derivation prefixed with
    ``id-``.  It is therefore:

    * collision-resistant across distinct identifiers,
    * stable under case-insensitive filesystem semantics (all lowercase),
    * free of Windows-reserved characters and device names,
    * never absolute and never a traversal component,
    * bounded in length (67 characters).

    Inputs that are not strings, are empty, are traversal components, or
    contain path separators or NUL bytes are rejected rather than coerced.
    """
    if not isinstance(identifier, str):
        raise TypeError("canonical identifier must be a string")
    if not identifier:
        raise ValueError("canonical identifier must be nonempty")
    if identifier in _TRAVERSAL:
        raise ValueError("canonical identifier must not be a traversal component")
    if any(separator in identifier for separator in _SEPARATORS):
        raise ValueError("canonical identifier must not contain path separators")
    if "\x00" in identifier:
        raise ValueError("canonical identifier must not contain NUL bytes")
    digest = sha256(identifier.encode("utf-8")).hexdigest()
    return f"{_PREFIX}{digest}"
