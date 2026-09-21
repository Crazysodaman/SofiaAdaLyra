import pytest

from sofia.package_foundations.clean import CleanupCandidate


def test_cleanup_requires_backup_and_review():
    assert not CleanupCandidate(('tmp/cache',)).eligible_for_manual_plan
    assert not CleanupCandidate(('tmp/cache',), True, False).eligible_for_manual_plan
    assert CleanupCandidate(('tmp/cache',), True, True).eligible_for_manual_plan


def test_state_and_protected_files_never_pass_generic_cleanup_gate():
    for path in ('state/sofia.db', 'src/sofia/constitution/constitution.md',
                 'src/sofia/identity/identity.json'):
        assert not CleanupCandidate((path,), True, True).eligible_for_manual_plan


@pytest.mark.parametrize('path', ['../secret', '/absolute', 'C:\\Windows\\system.ini'])
def test_unsafe_paths_rejected(path):
    with pytest.raises(ValueError):
        CleanupCandidate((path,), True, True)
