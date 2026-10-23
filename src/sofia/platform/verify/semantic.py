"""Verify real canonical integrity on live hosts, or isolated proof in CI.

The isolated fixture proves the installed semantic verifier rejects a
dangling private-session binding and accepts its corrected source. It is NOT
a test of live sofia.db and does not bootstrap production authority.
"""
from __future__ import annotations

import argparse
from contextlib import closing
from pathlib import Path
import sqlite3
import sys
import tempfile

from sofia.platform.config import create_production_configuration
from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard, bootstrap_canonical_sqlite
from sofia.platform.state.sqlite_plane import SQLiteStatePlane
from sofia.platform.verify.semantic_integrity import SemanticIntegrityVerifier


def _verifier(path: Path) -> SemanticIntegrityVerifier:
    # SQLiteStatePlane initializes schema and can create a missing file.
    # Canonical state must therefore be validated BEFORE constructing it,
    # and revalidated after schema inspection, not manufactured by VERIFY.
    guard = CanonicalSQLiteGuard(path)
    plane = SQLiteStatePlane(guard.canonical_path)
    guard.validate()
    return SemanticIntegrityVerifier(
        guard.canonical_path, state_plane=plane,
    )


def _verify_real_path(state_path: Path) -> int:
    report = _verifier(state_path).verify()
    if report.accepted:
        print(
            "Semantic integrity: accepted "
            f"checked_at={report.checked_at.isoformat()} findings=0"
        )
        return 0
    for finding in report.findings:
        print(
            f"{finding.severity.value}: {finding.code}: {finding.detail}",
            file=sys.stderr,
        )
    return 2


def _verify_isolated_fixture() -> int:
    """Prove reject-and-recover behavior without consulting a live state home."""
    with tempfile.TemporaryDirectory(prefix="sofia-semantic-ci-") as root:
        path = bootstrap_canonical_sqlite(Path(root) / "sofia.db")
        with closing(sqlite3.connect(path)) as db, db:
            db.execute(
                "CREATE TABLE conversation_sessions (id TEXT PRIMARY KEY)"
            )
            db.execute(
                "CREATE TABLE social_session_principal "
                "(session_id TEXT PRIMARY KEY)"
            )
            db.execute(
                "INSERT INTO social_session_principal VALUES (?)",
                ("ci:orphaned-session",),
            )
        broken = _verifier(path).verify()
        if broken.accepted or not any(
            finding.code == "social.binding_orphaned"
            for finding in broken.findings
        ):
            print(
                "isolated semantic fixture did not reject the orphaned binding",
                file=sys.stderr,
            )
            return 3
        with closing(sqlite3.connect(path)) as db, db:
            db.execute(
                "INSERT INTO conversation_sessions VALUES (?)",
                ("ci:orphaned-session",),
            )
        outcome = _verify_real_path(path)
        if outcome == 0:
            print(
                "Isolated semantic fixture passed reject-and-recover; "
                "this is NOT a live-host state integrity attestation."
            )
        return outcome


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m sofia.platform.verify.semantic")
    parser.add_argument(
        "--isolated-fixture", action="store_true",
        help="Run bounded synthetic evidence verification in disposable CI state",
    )
    args = parser.parse_args(argv)
    try:
        if args.isolated_fixture:
            return _verify_isolated_fixture()
        # No fixture path or environment override is used in the live path:
        # normal production startup must reject lost identity or sofia.db.
        configuration = create_production_configuration()
        return _verify_real_path(Path(configuration.state_path))
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        print(
            f"Semantic integrity verification failed: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
