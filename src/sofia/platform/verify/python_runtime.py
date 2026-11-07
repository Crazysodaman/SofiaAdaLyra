"""Prepare/inspect neutral CPython runtime bytes; no installation or activation."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
import os
from pathlib import Path
import re
import stat
import tempfile
import zipfile

from sofia.platform.state.artifact_file import read_artifact_file
from sofia.platform.state.private_file import assert_no_redirected_components
from sofia.platform.verify.native_artifact import verify_native_target
from sofia.sdk.artifact import ArtifactReference
from sofia.sdk.cognition_json import loads_strict_model_json
from sofia.sdk.platform_release import PlatformReleaseTarget
from sofia.sdk.python_runtime import PythonRuntimeManifest, RuntimeFile


@dataclass(frozen=True, slots=True)
class PreparedPythonRuntime:
    manifest: PythonRuntimeManifest
    reference: ArtifactReference


def _regular(path):
    assert_no_redirected_components(path, include_leaf=True)
    if not stat.S_ISREG(path.stat(follow_symlinks=False).st_mode):
        raise ValueError('ordinary nonredirected runtime file required')
    return path


def _members(prefix, target):
    windows = target is PlatformReleaseTarget.WINDOWS_X86_64
    primary = prefix / ('python.exe' if windows else 'bin/python3.12')
    library = prefix / ('Lib' if windows else 'lib/python3.12')
    paths = [_regular(primary)]
    def walk(directory):
        assert_no_redirected_components(directory, include_leaf=True)
        for item in sorted(directory.iterdir()):
            # Never descend into, observe or copy installed application packages.
            if item.name.casefold() in {'site-packages', 'dist-packages', '__pycache__', 'test', 'tests'}:
                continue
            assert_no_redirected_components(item, include_leaf=True)
            if item.is_dir():
                walk(item)
            else:
                paths.append(_regular(item))
            if len(paths) > 8192:
                raise ValueError('runtime file inventory exceeds bound')
    walk(library)
    if windows:
        dlls = prefix / 'DLLs'
        if dlls.exists():
            walk(dlls)
        for item in prefix.iterdir():
            if re.fullmatch(r'(?:python3(?:12)?|vcruntime[0-9_]+)\.dll', item.name.casefold()):
                paths.append(_regular(item))
    else:
        for item in (prefix / 'lib').glob('libpython*.so*'):
            # Only actual versioned libraries are needed, not alias symlinks.
            if not item.is_symlink():
                paths.append(_regular(item))
    license_file = prefix / 'LICENSE.txt'
    if license_file.exists():
        paths.append(_regular(license_file))
    return tuple(sorted(set(paths)))


def _write_member(archive, name, data, executable=False):
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | (0o755 if executable else 0o644)) << 16
    archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def build_python_runtime(prefix, output, *, target, python_version):
    """Snapshot a vetted full CPython prefix, excluding every site-package tree.

    The caller vets the upstream interpreter. This producer grants no signer,
    owner or runtime-health authority, and never installs its prepared bytes.
    """
    prefix, output = Path(prefix).absolute(), Path(output).absolute()
    if output.exists() or output.is_symlink():
        raise FileExistsError('runtime output must not replace existing data')
    assert_no_redirected_components(output.parent, include_leaf=True)
    assert_no_redirected_components(prefix, include_leaf=True)
    if prefix in output.parents:
        raise ValueError('runtime artifact must be outside its source prefix')
    if not isinstance(target, PlatformReleaseTarget):
        raise TypeError('typed runtime target required')
    primary = 'python.exe' if target is PlatformReleaseTarget.WINDOWS_X86_64 else 'bin/python3.12'
    files, snapshots = [], {}
    total = 0
    for path in _members(prefix, target):
        size = path.stat().st_size
        if size > 64 * 1024**2:
            raise ValueError('runtime file exceeds 64-MiB bound')
        total += size
        if total > 512 * 1024**2:
            raise ValueError('runtime bytes exceed bundle bound')
        digest, data = read_artifact_file(path, size, include_data=True)
        name = path.relative_to(prefix).as_posix()
        executable = name == primary
        files.append(RuntimeFile(name, digest, size, executable))
        snapshots[name] = data
    manifest = PythonRuntimeManifest(python_version, target, primary, tuple(files))
    verify_native_target(snapshots[primary], target)
    with tempfile.NamedTemporaryFile(prefix='.runtime-', suffix='.zip', dir=output.parent, delete=False) as temporary:
        temporary_path = Path(temporary.name)
    try:
        with zipfile.ZipFile(temporary_path, 'w') as archive:
            _write_member(archive, 'runtime-manifest.json', manifest.canonical_bytes)
            for member in manifest.files:
                _write_member(archive, 'python/' + member.path, snapshots[member.path], member.executable)
        size = temporary_path.stat().st_size
        digest, _ = read_artifact_file(temporary_path, size)
        expected = ArtifactReference(output.name, digest, size)
        verify_python_runtime(temporary_path, expected=expected, target=target, python_version=python_version)
        with temporary_path.open('rb+') as stream:
            os.fsync(stream.fileno())
        # Hard-link publication is atomic and refuses an output created mid-build.
        os.link(temporary_path, output)
        descriptor = os.open(output.parent, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0)) if os.name != 'nt' else None
        if descriptor is not None:
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    finally:
        temporary_path.unlink(missing_ok=True)
    return PreparedPythonRuntime(manifest, expected)


def _verified_runtime_snapshot(path, *, expected, target, python_version):
    """Inspect the same bounded snapshot that matched the supplied artifact hash.

    An outer signed release verifier must authenticate this reference before any
    installer uses it. A constructible reference is not an installation permit.
    """
    if not isinstance(expected, ArtifactReference) or not isinstance(target, PlatformReleaseTarget):
        raise TypeError('typed expected artifact and target required')
    if expected.size_bytes > 512 * 1024**2:
        raise ValueError('runtime archive exceeds bound')
    digest, raw = read_artifact_file(Path(path), expected.size_bytes, include_data=True)
    if digest != expected.sha256:
        raise ValueError('runtime archive digest differs')
    with zipfile.ZipFile(BytesIO(raw)) as archive:
        entries = archive.infolist()
        if not 4 <= len(entries) <= 8193 or sum(item.file_size for item in entries) > 514 * 1024**2:
            raise ValueError('runtime archive inventory exceeds bound')
        names = [item.filename for item in entries]
        if len(set(names)) != len(names) or any(item.orig_filename != item.filename for item in entries):
            raise ValueError('ambiguous runtime archive names')
        metadata = archive.getinfo('runtime-manifest.json')
        if not 1 <= metadata.file_size <= 2 * 1024**2:
            raise ValueError('runtime metadata exceeds bound')
        encoded = archive.read(metadata)
        manifest = PythonRuntimeManifest.from_payload(loads_strict_model_json(encoded.decode('utf-8')))
        if manifest.canonical_bytes != encoded or manifest.target is not target or manifest.python_version != python_version:
            raise ValueError('runtime manifest differs from expected target/version')
        wanted = {'runtime-manifest.json'} | {'python/' + item.path for item in manifest.files}
        if set(names) != wanted:
            raise ValueError('runtime archive files differ from manifest')
        for item in entries:
            mode = item.external_attr >> 16
            if not stat.S_ISREG(mode) or mode & 0o7777 not in (0o644, 0o755):
                raise ValueError('runtime archive member has unsafe type/mode')
        for member in manifest.files:
            info = archive.getinfo('python/' + member.path)
            if info.file_size != member.size_bytes or (info.external_attr >> 16) & 0o777 != (0o755 if member.executable else 0o644):
                raise ValueError('runtime archive member metadata differs')
            payload = archive.read(info)
            if sha256(payload).hexdigest() != member.sha256:
                raise ValueError('runtime archive member digest differs')
            if member.path == manifest.executable:
                verify_native_target(payload, target)
    return manifest, raw


def verify_python_runtime(path, *, expected, target, python_version):
    """Read-only byte verification; never an owner, install or health permit."""
    return _verified_runtime_snapshot(path, expected=expected, target=target,
        python_version=python_version)[0]


def materialize_python_runtime(path, destination, *, expected, target, python_version):
    """Write verified code into a new private candidate directory only.

    A partial failure leaves that new directory quarantined for review. Existing
    data is never repaired, replaced or activated, and no Platform state is opened.
    """
    destination = Path(destination).absolute()
    if destination.exists() or destination.is_symlink():
        raise FileExistsError('runtime candidate must not replace existing data')
    assert_no_redirected_components(destination.parent, include_leaf=True)
    manifest, raw = _verified_runtime_snapshot(path, expected=expected, target=target,
        python_version=python_version)
    destination.mkdir(mode=0o700)
    with zipfile.ZipFile(BytesIO(raw)) as archive:
        for member in archive.infolist():
            target_path = destination.joinpath(*member.filename.split('/'))
            target_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            assert_no_redirected_components(target_path.parent, include_leaf=True)
            with target_path.open('xb') as output:
                with archive.open(member) as source:
                    while chunk := source.read(65536):
                        output.write(chunk)
                output.flush()
                os.fsync(output.fileno())
            target_path.chmod((member.external_attr >> 16) & 0o777)
    if os.name != 'nt':
        for directory in sorted((p for p in destination.rglob('*') if p.is_dir()),
                key=lambda p: len(p.parts), reverse=True) + [destination]:
            descriptor = os.open(directory, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    return manifest


def probe_materialized_python(destination, manifest, *, timeout=15):
    """Execute vetted candidate code as the current user with no credential env.

    This verifies relocation on this host, not another OS or installation rights.
    The signed release/caller remains responsible for deciding trust in the bytes.
    """
    import json
    import subprocess
    import sys
    destination = Path(destination).absolute()
    if not isinstance(manifest, PythonRuntimeManifest):
        raise TypeError('typed byte-verified runtime inventory required')
    host_windows = os.name == 'nt'
    if host_windows != (manifest.target is PlatformReleaseTarget.WINDOWS_X86_64):
        raise ValueError('runtime probe requires a matching native host')
    assert_no_redirected_components(destination, include_leaf=True)
    wanted = {'runtime-manifest.json'} | {'python/' + item.path for item in manifest.files}
    observed = set()
    for path in destination.rglob('*'):
        assert_no_redirected_components(path, include_leaf=True)
        if not path.is_dir() and not path.is_file():
            raise ValueError('materialized runtime contains a nonregular entry')
        if path.is_file():
            observed.add(path.relative_to(destination).as_posix())
    if observed != wanted or (destination/'runtime-manifest.json').read_bytes() != manifest.canonical_bytes:
        raise ValueError('materialized runtime contains changed or unexpected files')
    for item in manifest.files:
        actual, _ = read_artifact_file(destination/'python'/item.path, item.size_bytes)
        if actual != item.sha256:
            raise ValueError('materialized runtime bytes changed before execution')
    prefix = destination/'python'
    environment = {'PATH': os.defpath}
    for name in ('SystemRoot', 'WINDIR', 'TEMP', 'TMP'):
        if name in os.environ:
            environment[name] = os.environ[name]
    if not host_windows:
        environment['LD_LIBRARY_PATH'] = str(prefix/'lib')
    source = '''import sys,json,importlib.util,ssl,sqlite3,ctypes,venv

def present(name):
    try: return importlib.util.find_spec(name) is not None
    except ModuleNotFoundError: return False

print(json.dumps(dict(python_version='.'.join(map(str,sys.version_info[:3])),prefix=sys.prefix,
    base_prefix=sys.base_prefix,executable=sys.executable,core_installed=present('sofia.core'),
    ollama_installed=present('ollama'),ssl=ssl.OPENSSL_VERSION,sqlite=sqlite3.sqlite_version)))
'''
    completed = subprocess.run([str(prefix/manifest.executable), '-B', '-I', '-c', source],
        env=environment, cwd=destination, capture_output=True, text=True, timeout=timeout)
    if completed.returncode or len(completed.stdout) > 8192:
        raise ValueError('relocated CPython process failed its bounded probe')
    report = loads_strict_model_json(completed.stdout)
    if (type(report) is not dict or report.get('python_version') != manifest.python_version
            or report.get('core_installed') is not False or report.get('ollama_installed') is not False
            or Path(report.get('prefix', '')).absolute() != prefix
            or Path(report.get('base_prefix', '')).absolute() != prefix):
        raise ValueError('relocated runtime identity/version/package projection differs')
    return dict(result='VERIFIED_RELOCATED_RUNTIME_PROCESS', host_platform=sys.platform,
        python_version=report['python_version'], files=len(manifest.files),
        core_installed=False, ollama_installed=False, production_authorized=False, release_accepted=False)
