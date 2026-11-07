"""Disposable VM tooling must not adopt output, remote daemons or fake receipts."""
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid5, NAMESPACE_URL

import pytest

from tools.aegis_debian_vm import DockerSession, fresh_output, validate_receipts


def test_existing_output_is_preserved_before_any_container_can_start(tmp_path):
    output = tmp_path / 'existing'
    output.mkdir()
    marker = output / 'keep'
    marker.write_text('concurrent work')
    with pytest.raises(FileExistsError):
        fresh_output(output)
    assert marker.read_text() == 'concurrent work'


def test_redirected_output_parent_is_denied(tmp_path):
    import os
    if os.name == 'nt':
        pytest.skip('Linux Docker VM runner path contract')
    real = tmp_path / 'real'
    real.mkdir()
    link = tmp_path / 'redirect'
    link.symlink_to(real, target_is_directory=True)
    with pytest.raises((OSError, ValueError)):
        fresh_output(link / 'new')
    assert not (real / 'new').exists()


def test_container_cleanup_is_limited_to_created_ids_and_uses_local_daemon():
    calls = []
    def run(args, **kwargs):
        calls.append((args, kwargs['env']))
        return SimpleNamespace(returncode=0, stdout='a' * 64 + '\n', stderr='')
    with DockerSession(run=run, environment={'DOCKER_HOST':'tcp://unapproved',
            'DOCKER_CONTEXT':'other', 'DOCKER_TLS_VERIFY':'1', 'DOCKER_CERT_PATH':'elsewhere',
            'HTTPS_PROXY':'retained-proxy'}) as docker:
        docker.create('pinned-image', 'true')
    assert len(calls) == 2
    assert all(args[:2] == ['docker', '--host=unix:///var/run/docker.sock'] for args, _ in calls)
    assert calls[1][0][2:] == ['rm', '--force', 'a' * 64]
    assert all('DOCKER_HOST' not in env and 'DOCKER_CONTEXT' not in env and
        'DOCKER_TLS_VERIFY' not in env and 'DOCKER_CERT_PATH' not in env for _, env in calls)
    assert all(env['HTTPS_PROXY'] == 'retained-proxy' for _, env in calls)


def test_unrecognized_container_id_is_not_adopted_or_deleted():
    calls = []
    def run(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout='existing-production-name\n', stderr='')
    with pytest.raises(RuntimeError):
        with DockerSession(run=run, environment={}) as docker:
            docker.create('pinned-image', 'true')
    assert len(calls) == 1


def receipt(boot='first', generations=(1, 2, 3)):
    return dict(schema='aegis.disposable.debian12-vm.v1', result='PASS', source_sha='a'*40,
        boot_id=str(uuid5(NAMESPACE_URL,boot)), platform_id='11111111-1111-4111-8111-111111111111', public_key_sha256='b'*64,
        generations=list(generations), python='3.12.16', kernel='6.1-test', pid1='systemd',
        os_version='12', core_installed=False, ollama_installed=False, graceful_stops=2,
        crash_recovered=True, duplicate_denied=True, production_authorized=False, release_accepted=False)


@pytest.mark.parametrize('defect', ['replay', 'identity', 'generation', 'core', 'source', 'release'])
def test_unverified_or_replayed_vm_evidence_cannot_pass(defect):
    first, second = receipt(), receipt('second', (4, 5, 6))
    if defect == 'replay': second['boot_id'] = first['boot_id']
    elif defect == 'identity': second['platform_id'] = 'different'
    elif defect == 'generation': second['generations'] = [1, 2, 3]
    elif defect == 'core': second['core_installed'] = True
    elif defect == 'source': second['source_sha'] = 'c'*40
    elif defect == 'release': second['release_accepted'] = True
    with pytest.raises(ValueError):
        validate_receipts(first, second, 'a'*40)


def test_two_fresh_boots_keep_identity_without_granting_release_acceptance():
    summary = validate_receipts(receipt(), receipt('second', (4, 5, 6)), 'a'*40)
    assert summary['result'] == 'VERIFIED_DISPOSABLE_VM_CONTRACT'
    assert summary['duplicate_denials'] == 2
    assert summary['production_authorized'] is False
    assert summary['release_accepted'] is False


def test_failed_vm_start_cleans_both_owned_containers_only():
    calls = []
    identities = iter(('a' * 64, 'b' * 64))
    def run(args, **kwargs):
        calls.append(args)
        if args[2] == 'create':
            return SimpleNamespace(returncode=0, stdout=next(identities), stderr='')
        return SimpleNamespace(returncode=1 if args[2] == 'start' else 0, stdout='', stderr='injected failure')
    with pytest.raises(RuntimeError):
        with DockerSession(run=run, environment={}) as docker:
            docker.create('base', 'true')
            helper = docker.create('base', 'helper')
            docker.command('start', '--attach', helper)
    assert [args[-1] for args in calls if args[2] == 'rm'] == ['b' * 64, 'a' * 64]


def test_one_cleanup_failure_does_not_strand_other_owned_container_or_report_success():
    removed = []
    identities = iter(('a' * 64, 'b' * 64))
    def run(args, **kwargs):
        if args[2] == 'create':
            return SimpleNamespace(returncode=0, stdout=next(identities), stderr='')
        removed.append(args[-1])
        return SimpleNamespace(returncode=int(args[-1] == 'b' * 64), stdout='', stderr='injected cleanup failure')
    with pytest.raises(RuntimeError, match='cleanup failed'):
        with DockerSession(run=run, environment={}) as docker:
            docker.create('base', 'true')
            docker.create('base', 'helper')
    assert removed == ['b' * 64, 'a' * 64]


def test_exported_base_can_be_released_early_without_adopting_foreign_container():
    calls = []
    identities = iter(('a' * 64, 'b' * 64))
    def run(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0,
            stdout=next(identities) if args[2] == 'create' else '', stderr='')
    with DockerSession(run=run, environment={}) as docker:
        base = docker.create('base', 'true')
        docker.release(base)
        with pytest.raises(PermissionError):
            docker.release('f' * 64)
        docker.create('base', 'helper')
    assert [args[-1] for args in calls if args[2] == 'rm'] == ['a' * 64, 'b' * 64]
    assert [args[2] for args in calls] == ['create', 'rm', 'create', 'rm']


def test_public_artifacts_must_be_present_readable_and_match_observed_build(tmp_path):
    from hashlib import sha256
    import json
    from tools.aegis_debian_vm import verify_public_artifacts
    binary = tmp_path / 'target/release/aegis-platform-service'
    binary.parent.mkdir(parents=True)
    binary.write_bytes(b'compiled service fixture')
    wheel = tmp_path / 'dependencies/sofia_sdk-0.1.0-py3-none-any.whl'
    wheel.parent.mkdir()
    wheel.write_bytes(b'wheel fixture')
    record = {p.name: sha256(p.read_bytes()).hexdigest() for p in (binary, wheel)}
    (tmp_path / 'built-artifacts.json').write_text(json.dumps(record))
    assert len(verify_public_artifacts(tmp_path)) == 2
    wheel.write_bytes(b'tampered')
    with pytest.raises(ValueError):
        verify_public_artifacts(tmp_path)
    import os
    if os.name == 'posix' and os.getuid() != 0:
        wheel.write_bytes(b'wheel fixture')
        wheel.chmod(0)
        try:
            with pytest.raises(PermissionError):
                verify_public_artifacts(tmp_path)
        finally:
            wheel.chmod(0o600)
    wheel.unlink()
    with pytest.raises(OSError):
        verify_public_artifacts(tmp_path)


def test_artifact_index_cannot_select_private_vm_state(tmp_path):
    import json
    from tools.aegis_debian_vm import verify_public_artifacts
    (tmp_path / 'built-artifacts.json').write_text(json.dumps({'platform.ext4': 'a' * 64}))
    with pytest.raises(ValueError):
        verify_public_artifacts(tmp_path)
