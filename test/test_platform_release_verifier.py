"""Signed Platform release verification does not activate any installed state."""
from base64 import b64encode
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import json
import struct

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sofia.sdk.artifact import ArtifactReference
from sofia.sdk.platform_release import PlatformReleaseManifest, PlatformReleaseAsset, PlatformReleaseTarget
from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.platform.ops.platform_release import PlatformReleaseVerifier, PlatformReleaseRejected
from sofia.platform.verify.component_artifacts import build_component


@pytest.fixture(scope='module')
def platform_wheels(tmp_path_factory):
    root=Path(__file__).resolve().parents[1]
    destination=tmp_path_factory.mktemp('release-wheels')
    return {kind:build_component(kind,destination,repo=root) for kind in ['sdk','platform']}


def fixture_release(tmp_path,platform_wheels,glibc='2.34'):
    assets=[]
    # Header/ABI fixture is signed inert test data, not an activated service.
    elf=bytearray(64)
    elf[:6]=b'\x7fELF\x02\x01'
    struct.pack_into('<H',elf,18,62)
    contents={'service':bytes(elf)+b'GLIBC_'+glibc.encode()+b'\0','python-runtime':b'test-runtime',
        'dependency-lock':b'# test-only lock\n','sbom':b'{}','provenance':b'test-only provenance'}
    for kind,wheel in platform_wheels.items():
        contents[kind]=wheel.read_bytes()
    for kind,data in contents.items():
        filename=platform_wheels[kind].name if kind in platform_wheels else kind+'.bin'
        (tmp_path/filename).write_bytes(data)
        assets.append(PlatformReleaseAsset(kind,ArtifactReference(filename,sha256(data).hexdigest(),len(data))))
    manifest=PlatformReleaseManifest('platform-rc1','0.1.0',1,'a'*40,PlatformReleaseTarget.DEBIAN12_X86_64,
        SDK_PROTOCOL_VERSION,'3.12.16',tuple(assets))
    key=Ed25519PrivateKey.generate()
    public=key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)
    signature=b64encode(key.sign(manifest.digest.encode())).decode()
    return manifest,key,public,signature


def verify(tmp_path,manifest,public,signature,**changes):
    args=dict(signature_b64=signature,signer_key_id='test-release',assets_root=tmp_path,
        expected_source_sha='a'*40,expected_target=PlatformReleaseTarget.DEBIAN12_X86_64,minimum_revision=1)
    args.update(changes)
    return PlatformReleaseVerifier({'test-release':public}).verify(manifest.to_payload(),**args)


def test_signed_platform_bundle_is_read_only_and_contains_no_core(tmp_path,platform_wheels):
    manifest,_,public,signature=fixture_release(tmp_path,platform_wheels)
    before={p.name:p.read_bytes() for p in tmp_path.iterdir()}
    assert verify(tmp_path,manifest,public,signature)==manifest
    assert {p.name:p.read_bytes() for p in tmp_path.iterdir()}==before
    assert not list(tmp_path.rglob('*.db'))


@pytest.mark.parametrize('defect',['signature','source','target','revision','parent','tampered','too_new_glibc'])
def test_release_rejects_wrong_signature_binding_revision_or_bytes(tmp_path,platform_wheels,defect):
    manifest,key,public,signature=fixture_release(tmp_path,platform_wheels, '2.39' if defect=='too_new_glibc' else '2.34')
    changes={}
    if defect=='signature': signature=b64encode(b'x'*64).decode()
    elif defect=='source': changes['expected_source_sha']='b'*40
    elif defect=='target': changes['expected_target']=PlatformReleaseTarget.WINDOWS_X86_64
    elif defect=='revision': changes['minimum_revision']=2
    elif defect=='parent': changes['expected_parent_manifest_sha256']='c'*64
    elif defect=='tampered': (tmp_path/'service.bin').write_bytes(b'tampered')
    with pytest.raises(PlatformReleaseRejected): verify(tmp_path,manifest,public,signature,**changes)


def test_bad_signature_does_not_observe_artifact_root(tmp_path,platform_wheels,monkeypatch):
    manifest,_,public,_=fixture_release(tmp_path,platform_wheels)
    def denied(*args,**kwargs): raise AssertionError('must not inspect unsigned artifacts')
    monkeypatch.setattr(Path,'stat',denied)
    with pytest.raises(PlatformReleaseRejected):
        verify(tmp_path,manifest,public,b64encode(b'x'*64).decode())


def test_component_report_uses_one_byte_snapshot(tmp_path,platform_wheels,monkeypatch):
    import io
    import zipfile
    from sofia.platform.verify.component_artifacts import inspect_wheel
    path=tmp_path/'mutable.whl'
    original=platform_wheels['sdk'].read_bytes()
    changed=io.BytesIO(original)
    with zipfile.ZipFile(changed,'a') as archive:
        archive.writestr('sofia/core/synthetic.py',b'# synthetic forbidden payload')
    path.write_bytes(original)
    actual=Path.read_bytes
    def swap_after_read(self):
        data=actual(self)
        if self==path: self.write_bytes(changed.getvalue())
        return data
    monkeypatch.setattr(Path,'read_bytes',swap_after_read)
    report=inspect_wheel(path,'sofia-sdk')
    assert report.sha256==sha256(original).hexdigest()
    assert not report.contains('sofia/core')


def test_signed_forbidden_wheel_cannot_swap_to_benign_during_inspection(tmp_path,platform_wheels,monkeypatch):
    import io
    import zipfile
    import sofia.platform.ops.platform_release as operation
    manifest,key,public,_=fixture_release(tmp_path,platform_wheels)
    sdk=next(a for a in manifest.assets if a.kind=='sdk')
    path=tmp_path/sdk.reference.path
    benign=path.read_bytes()
    changed=io.BytesIO(benign)
    with zipfile.ZipFile(changed,'a') as archive:
        archive.writestr('sofia/core/synthetic.py',b'# forbidden synthetic Core')
    bad=changed.getvalue()
    path.write_bytes(bad)
    updated=replace(sdk,reference=ArtifactReference(sdk.reference.path,sha256(bad).hexdigest(),len(bad)))
    manifest=replace(manifest,assets=tuple(updated if a.kind=='sdk' else a for a in manifest.assets))
    signature=b64encode(key.sign(manifest.digest.encode())).decode()
    read=operation.read_artifact_file
    def swapped(file,*args,**kwargs):
        result=read(file,*args,**kwargs)
        if file==path: path.write_bytes(benign)
        return result
    monkeypatch.setattr(operation,'read_artifact_file',swapped)
    with pytest.raises(PlatformReleaseRejected): verify(tmp_path,manifest,public,signature)


@pytest.mark.parametrize('location',['root','ancestor'])
def test_release_rejects_redirected_package_before_hashing(tmp_path,platform_wheels,location,monkeypatch):
    import os
    import subprocess
    parent=tmp_path/'real'
    parent.mkdir()
    package=parent/'package'
    package.mkdir()
    manifest,_,public,signature=fixture_release(package,platform_wheels)
    link=tmp_path/'redirect'
    target=package if location=='root' else parent
    if os.name=='nt':
        subprocess.run(['cmd','/c','mklink','/J',str(link),str(target)],check=True,capture_output=True)
    else: link.symlink_to(target,target_is_directory=True)
    root=link if location=='root' else link/'package'
    import sofia.platform.ops.platform_release as operation
    def denied(*args,**kwargs): raise AssertionError('redirected assets must not be hashed')
    monkeypatch.setattr(operation,'read_artifact_file',denied)
    with pytest.raises(PlatformReleaseRejected): verify(root,manifest,public,signature)


def test_release_cli_denial_is_structured_and_never_activates(tmp_path,platform_wheels,capsys):
    from sofia.platform.ops.platform_release import main
    manifest,_,public,_=fixture_release(tmp_path,platform_wheels)
    definition=tmp_path/'manifest.json'
    definition.write_text(json.dumps(manifest.to_payload()))
    key=tmp_path/'trusted.pem'
    key.write_bytes(public)
    result=main(['--manifest',str(definition),'--assets-root',str(tmp_path),'--trusted-public-key',str(key),
        '--signer-key-id','test-release','--signature',b64encode(b'x'*64).decode(),
        '--expected-source-sha','a'*40,'--target','debian12-x86_64','--minimum-revision','1'])
    assert result==2
    assert json.loads(capsys.readouterr().out)['result']=='REJECTED'
    assert not list(tmp_path.rglob('*.db'))


def replace_signed_asset(tmp_path, manifest, key, kind, data):
    asset = next(item for item in manifest.assets if item.kind == kind)
    (tmp_path / asset.reference.path).write_bytes(data)
    updated = replace(asset, reference=ArtifactReference(
        asset.reference.path, sha256(data).hexdigest(), len(data)))
    manifest = replace(manifest, assets=tuple(
        updated if item.kind == kind else item for item in manifest.assets))
    return manifest, b64encode(key.sign(manifest.digest.encode())).decode()


@pytest.mark.parametrize('defect', ['invalid_zip', 'sdk_dependency', 'core_dependency', 'duplicate_entry', 'core_case', 'data_relocation', 'lowercase_dependency', 'nul_header'])
def test_signed_component_content_still_obeys_platform_boundary(tmp_path, platform_wheels, defect):
    import io
    import zipfile
    manifest, key, public, _ = fixture_release(tmp_path, platform_wheels)
    kind = 'platform' if defect == 'core_dependency' else 'sdk'
    source = platform_wheels[kind].read_bytes()
    output = io.BytesIO()
    if defect != 'invalid_zip':
        with zipfile.ZipFile(io.BytesIO(source)) as original, zipfile.ZipFile(output, 'w') as archive:
            for entry in original.infolist():
                data = original.read(entry)
                if entry.filename.endswith('.dist-info/METADATA'):
                    if defect == 'sdk_dependency': data += b'Requires-Dist: unexpected-runtime\n'
                    if defect == 'lowercase_dependency': data += b'requires-dist: unexpected-runtime\n'
                    if defect == 'core_dependency': data += b'Requires-Dist: sofia-core; extra == "core"\n'
                archive.writestr(entry, data)
            if defect == 'nul_header': archive.writestr('sofia/sdk/partXignored.py', b'# ambiguous original header')
            if defect == 'core_case': archive.writestr('SOFIA/CORE/synthetic.py', b'# forbidden Core')
            if defect == 'data_relocation': archive.writestr('sofia_sdk-0.1.0.data/purelib/sofia/core/synthetic.py', b'# forbidden relocation')
            if defect == 'duplicate_entry':
                # A case variant is a different ZIP name but an ambiguous Windows path.
                archive.writestr('SOFIA/SDK/__INIT__.PY', b'# ambiguous package path')
    data = b'invalid archive' if defect == 'invalid_zip' else output.getvalue()
    if defect == 'nul_header': data = data.replace(b'partXignored.py', b'part\0ignored.py')
    manifest, signature = replace_signed_asset(tmp_path, manifest, key, kind, data)
    with pytest.raises(PlatformReleaseRejected):
        verify(tmp_path, manifest, public, signature)


@pytest.mark.parametrize('defect', ['none', 'architecture', 'format'])
def test_windows_service_header_is_checked_without_execution(tmp_path, platform_wheels, defect):
    manifest, key, public, _ = fixture_release(tmp_path, platform_wheels)
    pe = bytearray(128)
    pe[:2] = b'MZ'
    struct.pack_into('<I', pe, 60, 64)
    pe[64:68] = b'PE\0\0'
    struct.pack_into('<H', pe, 68, 0x14c if defect == 'architecture' else 0x8664)
    struct.pack_into('<H', pe, 88, 0x10b if defect == 'format' else 0x20b)
    manifest = replace(manifest, target=PlatformReleaseTarget.WINDOWS_X86_64)
    manifest, signature = replace_signed_asset(tmp_path, manifest, key, 'service', bytes(pe))
    if defect == 'none':
        assert verify(tmp_path, manifest, public, signature,
            expected_target=PlatformReleaseTarget.WINDOWS_X86_64) == manifest
    else:
        with pytest.raises(PlatformReleaseRejected):
            verify(tmp_path, manifest, public, signature,
                expected_target=PlatformReleaseTarget.WINDOWS_X86_64)


def test_state_schema_and_protocol_are_verified_even_with_trusted_signature(tmp_path, platform_wheels):
    from sofia.sdk.contracts import ProtocolVersion
    manifest, key, public, signature = fixture_release(tmp_path, platform_wheels)
    with pytest.raises(PlatformReleaseRejected):
        verify(tmp_path, manifest, public, signature, state_schema_revision=2)
    manifest = replace(manifest, sdk_protocol=ProtocolVersion(SDK_PROTOCOL_VERSION.major + 1, 0))
    signature = b64encode(key.sign(manifest.digest.encode())).decode()
    with pytest.raises(PlatformReleaseRejected):
        verify(tmp_path, manifest, public, signature)


def test_release_cli_success_reports_bytes_only(tmp_path, platform_wheels, capsys):
    from sofia.platform.ops.platform_release import main
    manifest, _, public, signature = fixture_release(tmp_path, platform_wheels)
    definition = tmp_path / 'manifest.json'
    definition.write_text(json.dumps(manifest.to_payload()))
    key = tmp_path / 'trusted.pem'
    key.write_bytes(public)
    assert main(['--manifest', str(definition), '--assets-root', str(tmp_path),
        '--trusted-public-key', str(key), '--signer-key-id', 'test-release',
        '--signature', signature, '--expected-source-sha', 'a' * 40,
        '--target', 'debian12-x86_64', '--minimum-revision', '1']) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['result'] == 'VERIFIED_PLATFORM_RELEASE_BYTES'
    assert result['activated'] is False
    assert not list(tmp_path.rglob('*.db'))
