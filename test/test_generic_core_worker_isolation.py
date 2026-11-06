"""Generic cognition workers import without a personal Core package."""
import os
from pathlib import Path
import subprocess
import sys

from test.test_platform_import_isolation import _BLOCK_CORE


def test_core_worker_module_import_does_not_require_personal_core():
    root = Path(__file__).resolve().parents[1]
    code = _BLOCK_CORE + (
        'import sys\n'
        'from sofia.platform.core_worker import CoreWorkerController, CoreEngineProcessSpec\n'
        'assert CoreEngineProcessSpec("test").kind == "test"\n'
        'assert not any(n == "sofia.core" or n.startswith("sofia.core.") for n in sys.modules)\n'
    )
    result = subprocess.run(
        [sys.executable, '-c', code], cwd=root,
        env={**os.environ, 'PYTHONPATH': str(root / 'src')},
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr


def test_legacy_engine_imports_preserve_class_identity():
    from sofia.core.cognition import engine, provider, llm_engine, test_engine
    from sofia.sdk import cognition_engine
    from sofia.platform.core_worker import engines

    assert engine.CognitiveEngine is cognition_engine.CognitiveEngine
    assert engine.CognitiveEngineError is cognition_engine.CognitiveEngineError
    assert provider.LLMProvider is cognition_engine.LLMProvider
    assert provider.LLMProviderError is cognition_engine.LLMProviderError
    assert llm_engine.LLMCognitiveEngine is engines.LLMCognitiveEngine
    assert test_engine.TestCognitiveEngine is engines.TestCognitiveEngine
