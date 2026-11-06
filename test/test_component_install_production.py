"""Production-machinery install tests for separated component wheels.

A real virtual environment receives the actual built wheels through pip, the
same installer surface production uses, and the full lifecycle is observed:
SDK+Platform without Core, Core installation without overwriting Platform or
SDK files, and Core uninstall that preserves the Platform installation.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

import pytest

from sofia.platform.verify.component_artifacts import build_all_components

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def component_wheels(tmp_path_factory) -> dict[str, Path]:
    return build_all_components(
        tmp_path_factory.mktemp("production-wheels"), repo=ROOT
    )


@pytest.fixture(scope="module")
def production_venv(tmp_path_factory, component_wheels) -> dict[str, object]:
    venv_root = tmp_path_factory.mktemp("production-venv")
    python = (
        venv_root / "Scripts" / "python.exe"
        if sys.platform == "win32"
        else venv_root / "bin" / "python"
    )
    context = {"venv_root": venv_root, "python": python, "log": []}

    def run(args: list[str], *, timeout: int = 600) -> str:
        completed = subprocess.run(
            [str(python), *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        context["log"].append((tuple(args), completed.returncode))
        if completed.returncode:
            raise RuntimeError(
                f"command failed ({completed.returncode}): {args}\n"
                f"{completed.stdout}\n{completed.stderr}"
            )
        return completed.stdout.strip()

    context["run"] = run
    subprocess.run(
        [sys.executable, "-m", "venv", str(venv_root)],
        check=True,
        capture_output=True,
        text=True,
    )
    run(["-m", "pip", "install", "--disable-pip-version-check", "--no-deps",
         str(component_wheels["sdk"])])
    run(["-m", "pip", "install", "--disable-pip-version-check", "--no-deps",
         str(component_wheels["platform"])])
    runtime_dependencies = ["cryptography", "tzdata", "ollama"]
    if sys.platform == "win32":
        runtime_dependencies.append("pywin32")
    run(["-m", "pip", "install", "--disable-pip-version-check",
         *runtime_dependencies])
    run(["-m", "pip", "check"])
    return context


def _wheel_entry_bytes(wheel: Path, name: str) -> bytes:
    with zipfile.ZipFile(wheel) as archive:
        return archive.read(name)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_production_component_install_lifecycle(production_venv, component_wheels):
    run = production_venv["run"]
    venv_root = production_venv["venv_root"]
    if sys.platform == "win32":
        site_packages = venv_root / "Lib" / "site-packages"
    else:
        site_packages = next((venv_root / "lib").glob("python*/site-packages"))
    sofia_root = site_packages / "sofia"

    installed_init = sofia_root / "__init__.py"
    sdk_init_bytes = _wheel_entry_bytes(component_wheels["sdk"], "sofia/__init__.py")
    assert installed_init.is_file()
    assert installed_init.read_bytes() == sdk_init_bytes

    platform_marker = "sofia/platform/run/active_release.py"
    platform_marker_path = sofia_root / "platform" / "run" / "active_release.py"
    assert platform_marker_path.is_file()
    platform_marker_digest = _sha256(platform_marker_path)
    assert platform_marker_digest == hashlib.sha256(
        _wheel_entry_bytes(component_wheels["platform"], platform_marker)
    ).hexdigest()

    core_probe = (
        "import sofia.core.constitution\n"
        "import sofia.core.identity.model\n"
        "import sofia.sdk.cognition_model\n"
        "import sofia.platform.run.active_release\n"
        "print('core-absent-probe-ok')\n"
    )
    without_core = subprocess.run(
        [str(production_venv["python"]), "-c", core_probe],
        capture_output=True, text=True, timeout=120, check=False,
        cwd=str(production_venv["venv_root"]),
    )
    assert without_core.returncode != 0
    assert "core-absent-probe-ok" not in without_core.stdout
    assert "sofia.core" in without_core.stderr

    run(["-m", "pip", "install", "--disable-pip-version-check", "--no-deps",
         str(component_wheels["core"])])
    run(["-m", "pip", "check"])

    assert installed_init.read_bytes() == sdk_init_bytes
    assert _sha256(platform_marker_path) == platform_marker_digest

    with_core = subprocess.run(
        [str(production_venv["python"]), "-c", core_probe],
        capture_output=True, text=True, timeout=120, check=False,
        cwd=str(production_venv["venv_root"]),
    )
    assert with_core.returncode == 0, with_core.stderr
    assert "core-absent-probe-ok" in with_core.stdout

    core_constitution = sofia_root / "core" / "constitution" / "constitution.md"
    assert core_constitution.is_file()

    run(["-m", "pip", "uninstall", "-y", "sofia-core"])

    assert installed_init.is_file()
    assert installed_init.read_bytes() == sdk_init_bytes
    assert _sha256(platform_marker_path) == platform_marker_digest
    after_uninstall = subprocess.run(
        [str(production_venv["python"]), "-c", core_probe],
        capture_output=True, text=True, timeout=120, check=False,
        cwd=str(production_venv["venv_root"]),
    )
    assert after_uninstall.returncode != 0
    run(["-m", "pip", "check"])

    assert any(
        path.name.startswith("sofia_platform-0.1.0.dist-info")
        for path in site_packages.glob("*.dist-info")
    )
    assert not any(
        path.name.startswith("sofia_core-") or path.name.startswith("sofia-core-")
        for path in site_packages.glob("*.dist-info")
    )


def test_production_venv_kept_platform_without_core(
    production_venv, component_wheels
):
    python = production_venv["python"]
    probe = "import sofia.platform.run.active_release; print('platform-ok')"
    completed = subprocess.run(
        [str(python), "-c", probe],
        capture_output=True, text=True, timeout=120, check=False,
        cwd=str(production_venv["venv_root"]),
    )
    assert completed.returncode == 0, completed.stderr
    assert "platform-ok" in completed.stdout


def test_platform_uninstall_reinstall_preserves_callsign_authority(production_venv, component_wheels, tmp_path):
    from test.test_fleet_callsigns import NamingFixture
    naming = NamingFixture(tmp_path)
    naming.rename(naming.first, 'Persistent Dawn')
    run = production_venv['run']
    from test.test_platform_import_isolation import _BLOCK_CORE
    probe = _BLOCK_CORE + (
        'from pathlib import Path\n'
        'from sofia.platform.ops.callsigns import CallsignAuthority\n'
        'from sofia.platform.state.installation_identity import InstallationIdentityStore\n'
        f'authority = CallsignAuthority(Path({str(naming.path)!r}), InstallationIdentityStore(Path({str(naming.installation.home)!r})))\n'
        f"assert authority.snapshot({naming.first!r})['name'] == 'Persistent Dawn'\n"
        f'assert authority.authority_id == {naming.authority.authority_id!r}\n'
        'print("callsign-install-ok")\n'
    )
    assert 'callsign-install-ok' in run(['-I','-c',probe])
    witness = naming.authority.witness_path.read_bytes()
    run(['-m','pip','uninstall','-y','sofia-platform'])
    assert naming.path.exists() and naming.authority.witness_path.read_bytes() == witness
    run(['-m','pip','install','--no-index','--no-deps',str(component_wheels['platform'])])
    run(['-m','pip','check'])
    assert 'callsign-install-ok' in run(['-I','-c',probe])
    assert naming.authority.witness_path.read_bytes() == witness


@pytest.mark.parametrize('kind', ['test', 'provider'])
def test_installed_generic_worker_runs_without_core(production_venv, tmp_path, kind):
    """Spawn a real installed worker; the venv contains no personal Core code."""
    import textwrap
    program = textwrap.dedent('''
        import importlib.util
        import os
        import sys
        from datetime import datetime, timedelta, timezone
        from pathlib import Path
        from uuid import uuid4
        from sofia.sdk.cognition_engine import LLMProvider
        from sofia.sdk.cognition_model import CognitiveMessage, CognitiveRole, CognitiveRequest, CognitiveResponse
        from sofia.platform.config.model import ProviderConfiguration
        from sofia.platform.config.roles import PlatformRole, PlatformRoleConfiguration
        from sofia.platform.state.local_store import PlatformLocalStore
        from sofia.platform.state.installation_identity import InstallationIdentityStore
        from sofia.platform.run import ComponentGenerationStore, LocalRunLeaseStore
        from sofia.platform.core_worker import CoreEngineProcessSpec, CoreWorkerController
        from sofia.platform.core_worker.process import (
            PlatformProviderBinding, installed_core_release_digest,
        )

        assert importlib.util.find_spec('sofia.core') is None
        root = Path(sys.argv[1])
        kind = sys.argv[2]
        platform = InstallationIdentityStore(root / 'identity').initialize()
        platform_id = str(platform.identity.canonical_uuid)
        core_id = str(uuid4())
        local = PlatformLocalStore(root / 'operational.db',
            roles=PlatformRoleConfiguration((PlatformRole.MODULE_HOST,)),
            host_identity=platform_id)
        leases = LocalRunLeaseStore(local.path)
        now = datetime.now(timezone.utc)
        lease = leases.acquire(owner_id=platform_id, now=now, ttl_seconds=300).lease
        assert lease is not None
        generations = ComponentGenerationStore(state_path=local.path, lease_store=leases)
        controller = CoreWorkerController(generations=generations, lease=lease,
            platform_instance_id=platform_id, core_identity_id=core_id,
            component_id='core.disposable', runtime_dir=root / 'ipc',
            response_timeout=timedelta(seconds=10))
        configuration = ProviderConfiguration(provider='test', model='disposable')
        class Provider(LLMProvider):
            def respond(self, request):
                assert request.messages[0].content == 'independent'
                return CognitiveResponse(content=f'provider-pid:{os.getpid()}')
        if kind == 'provider':
            controller.bind_providers({'primary': PlatformProviderBinding(configuration, Provider())})
        digest = installed_core_release_digest()
        spec = CoreEngineProcessSpec(kind,
            provider=configuration if kind == 'provider' else None,
            expected_runtime_digest=digest)
        try:
            health = controller.start(release_digest=digest, spec=spec, now=now)
            assert health.pid != os.getpid() and health.ready
            response = controller.respond(CognitiveRequest(messages=(CognitiveMessage(CognitiveRole.USER, 'independent'),)))
            expected = 'Test cognitive response.' if kind == 'test' else f'provider-pid:{os.getpid()}'
            assert response.content == expected
            assert not any(n == 'sofia.core' or n.startswith('sofia.core.') for n in sys.modules)
        finally:
            controller.shutdown(now=datetime.now(timezone.utc))
            leases.release(lease, now=datetime.now(timezone.utc))
        assert controller.pid is None
        assert InstallationIdentityStore(root / 'identity').load() == platform
        print('installed-worker-ok')
    ''')
    completed = subprocess.run(
        [str(production_venv['python']), '-I', '-c', program, str(tmp_path), kind],
        cwd=str(production_venv['venv_root']), capture_output=True, text=True, timeout=120,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert 'installed-worker-ok' in completed.stdout



def test_installed_neutral_providers_without_core(production_venv):
    from test.test_generic_cognition_providers import NEUTRAL_PROVIDER_PROBE

    completed = subprocess.run(
        [str(production_venv['python']), '-I', '-c', NEUTRAL_PROVIDER_PROBE],
        cwd=str(production_venv['venv_root']), capture_output=True, text=True, timeout=60,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert 'generic-providers-ok' in completed.stdout
