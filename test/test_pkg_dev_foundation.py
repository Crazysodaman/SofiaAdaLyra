import pytest

from sofia.package_foundations.dev import ChangeProposal


HASH = 'a' * 64


def test_scoped_path_and_hash_are_preserved():
    proposal = ChangeProposal('src\\sofia\\module.py', HASH, 'Fix a verified defect')
    assert proposal.normalized_path == 'src/sofia/module.py'


@pytest.mark.parametrize('path', ['/etc/passwd', '../secret', 'src/../secret',
                                  'C:\\Windows\\system.ini', 'src//module.py'])
def test_unscoped_paths_are_rejected(path):
    with pytest.raises(ValueError):
        ChangeProposal(path, HASH, 'test')


def test_unpinned_change_is_rejected():
    with pytest.raises(ValueError):
        ChangeProposal('src/module.py', 'not-a-digest', 'test')
