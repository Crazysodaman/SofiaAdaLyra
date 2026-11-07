"""Disposable VM signing never supplies production release or owner authority."""
from pathlib import Path
import json

import pytest

from test.fixtures.aegis_debian_vm.prepare_release import prepare_signed_vm_release
from test.test_platform_release_verifier import platform_wheels
from test.test_python_runtime_artifacts import fake_prefix

pytestmark=pytest.mark.pkg_ops


def test_disposable_vm_build_uses_real_release_and_runtime_staging(tmp_path,platform_wheels):
    output=tmp_path/'build'
    output.mkdir()
    rootfs=tmp_path/'guest'
    rootfs.mkdir()
    binary=output/'service'
    prefix=fake_prefix(output)
    binary.write_bytes((prefix/'bin/python3.12').read_bytes())  # Inert, never executed.
    (output/'inputs.json').write_text(json.dumps(dict(source_sha='a'*40,base_image='pinned-test-image')))
    report=prepare_signed_vm_release(output,rootfs,source_sha='a'*40,
        runtime_prefix=prefix,python_version='3.12.16',service=binary,
        wheels=tuple(platform_wheels.values()))
    assert report['activated'] is False
    assert report['source_sha']=='a'*40
    envelope=json.loads((output/'test-release-envelope.json').read_text())
    assert envelope['disposable_only'] is True
    assert 'private_key' not in envelope
    assert (rootfs/'opt/aegis/staged-release/runtime/python/bin/python3.12').exists()
    assert not list(rootfs.rglob('*.db'))


def test_source_mismatch_cannot_be_relabelled_by_test_signer(tmp_path):
    output=tmp_path/'build'
    output.mkdir()
    (output/'inputs.json').write_text(json.dumps(dict(source_sha='a'*40,base_image='test')))
    with pytest.raises(ValueError,match='source'):
        prepare_signed_vm_release(output,tmp_path/'guest',source_sha='b'*40,
            runtime_prefix=tmp_path/'absent',python_version='3.12.16',service=tmp_path/'absent',wheels=())
    assert list(output.iterdir())==[output/'inputs.json']
