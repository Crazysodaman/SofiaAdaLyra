"""Independently attest Git HEAD -> exported source -> installed wheel package.

This is a structural CI provenance gate, not unit tests and not proof that any
behavior works. It reads the checkout and staged archive; writes only a small
report file. It never imports the checkout's `src/sofia` directly.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha1, sha256
import importlib.util
import json
from pathlib import Path
import subprocess
import sys


def _git(root: Path, *args: str) -> bytes:
    return subprocess.run(
        ("git", *args), cwd=root, check=True, capture_output=True
    ).stdout


def prove_release_source(
    *, checkout: Path, archive: Path, venv: Path
) -> dict[str, object]:
    checkout = checkout.resolve(strict=True)
    archive = archive.resolve(strict=True)
    venv = venv.resolve(strict=True)
    if checkout == archive or checkout in archive.parents or archive in checkout.parents:
        raise ValueError("release archive must be outside Git checkout")
    if checkout == venv or archive == venv:
        raise ValueError("release venv must not replace checkout or source archive")
    if not (checkout / ".git").exists():
        raise ValueError("expected exact Git checkout")
    revision = _git(checkout, "rev-parse", "HEAD").decode("ascii").strip()
    if len(revision) != 40:
        raise ValueError("expected full revision")
    if _git(checkout, "diff", "--name-only", "HEAD", "--"):
        raise ValueError("tracked files differ from claimed revision")
    raw = _git(checkout, "ls-tree", "-r", "-z", "HEAD")
    entries = tuple(part for part in raw.split(b"\0") if part)
    if not entries:
        raise ValueError("empty Git tree")
    digests: list[str] = []
    for entry in entries:
        metadata, encoded_path = entry.split(b"\t", 1)
        mode, object_kind, expected_sha = metadata.decode("ascii").split(" ")
        if object_kind != "blob":
            raise ValueError("release tree includes an unexpected Git object kind")
        # Git names are byte sequences; archive and tracked paths on Windows
        # must be representable without collisions or ambiguous decoding.
        path = Path(encoded_path.decode("utf-8", "strict"))
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("unsafe tracked source path")
        staged = archive / path
        if not staged.is_file() or staged.is_symlink():
            raise ValueError(f"missing or symlinked archived source: {path}")
        content = staged.read_bytes()
        value = sha1(b"blob " + str(len(content)).encode("ascii") + b"\0" + content).hexdigest()
        if value != expected_sha:
            raise ValueError(f"source archive differs from HEAD: {path}")
        digests.append(f"{mode} {value} {path.as_posix()}")
    staged_files = {
        path.relative_to(archive).as_posix()
        for path in archive.rglob("*")
        if path.is_file()
    }
    tracked_files = {Path(row.split(b"\t", 1)[1].decode("utf-8", "strict")).as_posix() for row in entries}
    if staged_files != tracked_files:
        raise ValueError("release archive contains missing or unexpected files")
    spec = importlib.util.find_spec("sofia")
    if spec is None or not spec.origin:
        raise ValueError("installed Sofia package cannot be located")
    installed = Path(spec.origin).resolve(strict=True)
    if venv not in installed.parents:
        raise ValueError(f"Sofia imported from outside release venv: {installed}")
    if checkout in installed.parents or archive in installed.parents:
        raise ValueError("release validation imported checkout or staged source")
    return {
        "schema": "sofia.release-source-provenance-v1",
        "revision": revision,
        "source_file_count": len(entries),
        "git_blob_manifest_sha256": sha256(
            ("\n".join(digests) + "\n").encode("utf-8")
        ).hexdigest(),
        "installed_package_origin": str(installed),
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "scope": "source/archive/import location proof, NOT behavioral verification",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--venv", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    opts = parser.parse_args(argv)
    try:
        proof = prove_release_source(
            checkout=opts.checkout, archive=opts.archive, venv=opts.venv,
        )
    except (OSError, UnicodeError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"release provenance rejected: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    opts.evidence.parent.mkdir(parents=True, exist_ok=True)
    opts.evidence.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("release source and installed package identity structurally verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
