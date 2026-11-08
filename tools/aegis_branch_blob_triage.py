#!/usr/bin/env python3
"""Read-only Project Aegis main-only branch provenance audit.

Every remote branch is classified using actual Git ancestry and per-file
blob identity against current main, never commit counts alone.
This tool NEVER merges, resets, stashes, signs, deletes or pushes anything.
A suggested disposition is NOT security review or integration acceptance.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess
import sys


def git(*args: str, check: bool = True) -> str:
    process = subprocess.run(
        ["git", *args], capture_output=True, text=True, encoding="utf-8",
        errors="replace", check=False,
    )
    if check and process.returncode:
        raise RuntimeError(
            "git " + " ".join(args[:4]) + ": " + process.stderr.strip()[:400]
        )
    return process.stdout.strip() if process.returncode == 0 else ""


def blob(ref: str, path: str) -> str | None:
    result = git("rev-parse", "--verify", "--quiet", f"{ref}:{path}", check=False)
    return result or None


def status_rows(base: str, source: str) -> list[tuple[str, str]]:
    # No rename detection: each exact file must be assessed, not guessed from
    # similarity. Avoid parsing human-readable whitespace path lists.
    data = subprocess.run(
        ["git", "diff", "--no-renames", "--name-status", "-z",
         f"{base}..{source}"],
        capture_output=True, check=True,
    ).stdout.split(b"\x00")
    parts = [piece.decode("utf-8", "replace") for piece in data if piece]
    if len(parts) % 2:
        raise RuntimeError("unparseable NUL-delimited Git diff status")
    return list(zip(parts[::2], parts[1::2]))


def audit_branch(main_ref: str, branch: str) -> dict:
    record: dict = {
        "ref": branch, "head_sha": git("rev-parse", branch),
        "classification": "REVIEW_UNCLASSIFIED",
        "source_changes": 0, "matching_blobs": 0,
        "additions": [], "collisions": [], "deletions": [],
    }
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", branch, main_ref],
        check=False,
    ).returncode == 0:
        record["classification"] = "IN_MAIN_ANCESTOR"
        return record

    base = git("merge-base", branch, main_ref, check=False)
    if not base:
        record["classification"] = "HOLD_UNRELATED_HISTORY"
        return record

    changes = status_rows(base, branch)
    record["merge_base_sha"] = base
    record["source_changes"] = len(changes)
    for state, path in changes:
        branch_blob = blob(branch, path)
        main_blob = blob(main_ref, path)
        if branch_blob is not None and branch_blob == main_blob:
            record["matching_blobs"] += 1
        elif branch_blob is None:
            record["deletions"].append(path)
        elif main_blob is None:
            record["additions"].append(path)
        else:
            record["collisions"].append(path)

    if record["deletions"]:
        record["classification"] = "HOLD_DELETION_CONFLICT"
    elif record["collisions"]:
        record["classification"] = "REVIEW_COLLISION"
    elif record["additions"]:
        only_tests_docs = all(
            path.startswith(("docs/", "test/", ".github/workflows/"))
            or path in {"README.md", "ROADMAP.md"}
            for path in record["additions"]
        )
        record["classification"] = (
            "REVIEW_TEST_OR_DOCS" if only_tests_docs else "REVIEW_ADDITIVE"
        )
    else:
        record["classification"] = "IN_MAIN_BY_BLOB_CONTENT"
    # A divergence is not permission to override any canonical implementation.
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--main", default="refs/remotes/origin/main")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--remote", default="origin")
    args = parser.parse_args()

    main_sha = git("rev-parse", "--verify", args.main)
    prefix = f"refs/remotes/{args.remote}/"
    refs = git("for-each-ref", "--format=%(refname)", prefix)
    branches = sorted(
        ref for ref in refs.splitlines()
        if ref.startswith(prefix)
        and ref not in {prefix + "HEAD", prefix + "main"}
        and not ref.startswith(prefix + "backup/")
    )
    if not branches:
        raise RuntimeError("No remote branches enumerated; fetch --all first")
    results = [audit_branch(args.main, ref) for ref in branches]
    counts = dict(sorted(Counter(x["classification"] for x in results).items()))
    report = {
        "schema": "aegis.git.branch-blob-triage.v1",
        "main_sha": main_sha,
        "remote": args.remote,
        "branch_count": len(results),
        "classification_counts": counts,
        "notes": (
            "Read-only exact-blob and ancestry triage, NOT merge/release "
            "acceptance. Review source authority and running tests before "
            "importing any branch file. Preserve historical refs."
        ),
        "branches": results,
    }
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    print(
        f"Audited {len(results)} remote refs against {main_sha[:12]}: "
        + ", ".join(f"{name}={count}" for name, count in counts.items()),
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
