"""Installed Core byte attestation must preserve filesystem redirect evidence."""
import os
from pathlib import Path
import subprocess

import pytest

from sofia.platform.core_worker import process
from sofia.platform.core_worker.process import CoreWorkerError, installed_core_release_digest


def redirect(link, target):
    if os.name == 'nt':
        subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(target)],
                       check=True, capture_output=True)
    else:
        link.symlink_to(target, target_is_directory=True)


@pytest.mark.parametrize('location', ['root', 'ancestor', 'implicit_ancestor', 'nested'])
def test_package_digest_rejects_redirect_before_reading_release_bytes(tmp_path, monkeypatch, location):
    actual = tmp_path / 'actual'
    package = actual / 'sofia'
    (package / 'platform' / 'core_worker').mkdir(parents=True)
    (package / '__init__.py').write_text('SYNTHETIC_CORE = True\n')
    module = package / 'platform' / 'core_worker' / 'process.py'
    module.write_text('# synthetic package fixture\n')
    if location == 'root':
        root = tmp_path / 'redirected_package'
        redirect(root, package)
    elif location in {'ancestor', 'implicit_ancestor'}:
        link = tmp_path / 'redirected_parent'
        redirect(link, actual)
        root = link / 'sofia'
    else:
        root = package
        redirect(package / 'redirected_subpackage', package / 'platform')
    if location != 'nested':
        assert len(installed_core_release_digest(package)) == 64
    if location == 'implicit_ancestor':
        monkeypatch.setattr(process, '__file__', str(root / 'platform' / 'core_worker' / 'process.py'))
    def forbidden_read(*args, **kwargs):
        raise AssertionError('redirected release bytes must not be read')
    monkeypatch.setattr(Path, 'read_bytes', forbidden_read)
    with pytest.raises(CoreWorkerError, match='symlink or junction'):
        installed_core_release_digest(None if location == 'implicit_ancestor' else root)
