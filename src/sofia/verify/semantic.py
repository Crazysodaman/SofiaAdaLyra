from __future__ import annotations

from pathlib import Path
import sys

from sofia.config import create_production_configuration
from sofia.state.sqlite_plane import SQLiteStatePlane
from sofia.verify.semantic_integrity import SemanticIntegrityVerifier


def main(argv: list[str] | None = None) -> int:
    configuration = create_production_configuration()
    state_path = Path(configuration.state_path)
    try:
        verifier = SemanticIntegrityVerifier(
            state_path,
            state_plane=SQLiteStatePlane(state_path),
        )
        report = verifier.verify()
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
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        print(
            f"Semantic integrity verification failed: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
