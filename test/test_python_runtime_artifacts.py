"""Portable runtime artifacts contain code, never a Core or installed identity."""
from dataclasses import replace
from hashlib import sha256

import pytest

from sofia.sdk.python_runtime import PythonRuntimeManifest, RuntimeFile
from sofia.sdk.platform_release import PlatformReleaseTarget


def definition():
    files = (RuntimeFile('bin/python3.12', 'a'*64, 64, True),
        RuntimeFile('lib/python3.12/site.py', 'b'*64, 12, False),
        RuntimeFile('lib/python3.12/ensurepip/__init__.py', sha256(b'').hexdigest(), 0, False))
    return PythonRuntimeManifest('3.12.16', PlatformReleaseTarget.DEBIAN12_X86_64,
        'bin/python3.12', files)


def test_runtime_contract_round_trip_supports_empty_standard_library_files():
    manifest = definition()
    assert PythonRuntimeManifest.from_payload(manifest.to_payload()) == manifest
    assert len(manifest.digest) == 64
    assert 'identity' not in manifest.to_payload()
    assert 'constitution' not in manifest.to_payload()


@pytest.mark.parametrize('path', ['../owner.key', '/etc/shadow', 'Lib/site-packages/sofia/core/state.py',
    'lib/python3.12/dist-packages/ollama/client.py', 'Lib/SITE-PACKAGES/injected.py'])
def test_runtime_cannot_ship_installed_packages_or_external_state(path):
    with pytest.raises(ValueError):
        RuntimeFile(path, 'a'*64, 1, False)


@pytest.mark.parametrize('defect', ['version', 'duplicate', 'no_executable', 'wrong_arch_layout', 'boolean_size'])
def test_runtime_rejects_ambiguous_or_incomplete_contract(defect):
    manifest = definition()
    with pytest.raises((ValueError, TypeError)):
        if defect == 'version': replace(manifest, python_version='3.11.9')
        elif defect == 'duplicate': replace(manifest, files=manifest.files + (manifest.files[0],))
        elif defect == 'no_executable': replace(manifest, executable='bin/missing')
        elif defect == 'wrong_arch_layout': replace(manifest, target=PlatformReleaseTarget.WINDOWS_X86_64)
        elif defect == 'boolean_size': RuntimeFile('Lib/site.py', 'a'*64, True, False)


def fake_prefix(tmp_path):
    import struct
    prefix = tmp_path / 'python-prefix'
    binary = prefix / 'bin/python3.12'
    binary.parent.mkdir(parents=True)
    data = bytearray(64)
    data[:6] = b'\x7fELF\x02\x01'
    struct.pack_into('<H', data, 18, 62)
    binary.write_bytes(data)  # Inert header fixture, never executed.
    for name in ('site.py', 'ensurepip/__init__.py', 'os.py'):
        path = prefix / 'lib/python3.12' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'' if name.startswith('ensurepip') else b'# standard library fixture\n')
    unwanted = prefix / 'lib/python3.12/site-packages/sofia/core/synthetic.py'
    unwanted.parent.mkdir(parents=True)
    unwanted.write_bytes(b'# synthetic forbidden application payload')
    return prefix


def test_runtime_builder_excludes_application_packages_and_is_reproducible(tmp_path):
    from sofia.platform.verify.python_runtime import build_python_runtime, verify_python_runtime
    prefix = fake_prefix(tmp_path)
    first = build_python_runtime(prefix, tmp_path / 'first.zip',
        target=PlatformReleaseTarget.DEBIAN12_X86_64, python_version='3.12.16')
    second = build_python_runtime(prefix, tmp_path / 'second.zip',
        target=PlatformReleaseTarget.DEBIAN12_X86_64, python_version='3.12.16')
    assert first.reference.sha256 == second.reference.sha256
    assert not any('site-packages' in item.path for item in first.manifest.files)
    assert verify_python_runtime(tmp_path / 'first.zip', expected=first.reference,
        target=PlatformReleaseTarget.DEBIAN12_X86_64, python_version='3.12.16') == first.manifest
    (tmp_path / 'first.zip').write_bytes(b'tampered')
    with pytest.raises((OSError, ValueError)):
        verify_python_runtime(tmp_path / 'first.zip', expected=first.reference,
            target=PlatformReleaseTarget.DEBIAN12_X86_64, python_version='3.12.16')


def test_runtime_builder_preserves_existing_output(tmp_path):
    from sofia.platform.verify.python_runtime import build_python_runtime
    output = tmp_path / 'existing.zip'
    output.write_bytes(b'preserve concurrent output')
    with pytest.raises(FileExistsError):
        build_python_runtime(fake_prefix(tmp_path), output,
            target=PlatformReleaseTarget.DEBIAN12_X86_64, python_version='3.12.16')
    assert output.read_bytes() == b'preserve concurrent output'


@pytest.mark.parametrize('redirect', ['root', 'ancestor'])
def test_runtime_source_redirection_is_rejected_before_file_digest(tmp_path, monkeypatch, redirect):
    import os
    import subprocess
    import sofia.platform.verify.python_runtime as runtime
    real = tmp_path / 'real'
    real.mkdir()
    prefix = fake_prefix(real)
    link = tmp_path / 'redirect'
    target = prefix if redirect == 'root' else real
    if os.name == 'nt':
        subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(target)], check=True, capture_output=True)
    else:
        link.symlink_to(target, target_is_directory=True)
    selected = link if redirect == 'root' else link / prefix.name
    def denied(*args, **kwargs):
        raise AssertionError('redirected source must not be digested')
    monkeypatch.setattr(runtime, 'read_artifact_file', denied)
    with pytest.raises((OSError, ValueError)):
        runtime.build_python_runtime(selected, tmp_path / 'runtime.zip',
            target=PlatformReleaseTarget.DEBIAN12_X86_64, python_version='3.12.16')


def test_runtime_materialization_is_new_directory_only_and_uses_verified_bytes(tmp_path):
    from sofia.platform.verify.python_runtime import build_python_runtime, materialize_python_runtime
    prepared = build_python_runtime(fake_prefix(tmp_path), tmp_path / 'prepared.zip',
        target=PlatformReleaseTarget.DEBIAN12_X86_64, python_version='3.12.16')
    output = tmp_path / 'materialized'
    materialize_python_runtime(tmp_path / 'prepared.zip', output, expected=prepared.reference,
        target=PlatformReleaseTarget.DEBIAN12_X86_64, python_version='3.12.16')
    assert (output / 'python/bin/python3.12').read_bytes() == b'\x7fELF\x02\x01' + b'\0'*12 + b'>\0' + b'\0'*44
    with pytest.raises(FileExistsError):
        materialize_python_runtime(tmp_path / 'prepared.zip', output, expected=prepared.reference,
            target=PlatformReleaseTarget.DEBIAN12_X86_64, python_version='3.12.16')
    (tmp_path / 'prepared.zip').write_bytes(b'corrupt')
    denied = tmp_path / 'denied'
    with pytest.raises((OSError, ValueError)):
        materialize_python_runtime(tmp_path / 'prepared.zip', denied, expected=prepared.reference,
            target=PlatformReleaseTarget.DEBIAN12_X86_64, python_version='3.12.16')
    assert not denied.exists()


def test_actual_native_cpython_archive_runs_after_relocation_without_app_packages(tmp_path):
    """Real native interpreter, separate from the inert header/negative fixtures."""
    import os
    import sys
    from pathlib import Path
    from sofia.platform.verify.python_runtime import (
        build_python_runtime, materialize_python_runtime, probe_materialized_python,
    )
    if sys.version_info[:2] != (3, 12) or sys.platform not in ('linux', 'win32'):
        if os.environ.get('AEGIS_REQUIRE_RUNTIME_PROBE') == '1':
            pytest.fail('required native CPython3.12 archive probe host unavailable')
        pytest.skip('native CPython3.12 Linux/Windows packaging contract')
    target = PlatformReleaseTarget.WINDOWS_X86_64 if os.name == 'nt' else PlatformReleaseTarget.DEBIAN12_X86_64
    version = '.'.join(map(str, sys.version_info[:3]))
    prepared = build_python_runtime(Path(sys.base_prefix), tmp_path/'native.zip',
        target=target, python_version=version)
    materialize_python_runtime(tmp_path/'native.zip', tmp_path/'candidate', expected=prepared.reference,
        target=target, python_version=version)
    result = probe_materialized_python(tmp_path/'candidate', prepared.manifest)
    assert result['result'] == 'VERIFIED_RELOCATED_RUNTIME_PROCESS'
    assert result['python_version'] == version
    assert result['core_installed'] is False
    assert result['ollama_installed'] is False
    assert result['release_accepted'] is False


@pytest.mark.parametrize('defect', ['symlink', 'extra', 'changed_bytes', 'target', 'version'])
def test_runtime_rejects_untrusted_archive_before_creating_candidate(tmp_path, defect):
    from io import BytesIO
    import stat
    import zipfile
    from sofia.sdk.artifact import ArtifactReference
    from sofia.platform.verify.python_runtime import build_python_runtime, materialize_python_runtime
    path = tmp_path/'archive.zip'
    prepared = build_python_runtime(fake_prefix(tmp_path), path,
        target=PlatformReleaseTarget.DEBIAN12_X86_64, python_version='3.12.16')
    if defect in {'symlink', 'extra', 'changed_bytes'}:
        original = path.read_bytes()
        with zipfile.ZipFile(BytesIO(original)) as source, zipfile.ZipFile(path, 'w') as output:
            for index, member in enumerate(source.infolist()):
                data = source.read(member)
                if index == 1 and defect == 'symlink':
                    member.external_attr = (stat.S_IFLNK | 0o777) << 16
                if index == 1 and defect == 'changed_bytes':
                    data = b'X' * len(data)
                output.writestr(member, data)
            if defect == 'extra':
                output.writestr('python/../../owner.key', b'forbidden synthetic payload')
    raw = path.read_bytes()
    expected = ArtifactReference(path.name, sha256(raw).hexdigest(), len(raw))
    destination = tmp_path/'candidate'
    with pytest.raises(ValueError):
        materialize_python_runtime(path, destination, expected=expected,
            target=PlatformReleaseTarget.WINDOWS_X86_64 if defect == 'target' else prepared.manifest.target,
            python_version='3.12.17' if defect == 'version' else '3.12.16')
    assert not destination.exists()



def test_runtime_builder_verifier_and_materializer_stream_non_native_bytes(
        tmp_path, monkeypatch):
    """One actual signed-format CPython ZIP through all original B1 stages.

    Non-executable source files and the complete ZIP must never use the
    eager 512MiB reader. The original native header is still read in full
    (at most 64MiB) because architecture verification needs native bytes.
    """
    import tracemalloc
    import sofia.platform.verify.python_runtime as module

    prefix = fake_prefix(tmp_path)
    large_source = prefix / 'lib/python3.12/os.py'
    with large_source.open('wb') as output:
        output.truncate(16 * 1024 * 1024 + 3)

    original = module.read_artifact_file
    eager = []
    def checked_reader(path, size, *, include_data=False):
        if include_data:
            eager.append(str(path))
            assert Path(path).name == 'python3.12'
        return original(path, size, include_data=include_data)
    monkeypatch.setattr(module, 'read_artifact_file', checked_reader)

    runtime = tmp_path / 'signed-python-runtime.zip'
    destination = tmp_path / 'owner-private-materialized-runtime'
    tracemalloc.start()
    try:
        packaged = module.build_python_runtime(
            prefix, runtime, target=PlatformReleaseTarget.DEBIAN12_X86_64,
            python_version='3.12.16',
        )
        observed = module.verify_python_runtime(
            runtime, expected=packaged.reference,
            target=PlatformReleaseTarget.DEBIAN12_X86_64,
            python_version='3.12.16',
        )
        extracted = module.materialize_python_runtime(
            runtime, destination, expected=packaged.reference,
            target=PlatformReleaseTarget.DEBIAN12_X86_64,
            python_version='3.12.16',
        )
        _current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert observed == packaged.manifest == extracted
    assert (destination / 'python/lib/python3.12/os.py').stat().st_size == (
        16 * 1024 * 1024 + 3
    )
    assert not list(destination.rglob('sofia.db'))
    assert len(eager) == 1
    assert peak < 12 * 1024 * 1024


def test_runtime_streaming_review_denies_corrupted_publisher_signed_zip(
        tmp_path):
    from sofia.platform.verify.python_runtime import (
        build_python_runtime, verify_python_runtime,
    )
    from sofia.sdk.artifact import ArtifactReference

    prefix = fake_prefix(tmp_path)
    output = tmp_path / 'signed-runtime.zip'
    packaged = build_python_runtime(
        prefix, output, target=PlatformReleaseTarget.DEBIAN12_X86_64,
        python_version='3.12.16',
    )
    raw = bytearray(output.read_bytes())
    # Mutating one byte of the outer ZIP with the SAME declared ArtifactReference
    # must fail before any runtime materialization or installation.
    raw[len(raw) // 2] ^= 1
    output.write_bytes(raw)
    with pytest.raises((ValueError, PermissionError)):
        verify_python_runtime(
            output, expected=packaged.reference,
            target=PlatformReleaseTarget.DEBIAN12_X86_64,
            python_version='3.12.16',
        )
