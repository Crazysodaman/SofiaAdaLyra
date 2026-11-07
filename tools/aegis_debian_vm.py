"""Build and boot an offline disposable Debian12 service test, never an installer."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from uuid import UUID

from sofia.platform.state.private_file import assert_no_redirected_components
from sofia.platform.verify.component_artifacts import build_component
from sofia.platform.verify.stage_release_source import stage_reviewed_git_tree

BASE_IMAGE = 'python@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df'


def fresh_output(path: Path) -> Path:
    path = Path(path).absolute()
    if '..' in path.parts or any(c in str(path) for c in ',\n\r\0'):
        raise ValueError('unambiguous new VM output path required')
    assert_no_redirected_components(path.parent, include_leaf=True)
    if path.exists() or path.is_symlink():
        raise FileExistsError('VM output must not adopt an existing path')
    path.mkdir(mode=0o700)
    return path


class DockerSession:
    """Own only returned container IDs on the explicitly local managed daemon."""
    def __init__(self, *, run=subprocess.run, environment=None):
        self.run = run
        self.environment = dict(os.environ if environment is None else environment)
        for key in ('DOCKER_HOST', 'DOCKER_CONTEXT', 'DOCKER_TLS', 'DOCKER_TLS_VERIFY', 'DOCKER_CERT_PATH'):
            self.environment.pop(key, None)
        self.prefix = ['docker', '--host=unix:///var/run/docker.sock']
        self.owned = []

    def command(self, *args, timeout=60):
        result = self.run(self.prefix + list(args), env=self.environment,
            capture_output=True, text=True, timeout=timeout)
        if result.returncode:
            raise RuntimeError('local Docker operation failed: ' + result.stderr[:2048])
        return result.stdout

    def create(self, *args):
        identity = self.command('create', *map(str, args), timeout=180).strip()
        if re.fullmatch('[0-9a-f]{64}', identity) is None:
            raise RuntimeError('Docker did not return an identifiable owned container')
        self.owned.append(identity)
        return identity

    def release(self, identity):
        if identity not in self.owned:
            raise PermissionError('cannot adopt or remove an unowned container')
        self.command('rm', '--force', identity, timeout=120)
        self.owned.remove(identity)

    def __enter__(self):
        return self

    def __exit__(self, *error):
        failures = []
        for identity in reversed(self.owned.copy()):
            try:
                self.release(identity)
            except Exception as failure:
                failures.append(failure)
        if failures:
            raise RuntimeError('owned disposable container cleanup failed') from failures[0]


def _uuid(value):
    if not isinstance(value, str) or str(UUID(value)) != value or UUID(value).int == 0:
        raise ValueError('canonical non-null evidence UUID required')


def validate_receipts(first, second, source_sha):
    fields = {'schema', 'result', 'source_sha', 'boot_id', 'platform_id', 'public_key_sha256',
        'generations', 'python', 'kernel', 'pid1', 'os_version', 'core_installed', 'ollama_installed',
        'graceful_stops', 'crash_recovered', 'duplicate_denied', 'production_authorized', 'release_accepted'}
    if not isinstance(source_sha, str) or re.fullmatch('[0-9a-f]{40}', source_sha) is None:
        raise ValueError('exact observed source SHA required')
    for row in (first, second):
        if type(row) is not dict or set(row) != fields:
            raise ValueError('VM receipt fields differ')
        if (row['schema'] != 'aegis.disposable.debian12-vm.v1' or row['result'] != 'PASS'
                or row['source_sha'] != source_sha or row['pid1'] != 'systemd' or row['os_version'] != '12'
                or row['core_installed'] is not False or row['ollama_installed'] is not False
                or row['crash_recovered'] is not True or row['duplicate_denied'] is not True or row['production_authorized'] is not False
                or row['release_accepted'] is not False or type(row['graceful_stops']) is not int
                or row['graceful_stops'] != 2):
            raise ValueError('VM receipt does not establish the disposable service contract')
        _uuid(row['boot_id'])
        _uuid(row['platform_id'])
        if (not isinstance(row['public_key_sha256'], str)
                or re.fullmatch('[0-9a-f]{64}', row['public_key_sha256']) is None
                or not isinstance(row['python'], str) or re.fullmatch(r'3\.12\.[0-9]+', row['python']) is None
                or not isinstance(row['kernel'], str) or not 1 <= len(row['kernel']) <= 255):
            raise ValueError('VM runtime/identity evidence differs')
        generations = row['generations']
        if (type(generations) is not list or len(generations) != 3
                or any(type(g) is not int or not 1 <= g <= 2**63-1 for g in generations)
                or not generations[0] < generations[1] < generations[2]):
            raise ValueError('VM generation did not advance')
    if (first['boot_id'] == second['boot_id'] or first['platform_id'] != second['platform_id']
            or first['public_key_sha256'] != second['public_key_sha256']
            or second['generations'][0] <= first['generations'][-1]):
        raise ValueError('VM reboot identity/generation continuity failed')
    return dict(schema='aegis.disposable.debian12-summary.v1',
        result='VERIFIED_DISPOSABLE_VM_CONTRACT', source_sha=source_sha,
        platform_id=first['platform_id'], boot_ids=[r['boot_id'] for r in (first, second)],
        generations=first['generations'] + second['generations'], graceful_stops=4,
        crash_recoveries=2, duplicate_denials=2, production_authorized=False, release_accepted=False)


def observed_source(checkout):
    def git(*args):
        return subprocess.run(['git', '-C', str(checkout), *args], check=True,
            capture_output=True, text=True, timeout=30).stdout.strip()
    source = git('rev-parse', 'HEAD')
    if re.fullmatch('[0-9a-f]{40}', source) is None or git('status', '--porcelain', '--untracked-files=no'):
        raise ValueError('disposable VM requires clean tracked source at an exact commit')
    return source


def build_and_boot(checkout: Path, output: Path, toolchain: Path, certificate: Path):
    if sys.platform != 'linux':
        raise RuntimeError('disposable Debian VM runner requires a Linux Docker host')
    output = fresh_output(output)
    checkout = Path(checkout).absolute()
    source = observed_source(checkout)
    for path in (checkout, toolchain, certificate):
        assert_no_redirected_components(path, include_leaf=True)
    if not (toolchain / 'bin/rustc').is_file() or not certificate.is_file():
        raise ValueError('installed Rust toolchain and public CA bundle required')
    with tempfile.TemporaryDirectory(prefix='aegis-vm-input-') as directory, \
            tempfile.TemporaryDirectory(prefix='aegis-vm-source-') as staged:
        context = Path(directory)
        reviewed = Path(staged)
        stage_reviewed_git_tree(checkout, reviewed)
        for component in ('sdk', 'platform'):
            build_component(component, context / 'wheels', repo=reviewed)
        for name in ('Cargo.toml', 'Cargo.lock'):
            shutil.copy2(reviewed / name, context / name)
        shutil.copytree(reviewed / 'rust', context / 'rust')
        for name in ('build.sh', 'probe.py'):
            shutil.copy2(reviewed / 'test/fixtures/aegis_debian_vm' / name, context / name)
        shutil.copy2(reviewed / 'packaging/services/aegis-platform.service', context / 'aegis-platform.service')
        manifest = dict(source_sha=source, base_image=BASE_IMAGE, production_authorized=False,
            release_accepted=False, files={p.relative_to(context).as_posix(): sha256(p.read_bytes()).hexdigest()
                for p in context.rglob('*') if p.is_file()})
        (context / 'inputs.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
        shutil.copy2(context / 'inputs.json', output / 'inputs.json')
        if observed_source(checkout) != source:
            raise ValueError('source changed while staging disposable VM inputs')
        with DockerSession() as docker:
            docker.command('pull', BASE_IMAGE, timeout=180)
            base = docker.create(BASE_IMAGE, 'true')
            docker.command('export', '--output', str(output / 'debian-python-rootfs.tar'), base, timeout=180)
            docker.release(base)
            helper = docker.create('--mount', f'type=bind,src={output},dst=/vm',
                '--mount', f'type=bind,src={context},dst=/input,readonly',
                '--mount', f'type=bind,src={toolchain},dst=/toolchain,readonly',
                '--mount', f'type=bind,src={certificate},dst=/run/proxy-ca.crt,readonly',
                '-e', 'PIP_CERT=/run/proxy-ca.crt', '-e', f'AEGIS_OUTPUT_UID={os.getuid()}',
                '-e', f'AEGIS_OUTPUT_GID={os.getgid()}', BASE_IMAGE, 'bash', '/input/build.sh')
            with (output / 'build-and-boot.log').open('w') as log:
                result = subprocess.run(docker.prefix + ['start', '--attach', helper], env=docker.environment,
                    stdout=log, stderr=subprocess.STDOUT, text=True, timeout=1500)
            if result.returncode:
                raise RuntimeError('disposable VM failed; retain build-and-boot.log, never accept partial receipts')
        if observed_source(checkout) != source:
            raise ValueError('source changed during disposable VM execution')
        first, second = [json.loads((output / f'receipt-{n}.json').read_text()) for n in (1, 2)]
        summary = validate_receipts(first, second, source)
        (output / 'summary.json').write_text(json.dumps(summary, indent=2, sort_keys=True) + '\n')
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkout', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--toolchain', type=Path, required=True)
    parser.add_argument('--certificate', type=Path, default=Path('/etc/ssl/certs/ca-certificates.crt'))
    parser.add_argument('--disposable-vm', action='store_true', required=True)
    args = parser.parse_args()
    print(build_and_boot(args.checkout, args.output, args.toolchain, args.certificate))


if __name__ == '__main__':
    main()
