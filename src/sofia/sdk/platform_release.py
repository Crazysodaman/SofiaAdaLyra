"""Platform-only signed release metadata, independent of any personal Core."""
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from pathlib import PureWindowsPath
import re

from sofia.sdk.artifact import ArtifactReference
from sofia.sdk.contracts import ProtocolVersion

PLATFORM_RELEASE_SCHEMA = 'aegis.platform.release.v1'
_DOMAIN = PLATFORM_RELEASE_SCHEMA.encode()+b'\0'
_REQUIRED = frozenset({'sdk','platform','service','python-runtime','dependency-lock','sbom','provenance'})


class PlatformReleaseTarget(str, Enum):
    WINDOWS_X86_64 = 'windows-x86_64'
    DEBIAN12_X86_64 = 'debian12-x86_64'


@dataclass(frozen=True, slots=True)
class PlatformReleaseAsset:
    kind: str
    reference: ArtifactReference

    def __post_init__(self):
        if self.kind not in _REQUIRED | {'dependency'}:
            raise ValueError('unsupported Platform release asset kind')
        if not isinstance(self.reference, ArtifactReference) or not self.reference.path.isascii():
            raise ValueError('typed ASCII Platform artifact reference required')

    def to_payload(self):
        return dict(kind=self.kind, reference=self.reference.to_payload())

    @classmethod
    def from_payload(cls, value):
        if type(value) is not dict or set(value) != {'kind','reference'}:
            raise ValueError('Platform asset fields differ')
        return cls(value['kind'], ArtifactReference.from_payload(value['reference']))


@dataclass(frozen=True, slots=True)
class PlatformReleaseManifest:
    """Inert metadata: signature verification never grants install authority."""
    release_id: str
    version: str
    revision: int
    source_sha: str
    target: PlatformReleaseTarget
    sdk_protocol: ProtocolVersion
    python_version: str
    assets: tuple[PlatformReleaseAsset, ...]
    parent_manifest_sha256: str | None = None
    state_schema_min: int = 1
    state_schema_max: int = 1

    def __post_init__(self):
        if (not isinstance(self.release_id, str)
                or re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,119}',self.release_id) is None
                or self.release_id.endswith('.') or PureWindowsPath(self.release_id).is_reserved()):
            raise ValueError('bounded unambiguous release identity required')
        if not isinstance(self.version, str) or re.fullmatch(r'(0|[1-9][0-9]{0,4})\.(0|[1-9][0-9]{0,4})\.(0|[1-9][0-9]{0,4})',self.version) is None:
            raise ValueError('canonical release version required')
        if type(self.revision) is not int or not 1 <= self.revision <= 2**63-1:
            raise ValueError('bounded positive release revision required')
        if not isinstance(self.source_sha, str) or re.fullmatch('[0-9a-f]{40}',self.source_sha) is None:
            raise ValueError('exact source SHA required')
        if not isinstance(self.target, PlatformReleaseTarget) or not isinstance(self.sdk_protocol, ProtocolVersion):
            raise TypeError('typed Platform target and SDK protocol required')
        if not isinstance(self.python_version, str) or re.fullmatch(r'3\.12\.(0|[1-9][0-9]{0,4})',self.python_version) is None:
            raise ValueError('supported exact Python 3.12 runtime required')
        if self.parent_manifest_sha256 is not None and (not isinstance(self.parent_manifest_sha256,str)
                or re.fullmatch('[0-9a-f]{64}',self.parent_manifest_sha256) is None):
            raise ValueError('canonical parent manifest digest required')
        if (type(self.state_schema_min) is not int or type(self.state_schema_max) is not int
                or not 1 <= self.state_schema_min <= self.state_schema_max <= 2**31-1):
            raise ValueError('bounded Platform state schema range required')
        if not isinstance(self.assets,tuple) or not 7 <= len(self.assets) <= 96 or any(
                not isinstance(item,PlatformReleaseAsset) for item in self.assets):
            raise ValueError('bounded typed Platform release assets required')
        for kind in _REQUIRED:
            if sum(item.kind == kind for item in self.assets) != 1:
                raise ValueError('every required Platform artifact must occur once')
        paths = [asset.reference.path.casefold() for asset in self.assets]
        if len(set(paths)) != len(paths) or sum(a.reference.size_bytes for a in self.assets) > 1024**3:
            raise ValueError('duplicate paths or excessive Platform bundle size')
        object.__setattr__(self,'assets',tuple(sorted(self.assets,key=lambda a:(a.kind,a.reference.path))))

    def to_payload(self):
        return dict(schema=PLATFORM_RELEASE_SCHEMA,release_id=self.release_id,version=self.version,
            revision=self.revision,source_sha=self.source_sha,target=self.target.value,
            sdk_protocol=str(self.sdk_protocol),python_version=self.python_version,
            assets=[a.to_payload() for a in self.assets],parent_manifest_sha256=self.parent_manifest_sha256,
            state_schema_min=self.state_schema_min,state_schema_max=self.state_schema_max)

    @classmethod
    def from_payload(cls,value):
        keys={'schema','release_id','version','revision','source_sha','target','sdk_protocol','python_version','assets','parent_manifest_sha256','state_schema_min','state_schema_max'}
        if type(value) is not dict or set(value) != keys or value['schema'] != PLATFORM_RELEASE_SCHEMA:
            raise ValueError('unsupported Platform release fields/schema')
        if not isinstance(value['assets'],list) or len(value['assets']) > 96:
            raise ValueError('bounded release assets required')
        result=cls(value['release_id'],value['version'],value['revision'],value['source_sha'],
            PlatformReleaseTarget(value['target']),ProtocolVersion.parse(value['sdk_protocol']),value['python_version'],
            tuple(PlatformReleaseAsset.from_payload(a) for a in value['assets']),value['parent_manifest_sha256'],
            value['state_schema_min'],value['state_schema_max'])
        if result.to_payload() != value: raise ValueError('noncanonical Platform release encoding')
        return result

    @property
    def canonical_bytes(self):
        raw=json.dumps(self.to_payload(),sort_keys=True,separators=(',', ':'),ensure_ascii=False,allow_nan=False).encode()
        if len(raw)>131072: raise ValueError('Platform release manifest exceeds 128 KiB')
        return raw

    @property
    def digest(self):
        return sha256(_DOMAIN+self.canonical_bytes).hexdigest()
