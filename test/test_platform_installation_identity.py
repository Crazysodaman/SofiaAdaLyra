"""Explicit installation bootstrap preserves keys and fails closed on damage."""
import json
import os
from concurrent.futures import ThreadPoolExecutor

import pytest

from sofia.platform.state import installation_identity as module
from sofia.platform.state.installation_identity import (
    InstallationIdentityStore, InstallationIdentityUnavailable,
    configured_platform_identity_id,
)


def test_reopen_preserves_identity_and_key(tmp_path):
    store = InstallationIdentityStore(tmp_path / 'identity')
    first = store.initialize()
    before = {p.name: p.read_bytes() for p in store.home.iterdir()}
    assert InstallationIdentityStore(store.home).initialize() == first
    assert store.load() == first
    assert before == {p.name: p.read_bytes() for p in store.home.iterdir()}
    assert first.identity.serial.startswith('AEG-P-')
    assert len(first.public_key_sha256) == 64
    public = json.dumps(first.to_payload())
    assert 'PRIVATE KEY' not in public
    assert 'signature' not in first.to_payload()
    other = InstallationIdentityStore(tmp_path / 'other').initialize()
    assert first.identity != other.identity
    assert first.public_key_sha256 != other.public_key_sha256


@pytest.mark.parametrize('damage', ['schema', 'signature', 'uuid', 'kind', 'extra', 'duplicate', 'key', 'missing_key', 'missing_metadata'])
def test_damage_never_regenerates(tmp_path, damage):
    store = InstallationIdentityStore(tmp_path / 'identity')
    store.initialize()
    raw = json.loads(store.metadata_path.read_text())
    if damage == 'schema': raw['schema'] = 'future'
    elif damage == 'signature': raw['signature'] = 'AAAA'
    elif damage == 'uuid': raw['identity']['uuid'] = '00000000-0000-0000-0000-000000000000'
    elif damage == 'kind': raw['identity']['kind'] = 'core'
    elif damage == 'extra': raw['owner'] = True
    if damage in {'schema', 'signature', 'uuid', 'kind', 'extra'}:
        store.metadata_path.write_text(json.dumps(raw))
    elif damage == 'duplicate':
        store.metadata_path.write_text('{"schema":"a", "schema":"b"}')
    elif damage == 'key': store.key_path.write_text('damaged key')
    elif damage == 'missing_key': store.key_path.unlink()
    elif damage == 'missing_metadata': store.metadata_path.unlink()
    before = {p.name: p.read_bytes() for p in store.home.iterdir()}
    with pytest.raises(InstallationIdentityUnavailable):
        InstallationIdentityStore(store.home).initialize()
    assert before == {p.name: p.read_bytes() for p in store.home.iterdir()}


def test_partial_write_is_retained_and_refused(tmp_path, monkeypatch):
    store = InstallationIdentityStore(tmp_path / 'identity')
    write = module.atomic_write_private_text
    def fail_metadata(path, text):
        if path == store.metadata_path:
            raise OSError('simulated interruption')
        write(path, text)
    monkeypatch.setattr(module, 'atomic_write_private_text', fail_metadata)
    with pytest.raises(OSError): store.initialize()
    key = store.key_path.read_bytes()
    monkeypatch.setattr(module, 'atomic_write_private_text', write)
    with pytest.raises(InstallationIdentityUnavailable): store.initialize()
    assert store.key_path.read_bytes() == key
    assert not store.metadata_path.exists()


def test_concurrent_initializers_never_replace_winner(tmp_path):
    home = tmp_path / 'identity'
    def initialize(_):
        try: return InstallationIdentityStore(home).initialize()
        except InstallationIdentityUnavailable: return None
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(initialize, range(12)))
    final = InstallationIdentityStore(home).load()
    assert any(result is not None for result in results)
    assert all(result is None or result == final for result in results)


@pytest.mark.skipif(os.name == 'nt', reason='POSIX permissions and symlink exercise')
@pytest.mark.parametrize('target', ['home', 'key', 'metadata', 'parent'])
def test_unsafe_paths_are_refused(tmp_path, target):
    store = InstallationIdentityStore(tmp_path / 'identity')
    store.initialize()
    if target == 'home': store.home.chmod(0o755)
    elif target == 'key': store.key_path.chmod(0o644)
    elif target == 'metadata': store.metadata_path.chmod(0o644)
    else:
        alias = tmp_path / 'alias'
        alias.symlink_to(store.home, target_is_directory=True)
        store = InstallationIdentityStore(alias)
    with pytest.raises(InstallationIdentityUnavailable): store.load()


def test_configuration_is_explicit_and_has_no_fallback(tmp_path, monkeypatch):
    monkeypatch.delenv('AEGIS_PLATFORM_IDENTITY_HOME', raising=False)
    monkeypatch.delenv('SOFIA_PLATFORM_INSTANCE_ID', raising=False)
    assert configured_platform_identity_id() == 'platform:local'
    home = tmp_path / 'identity'
    monkeypatch.setenv('AEGIS_PLATFORM_IDENTITY_HOME', str(home))
    with pytest.raises(InstallationIdentityUnavailable): configured_platform_identity_id()
    assert not home.exists()
    identity = InstallationIdentityStore(home).initialize()
    assert configured_platform_identity_id() == identity.identity.canonical_uuid
    monkeypatch.setenv('SOFIA_PLATFORM_INSTANCE_ID', 'wrong')
    with pytest.raises(InstallationIdentityUnavailable): configured_platform_identity_id()


def test_cli_public_bootstrap_and_show(tmp_path, capsys):
    from sofia.platform.launcher import main
    home = tmp_path / 'identity'
    assert main(['identity-init', '--home', str(home)]) == 0
    created = json.loads(capsys.readouterr().out)
    assert 'bootstrap' not in created
    assert 'selected_core' not in created
    assert 'callsign' not in created
    assert main(['identity-show', '--home', str(home)]) == 0
    assert json.loads(capsys.readouterr().out) == created


def test_loading_never_allocates_identity_or_key(tmp_path, monkeypatch):
    store = InstallationIdentityStore(tmp_path / 'identity')
    first = store.initialize()
    def forbidden(): raise AssertionError('load allocated a new UUID')
    monkeypatch.setattr(module, 'uuid4', forbidden)
    assert InstallationIdentityStore(store.home).initialize() == first
    assert store.load() == first


def test_open_store_rejects_replacement_with_another_valid_identity(tmp_path):
    store = InstallationIdentityStore(tmp_path / 'identity')
    store.initialize()
    other = InstallationIdentityStore(tmp_path / 'other')
    other.initialize()
    store.key_path.write_bytes(other.key_path.read_bytes())
    store.metadata_path.write_bytes(other.metadata_path.read_bytes())
    with pytest.raises(InstallationIdentityUnavailable): store.load()
