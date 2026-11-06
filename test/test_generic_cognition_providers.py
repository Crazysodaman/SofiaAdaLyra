"""Generic model construction and transport do not require personal Core code."""
import os
from pathlib import Path
import subprocess
import sys
import textwrap

from test.test_platform_import_isolation import _BLOCK_CORE

NEUTRAL_PROVIDER_PROBE = textwrap.dedent('''
    import sys
    from types import SimpleNamespace
    from dataclasses import replace
    from uuid import uuid4
    from sofia.sdk.cognition_engine import LLMProviderError
    from sofia.sdk.cognition_model import CognitiveMessage, CognitiveRole, CognitiveRequest, CognitiveResponse
    from sofia.platform.config.model import ProviderConfiguration
    from sofia.platform.cognition_provider import create_generic_llm_provider
    from sofia.platform.core_worker import ollama_transport
    from sofia.platform.distributed.inference import RemoteInferenceRequest
    from sofia.platform.distributed.inference_service import (
        LocalOllamaInferenceService, RemoteInferencePolicy, RemoteInferenceDenied,
    )

    class Client:
        def __init__(self, *, host):
            self.host = host
            self.calls = []
        def chat(self, **kwargs):
            self.calls.append(kwargs)
            return SimpleNamespace(message=SimpleNamespace(
                content=kwargs['messages'][0]['content'], tool_calls=[]))

    ollama_transport.GenericOllamaProvider._new_client = staticmethod(lambda endpoint: Client(host=endpoint))
    providers = []
    for name in ('Synthetic Sofía', 'Synthetic Roland', 'Synthetic John'):
        marker = f'{name}: {uuid4()}'
        request = CognitiveRequest(messages=(CognitiveMessage(CognitiveRole.USER, marker),), allow_tools=False)
        deterministic = create_generic_llm_provider(ProviderConfiguration('test-llm', 'disposable'))
        deterministic.response = CognitiveResponse(content=marker)
        assert deterministic.respond(request).content == marker
        assert deterministic.received_request is request
        provider = create_generic_llm_provider(ProviderConfiguration('ollama', 'disposable'), endpoint='http://127.0.0.1:11434')
        assert provider.respond(request).content == marker
        assert len(provider.client.calls) == 1
        assert provider.client.calls[0]['messages'] == [{'role': 'user', 'content': marker}]
        assert 'tools' not in provider.client.calls[0]
        providers.append((provider, marker))
        node_id = uuid4()
        service = LocalOllamaInferenceService(node_id=node_id,
            policy=RemoteInferencePolicy(allowed_models=('disposable',)),
            provider_factory=create_generic_llm_provider)
        envelope = RemoteInferenceRequest(request_id=uuid4(), node_id=node_id,
            grant_id=uuid4(), provider=ProviderConfiguration('ollama', 'disposable'), request=request)
        result = service.infer(envelope)
        assert result.response.content == marker and result.request_id == envelope.request_id
        try:
            service.infer(replace(envelope, node_id=uuid4()))
        except RemoteInferenceDenied:
            pass
        else:
            raise AssertionError('wrong target inference admitted')
    assert len({id(p.client) for p, _ in providers}) == 3
    for provider, marker in providers:
        assert provider.client.calls[0]['messages'][0]['content'] == marker
    try:
        create_generic_llm_provider(ProviderConfiguration('unknown', 'disposable'))
    except ValueError:
        pass
    else:
        raise AssertionError('unknown generic provider admitted')
    bad_call = SimpleNamespace(function=SimpleNamespace(name='inspect', arguments='{"x": 1, "x": 2}'))
    try:
        ollama_transport.GenericOllamaProvider._tool_call_from_ollama(bad_call)
    except LLMProviderError:
        pass
    else:
        raise AssertionError('ambiguous tool arguments admitted')
    assert not any(n == 'sofia.core' or n.startswith('sofia.core.') for n in sys.modules)
    print('generic-providers-ok')
''')


def test_platform_provider_factory_imports_without_core():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, '-c', _BLOCK_CORE + NEUTRAL_PROVIDER_PROBE],
        cwd=root, env={**os.environ, 'PYTHONPATH': str(root / 'src')},
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert 'generic-providers-ok' in result.stdout


def test_shared_provider_helpers_preserve_legacy_class_identity():
    from sofia.core.cognition import budgets, strict_json
    from sofia.core.cognition.providers.test_provider import TestLLMProvider
    from sofia.platform import cognition_budget
    from sofia.platform.core_worker import engines
    from sofia.sdk import cognition_json

    assert budgets.ModelTokenBudget is cognition_budget.ModelTokenBudget
    assert budgets.model_token_budget is cognition_budget.model_token_budget
    assert strict_json.loads_strict_model_json is cognition_json.loads_strict_model_json
    assert TestLLMProvider is engines.TestLLMProvider


def test_deterministic_factory_and_transport_import_without_optional_ollama():
    root = Path(__file__).resolve().parents[1]
    code = _BLOCK_CORE + textwrap.dedent('''
        class BlockOllama(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname == 'ollama' or fullname.startswith('ollama.'):
                    raise ImportError('optional Ollama package unavailable')
        sys.meta_path.insert(0, BlockOllama())
        from sofia.platform.cognition_provider import create_generic_llm_provider
        from sofia.platform.core_worker.ollama_transport import GenericOllamaProvider
        from sofia.platform.config.model import ProviderConfiguration
        from sofia.sdk.cognition_model import CognitiveRequest, CognitiveResponse
        provider = create_generic_llm_provider(ProviderConfiguration('test-llm', 'disposable'))
        provider.response = CognitiveResponse('neutral')
        assert provider.respond(CognitiveRequest(messages=())).content == 'neutral'
        try:
            create_generic_llm_provider(ProviderConfiguration('ollama', 'disposable'))
        except ImportError:
            pass
        else:
            raise AssertionError('missing optional provider silently substituted')
    ''')
    result = subprocess.run(
        [sys.executable, '-c', code], cwd=root,
        env={**os.environ, 'PYTHONPATH': str(root / 'src')},
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr


def test_inference_service_imports_without_core():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, '-c', _BLOCK_CORE + 'import sofia.platform.distributed.inference_service\n'],
        cwd=root, env={**os.environ, 'PYTHONPATH': str(root / 'src')},
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
