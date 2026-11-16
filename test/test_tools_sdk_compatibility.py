from __future__ import annotations

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tomllib

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "tools" / "aegis_sdk_compatibility.py"
SDK_DIR = ROOT / "src" / "sofia" / "sdk"


def _load_tool():
    spec = importlib.util.spec_from_file_location(
        "aegis_sdk_compatibility_tool", TOOL_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


TOOL = _load_tool()


@pytest.fixture(scope="module")
def inventory() -> dict[str, object]:
    return TOOL.build_inventory(ROOT)


def _modules(inventory: dict[str, object]) -> dict[str, dict[str, object]]:
    return {
        module["module"]: module
        for module in inventory["python"]["modules"]  # type: ignore[index]
    }


def _expected_modules() -> set[str]:
    return {
        "sofia.sdk" if path.name == "__init__.py" else f"sofia.sdk.{path.stem}"
        for path in SDK_DIR.glob("*.py")
    }


def test_inventory_schema_and_no_compatibility_claim(
    inventory: dict[str, object],
) -> None:
    assert inventory["schema"] == "aegis.sdk.compatibility-inventory.v1"
    assert inventory["inventory_only"] is True
    assert inventory["compatibility_claim"] is False
    assert inventory["unreviewed"]
    json.dumps(inventory)


def test_inventory_uses_exact_git_head(inventory: dict[str, object]) -> None:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert inventory["source"]["commit"] == completed.stdout.strip()


def test_inventory_includes_every_sdk_module_once(
    inventory: dict[str, object],
) -> None:
    modules = _modules(inventory)
    assert set(modules) == _expected_modules()
    assert "sofia.sdk.compatibility" in modules
    assert len(modules) == len(list(SDK_DIR.glob("*.py")))
    for record in modules.values():
        assert record["parse_error"] is None
        path = ROOT / record["path"]
        assert path.is_file()
        assert record["sha256"] == sha256(path.read_bytes()).hexdigest()


def test_inventory_records_versions_and_protocol_separately(
    inventory: dict[str, object],
) -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert inventory["python"]["distribution"] == {
        "name": project["project"]["name"],
        "version": project["project"]["version"],
        "source": "pyproject.toml",
    }
    assert inventory["python"]["distribution"]["version"] == "0.1.0"
    assert inventory["python"]["protocol_version"] == "1.0"
    assert inventory["python"]["wire_supported_protocol"] == "1.0"
    assert inventory["rust"]["supported_protocol"] == "1.0"
    crates = {crate["crate"]: crate for crate in inventory["rust"]["crates"]}
    for name in (
        "sofia-contracts",
        "sofia-core-link",
        "sofia-platform-lifecycle",
        "sofia-ui-broker",
    ):
        assert crates[name]["version"] == "0.1.0"
        assert crates[name]["sdk_facing"] is True
        assert crates[name]["file_hashes"]
    assert inventory["rust"]["sdk_facing_crates"] == sorted(crates)


def test_inventory_records_exports_consumers_and_protocol_constants(
    inventory: dict[str, object],
) -> None:
    modules = _modules(inventory)
    contracts = modules["sofia.sdk.contracts"]
    assert "ProtocolVersion" in contracts["classes"]
    assert "ProtocolVersionRange" in contracts["classes"]
    assert "negotiate_protocol" in contracts["functions"]
    assert any(
        constant["name"] == "SDK_PROTOCOL_VERSION"
        and constant["value"] == "1.0"
        for constant in contracts["protocol_constants"]
    )
    wire = modules["sofia.sdk.contract_wire"]
    assert any(
        constant["name"] == "SUPPORTED_PROTOCOL"
        and constant["value"] == "1.0"
        for constant in wire["protocol_constants"]
    )
    assert "src/sofia/sdk/core_definition.py" in contracts["import_consumers"]
    assert "src/sofia/sdk/core_link.py" in contracts["import_consumers"]
    package = modules["sofia.sdk"]
    assert "ProtocolVersion" in package["exports"]
    assert "SDK_PROTOCOL_VERSION" in package["exports"]


def test_unreviewed_covers_every_sdk_module_and_sdk_facing_crate(
    inventory: dict[str, object],
) -> None:
    unreviewed = set(inventory["unreviewed"])
    assert {
        record["path"] for record in inventory["python"]["modules"]
    }.issubset(unreviewed)
    for crate in inventory["rust"]["crates"]:
        if crate["sdk_facing"]:
            assert set(crate["file_hashes"]).issubset(unreviewed)


def test_render_is_deterministic(inventory: dict[str, object]) -> None:
    assert TOOL.render(inventory) == TOOL.render(
        TOOL.build_inventory(ROOT, source_commit=inventory["source"]["commit"])
    )


def test_file_hash_tamper_detection(tmp_path: Path) -> None:
    source = tmp_path / "checkout"
    shutil.copytree(SDK_DIR, source / "src" / "sofia" / "sdk")
    shutil.copy2(ROOT / "pyproject.toml", source / "pyproject.toml")
    commit = "0" * 40
    first = TOOL.build_inventory(source, source_commit=commit)
    first_modules = _modules(first)
    target = source / "src" / "sofia" / "sdk" / "contracts.py"
    first_hash = first_modules["sofia.sdk.contracts"]["sha256"]

    target.write_text(
        target.read_text(encoding="utf-8") + "\n# unreviewed tamper\n",
        encoding="utf-8",
    )
    second = TOOL.build_inventory(source, source_commit=commit)
    second_modules = _modules(second)

    assert first["source"]["commit"] == second["source"]["commit"] == commit
    assert first_hash != second_modules["sofia.sdk.contracts"]["sha256"]
    assert (
        second_modules["sofia.sdk.contracts"]["sha256"]
        == sha256(target.read_bytes()).hexdigest()
    )
