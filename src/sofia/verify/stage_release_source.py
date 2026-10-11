"""Stage exact Git HEAD bytes outside checkout for a reproducible release.

Never use the editable working tree, Git archive extraction, Windows newline
conversion, or an unverified unpacked path as release provenance. For every
regular blob listed by the reviewed Git tree, verify the raw Git object SHA-1
and write those exact bytes to a newly created, empty, external stage.
"""
from __future__ import annotations

import argparse
from hashlib import sha1
import os
from pathlib import Path
import subprocess
import sys


def _git(repo: Path, *args: str) -> bytes:
    return subprocess.run(("git", *args), cwd=repo, check=True,
                          capture_output=True).stdout


def stage_reviewed_git_tree(checkout: Path, target: Path) -> int:
    root = checkout.resolve(strict=True)
    if not (root / ".git").exists():
        raise ValueError("source checkout has no Git metadata")
    outside = target.absolute()
    if outside == root or root in outside.parents or outside in root.parents:
        raise ValueError("release source stage must be outside checkout")
    if outside.exists():
        if outside.is_symlink() or not outside.is_dir() or any(outside.iterdir()):
            raise ValueError("release source stage must be an empty ordinary directory")
    else:
        outside.mkdir(parents=True, exist_ok=False)
    rows = tuple(row for row in _git(root, "ls-tree", "-r", "-z", "HEAD").split(b"\0")
                 if row)
    if not rows:
        raise ValueError("no reviewed Git blobs to stage")
    seen: set[str] = set()
    for row in rows:
        fields, path_bytes = row.split(b"\t", 1)
        mode, kind, object_sha = fields.decode("ascii").split(" ")
        if kind != "blob" or mode not in ("100644", "100755"):
            raise ValueError("unexpected nonregular Git tree object")
        relative = Path(path_bytes.decode("utf-8", "strict"))
        if (relative.is_absolute() or ".." in relative.parts or
            not relative.parts or ":" in str(relative)):
            raise ValueError("unsafe release source path")
        normalized = relative.as_posix().casefold()
        if normalized in seen:
            raise ValueError("two Git paths collide on a case-insensitive host")
        seen.add(normalized)
        item = outside / relative
        if item.exists() or item.is_symlink():
            raise ValueError("duplicate or redirected stage target")
        if any(parent.is_symlink() for parent in item.parents if
               parent == outside or outside in parent.parents):
            raise ValueError("redirected stage parent")
        blob = _git(root, "cat-file", "blob", object_sha)
        proof = sha1(
            b"blob " + str(len(blob)).encode("ascii") + b"\0" + blob
        ).hexdigest()
        if proof != object_sha:
            raise ValueError("Git object content failed its reviewed SHA")
        item.parent.mkdir(parents=True, exist_ok=True)
        with item.open("xb") as staged:
            staged.write(blob)
        if item.read_bytes() != blob:
            raise OSError("written release bytes differ from Git object")
    return len(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        count = stage_reviewed_git_tree(args.checkout, args.target)
    except (OSError, ValueError, UnicodeError, subprocess.CalledProcessError) as exc:
        print(f"release source staging refused: {type(exc).__name__}: {exc}",
              file=sys.stderr)
        return 2
    print(f"staged {count} exact reviewed HEAD blobs (no checkout autocrlf)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
