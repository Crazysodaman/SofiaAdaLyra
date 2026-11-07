"""Test-only release signing and production staging for an explicit lab VM.

The disposable signer is generated in memory, never persisted, and is not an
owner principal or a production trust root. This is not an OS installer.
"""
from base64 import b64encode
from email.parser import BytesParser
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
import shutil
import zipfile

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sofia.platform.ops.platform_release import PlatformReleaseVerifier
from sofia.platform.ops.platform_release_staging import stage_platform_release
from sofia.platform.state.artifact_file import read_artifact_file
from sofia.platform.state.private_file import assert_no_redirected_components, ensure_owner_private_directory
from sofia.platform.verify.python_runtime import build_python_runtime
from sofia.sdk.artifact import ArtifactReference, validate_artifact_path
from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.sdk.cognition_json import loads_strict_model_json
from sofia.sdk.platform_release import PlatformReleaseAsset, PlatformReleaseManifest, PlatformReleaseTarget


def _snapshot(path):
    path=Path(path).absolute()
    assert_no_redirected_components(path,include_leaf=True)
    return read_artifact_file(path,path.stat(follow_symlinks=False).st_size,include_data=True)[1]


def _json(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def prepare_signed_vm_release(output,rootfs,*,source_sha,runtime_prefix,python_version,service,wheels):
    """Prepare genuine signed byte bindings using only disposable test trust."""
    output,rootfs=Path(output),Path(rootfs)
    encoded=_snapshot(output/'inputs.json')
    if len(encoded)>131072: raise ValueError('VM input index exceeds bound')
    inputs=loads_strict_model_json(encoded.decode('utf-8'))
    if not isinstance(source_sha,str) or source_sha!=inputs.get('source_sha') or re.fullmatch('[0-9a-f]{40}',source_sha) is None:
        raise ValueError('exact observed VM source required')
    if not 2<=len(wheels)<=89:
        raise ValueError('bounded mandatory wheel set required')
    assets_root=output/'release-assets'
    assets_root.mkdir(mode=0o700)
    assets=[]
    observed=[]
    seen=set()
    def add(kind,name,data):
        validate_artifact_path(name)
        if '/' in name or not name.isascii() or name.casefold() in seen:
            raise ValueError('unique plain artifact filenames required')
        seen.add(name.casefold())
        reference=ArtifactReference(name,sha256(data).hexdigest(),len(data))
        with (assets_root/name).open('xb') as stream: stream.write(data)
        assets.append(PlatformReleaseAsset(kind,reference))
        return reference
    for wheel in wheels:
        wheel=Path(wheel)
        raw=_snapshot(wheel)
        with zipfile.ZipFile(BytesIO(raw)) as archive:
            metadata=[item for item in archive.infolist() if item.filename.endswith('.dist-info/METADATA')]
            if len(metadata)!=1 or metadata[0].file_size>262144:
                raise ValueError('bounded wheel metadata required')
            details=BytesParser().parsebytes(archive.read(metadata[0]))
        name,version=details.get('Name'),details.get('Version')
        if not isinstance(name,str) or not isinstance(version,str):
            raise ValueError('wheel identity required')
        normalized=re.sub('[-_.]+','-',name).lower()
        if normalized in {'sofia-core','ollama'}:
            raise ValueError('disposable Platform baseline cannot include Core/inference')
        kind={'sofia-sdk':'sdk','sofia-platform':'platform'}.get(normalized,'dependency')
        reference=add(kind,wheel.name,raw)
        observed.append(dict(distribution=name,version=version,artifact=reference.to_payload()))
    add('service','aegis-platform-service',_snapshot(service))
    runtime=build_python_runtime(runtime_prefix,output/'python-runtime.zip',
        target=PlatformReleaseTarget.DEBIAN12_X86_64,python_version=python_version)
    add('python-runtime',runtime.reference.path,_snapshot(output/runtime.reference.path))
    (output/'runtime-reference.json').write_bytes(_json(runtime.reference.to_payload()))
    add('dependency-lock','dependency-index.json',_json(dict(
        schema='aegis.disposable.vm.dependency-index.v1',wheels=observed,production_authorized=False)))
    add('sbom','observed-sbom.json',_json(dict(schema='aegis.disposable.vm.sbom.v1',
        packages=observed,python_version=python_version,standards_compliance_claimed=False)))
    add('provenance','assembly-provenance.json',_json(dict(schema='aegis.disposable.vm.provenance.v1',
        observed_source_sha=source_sha,base_image=inputs.get('base_image'),
        input_index_sha256=sha256(_json(inputs)).hexdigest(),
        artifact_hashes={item.reference.path:item.reference.sha256 for item in assets},
        production_release_attested=False)))
    manifest=PlatformReleaseManifest('disposable-vm-release','0.1.0',1,source_sha,
        PlatformReleaseTarget.DEBIAN12_X86_64,SDK_PROTOCOL_VERSION,python_version,tuple(assets))
    key=Ed25519PrivateKey.generate()
    public=key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)
    signature=b64encode(key.sign(manifest.digest.encode('ascii'))).decode('ascii')
    signer='disposable-vm-release'
    envelope=dict(disposable_only=True,manifest=manifest.to_payload(),signer_key_id=signer,
        signature_b64=signature,public_key_pem=public.decode('ascii'))
    (output/'test-release-envelope.json').write_bytes(_json(envelope))
    parent=rootfs/'opt/aegis'
    ensure_owner_private_directory(parent)
    receipt=stage_platform_release(verifier=PlatformReleaseVerifier({signer:public}),
        payload=manifest.to_payload(),signature_b64=signature,signer_key_id=signer,
        assets_root=assets_root,destination=parent/'staged-release',expected_source_sha=source_sha,
        expected_target=manifest.target,minimum_revision=1)
    (output/'test-release-stage.json').write_bytes(_json(receipt))
    shutil.copyfile(output/'test-release-envelope.json',parent/'test-release-envelope.json')
    return receipt


if __name__=='__main__':
    import argparse
    import sys
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disposable-vm',action='store_true',required=True)
    parser.parse_args()
    root=Path('/vm')
    inputs=json.loads(_snapshot(root/'inputs.json'))
    result=prepare_signed_vm_release(root,root/'rootfs',source_sha=inputs['source_sha'],
        runtime_prefix=Path(sys.base_prefix),python_version='.'.join(map(str,sys.version_info[:3])),
        service=root/'target/release/aegis-platform-service',wheels=tuple((root/'dependencies').glob('*.whl')))
    print(json.dumps(result,sort_keys=True))
