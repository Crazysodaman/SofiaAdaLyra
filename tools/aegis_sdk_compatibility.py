"""Deterministic SDK compatibility *inventory*, never a compatibility claim.

The report pins the exact ``git rev-parse HEAD`` and hashes every Python SDK
module and Rust SDK-facing crate at the current checkout.  It lists exports,
classes, functions, protocol constants and import consumers so reviewers can
start from observed source instead of an assumed package version.

It deliberately does not import the SDK, Core or Platform and does not run any
component.  Missing review provenance is reported as ``unreviewed``.
"""
from __future__ import annotations

import argparse
import ast
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import sys
import tomllib


SCHEMA = "aegis.sdk.compatibility-inventory.v1"
SDK_DIR = Path("src/sofia/sdk")
RUST_CRATE_DIR = Path("rust/crates")
SDK_FACING_CRATES = (
    "sofia-contracts",
    "sofia-core-link",
    "sofia-platform-lifecycle",
    "sofia-ui-broker",
)
CONSUMER_DIRS = ("src", "test", "tools", "examples", "scripts")
SKIP_DIRS = {
    ".git", "__pycache__", ".venv", "venv", "target", "node_modules",
    ".mypy_cache", ".pytest_cache", ".ruff_cache",
}
_RUST_CONSTANT = re.compile(
    r"pub\s+const\s+([A-Z][A-Z0-9_]*)\s*:\s*([^=;]+?)\s*=\s*([^;]+);"
)


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _display(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _parse(path: Path) -> tuple[ast.Module | None, str | None]:
    try:
        return ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path)), None
    except (OSError, SyntaxError, UnicodeError) as exc:
        return None, f"{type(exc).__name__}: {exc}"


def _literal(node: ast.AST, environment: dict[str, object]) -> object:
    if isinstance(node, ast.Constant) and (
        node.value is None or type(node.value) in {str, int, bool}
    ):
        return node.value
    if isinstance(node, (ast.Tuple, ast.List)):
        return [_literal(value, environment) for value in node.elts]
    if isinstance(node, ast.Name) and node.id in environment:
        return environment[node.id]
    if isinstance(node, ast.Dict):
        result: dict[object, object] = {}
        for key, value in zip(node.keys, node.values):
            if key is None:
                expanded = _literal(value, environment)
                if not isinstance(expanded, dict):
                    raise ValueError("unsupported dictionary expansion")
                result.update(expanded)
            else:
                result[_literal(key, environment)] = _literal(value, environment)
        return result
    if isinstance(node, ast.DictComp):
        result = {}
        for scope in _comprehension_scopes(node.generators, environment):
            result[_literal(node.key, scope)] = _literal(node.value, scope)
        return result
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"list", "tuple", "frozenset"}
        and len(node.args) == 1
        and not node.keywords
    ):
        value = _literal(node.args[0], environment)
        if isinstance(value, dict):
            return list(value)
        if not isinstance(value, (list, tuple, set, frozenset)):
            raise ValueError("unsupported conversion")
        return list(value)
    raise ValueError("unsupported static expression")


def _comprehension_scopes(
    generators: list[ast.comprehension], environment: dict[str, object]
) -> list[dict[str, object]]:
    for generator in generators:
        if generator.ifs or not isinstance(generator.target, ast.Name):
            raise ValueError("unsupported comprehension")
    scopes = [dict(environment)]
    for generator in generators:
        expanded: list[dict[str, object]] = []
        for scope in scopes:
            values = _literal(generator.iter, scope)
            if not isinstance(values, (list, tuple, set, frozenset)):
                raise ValueError("unsupported comprehension iterable")
            for value in values:
                child = dict(scope)
                child[generator.target.id] = value
                expanded.append(child)
        scopes = expanded
    return scopes


def _assignment_nodes(tree: ast.Module):
    for node in tree.body:
        if isinstance(node, ast.Assign):
            yield from ((target, node.value, node.lineno) for target in node.targets)
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            yield node.target, node.value, node.lineno


def _surface(tree: ast.Module | None) -> dict[str, object]:
    if tree is None:
        return {
            "classes": [], "functions": [], "constants": [], "exports": [],
            "protocol_constants": [], "imports": [],
        }
    environment: dict[str, object] = {}
    constants: list[str] = []
    protocol_constants: list[dict[str, object]] = []
    for target, value, line in _assignment_nodes(tree):
        if isinstance(target, ast.Name):
            try:
                environment[target.id] = _literal(value, environment)
            except ValueError:
                pass
            if target.id.isupper() and not target.id.startswith("_"):
                constants.append(target.id)
            if "PROTOCOL" in target.id or target.id == "SDK_PROTOCOL_VERSION":
                constant: object = None
                try:
                    constant = _literal(value, environment)
                except ValueError:
                    if (
                        isinstance(value, ast.Call)
                        and isinstance(value.func, ast.Name)
                        and value.func.id == "ProtocolVersion"
                        and len(value.args) >= 2
                        and all(
                            isinstance(argument, ast.Constant)
                            and type(argument.value) is int
                            for argument in value.args[:2]
                        )
                    ):
                        constant = f"{value.args[0].value}.{value.args[1].value}"
                if isinstance(constant, (str, int)):
                    protocol_constants.append({
                        "name": target.id, "line": line, "value": constant,
                    })
    classes = sorted(
        node.name for node in tree.body if isinstance(node, ast.ClassDef)
    )
    functions = sorted(
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    )
    declared = environment.get("__all__")
    if isinstance(declared, list) and all(isinstance(item, str) for item in declared):
        exports = list(declared)
    else:
        exports = sorted(set(
            name for name in classes + functions + constants
            if not name.startswith("_")
        ))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add("." * node.level + (node.module or ""))
    return {
        "classes": classes,
        "functions": functions,
        "constants": sorted(set(constants)),
        "exports": exports,
        "protocol_constants": sorted(
            protocol_constants, key=lambda item: (item["line"], item["name"])
        ),
        "imports": sorted(imports),
    }


def _module_name(path: Path, root: Path) -> str:
    source_root = root / "src"
    try:
        relative = path.relative_to(source_root)
    except ValueError:
        relative = path.relative_to(root)
    parts = list(relative.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _resolve_import_from(
    consumer: Path, root: Path, node: ast.ImportFrom
) -> str:
    if node.level == 0:
        return node.module or ""
    module = _module_name(consumer, root)
    package = module if consumer.name == "__init__.py" else module.rpartition(".")[0]
    parts = package.split(".") if package else []
    if node.level > 1:
        parts = parts[: max(0, len(parts) - (node.level - 1))]
    base = ".".join(parts)
    if node.module:
        base = f"{base}.{node.module}" if base else node.module
    return base


def _python_files(root: Path) -> list[Path]:
    paths: list[Path] = []
    for directory in CONSUMER_DIRS:
        base = root / directory
        if not base.is_dir():
            continue
        for path in base.rglob("*.py"):
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            paths.append(path)
    return sorted(set(paths))


def _import_consumers(
    root: Path, modules: dict[str, Path]
) -> dict[str, list[str]]:
    consumers: dict[str, set[str]] = {name: set() for name in modules}
    for path in _python_files(root):
        tree, _ = _parse(path)
        if tree is None:
            continue
        display = _display(root, path)
        for node in ast.walk(tree):
            targets: set[str] = set()
            if isinstance(node, ast.Import):
                targets.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                base = _resolve_import_from(path, root, node)
                if base in modules:
                    targets.add(base)
                if base == "sofia.sdk":
                    targets.update(
                        f"sofia.sdk.{alias.name}" for alias in node.names
                    )
            for target in targets:
                if target in consumers and modules[target] != path:
                    consumers[target].add(display)
    return {name: sorted(files) for name, files in consumers.items()}


def _python_inventory(root: Path) -> dict[str, object]:
    sdk_directory = root / SDK_DIR
    paths = sorted(sdk_directory.glob("*.py")) if sdk_directory.is_dir() else []
    modules = {_module_name(path, root): path for path in paths}
    consumers = _import_consumers(root, modules)
    records: list[dict[str, object]] = []
    for path in paths:
        module_name = _module_name(path, root)
        tree, error = _parse(path)
        surface = _surface(tree)
        record = {
            "module": module_name,
            "path": _display(root, path),
            "sha256": _sha256(path),
            "bytes": path.stat().st_size,
            "parse_error": error,
            **surface,
            "import_consumers": consumers.get(module_name, []),
        }
        records.append(record)
    return {
        "protocol_version": _find_protocol(records, "SDK_PROTOCOL_VERSION"),
        "wire_supported_protocol": _find_protocol(records, "SUPPORTED_PROTOCOL"),
        "modules": records,
    }


def _find_protocol(records: list[dict[str, object]], name: str) -> str | None:
    for record in records:
        for constant in record["protocol_constants"]:  # type: ignore[index]
            if constant["name"] == name:
                value = constant["value"]
                return str(value)
    return None


def _rust_inventory(root: Path) -> dict[str, object]:
    crate_directory = root / RUST_CRATE_DIR
    crates: list[dict[str, object]] = []
    if crate_directory.is_dir():
        for directory in sorted(
            path for path in crate_directory.iterdir() if path.is_dir()
        ):
            manifest = directory / "Cargo.toml"
            if not manifest.is_file():
                continue
            try:
                package = tomllib.loads(
                    manifest.read_text(encoding="utf-8")
                ).get("package", {})
            except (OSError, tomllib.TOMLDecodeError, UnicodeError):
                package = {}
            files = sorted(
                path
                for path in directory.rglob("*")
                if path.is_file()
                and path.suffix in {".rs", ".toml"}
                and "target" not in path.parts
            )
            constants: list[dict[str, object]] = []
            for source in files:
                if source.suffix != ".rs":
                    continue
                try:
                    text = source.read_text(encoding="utf-8-sig")
                except (OSError, UnicodeError):
                    continue
                for match in _RUST_CONSTANT.finditer(text):
                    name, _, value = match.groups()
                    if "PROTOCOL" in name:
                        constants.append({
                            "name": name,
                            "path": _display(root, source),
                            "value": value.strip(),
                        })
            crates.append({
                "crate": package.get("name", directory.name),
                "path": _display(root, directory),
                "version": package.get("version"),
                "sdk_facing": directory.name in SDK_FACING_CRATES,
                "file_hashes": {
                    _display(root, path): _sha256(path) for path in files
                },
                "protocol_constants": sorted(
                    constants, key=lambda item: (item["path"], item["name"])
                ),
            })
    return {
        "supported_protocol": _rust_protocol(crates),
        "sdk_facing_crates": sorted(
            crate["crate"] for crate in crates if crate["sdk_facing"]
        ),
        "crates": crates,
    }


def _rust_protocol(crates: list[dict[str, object]]) -> str | None:
    for crate in crates:
        if crate["crate"] != "sofia-contracts":
            continue
        for constant in crate["protocol_constants"]:  # type: ignore[index]
            if constant["name"] == "SUPPORTED_PROTOCOL":
                return constant["value"].strip().strip('"')
    return None


def _distribution(root: Path) -> dict[str, object]:
    manifest = root / "pyproject.toml"
    if not manifest.is_file():
        return {"name": None, "version": None, "source": "pyproject.toml"}
    try:
        project = tomllib.loads(
            manifest.read_text(encoding="utf-8")
        ).get("project", {})
    except (OSError, tomllib.TOMLDecodeError, UnicodeError):
        project = {}
    return {
        "name": project.get("name"),
        "version": project.get("version"),
        "source": "pyproject.toml",
    }


def _review_hashes(root: Path) -> dict[str, str]:
    path = root / "contracts" / "sdk" / "reviewed.json"
    if not path.is_file():
        return {}
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return {}
    files = document.get("files") if isinstance(document, dict) else None
    if not isinstance(files, dict):
        return {}
    return {
        name: digest for name, digest in files.items()
        if isinstance(name, str) and isinstance(digest, str)
    }


def _unreviewed(
    python: dict[str, object], rust: dict[str, object], reviewed: dict[str, str]
) -> list[str]:
    unchecked: dict[str, str] = {}
    for module in python["modules"]:  # type: ignore[index]
        unchecked[module["path"]] = module["sha256"]
    for crate in rust["crates"]:  # type: ignore[index]
        if crate["sdk_facing"]:
            unchecked.update(crate["file_hashes"])
    return sorted(
        path for path, digest in unchecked.items()
        if reviewed.get(path) != digest
    )


def _git_head(root: Path) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def build_inventory(
    root: Path | str | None = None, *, source_commit: str | None = None
) -> dict[str, object]:
    """Build the deterministic inventory for ``root`` at one source commit."""
    root = Path(root).resolve() if root is not None else Path(__file__).resolve().parents[1]
    commit = source_commit if source_commit is not None else _git_head(root)
    python = _python_inventory(root)
    rust = _rust_inventory(root)
    reviewed = _review_hashes(root)
    return {
        "schema": SCHEMA,
        "inventory_only": True,
        "compatibility_claim": False,
        "source": {"commit": commit},
        "python": {
            "distribution": _distribution(root),
            **python,
        },
        "rust": rust,
        "unreviewed": _unreviewed(python, rust, reviewed),
    }


def render(inventory: dict[str, object]) -> str:
    """Render stable JSON so repeated observations of one tree are identical."""
    return json.dumps(inventory, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1],
        help="repository checkout to inventory",
    )
    parser.add_argument("--source-commit", help="override git rev-parse HEAD")
    parser.add_argument("--output", type=Path, help="write JSON instead of stdout")
    arguments = parser.parse_args(argv)
    text = render(
        build_inventory(
            arguments.root, source_commit=arguments.source_commit
        )
    )
    if arguments.output:
        arguments.output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
