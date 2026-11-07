"""Versioned inert CPython runtime file inventory; no installation authority."""
from dataclasses import dataclass
from hashlib import sha256
import json
import re

from sofia.sdk.artifact import validate_artifact_path
from sofia.sdk.platform_release import PlatformReleaseTarget

PYTHON_RUNTIME_SCHEMA = 'aegis.python-runtime.v1'
_EMPTY = sha256(b'').hexdigest()


@dataclass(frozen=True, slots=True)
class RuntimeFile:
    path: str
    sha256: str
    size_bytes: int
    executable: bool

    def __post_init__(self):
        validate_artifact_path(self.path)
        if not self.path.isascii() or any(part.casefold() in {'site-packages', 'dist-packages'}
                for part in self.path.split('/')):
            raise ValueError('runtime inventory excludes installed application packages')
        if not isinstance(self.sha256, str) or re.fullmatch('[0-9a-f]{64}', self.sha256) is None:
            raise ValueError('canonical runtime file digest required')
        if type(self.size_bytes) is not int or not 0 <= self.size_bytes <= 64 * 1024**2:
            raise ValueError('runtime member must be within 0..64 MiB')
        if type(self.executable) is not bool:
            raise TypeError('explicit executable flag required')
        if self.size_bytes == 0 and self.sha256 != _EMPTY:
            raise ValueError('empty runtime file digest differs')
        if self.executable and self.size_bytes < 64:
            raise ValueError('runtime executable cannot be empty or truncated')

    def to_payload(self):
        return dict(path=self.path, sha256=self.sha256, size_bytes=self.size_bytes, executable=self.executable)

    @classmethod
    def from_payload(cls, value):
        if type(value) is not dict or set(value) != {'path', 'sha256', 'size_bytes', 'executable'}:
            raise ValueError('runtime member fields differ')
        return cls(**value)


@dataclass(frozen=True, slots=True)
class PythonRuntimeManifest:
    python_version: str
    target: PlatformReleaseTarget
    executable: str
    files: tuple[RuntimeFile, ...]

    def __post_init__(self):
        if not isinstance(self.python_version, str) or re.fullmatch(r'3\.12\.(0|[1-9][0-9]{0,4})', self.python_version) is None:
            raise ValueError('canonical supported CPython 3.12 version required')
        if not isinstance(self.target, PlatformReleaseTarget):
            raise TypeError('typed runtime target required')
        if not isinstance(self.files, tuple) or not 3 <= len(self.files) <= 8192 or any(
                not isinstance(item, RuntimeFile) for item in self.files):
            raise ValueError('bounded typed runtime file inventory required')
        names = [item.path.casefold() for item in self.files]
        if len(set(names)) != len(names) or sum(item.size_bytes for item in self.files) > 512 * 1024**2:
            raise ValueError('ambiguous paths or excessive runtime size')
        windows = self.target is PlatformReleaseTarget.WINDOWS_X86_64
        expected_executable = 'python.exe' if windows else 'bin/python3.12'
        library = 'Lib' if windows else 'lib/python3.12'
        if self.executable != expected_executable:
            raise ValueError('runtime executable differs from target layout')
        entries = {item.path: item for item in self.files}
        if (self.executable not in entries or not entries[self.executable].executable
                or library + '/site.py' not in entries
                or library + '/ensurepip/__init__.py' not in entries):
            raise ValueError('complete standard CPython layout required')
        for item in self.files:
            if windows:
                allowed = (item.path in {'python.exe', 'pythonw.exe', 'LICENSE.txt'}
                    or item.path.startswith(('Lib/', 'DLLs/'))
                    or re.fullmatch(r'(?:python3(?:12)?|vcruntime[0-9_]+)\.dll', item.path.casefold()) is not None)
            else:
                allowed = (item.path in {'bin/python3.12', 'LICENSE.txt'}
                    or item.path.startswith('lib/python3.12/')
                    or re.fullmatch(r'lib/libpython(?:3|3\.12)\.so(?:\.[0-9]+)*', item.path) is not None)
            if not allowed:
                raise ValueError('runtime member is outside the supported code layout')
        object.__setattr__(self, 'files', tuple(sorted(self.files, key=lambda item: item.path)))

    def to_payload(self):
        return dict(schema=PYTHON_RUNTIME_SCHEMA, python_version=self.python_version,
            target=self.target.value, executable=self.executable,
            files=[item.to_payload() for item in self.files])

    @classmethod
    def from_payload(cls, value):
        if type(value) is not dict or set(value) != {'schema', 'python_version', 'target', 'executable', 'files'} or value['schema'] != PYTHON_RUNTIME_SCHEMA:
            raise ValueError('unsupported runtime inventory fields/schema')
        if type(value['files']) is not list or len(value['files']) > 8192:
            raise ValueError('bounded runtime inventory required')
        result = cls(value['python_version'], PlatformReleaseTarget(value['target']), value['executable'],
            tuple(RuntimeFile.from_payload(item) for item in value['files']))
        if result.to_payload() != value:
            raise ValueError('noncanonical runtime inventory')
        return result

    @property
    def canonical_bytes(self):
        value = json.dumps(self.to_payload(), sort_keys=True, separators=(',', ':'),
            ensure_ascii=False, allow_nan=False).encode('utf-8')
        if len(value) > 2 * 1024**2:
            raise ValueError('runtime inventory exceeds 2-MiB bound')
        return value

    @property
    def digest(self):
        return sha256(PYTHON_RUNTIME_SCHEMA.encode() + b'\0' + self.canonical_bytes).hexdigest()
