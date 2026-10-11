"""Deferred signed state-home pointer trust/ancestor redirect regressions.

Fixture-only owner record. No live pointer, key, or database is modified.
"""
from hashlib import sha256
import hmac
import json

import pytest

from sofia.config.state_home_pointer import (
    _DOMAIN, _SCHEMA, read_verified_state_home,
)
from sofia.state.canonical_sqlite import bootstrap_canonical_sqlite


def _link_or_skip(path, destination, *, directory=False):
    try:
        path.symlink_to(destination, target_is_directory=directory)
    except (OSError, NotImplementedError):
        pytest.skip("OS refuses symlink fixture")


def _signed(tmp_path, *, root=None, trust_root=None):
    trust = trust_root or (tmp_path / "independent-trust")
    trust.mkdir(parents=True, exist_ok=True)
    home = root or (tmp_path / "state-home")
    home.mkdir(parents=True, exist_ok=True)
    bootstrap_canonical_sqlite(home / "sofia.db")
    protected = home / "protected"
    protected.mkdir(exist_ok=True)
    (protected / "identity.json").write_text('{"fixture":true}', encoding="utf-8")

    key = trust / "home.key"
    key.write_bytes(b"k" * 32)
    record = {
        "schema": _SCHEMA, "state_root": str(home),
        "writer_host_id": "Artemis:sofia-fixture",
        "epoch": 2, "operator_approval_ref": "offline-verified-test",
    }
    signed = json.dumps(
        record, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    record["hmac_sha256"] = hmac.new(
        key.read_bytes(), _DOMAIN + signed, sha256,
    ).hexdigest()
    pointer = trust / "home.json"
    pointer.write_text(json.dumps(record), encoding="utf-8")
    return home, pointer, key


def _open(pointer, key):
    return read_verified_state_home(
        pointer_path=pointer, key_path=key,
        expected_writer_host_id="Artemis:sofia-fixture",
        minimum_writer_epoch=2,
    )


def test_signed_pointer_accepts_actual_real_local_fixture_home(tmp_path):
    home, pointer, key = _signed(tmp_path)
    selected = _open(pointer, key)
    assert selected.root == home
    assert selected.writer_host_id == "Artemis:sofia-fixture"
    assert selected.epoch == 2


def test_signed_pointer_denies_symlinked_trust_parent(tmp_path):
    home, pointer, key = _signed(tmp_path)
    redirected = tmp_path / "redirected-trust"
    _link_or_skip(redirected, pointer.parent, directory=True)
    with pytest.raises(PermissionError, match="symbolic link or junction"):
        _open(redirected / pointer.name, redirected / key.name)


def test_signed_pointer_denies_redirected_canonical_db(tmp_path):
    home, pointer, key = _signed(tmp_path)
    external = tmp_path / "outside.db"
    external.write_bytes((home / "sofia.db").read_bytes())
    (home / "sofia.db").unlink()
    _link_or_skip(home / "sofia.db", external)
    with pytest.raises(PermissionError, match="symbolic link or junction"):
        _open(pointer, key)


def test_signed_pointer_denies_redirected_protected_identity(tmp_path):
    home, pointer, key = _signed(tmp_path)
    external = tmp_path / "outside-identity.json"
    external.write_text('{"fixture":"external"}', encoding="utf-8")
    identity = home / "protected" / "identity.json"
    identity.unlink()
    _link_or_skip(identity, external)
    with pytest.raises(PermissionError, match="symbolic link or junction"):
        _open(pointer, key)


def test_signed_pointer_denies_symlinked_home_parent(tmp_path):
    home, pointer, key = _signed(tmp_path)
    parent = tmp_path / "redirected"
    _link_or_skip(parent, home, directory=True)
    record = json.loads(pointer.read_text(encoding="utf-8"))
    record["state_root"] = str(parent)
    payload = {k: v for k, v in record.items() if k != "hmac_sha256"}
    signed = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    record["hmac_sha256"] = hmac.new(
        key.read_bytes(), _DOMAIN + signed, sha256,
    ).hexdigest()
    pointer.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(PermissionError, match="symbolic link or junction"):
        _open(pointer, key)
