"""Current canonical selection, not a GUI flag, admits Rust status reads."""
from datetime import timedelta
import json

import pytest

from sofia.platform.core_link import CoreLinkBindingState
from sofia.platform.core_link.rust_authority import status_admission, main
from test.test_core_link_binding import store, activate, binding, NOW

NONCE = 'a' * 64


def selected_store(tmp_path):
    registry = store(tmp_path)
    current = activate(registry)
    return registry, registry.select('binding:sofia-primary', expected_store_revision=current.revision)


def test_active_status_selection_returns_metadata_without_writes(tmp_path):
    registry, current = selected_store(tmp_path)
    original = registry.path.read_bytes()
    result = status_admission(registry, request_id=NONCE)
    assert result['admission'] == 'allowed'
    assert result['store_revision'] == current.revision
    assert result['binding'] == current.selected().to_payload()
    assert registry.path.read_bytes() == original
    assert 'PRIVATE KEY' not in json.dumps(result)


@pytest.mark.parametrize('state', [CoreLinkBindingState.OFFLINE, CoreLinkBindingState.QUARANTINED, CoreLinkBindingState.REVOKED])
def test_changed_selection_is_denied_after_initial_admission(tmp_path, state):
    registry, current = selected_store(tmp_path)
    assert status_admission(registry, request_id=NONCE)['admission'] == 'allowed'
    selected = current.selected()
    registry.transition(selected.binding_id, expected_binding_revision=selected.revision,
        expected_store_revision=current.revision, state=state, at=NOW + timedelta(seconds=3))
    result = status_admission(registry, request_id=NONCE)
    assert result['admission'] == 'denied' and result['binding'] is None
    assert result['store_revision'] > current.revision


def test_missing_store_does_not_create_authority(tmp_path):
    registry = store(tmp_path)
    assert status_admission(registry, request_id=NONCE)['admission'] == 'denied'
    assert not registry.path.exists()


def test_expected_identity_revision_and_rollback_are_enforced(tmp_path):
    registry, current = selected_store(tmp_path)
    selected = current.selected()
    for kwargs in [dict(binding_id='binding:other', expected_binding_revision=selected.revision),
                   dict(binding_id=selected.binding_id, expected_binding_revision=selected.revision+1),
                   dict(minimum_store_revision=current.revision+1)]:
        assert status_admission(registry, request_id=NONCE, **kwargs)['admission'] == 'denied'


def test_status_scope_is_required(tmp_path):
    registry = store(tmp_path)
    # Synthetic fixture setup; the adapter never changes a scope or state.
    original = binding(granted_scopes=('conversation.read',))
    registry.add_pending(original, expected_store_revision=0)
    registry.transition(original.binding_id, expected_binding_revision=1,
        expected_store_revision=1, state=CoreLinkBindingState.VERIFYING, at=NOW+timedelta(seconds=1))
    current = registry.reconcile_contact(original.binding_id, expected_binding_revision=2,
        expected_store_revision=2, remote_platform_id=original.remote_platform_id,
        remote_core_identity_id=original.remote_core_identity_id, remote_core_generation=original.remote_core_generation,
        endpoint_id=original.endpoint_id, trust_anchor_ref=original.trust_anchor_ref, at=NOW+timedelta(seconds=2))
    registry.select(original.binding_id, expected_store_revision=current.revision)
    assert status_admission(registry, request_id=NONCE)['admission'] == 'denied'


def test_cli_output_is_correlated_and_corruption_is_not_cached(tmp_path, capsys):
    registry, _ = selected_store(tmp_path)
    args = ['--store',str(registry.path),'--request-id',NONCE]
    assert main(args) == 0
    assert json.loads(capsys.readouterr().out)['request_id'] == NONCE
    registry.path.write_text('{',encoding='utf-8')
    assert main(args) == 2
    assert capsys.readouterr().out == ''
