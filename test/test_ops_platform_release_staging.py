"""Signed candidate code staging is separate from installation authority."""
from base64 import b64encode
from dataclasses import replace

import pytest

from sofia.platform.ops.platform_release import PlatformReleaseVerifier
from sofia.platform.ops.platform_release_staging import stage_platform_release
from sofia.sdk.platform_release import PlatformReleaseTarget, PlatformReleaseManifest
from sofia.platform.verify.python_runtime import build_python_runtime
from test.test_platform_release_verifier import fixture_release, platform_wheels
from test.test_python_runtime_artifacts import fake_prefix

pytestmark = pytest.mark.pkg_ops


def candidate_path(tmp_path):
    from sofia.platform.state.private_file import ensure_owner_private_directory
    parent=tmp_path/'staging'
    ensure_owner_private_directory(parent)
    return parent/'candidate'


def signed_candidate(tmp_path, platform_wheels, runtime_version='3.12.16'):
    source=tmp_path/'source'
    source.mkdir()
    manifest,key,public,_=fixture_release(source,platform_wheels)
    runtime=build_python_runtime(fake_prefix(source),source/'python-runtime.zip',
        target=manifest.target,python_version=runtime_version)
    manifest=replace(manifest,assets=tuple(replace(item,reference=runtime.reference)
        if item.kind=='python-runtime' else item for item in manifest.assets))
    signature=b64encode(key.sign(manifest.digest.encode())).decode()
    return manifest,public,signature,source


def test_signed_candidate_stages_exact_code_without_installing_or_opening_state(tmp_path,platform_wheels):
    args=arguments(tmp_path,platform_wheels)
    receipt=stage_platform_release(**args)
    manifest=PlatformReleaseManifest.from_payload(args['payload'])
    source=args['assets_root']
    assert receipt['result']=='VERIFIED_PLATFORM_CODE_STAGED'
    assert receipt['manifest_sha256']==manifest.digest
    assert receipt['activated'] is False
    assert receipt['service_health_verified'] is False
    for item in manifest.assets:
        assert (tmp_path/'staging/candidate/assets'/item.reference.path).read_bytes()==(source/item.reference.path).read_bytes()
    assert (tmp_path/'staging/candidate/runtime/python/bin/python3.12').read_bytes().startswith(b'\x7fELF')
    assert not list((tmp_path/'staging/candidate').rglob('*.db'))


def arguments(tmp_path,platform_wheels):
    manifest,public,signature,source=signed_candidate(tmp_path,platform_wheels)
    return dict(verifier=PlatformReleaseVerifier({'disposable':public}),payload=manifest.to_payload(),
        signature_b64=signature,signer_key_id='disposable',assets_root=source,
        destination=candidate_path(tmp_path),expected_source_sha='a'*40,
        expected_target=manifest.target,minimum_revision=1)


def test_bad_signature_cannot_observe_candidate_or_artifact_paths(tmp_path,platform_wheels,monkeypatch):
    from pathlib import Path
    from sofia.platform.ops.platform_release import PlatformReleaseRejected
    args=arguments(tmp_path,platform_wheels)
    args['signature_b64']=b64encode(b'x'*64).decode()
    def denied(*args,**kwargs):
        raise AssertionError('unverified release must not observe paths')
    monkeypatch.setattr(Path,'stat',denied)
    with pytest.raises(PlatformReleaseRejected):
        stage_platform_release(**args)


def test_existing_candidate_is_never_overwritten(tmp_path,platform_wheels):
    args=arguments(tmp_path,platform_wheels)
    args['destination'].mkdir()
    marker=args['destination']/'preserve'
    marker.write_bytes(b'concurrent work')
    with pytest.raises(FileExistsError):
        stage_platform_release(**args)
    assert marker.read_bytes()==b'concurrent work'
    assert list(args['destination'].iterdir())==[marker]


def test_source_change_after_initial_verification_leaves_quarantined_candidate(tmp_path,platform_wheels,monkeypatch):
    from sofia.platform.ops.platform_release import PlatformReleaseRejected
    args=arguments(tmp_path,platform_wheels)
    verifier=args['verifier']
    original=verifier.verify
    def change_after_verification(*values,**options):
        manifest=original(*values,**options)
        reference=next(item.reference for item in manifest.assets if item.kind=='sdk')
        (args['assets_root']/reference.path).write_bytes(b'changed after verification')
        return manifest
    monkeypatch.setattr(verifier,'verify',change_after_verification)
    with pytest.raises((OSError,ValueError)):
        stage_platform_release(**args)
    assert args['destination'].is_dir()
    assert not (args['destination']/'stage-receipt.json').exists()
    with pytest.raises(PlatformReleaseRejected):
        original(args['payload'],signature_b64=args['signature_b64'],signer_key_id='disposable',
            assets_root=args['assets_root'],expected_source_sha='a'*40,
            expected_target=PlatformReleaseTarget.DEBIAN12_X86_64,minimum_revision=1)


def test_copy_uses_same_verified_snapshot_even_if_source_path_changes(tmp_path,platform_wheels,monkeypatch):
    import sofia.platform.ops.platform_release_staging as staging
    args=arguments(tmp_path,platform_wheels)
    sdk=next(item['reference'] for item in args['payload']['assets'] if item['kind']=='sdk')
    path=args['assets_root']/sdk['path']
    expected=path.read_bytes()
    original=staging.read_artifact_file
    def change_after_read(selected,*values,**options):
        result=original(selected,*values,**options)
        if selected==path:
            path.write_bytes(b'untrusted replacement after snapshot')
        return result
    monkeypatch.setattr(staging,'read_artifact_file',change_after_read)
    assert stage_platform_release(**args)['activated'] is False
    assert (args['destination']/'assets'/sdk['path']).read_bytes()==expected


def test_disk_failure_never_returns_a_success_receipt(tmp_path,platform_wheels,monkeypatch):
    import sofia.platform.ops.platform_release_staging as staging
    args=arguments(tmp_path,platform_wheels)
    def fail(*values):
        raise OSError('injected disk failure')
    monkeypatch.setattr(staging.os,'fsync',fail)
    with pytest.raises(OSError):
        stage_platform_release(**args)
    assert args['destination'].is_dir()
    assert not (args['destination']/'stage-receipt.json').exists()


def test_signed_outer_release_cannot_hide_incompatible_runtime(tmp_path,platform_wheels):
    manifest,public,signature,source=signed_candidate(tmp_path,platform_wheels,'3.12.17')
    destination=candidate_path(tmp_path)
    with pytest.raises(ValueError,match='target/version'):
        stage_platform_release(verifier=PlatformReleaseVerifier({'disposable':public}),
            payload=manifest.to_payload(),signature_b64=signature,signer_key_id='disposable',
            assets_root=source,destination=destination,expected_source_sha='a'*40,
            expected_target=manifest.target,minimum_revision=1)
    assert destination.exists()
    assert not (destination/'stage-receipt.json').exists()


def test_corrupt_staged_copy_is_rejected_before_receipt(tmp_path,platform_wheels,monkeypatch):
    import sofia.platform.ops.platform_release_staging as staging
    args=arguments(tmp_path,platform_wheels)
    original=staging._write_new
    def corrupt(path,data):
        original(path,data)
        if path.suffix=='.whl':
            path.write_bytes(b'corrupt copied wheel')
    monkeypatch.setattr(staging,'_write_new',corrupt)
    with pytest.raises((OSError,ValueError)):
        stage_platform_release(**args)
    assert not (args['destination']/'stage-receipt.json').exists()


def test_redirected_candidate_parent_is_rejected_without_writes(tmp_path,platform_wheels):
    import os
    import subprocess
    args=arguments(tmp_path,platform_wheels)
    real=tmp_path/'private-parent'
    real.mkdir(mode=0o700)
    link=tmp_path/'redirect'
    if os.name=='nt':
        subprocess.run(['cmd','/c','mklink','/J',str(link),str(real)],check=True,capture_output=True)
    else:
        link.symlink_to(real,target_is_directory=True)
    args['destination']=link/'candidate'
    with pytest.raises((OSError,ValueError)):
        stage_platform_release(**args)
    assert not list(real.iterdir())
