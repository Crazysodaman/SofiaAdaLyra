"""Versioned inert individual Core definitions; no allocation or activation."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import PurePosixPath, PureWindowsPath
import re
import unicodedata

from sofia.sdk.contracts import ProtocolVersion
from sofia.sdk.identity import AegisIdentity, IdentityKind

CORE_DEFINITION_SCHEMA = 'aegis.core.definition.v1'
MAX_CORE_ASSET_BYTES = 16 * 1024 * 1024
_SHA256 = re.compile(r'[0-9a-f]{64}', re.ASCII)
_DOMAIN = b'aegis.core.definition.v1\x00'


def _digest(value):
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ValueError('lowercase SHA-256 required')


@dataclass(frozen=True, slots=True)
class CoreAssetReference:
    """One package-relative immutable definition asset; grants no state access."""
    path: str
    sha256: str
    size_bytes: int

    def __post_init__(self):
        if not isinstance(self.path, str) or not 1 <= len(self.path.encode('utf-8')) <= 1024:
            raise ValueError('bounded asset path required')
        parts = self.path.split('/')
        if (PurePosixPath(self.path).is_absolute() or any(p in {'', '.', '..'} for p in parts) or
            any(c in self.path for c in ('\\', ':')) or
            any(unicodedata.category(c).startswith('C') for c in self.path)):
            raise ValueError('asset path must be unambiguous and package-relative')
        if any(p.endswith((' ', '.')) for p in parts):
            raise ValueError('ambiguous Windows asset path')
        if any(PureWindowsPath(p).is_reserved() for p in parts):
            raise ValueError('reserved device asset path')
        _digest(self.sha256)
        if type(self.size_bytes) is not int or not 1 <= self.size_bytes <= MAX_CORE_ASSET_BYTES:
            raise ValueError('personal asset must contain 1..16 MiB')

    def to_payload(self):
        return {'path':self.path, 'sha256':self.sha256, 'size_bytes':self.size_bytes}

    @classmethod
    def from_payload(cls, value):
        if type(value) is not dict or set(value) != {'path','sha256','size_bytes'}:
            raise ValueError('asset reference requires exactly path, sha256 and size_bytes')
        return cls(**value)


@dataclass(frozen=True, slots=True)
class CoreDefinition:
    """A named identity plus signed-data references, never executable authority.

    Existing identity UUIDs are supplied, not generated. Runtime code, mutable
    memory/state, owner credentials and Platform identity are separate domains.
    """
    identity: AegisIdentity
    name: str
    revision: int
    runtime_release_sha256: str
    sdk_protocol: ProtocolVersion
    constitution: CoreAssetReference
    personality: CoreAssetReference

    def __post_init__(self):
        if not isinstance(self.identity, AegisIdentity) or self.identity.kind is not IdentityKind.CORE or self.identity.identity_id.int == 0:
            raise ValueError('existing non-null typed Core UUID required')
        if (not isinstance(self.name, str) or not 1 <= len(self.name) <= 160 or
            self.name != self.name.strip() or unicodedata.normalize('NFC',self.name) != self.name or
            any(unicodedata.category(c).startswith('C') for c in self.name)):
            raise ValueError('bounded visible NFC Core name required')
        self.name.encode('utf-8',errors='strict')
        if type(self.revision) is not int or not 1 <= self.revision <= 2**63-1:
            raise ValueError('positive bounded definition revision required')
        _digest(self.runtime_release_sha256)
        if not isinstance(self.sdk_protocol, ProtocolVersion):
            raise TypeError('typed SDK protocol required')
        if not isinstance(self.constitution, CoreAssetReference) or not isinstance(self.personality, CoreAssetReference):
            raise TypeError('typed personal asset references required')
        if unicodedata.normalize('NFKC',self.constitution.path).casefold() == unicodedata.normalize('NFKC',self.personality.path).casefold():
            raise ValueError('constitution and personality must be distinct assets')

    def to_payload(self):
        return {'schema':CORE_DEFINITION_SCHEMA, 'identity':self.identity.to_payload(),
            'name':self.name, 'revision':self.revision, 'runtime_release_sha256':self.runtime_release_sha256,
            'sdk_protocol':str(self.sdk_protocol), 'constitution':self.constitution.to_payload(),
            'personality':self.personality.to_payload()}

    @classmethod
    def from_payload(cls, value):
        fields = {'schema','identity','name','revision','runtime_release_sha256','sdk_protocol','constitution','personality'}
        if type(value) is not dict or set(value) != fields or value['schema'] != CORE_DEFINITION_SCHEMA:
            raise ValueError('unsupported Core definition fields/schema')
        result = cls(AegisIdentity.from_payload(value['identity']), value['name'], value['revision'],
            value['runtime_release_sha256'], ProtocolVersion.parse(value['sdk_protocol']),
            CoreAssetReference.from_payload(value['constitution']), CoreAssetReference.from_payload(value['personality']))
        if result.to_payload() != value:
            raise ValueError('Core definition must use canonical encodings')
        return result

    @property
    def canonical_bytes(self):
        raw = json.dumps(self.to_payload(), sort_keys=True, separators=(',', ':'),
                         ensure_ascii=False, allow_nan=False).encode('utf-8')
        if len(raw) > 16_384:
            raise ValueError('definition exceeds 16-KiB bound')
        return raw

    @property
    def digest(self):
        return sha256(_DOMAIN + self.canonical_bytes).hexdigest()
