"""Authenticate recorded V18 Gate-4 CI runs against GitHub, not ledger claims.

Read-only independent verification. A completed workflow run verifies only its
recorded SHA and conclusion; human review must still establish test relevance
and the original task's full acceptance scope.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
import os
from pathlib import Path
import re
import sys
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from sofia.verify.v18_gate4 import gate4_snapshot
from sofia.verify.v18_roadmap import RoadmapIntegrityError, LEDGER_RELATIVE

_REPO = "Crazysodaman/SofiaAdaLyra"
_TEST = re.compile(r"^test/test_[A-Za-z0-9_./-]+\\.py(?:::[A-Za-z0-9_\\[\\]-]+)?$")
_SHA = re.compile(r"^[0-9a-f]{40}$")
_EXTRA = "docs/development/v18-supplemental-gate4-proofs.json"


def gate4_ci_claims(root: Path) -> tuple[tuple[str, dict], ...]:
    """Read the canonical original and separately governed supplemental proofs."""
    gate4_snapshot(root)  # validates all original IDs and content-bound proofs
    ledger = json.loads((root / LEDGER_RELATIVE).read_text(encoding="utf-8"))
    extra = json.loads((root / _EXTRA).read_text(encoding="utf-8"))
    claims = []
    for task in ledger["tasks"]:
        proofs = task.get("gate4_proofs", [])
        if len(proofs) == 4:
            claims.append((task["id"], proofs[-1]))
    for task_id, proofs in extra["tasks"].items():
        if len(proofs) == 4:
            claims.append((task_id, proofs[-1]))
    return tuple(claims)


def validate_ci_run(
    task_id: str, proof: dict, run: dict, *, repository: str = _REPO,
) -> None:
    """A claimed successful run must exist and belong to the exact SHA/repo."""
    ci = proof.get("ci", {})
    if not isinstance(ci, dict):
        raise RoadmapIntegrityError(f"{task_id}: missing CI claim")
    run_id = ci.get("run_id")
    revision = proof.get("revision")
    if (
        type(run_id) is not int or run_id <= 0
        or not isinstance(revision, str) or not _SHA.fullmatch(revision)
    ):
        raise RoadmapIntegrityError(f"{task_id}: invalid run ID or revision")
    if (
        type(run) is not dict
        or run.get("id") != run_id
        or run.get("status") != "completed"
        or run.get("conclusion") != "success"
        or run.get("head_sha") != revision
        or run.get("head_branch") != "main"
        or (run.get("repository") or {}).get("full_name") != repository
        or run.get("event") not in {"push", "workflow_dispatch"}
        or not isinstance(run.get("path"), str)
        or not run["path"].startswith(".github/workflows/")
        or not run["path"].endswith((".yml", ".yaml"))
    ):
        raise RoadmapIntegrityError(
            f"{task_id}: GitHub run contradicts recorded SHA or successful CI"
        )
    # This checks well-formed source test selectors, NOT whether the workflow
    # actually executed every selector. That is a separate human review gate.
    ids = ci.get("test_ids", [])
    if not isinstance(ids, list) or not ids:
        raise RoadmapIntegrityError(f"{task_id}: missing task test selectors")
    for selector in ids:
        if (
            not isinstance(selector, str)
            or not _TEST.fullmatch(selector)
            or ".." in Path(selector.split("::", 1)[0]).parts
        ):
            raise RoadmapIntegrityError(
                f"{task_id}: unsafe or unsupported task test selector"
            )


def github_run_loader(token: str, repository: str = _REPO) -> Callable[[int], dict]:
    """Explicitly bounded authenticated GitHub Actions lookup, no host changes."""
    if not isinstance(token, str) or not token.strip():
        raise RoadmapIntegrityError("GITHUB_TOKEN required for CI receipt authentication")
    if repository != _REPO:
        raise RoadmapIntegrityError("unexpected GitHub evidence repository")

    def load(run_id: int) -> dict:
        url = f"https://api.github.com/repos/{repository}/actions/runs/{run_id}"
        request = Request(url, headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "sofia-v18-ci-evidence",
        })
        try:
            with urlopen(request, timeout=20) as response:
                payload = response.read(512_001)
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise RoadmapIntegrityError(
                f"GitHub CI receipt unavailable for run {run_id}: "
                f"{type(exc).__name__}"
            ) from exc
        if len(payload) > 512_000:
            raise RoadmapIntegrityError("GitHub CI receipt exceeds size bound")
        try:
            value = json.loads(payload)
        except (ValueError, UnicodeError) as exc:
            raise RoadmapIntegrityError("GitHub CI receipt is invalid JSON") from exc
        if not isinstance(value, dict):
            raise RoadmapIntegrityError("GitHub CI receipt must be a JSON object")
        return value

    return load


def audit_ci_receipts(
    root: Path,
    *,
    loader: Callable[[int], dict],
    repository: str = _REPO,
) -> dict:
    """Verify recorded Gate-4 source claims against actual run metadata."""
    claims = gate4_ci_claims(root)
    by_run = defaultdict(list)
    for task_id, proof in claims:
        by_run[proof["ci"]["run_id"]].append((task_id, proof))
    # Bound network work even if ledger receives a pathological number of
    # distinct references. Reviewed batching can raise this later if needed.
    if len(by_run) > 200:
        raise RoadmapIntegrityError("too many independent CI runs for one audit")
    for run_id, groups in by_run.items():
        run = loader(run_id)
        for task_id, proof in groups:
            validate_ci_run(task_id, proof, run, repository=repository)
    return {
        "schema": "sofia.v18-ci-remote-receipts-v1",
        "authenticated_run_ids": sorted(by_run),
        "authenticated_task_ids": sorted(task_id for task_id, _ in claims),
        "authenticated_claims": len(claims),
        "note": "GitHub run identity, revision and conclusion validated. "
                "Test-selector relevance, host trials and owner approval still "
                "require independent review.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        loader = github_run_loader(os.environ.get("GITHUB_TOKEN", ""))
        result = audit_ci_receipts(args.repo.resolve(strict=True), loader=loader)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\\n", encoding="utf-8")
        print(
            f"authenticated_ci_runs={len(result['authenticated_run_ids'])} "
            f"task_claims={result['authenticated_claims']}"
        )
        return 0
    except (RoadmapIntegrityError, OSError, ValueError) as exc:
        print(f"CI receipt authentication refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
