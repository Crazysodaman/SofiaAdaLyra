from __future__ import annotations

import ctypes
from ctypes import wintypes
from pathlib import Path
import os


class SecretStoreUnavailable(RuntimeError):
    pass


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


def _protect_windows(data: bytes) -> bytes:
    if os.name != "nt":
        raise SecretStoreUnavailable("Windows DPAPI is unavailable")
    buffer = ctypes.create_string_buffer(data)
    source = _DATA_BLOB(
        len(data),
        ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)),
    )
    result = _DATA_BLOB()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    protect = crypt32.CryptProtectData
    protect.argtypes = [
        ctypes.POINTER(_DATA_BLOB),
        wintypes.LPCWSTR,
        ctypes.POINTER(_DATA_BLOB),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DATA_BLOB),
    ]
    protect.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [wintypes.HLOCAL]
    kernel32.LocalFree.restype = wintypes.HLOCAL
    ok = protect(
        ctypes.byref(source),
        "SofiaAdaLyra",
        None,
        None,
        None,
        0x1,
        ctypes.byref(result),
    )
    if not ok:
        raise OSError("CryptProtectData failed")
    try:
        return ctypes.string_at(result.pbData, result.cbData)
    finally:
        kernel32.LocalFree(result.pbData)


def _unprotect_windows(data: bytes) -> bytes:
    if os.name != "nt":
        raise SecretStoreUnavailable("Windows DPAPI is unavailable")
    buffer = ctypes.create_string_buffer(data)
    source = _DATA_BLOB(
        len(data),
        ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)),
    )
    result = _DATA_BLOB()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    unprotect = crypt32.CryptUnprotectData
    unprotect.argtypes = [
        ctypes.POINTER(_DATA_BLOB),
        ctypes.POINTER(wintypes.LPWSTR),
        ctypes.POINTER(_DATA_BLOB),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DATA_BLOB),
    ]
    unprotect.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [wintypes.HLOCAL]
    kernel32.LocalFree.restype = wintypes.HLOCAL
    ok = unprotect(
        ctypes.byref(source),
        None,
        None,
        None,
        None,
        0x1,
        ctypes.byref(result),
    )
    if not ok:
        raise OSError("CryptUnprotectData failed")
    try:
        return ctypes.string_at(result.pbData, result.cbData)
    finally:
        kernel32.LocalFree(result.pbData)


class ProtectedSecretStore:
    """Small local secret store backed by Windows DPAPI."""

    def __init__(
        self,
        root: str | Path,
        *,
        protect=_protect_windows,
        unprotect=_unprotect_windows,
    ) -> None:
        self.root = Path(root)
        self._protect = protect
        self._unprotect = unprotect

    @classmethod
    def for_state_path(
        cls,
        state_path: str | Path,
    ) -> "ProtectedSecretStore":
        state = Path(state_path)
        return cls(state.parent / "protected" / "secrets")

    @staticmethod
    def _name(key: str) -> str:
        if not isinstance(key, str) or not key.strip():
            raise ValueError("secret key must be nonempty")
        safe = key.strip().lower().replace("_", "-")
        if not safe.replace("-", "").isalnum():
            raise ValueError("secret key contains unsupported characters")
        return safe + ".dpapi"

    def _path(self, key: str) -> Path:
        return self.root / self._name(key)

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def set(self, key: str, value: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("secret value must be nonempty")
        self.root.mkdir(parents=True, exist_ok=True)
        encrypted = self._protect(value.encode("utf-8"))
        target = self._path(key)
        temporary = target.with_suffix(target.suffix + ".tmp")
        try:
            temporary.write_bytes(encrypted)
            os.replace(temporary, target)
        finally:
            if temporary.exists():
                temporary.unlink()

    def get(self, key: str) -> str | None:
        target = self._path(key)
        if not target.is_file():
            return None
        decrypted = self._unprotect(target.read_bytes())
        value = decrypted.decode("utf-8")
        if not value:
            raise RuntimeError("protected secret decrypted to an empty value")
        return value

    def clear(self, key: str) -> bool:
        target = self._path(key)
        try:
            target.unlink()
        except FileNotFoundError:
            return False
        return True
