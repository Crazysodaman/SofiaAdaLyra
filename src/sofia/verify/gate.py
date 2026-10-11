from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import importlib.util
import json
import os
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
        expected = _PHASES.get(self.phase)
        if expected is None or len(self.commands) != len(expected):
            # An empty, shortened, reordered, or duplicated command
            # manifest must never satisfy release acceptance.
            return False
        if type(self.tracked_tree_clean) is not bool:
            return False
        if not self.tracked_tree_clean and self.phase != "candidate":
            return False
        if (
            not isinstance(self.git_revision, str)
            or len(self.git_revision) != 40
            or any(char not in "0123456789abcdef" for char in self.git_revision)
        ):
            return False
        for observed, (expected_name, expected_args) in zip(
            self.commands, expected, strict=True
        ):
            if observed.name != expected_name or type(observed.returncode) is not int:
                return False
            if observed.returncode != 0 or not observed.argv:
                return False
            # The first field is the actual venv Python executable. Verify
            # the real subcommand and restrict installed-wheel-only override
            # arguments to the existing pytest invocation.
            if observed.argv[1:1 + len(expected_args)] != expected_args:
                return False
            trailing = observed.argv[1 + len(expected_args):]
            if trailing and not (
                expected_name == "pytest"
                and trailing == ("--override-ini", "pythonpath=.")
            ):
                return False
        return True


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
    (
        "v18-task-traceability",
        ("-m", "sofia.verify.v18_roadmap"),
    ),
    (
        "nonempty-package-collection",
        ("-m", "sofia.verify.package_selection", "--all"),
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


def _git_revision(repo_root: Path) -> str:
    result = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    value = result.stdout.strip()
    if len(value) != 40:
        raise RuntimeError("git revision is not a full commit SHA")
    return value


def _tracked_tree_clean(repo_root: Path) -> bool:
    """Require executed code and tracked files to equal the reported revision."""

    result = subprocess.run(
        ("git", "diff", "--quiet", "HEAD", "--"),
        cwd=repo_root,
        check=False,
    )
    if result.returncode not in {0, 1}:
        raise RuntimeError("could not determine tracked worktree state")
    return result.returncode == 0


def _assert_installed_wheel_origin(repo: Path) -> None:
    """Reject release test execution against checkout/editable source."""
    if sys.prefix == sys.base_prefix:
        raise RuntimeError("installed-only verification requires an isolated venv")
    spec = importlib.util.find_spec("sofia")
    if spec is None or not spec.origin:
        raise RuntimeError("installed Sofía distribution is unavailable")
    origin = Path(spec.origin).resolve(strict=True)
    environment = Path(sys.prefix).resolve(strict=True)
    if environment not in origin.parents:
        raise RuntimeError("verification is importing Sofía outside the release venv")
    if repo in origin.parents or (repo / "src") in origin.parents:
        raise RuntimeError("verification imported checkout source, not the wheel")


def run_gate(
    phase: str,
    *,
    evidence_path: Path,
    repo_root: Path | None = None,
    installed_wheel_only: bool = False,
) -> VerificationEvidence:
    if phase not in _PHASES:
        raise ValueError(f"unsupported verification phase: {phase}")
    if not isinstance(evidence_path, Path):
        raise TypeError("evidence_path must be a Path")
    if repo_root is not None and not isinstance(repo_root, Path):
        raise TypeError("repo_root must be a Path")
    repo = (repo_root if repo_root is not None else Path.cwd()).resolve(strict=True)
    # The production verifier may be imported from an installed wheel.
    # Its code path is NOT the repository's source-of-truth directory.
    if not (repo / ".git").exists() or not (repo / "pyproject.toml").is_file():
        raise RuntimeError("verification requires the actual Git checkout root")
    checkout = subprocess.run(
        ("git", "rev-parse", "--show-toplevel"), cwd=repo,
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    # Windows Git normally returns C:/... while pathlib renders C:\\....
    if Path(checkout).resolve(strict=True) != repo:
        raise RuntimeError("verification repository is not the checkout root")

    if type(installed_wheel_only) is not bool:
        raise TypeError("installed_wheel_only must be a bool")
    if installed_wheel_only:
        _assert_installed_wheel_origin(repo)

    commands: list[GateCommandEvidence] = []
    for name, args in _PHASES[phase]:
        command = (sys.executable, *args)
        if installed_wheel_only and name == "pytest":
            # pyproject normally adds ./src to pytest imports for developer
            # editable tests. An installed-wheel release must not do that.
            command += ("--override-ini", "pythonpath=.")
        child_env = os.environ.copy()
        if installed_wheel_only:
            child_env.pop("PYTHONPATH", None)
            child_env["SOFIA_VERIFY_INSTALLED_ONLY"] = "1"
        else:
            child_env.pop("SOFIA_VERIFY_INSTALLED_ONLY", None)
        start_wall = datetime.now(timezone.utc)
        start = time.monotonic()
        result = subprocess.run(
            command, cwd=repo, env=child_env, check=False,
        )
        end = time.monotonic()
        finish_wall = datetime.now(timezone.utc)
        evidence = GateCommandEvidence(
            name=name,
            argv=command,
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
        git_revision=_git_revision(repo),
        python_version=sys.version,
        tracked_tree_clean=_tracked_tree_clean(repo),
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
    parser.add_argument(
        "--repo", type=Path, default=Path.cwd(),
        help="Exact checkout root; never derive from installed site-packages.",
    )
    parser.add_argument(
        "--installed-wheel-only", action="store_true",
        help="Reject editable/checkout imports during release package verification.",
    )
    args = parser.parse_args(argv)
    try:
        report = run_gate(
            args.phase,
            evidence_path=Path(args.evidence_path),
            repo_root=args.repo,
            installed_wheel_only=args.installed_wheel_only,
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
