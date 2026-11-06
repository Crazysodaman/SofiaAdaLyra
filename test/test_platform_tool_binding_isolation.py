"""Platform tool descriptions must not import the Core dispatcher."""
import os
from pathlib import Path
import subprocess
import sys

import pytest

from test.test_platform_import_isolation import _BLOCK_CORE


@pytest.mark.parametrize("module", [
    "sofia.platform.capability.catalog",
    "sofia.platform.filesystem.change_capability",
    "sofia.platform.net.capability",
    "sofia.platform.machine.capability",
    "sofia.platform.distributed.capability",
    "sofia.platform.ops.capability",
    "sofia.platform.dev.capability",
    "sofia.platform.safe.permission_capability",
])
def test_platform_tool_surface_imports_without_core(module):
    root = Path(__file__).resolve().parents[1]
    environment = dict(os.environ, PYTHONPATH=str(root / "src"))
    result = subprocess.run(
        [sys.executable, "-c", _BLOCK_CORE + f"import {module}\n"],
        cwd=root, env=environment, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr


def test_legacy_binding_import_is_same_sdk_class():
    from sofia.core.cognition.tools import CognitiveToolBinding as legacy
    from sofia.sdk import CognitiveToolBinding

    assert legacy is CognitiveToolBinding


def test_core_free_factories_construct_inert_bindings():
    root = Path(__file__).resolve().parents[1]
    code = _BLOCK_CORE + '''
from sofia.sdk.tool_binding import CognitiveToolBinding
from sofia.platform.capability.catalog import create_tool_catalog_binding
from sofia.platform.machine.capability import create_machine_tool_bindings
from sofia.platform.ops.capability import create_ops_tool_bindings
bindings = (create_tool_catalog_binding(), *create_machine_tool_bindings(), *create_ops_tool_bindings())
assert len(bindings) > 10
assert all(isinstance(binding, CognitiveToolBinding) for binding in bindings)
assert not [name for name in sys.modules if name == 'sofia.core' or name.startswith('sofia.core.')]
'''
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=root,
        env=dict(os.environ, PYTHONPATH=str(root / "src")),
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr


def test_independent_adapters_do_not_import_unrelated_core_integration():
    root = Path(__file__).resolve().parents[1]
    code = _BLOCK_CORE + '''
from sofia.modules.integrations import HyperVAdapter
from sofia.modules.integrations.hyperv import HyperVAdapter as direct
from sofia.modules.inference.endpoint import configured_ollama_endpoint
assert HyperVAdapter is direct
assert not [name for name in sys.modules if name == 'sofia.core' or name.startswith('sofia.core.')]
'''
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=root,
        env=dict(os.environ, PYTHONPATH=str(root / "src")),
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
