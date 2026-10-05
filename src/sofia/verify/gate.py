from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time


@dataclass(frozen=True, slots=True)
class GateCommandEvidence:
    name: str
    argv: tuple[str, ...]
    returncode: int
    started_at: str
    finished_at: str
    duration_seconds: float


@dataclass(frozen=True, slots=True)
class VerificationEvidence:
    phase: str
    git_revision: str
    python_version: str
    tracked_tree_clean: bool
    generated_at: str
    commands: tuple[GateCommandEvidence, ...]

    @property
    def accepted(self) -> bool:
        source_state_acceptable = (
            self.tracked_tree_clean or self.phase == "candidate"
        )
        return source_state_acceptable and all(
            item.returncode == 0 for item in self.commands
        )


_STATIC_COMMANDS = (
    (
        "compile",
        (
            "-m",
            "compileall",
            "-q",
            "src/sofia",
            "test",
            "tools",
        ),
    ),
    ("dependency-check", ("-m", "pip", "check")),
)

_PHASES = {
    "static": _STATIC_COMMANDS,
    "full": (
        *_STATIC_COMMANDS,
        (
            "pytest",
            ("-m", "pytest", "-q", "-m", "not integration"),
        ),
        ("semantic", ("-m", "sofia.verify.semantic")),
    ),
    "candidate": (
        *_STATIC_COMMANDS,
        (
            "pytest",
            ("-m", "pytest", "-q", "-m", "not integration"),
        ),
        ("semantic", ("-m", "sofia.verify.semantic")),
    ),
    "prelive": (
        *_STATIC_COMMANDS,
        ("pytest", ("-m", "pytest", "-q")),
        ("semantic", ("-m", "sofia.verify.semantic")),
    ),
}


def _git_revision() -> str:
    result = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        check=True,
        capture_output=True,
        text=True,
    )
    value = result.stdout.strip()
    if len(value) != 40:
        raise RuntimeError("git revision is not a full commit SHA")
    return value


def _tracked_tree_clean() -> bool:
    """Require executed code and tracked files to equal the reported revision."""

    result = subprocess.run(
        ("git", "diff", "--quiet", "HEAD", "--"),
        check=False,
    )
    if result.returncode not in {0, 1}:
        raise RuntimeError("could not determine tracked worktree state")
    return result.returncode == 0


def run_gate(
    phase: str,
    *,
    evidence_path: Path,
) -> VerificationEvidence:
    if phase not in _PHASES:
        raise ValueError(f"unsupported verification phase: {phase}")
    if not isinstance(evidence_path, Path):
        raise TypeError("evidence_path must be a Path")

    commands: list[GateCommandEvidence] = []
    for name, args in _PHASES[phase]:
        start_wall = datetime.now(timezone.utc)
        start = time.monotonic()
        result = subprocess.run(
            (sys.executable, *args),
            check=False,
        )
        end = time.monotonic()
        finish_wall = datetime.now(timezone.utc)
        evidence = GateCommandEvidence(
            name=name,
            argv=(sys.executable, *args),
            returncode=result.returncode,
            started_at=start_wall.isoformat(),
            finished_at=finish_wall.isoformat(),
            duration_seconds=round(end - start, 6),
        )
        commands.append(evidence)
        if result.returncode != 0:
            break

    report = VerificationEvidence(
        phase=phase,
        git_revision=_git_revision(),
        python_version=sys.version,
        tracked_tree_clean=_tracked_tree_clean(),
        generated_at=datetime.now(timezone.utc).isoformat(),
        commands=tuple(commands),
    )
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    temp = evidence_path.with_suffix(evidence_path.suffix + ".tmp")
    temp.write_text(
        json.dumps(
            {
                **asdict(report),
                "accepted": report.accepted,
            },
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    temp.replace(evidence_path)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m sofia.verify.gate"
    )
    parser.add_argument(
        "--phase",
        required=True,
        choices=tuple(_PHASES),
    )
    parser.add_argument(
        "--evidence-path",
        default="verify-evidence.json",
    )
    args = parser.parse_args(argv)
    try:
        report = run_gate(
            args.phase,
            evidence_path=Path(args.evidence_path),
        )
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        print(
            f"Verification gate failed to run: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 3
    print(
        f"verification phase={report.phase} "
        f"revision={report.git_revision} "
        f"accepted={report.accepted}"
    )
    return 0 if report.accepted else 2


if __name__ == "__main__":
    raise SystemExit(main())
