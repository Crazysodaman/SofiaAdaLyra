"""Explicit operator CLI for unsigned 47-module release preparation ONLY.

Never signs, installs, registers factories, authorizes, or activates components.
Policy JSON is external; no project secrets are loaded or inferred.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import json

from .optional_release_packages import (
    OwnerReviewedReleasePolicy, prepare_release_batch, materialize_unsigned_batch,
)


def _policy(path: Path) -> OwnerReviewedReleasePolicy:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 256 * 1024:
        raise ValueError("policy must be a bounded, regular local file")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or set(data) != {
        "package_ids", "capability_schema_refs", "publisher", "trust_ref",
        "platform_api_minimum", "supported_os_arch", "isolation_profile",
        "allowed_host_classes", "data_classes", "review_receipt",
    }:
        raise ValueError("policy requires precisely the reviewed contract fields")
    return OwnerReviewedReleasePolicy(
        package_ids=data["package_ids"],
        capability_schema_refs=data["capability_schema_refs"],
        publisher=data["publisher"], trust_ref=data["trust_ref"],
        platform_api_minimum=data["platform_api_minimum"],
        supported_os_arch=tuple(data["supported_os_arch"]),
        isolation_profile=data["isolation_profile"],
        allowed_host_classes=tuple(data["allowed_host_classes"]),
        data_classes={name: tuple(classes) for name, classes in data["data_classes"].items()},
        review_receipt=data["review_receipt"],
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True,
                        help="External caller-supplied SHA256; not a Git verification receipt")
    parser.add_argument("--output", type=Path, required=True,
                        help="New, NONEXISTENT directory for unsigned review bundles")
    args = parser.parse_args(argv)
    drafts = prepare_release_batch(args.repo_root, policy=_policy(args.policy),
                                   source_revision_sha=args.source_sha256)
    path = materialize_unsigned_batch(drafts, repo_root=args.repo_root,
                                      output_root=args.output)
    print(f"Unsigned review only: {len(drafts)} drafts at {path}")
    print("No signatures, approved factories, lifecycle records, or release claims created")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
