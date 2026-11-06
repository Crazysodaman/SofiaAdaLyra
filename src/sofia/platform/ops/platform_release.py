"""Verify Platform-only release bytes. No install, selection or activation."""
from __future__ import annotations
import argparse
from email.parser import BytesParser
import json
from io import BytesIO
from pathlib import Path
import re
import struct
import zipfile
import unicodedata
import stat
import zlib

from sofia.sdk.artifact import validate_artifact_path

from sofia.platform.ops.component_install import Ed25519ComponentSignatureVerifier, CoreComponentInstallError
from sofia.platform.state.artifact_file import read_artifact_file
from sofia.platform.state.private_file import assert_no_redirected_components
from sofia.platform.verify.component_artifacts import inspect_wheel, ComponentArtifactError
from sofia.sdk.platform_release import PlatformReleaseManifest, PlatformReleaseTarget
from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.sdk.cognition_json import loads_strict_model_json


class PlatformReleaseRejected(PermissionError):
    pass


def _service_target(data, target):
    """Check architecture/ABI declarations, never execution health or authority."""
    if target is PlatformReleaseTarget.DEBIAN12_X86_64:
        if (len(data)<64 or data[:6]!=b'\x7fELF\x02\x01'
                or struct.unpack_from('<H',data,18)[0]!=62):
            raise PlatformReleaseRejected('service header does not match Debian12 x86_64')
        requirements=[tuple(int(v) for v in raw.split(b'.'))
            for raw in re.findall(rb'GLIBC_([0-9]+(?:\.[0-9]+){1,2})\x00',data)]
        if any(version>(2,36) for version in requirements):
            raise PlatformReleaseRejected('service requires a newer glibc than Debian12')
    else:
        if len(data)<64 or data[:2]!=b'MZ':
            raise PlatformReleaseRejected('service header does not match Windows')
        offset=struct.unpack_from('<I',data,60)[0]
        if (offset>len(data)-26 or data[offset:offset+4]!=b'PE\0\0'
                or struct.unpack_from('<H',data,offset+4)[0]!=0x8664
                or struct.unpack_from('<H',data,offset+24)[0]!=0x20b):
            raise PlatformReleaseRejected('service must declare a Windows x86_64 executable')


def _component_wheel(path,kind,version,data):
    # Reuse the existing metadata/content report after bounding the archive.
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            infos=archive.infolist()
            if len(infos)>8192 or sum(i.file_size for i in infos)>256*1024*1024:
                raise PlatformReleaseRejected('component archive exceeds policy bounds')
            metadata_files = [i for i in infos if i.filename.endswith('.dist-info/METADATA')]
            if len(metadata_files) != 1:
                raise PlatformReleaseRejected('exactly one component metadata file required')
            metadata_root = metadata_files[0].filename.rsplit('/', 1)[0]
            metadata = None
            names=set()
            for info in infos:
                if info.orig_filename != info.filename:
                    raise PlatformReleaseRejected('archive header name was normalized or truncated')
                name=info.filename.rstrip('/')
                validate_artifact_path(name)
                normalized=unicodedata.normalize('NFKC',name).casefold()
                if normalized in names or stat.S_ISLNK(info.external_attr>>16):
                    raise PlatformReleaseRejected('ambiguous or redirected wheel entry')
                names.add(normalized)
                package_prefix = 'sofia/' + kind + '/'
                if info.is_dir():
                    allowed = (name in {'sofia', 'sofia/' + kind, metadata_root}
                        or name.startswith(package_prefix) or name.startswith(metadata_root + '/'))
                else:
                    allowed = (name.startswith(package_prefix) or name.startswith(metadata_root + '/')
                        or (kind == 'sdk' and name == 'sofia/__init__.py'))
                if not allowed:
                    raise PlatformReleaseRejected('component contains payload outside its package ownership')
                if info.filename == metadata_files[0].filename:
                    if info.file_size > 262144:
                        raise PlatformReleaseRejected('component metadata exceeds bound')
                    metadata = BytesParser().parsebytes(archive.read(info))
            if metadata is None or any(len(metadata.get_all(field, [])) != 1 for field in ('Name', 'Version')):
                raise PlatformReleaseRejected('ambiguous component metadata')
        report=inspect_wheel(path,'sofia-'+kind,payload=data)
        forbidden=('sofia/core','sofia/modules','sofia/platform' if kind=='sdk' else 'sofia/sdk')
        if report.contains_any(forbidden) or (kind=='platform' and report.version!=version):
            raise PlatformReleaseRejected('component wheel violates Platform release scope/version')
        requirements = tuple(metadata.get_all('Requires-Dist', []))
        if kind=='sdk' and requirements:
            raise PlatformReleaseRejected('SDK must remain independently dependency-free')
        for requirement in requirements:
            name,_,marker=requirement.partition(';')
            match=re.match('[A-Za-z0-9][A-Za-z0-9._-]*',name.strip())
            normalized='' if match is None else re.sub('[-_.]+','-',match.group()).lower()
            if normalized=='sofia-core':
                raise PlatformReleaseRejected('Platform baseline cannot require Core')
            if normalized=='ollama' and marker.strip() not in {'extra == "ollama"',"extra == 'ollama'"}:
                raise PlatformReleaseRejected('inference must remain an explicit optional extra')
    except (zipfile.BadZipFile,zipfile.LargeZipFile,zlib.error,RuntimeError) as error:
        raise PlatformReleaseRejected('component wheel rejected') from error


class PlatformReleaseVerifier:
    def __init__(self,trusted_keys):
        self.signatures=Ed25519ComponentSignatureVerifier(trusted_keys)

    def verify(self,payload,*,signature_b64,signer_key_id,assets_root,expected_source_sha,
               expected_target,minimum_revision,expected_parent_manifest_sha256=None,state_schema_revision=1):
        try:
            manifest=PlatformReleaseManifest.from_payload(payload)
            if not isinstance(expected_target,PlatformReleaseTarget) or manifest.target is not expected_target:
                raise PlatformReleaseRejected('release target differs')
            if manifest.source_sha!=expected_source_sha:
                raise PlatformReleaseRejected('release source differs')
            if type(minimum_revision) is not int or minimum_revision<1 or manifest.revision<minimum_revision:
                raise PlatformReleaseRejected('release revision is below the trusted floor')
            if manifest.parent_manifest_sha256!=expected_parent_manifest_sha256:
                raise PlatformReleaseRejected('release parent differs')
            if manifest.sdk_protocol.major!=SDK_PROTOCOL_VERSION.major or manifest.sdk_protocol.minor>SDK_PROTOCOL_VERSION.minor:
                raise PlatformReleaseRejected('unsupported SDK protocol')
            if type(state_schema_revision) is not int or not manifest.state_schema_min <= state_schema_revision <= manifest.state_schema_max:
                raise PlatformReleaseRejected('unsupported Platform state schema')
            self.signatures.verify_digest(manifest.digest,signature_b64=signature_b64,signer_key_id=signer_key_id)
            root=Path(assets_root).absolute()
            assert_no_redirected_components(root,include_leaf=True)
            if not root.is_dir(): raise PlatformReleaseRejected('release root unavailable')
            for asset in manifest.assets:
                path=root.joinpath(*asset.reference.path.split('/'))
                if asset.kind in {'service','sdk','platform'} and asset.reference.size_bytes>64*1024*1024:
                    raise PlatformReleaseRejected('executable/component exceeds 64-MiB policy bound')
                digest,data=read_artifact_file(path,asset.reference.size_bytes,include_data=asset.kind in {'service','sdk','platform'})
                if digest!=asset.reference.sha256:
                    raise PlatformReleaseRejected('release artifact digest differs')
                if asset.kind in {'sdk','platform'}:
                    _component_wheel(path,asset.kind,manifest.version,data)
                if asset.kind=='service': _service_target(data,expected_target)
            return manifest  # Inert verified bytes, never an install/owner permit.
        except PlatformReleaseRejected:
            raise
        except (OSError,ValueError,TypeError,KeyError,CoreComponentInstallError,ComponentArtifactError) as error:
            raise PlatformReleaseRejected('signed Platform release rejected') from error


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--assets-root',type=Path,required=True)
    parser.add_argument('--trusted-public-key',type=Path,required=True)
    parser.add_argument('--signer-key-id',required=True)
    parser.add_argument('--signature',required=True)
    parser.add_argument('--expected-source-sha',required=True)
    parser.add_argument('--target',choices=[v.value for v in PlatformReleaseTarget],required=True)
    parser.add_argument('--minimum-revision',type=int,required=True)
    parser.add_argument('--expected-parent-sha256')
    args=parser.parse_args(argv)
    try:
        details=args.manifest.lstat()
        if not 1<=details.st_size<=131072: raise ValueError('manifest exceeds 128-KiB bound')
        _,raw=read_artifact_file(args.manifest,details.st_size,include_data=True)
        payload=loads_strict_model_json(raw.decode('utf-8'))
        verified=PlatformReleaseVerifier({args.signer_key_id:args.trusted_public_key}).verify(payload,
            signature_b64=args.signature,signer_key_id=args.signer_key_id,assets_root=args.assets_root,
            expected_source_sha=args.expected_source_sha,expected_target=PlatformReleaseTarget(args.target),
            minimum_revision=args.minimum_revision,expected_parent_manifest_sha256=args.expected_parent_sha256)
        print(json.dumps(dict(result='VERIFIED_PLATFORM_RELEASE_BYTES',release_id=verified.release_id,
            revision=verified.revision,manifest_sha256=verified.digest,activated=False),sort_keys=True))
        return 0
    except (OSError,ValueError,TypeError):
        print(json.dumps(dict(result='REJECTED',reason='Platform release verification denied'),sort_keys=True))
        return 2


if __name__=='__main__': raise SystemExit(main())
