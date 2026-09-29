import sys

import pytest

from sofia.safe.secret_store import ProtectedSecretStore


def test_secret_store_round_trip_without_plaintext(tmp_path):
    def protect(data: bytes) -> bytes:
        return b"wrapped:" + data[::-1]

    def unprotect(data: bytes) -> bytes:
        assert data.startswith(b"wrapped:")
        return data[len(b"wrapped:"):][::-1]

    store = ProtectedSecretStore(
        tmp_path / "secrets",
        protect=protect,
        unprotect=unprotect,
    )

    store.set("discord-token", "super-secret-token")

    path = tmp_path / "secrets" / "discord-token.dpapi"
    assert path.is_file()
    assert b"super-secret-token" not in path.read_bytes()
    assert store.exists("discord-token") is True
    assert store.get("discord-token") == "super-secret-token"


def test_secret_store_clear_is_idempotent(tmp_path):
    store = ProtectedSecretStore(
        tmp_path / "secrets",
        protect=lambda data: b"x" + data,
        unprotect=lambda data: data[1:],
    )

    store.set("home-assistant-token", "ha-secret")
    assert store.clear("home-assistant-token") is True
    assert store.clear("home-assistant-token") is False
    assert store.get("home-assistant-token") is None



@pytest.mark.skipif(sys.platform != "win32", reason="Windows DPAPI only")
def test_windows_dpapi_round_trip(tmp_path):
    store = ProtectedSecretStore(tmp_path / "dpapi-secrets")

    store.set("discord-token", "windows-dpapi-secret")

    path = tmp_path / "dpapi-secrets" / "discord-token.dpapi"
    assert b"windows-dpapi-secret" not in path.read_bytes()
    assert store.get("discord-token") == "windows-dpapi-secret"
