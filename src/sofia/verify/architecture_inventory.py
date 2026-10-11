"""Read-only, non-executing audit of production source ownership and duplication.

Forensic hints only. This scanner does not import project modules, call a
provider, invoke a tool, touch sofia.db, run tests, or delete source files.
Duplicate-looking ASTs are *candidates* requiring a caller and ABI audit.
"""
from __future__ import annotations

import argparse
import ast
from collections import defaultdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys


# Paths are existing canonical implementation owners, NOT evidence that they
# were ever exercised through the actual production bootstrap.
OWNERS: dict[str, str] = {
    "application": "src/sofia/application/bootstrap.py",
    "turn_kernel": "src/sofia/cognition/v2/kernel.py",
    "conversation": "src/sofia/conversation/store.py",
    "social_scope": "src/sofia/social/store.py",
    "memory": "src/sofia/memory/system.py",
    "memory_review": "src/sofia/application/memory_review.py",
    "emotion": "src/sofia/emotion/journal.py",
    "relationship": "src/sofia/rel/store.py",
    "goal": "src/sofia/goals/service.py",
    "life": "src/sofia/life/coordinator.py",
    "run": "src/sofia/run/work.py",
    "safe": "src/sofia/safe/permissions.py",
    "act": "src/sofia/application/act_service.py",
    "neuro": "src/sofia/neuro/runtime.py",
    "world": "src/sofia/interaction/world_store.py",
    "creative": "src/sofia/creative/service.py",
    "fleet": "src/sofia/distributed/state_paths.py",
    "state": "src/sofia/state/sqlite_plane.py",
    "backup": "src/sofia/ops/backup.py",
    "release": "src/sofia/dev/release_cli.py",
    "verify": "src/sofia/verify/gate.py",
}


def _body_fingerprint(node: ast.AST) -> str | None:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return None
    statements = list(node.body)
    if statements and isinstance(statements[0], ast.Expr):
        if isinstance(statements[0].value, ast.Constant):
            if isinstance(statements[0].value.value, str):
                statements.pop(0)
    if not statements:
        return None
    normalized = ast.dump(
        ast.Module(body=statements, type_ignores=[]),
        annotate_fields=True, include_attributes=False,
    )
    if len(normalized) < 240:
        return None  # ignore trivial boilerplate
    return sha256(normalized.encode("utf-8")).hexdigest()


def source_architecture_inventory(root: Path) -> dict[str, object]:
    root = root.resolve(strict=True)
    directory = root / "src" / "sofia"
    if not directory.is_dir():
        raise ValueError("requested root is not a Sofía source checkout")
    owners = {
        name: {"path": path, "source_present": (root / path).is_file()}
        for name, path in OWNERS.items()
    }
    module_count = 0
    syntax_errors: list[dict[str, str]] = []
    fingerprints: dict[str, list[str]] = defaultdict(list)
    imports: dict[str, set[str]] = defaultdict(set)
    for file in sorted(directory.rglob("*.py")):
        relative = file.relative_to(root).as_posix()
        try:
            tree = ast.parse(file.read_text(encoding="utf-8-sig"), filename=relative)
        except (SyntaxError, UnicodeError) as exc:
            syntax_errors.append({"path": relative, "error": type(exc).__name__})
            continue
        module_count += 1
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("sofia."):
                        imports[alias.name].add(relative)
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.startswith("sofia."):
                    imports[node.module].add(relative)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fingerprint = _body_fingerprint(node)
                if fingerprint:
                    fingerprints[fingerprint].append(f"{relative}:{node.lineno}:{node.name}")
    candidates = tuple(
        {"fingerprint": digest, "definitions": sorted(paths)}
        for digest, paths in sorted(fingerprints.items())
        if len({part.split(":")[0] for part in paths}) > 1
    )
    return {
        "schema": "sofia.static-ownership-audit-v1",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "source_root": str(directory),
        "mode": "static_read_only_no_imports_no_tests",
        "owners": owners,
        "source_module_count": module_count,
        "parse_errors": syntax_errors,
        "possible_duplicate_function_bodies": candidates,
        "imported_modules": {name: len(sites) for name, sites in sorted(imports.items())},
        "warnings": (
            "path presence is not production reachability or live acceptance",
            "same AST body is not evidence either implementation can be deleted",
            "dynamic imports, service entrypoints and serialized compatibility are not fully resolved",
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        report = source_architecture_inventory(args.root)
    except (OSError, ValueError) as exc:
        print(f"architecture audit unavailable: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return 0 if not report["parse_errors"] and all(
        entry["source_present"] for entry in report["owners"].values()
    ) else 2


if __name__ == "__main__":
    raise SystemExit(main())
