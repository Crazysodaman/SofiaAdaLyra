"""Shared SQLite URI construction for canonical, share and local state.

A normal pathlib as_uri() renders a Windows UNC target as an unsupported
URI authority (the server segment), so every canonical SQLite open fails
on a network-hosted state path. This builder keeps ``//server/share``
inside the encoded path portion, as the established verifier pattern
does, and is shared across application surfaces so one path policy
protects all of them.
"""
from pathlib import Path
from urllib.parse import quote


def sqlite_uri_from_posix(raw: str, *, read_only: bool | None = None) -> str:
    """Build a SQLite file URI from a POSIX-style path string.

    A Unix absolute path keeps the documented single-slash no-authority
    form. A Windows drive path receives an empty authority. A UNC path
    keeps its double leading slash; open failures are then reported by
    sqlite itself, without ever creating a different file.
    """
    if not isinstance(raw, str):
        raise TypeError("The POSIX path must be a string.")

    encoded = quote(raw, safe="/:")

    if raw.startswith("//"):
        target = "file://" + encoded
    elif len(raw) >= 2 and raw[1] == ":":
        target = "file:///" + encoded
    else:
        target = "file:" + encoded

    if read_only is None:
        return target

    if not isinstance(read_only, bool):
        raise TypeError("read_only must be bool or None")

    return target + ("?mode=ro" if read_only else "?mode=rw")


def sqlite_file_uri(path: Path | str, *, read_only: bool | None = None) -> str:
    """Build a SQLite file URI from a Path or path string."""
    if not isinstance(path, (Path, str)):
        raise TypeError(
            "The SQLite path must be a Path or a path string."
        )

    return sqlite_uri_from_posix(
        Path(path).as_posix(),
        read_only=read_only,
    )
