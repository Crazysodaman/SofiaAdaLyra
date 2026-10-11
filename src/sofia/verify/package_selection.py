"""Exact-SHA, nonempty pytest package selection proof without running tests.

Collects the test suite and checks real item ownership *after* all pytest
mark/deselection hooks. This rejects zero-selected package jobs even if an
incorrect filename mapping made a suite look like it existed. It never runs
test bodies; package CI subsequently runs the actual selected tests.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tomllib

from sofia.verify.v18_roadmap import RoadmapIntegrityError


PKG_RE = re.compile(r"^pkg_[a-z_]+$")
WORKFLOW_MARKER_RE = re.compile(r"^\s+- (pkg_[a-z_]+)\s*$", re.MULTILINE)


def expected_packages(repo: Path) -> tuple[str, ...]:
    """Bind all packages to the real pytest config and Actions matrix."""
    config = tomllib.loads((repo / "pyproject.toml").read_text(encoding="utf-8"))
    names: list[str] = []
    for value in config["tool"]["pytest"]["ini_options"]["markers"]:
        name = value.split(":", 1)[0].strip()
        if PKG_RE.fullmatch(name):
            names.append(name)
    if len(names) != 22 or len(set(names)) != len(names):
        raise RoadmapIntegrityError("expected 22 distinct configured package markers")
    workflow = (repo / ".github/workflows/package-tests.yml").read_text(
        encoding="utf-8"
    )
    scheduled = WORKFLOW_MARKER_RE.findall(workflow)
    if sorted(names) != sorted(scheduled):
        raise RoadmapIntegrityError("package CI matrix and pytest markers differ")
    return tuple(sorted(names))


@dataclass
class PackageSelectionProbe:
    """Observe pytest's fully selected items without taking any test action."""
    markers: tuple[str, ...]
    selected: dict[str, list[str]] = field(init=False)
    collection_finished: bool = False

    def __post_init__(self) -> None:
        self.selected = {name: [] for name in self.markers}

    def pytest_collection_finish(self, session) -> None:
        self.collection_finished = True
        for item in session.items:
            for name in self.markers:
                if tuple(item.iter_markers(name=name)):
                    self.selected[name].append(item.nodeid)


def _revision(repo: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo,
        capture_output=True, text=True, check=True,
    )
    revision = result.stdout.strip()
    if re.fullmatch(r"[0-9a-f]{40}", revision) is None:
        raise RoadmapIntegrityError("package report requires exact Git revision")
    return revision


def collect_package_selection(
    repo: Path, *, marker: str | None = None,
) -> dict[str, object]:
    """Collect all 22 or one exact package, requiring nonempty real tests.

    `pytest.main` with `--collect-only` never runs test functions. This must
    not be described as passing any test or proving package acceptance.
    """
    repo = repo.resolve(strict=True)
    names = expected_packages(repo)
    if marker is not None and marker not in names:
        raise RoadmapIntegrityError(f"unknown package marker: {marker}")
    if not (repo / "test/conftest.py").is_file():
        raise RoadmapIntegrityError("canonical pytest collection root missing")
    import pytest

    checked = names if marker is None else (marker,)
    probe = PackageSelectionProbe(checked)
    expression = "not integration" if marker is None else f"{marker} and not integration"
    collection_args = [
        "--collect-only", "-qq", "--disable-warnings",
        "-m", expression, str(repo / "test"),
    ]
    if os.environ.get("SOFIA_VERIFY_INSTALLED_ONLY") == "1":
        collection_args += ["--override-ini", "pythonpath=."]
    exitcode = pytest.main(collection_args, plugins=[probe])
    counts = {name: len(probe.selected[name]) for name in checked}
    if exitcode != 0 or not probe.collection_finished or any(
        count == 0 for count in counts.values()
    ):
        raise RoadmapIntegrityError(
            "nonempty package collection gate failed "
            f"(pytest={exitcode}, finished={probe.collection_finished}, "
            f"selected={counts}); do not label an empty package green"
        )
    return {
        "schema": "sofia.package-selection-v1",
        "git_revision": _revision(repo),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "all" if marker is None else marker,
        "selected_test_counts": counts,
        "verified_nonempty": True,
        "tests_executed": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m sofia.verify.package_selection")
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--all", action="store_true")
    selector.add_argument("--marker")
    parser.add_argument(
        "--repo", type=Path, default=Path.cwd(),
    )
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args(argv)
    try:
        report = collect_package_selection(
            args.repo, marker=None if args.all else args.marker,
        )
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        print(
            f"Package selection proof failed: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2
    if args.receipt is not None:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        staging = args.receipt.with_suffix(args.receipt.suffix + ".tmp")
        staging.write_text(
            json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8",
        )
        staging.replace(args.receipt)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
