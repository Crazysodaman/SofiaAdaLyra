"""Actual minimal component installation, with optional inference absent."""
from email.parser import Parser
from pathlib import Path
import subprocess
import sys
import tomllib
import zipfile

from sofia.platform.verify.component_artifacts import _generate_pyproject, load_component_manifest
from test.test_component_install_production import component_wheels


def test_platform_declares_optional_ollama_without_requiring_it():
    component = load_component_manifest(Path(__file__).resolve().parents[1])['platform']
    generated = tomllib.loads(_generate_pyproject(component, '1.0.0'))['project']
    assert generated['optional-dependencies']['ollama'] == ['ollama']
    assert not any('ollama' in value for value in generated['dependencies'])


def test_installed_baseline_needs_neither_core_nor_optional_inference(tmp_path, component_wheels):
    home = tmp_path / 'venv'
    subprocess.run([sys.executable, '-m', 'venv', str(home)], check=True, capture_output=True)
    python = home / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
    install = subprocess.run([str(python), '-m', 'pip', 'install', '--disable-pip-version-check',
        str(component_wheels['sdk']), str(component_wheels['platform'])],
        capture_output=True, text=True, timeout=300)
    assert install.returncode == 0, install.stderr
    probe = '''
import importlib.util
import sys
from pathlib import Path
from sofia.platform.state.installation_identity import InstallationIdentityStore
from sofia.platform.cognition_provider import create_generic_llm_provider
from sofia.platform.config.model import ProviderConfiguration
assert importlib.util.find_spec('sofia.core') is None
assert importlib.util.find_spec('ollama') is None
store = InstallationIdentityStore(Path(sys.argv[1]))
first = store.initialize()
assert store.load().to_payload() == first.to_payload()
assert create_generic_llm_provider(ProviderConfiguration(provider='test-llm', model='synthetic')) is not None
assert not any(name.startswith('sofia.core') for name in sys.modules)
assert not list(Path(sys.argv[1]).parent.rglob('sofia.db'))
print('minimal-platform-ok')
'''
    result = subprocess.run([str(python), '-I', '-c', probe, str(tmp_path/'identity')],
        cwd=home, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == 'minimal-platform-ok'
    subprocess.run([str(python), '-m', 'pip', 'check'], check=True, capture_output=True)
    with zipfile.ZipFile(component_wheels['platform']) as archive:
        metadata = Parser().parsestr(archive.read(next(name for name in archive.namelist()
            if name.endswith('.dist-info/METADATA'))).decode())
    assert 'ollama' in metadata.get_all('Provides-Extra', [])
    assert any('extra == "ollama"' in requirement for requirement in metadata.get_all('Requires-Dist', []))
