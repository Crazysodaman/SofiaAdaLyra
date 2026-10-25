"""Pure static release preflight must never confuse a source audit with BETA."""
from __future__ import annotations
from pathlib import Path
import json
import pytest
from sofia.modules.optional_release_audit import (
    EXPECTED_OPTIONAL_IDS, _resources, audit_optional_source_tree,
    package_id_proposal,
)


def fake_module(root: Path, id_: str, capability: str = 'sample.check.v1', *,
                injection: str = '', resource='RESOURCES=(("cpu_millicores",50),("ram_mib",32),("gpu_mib",0))') -> None:
    dest = root / 'src/sofia/modules/sample' / ('check_' + id_.lower().replace('-', '_') + '.py')
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(f'''MODULE_ID={id_!r}\nMODULE_VERSION="0.1.0"\nCAPABILITY_ID={capability!r}\nPROFILE="OBSERVE"\n{resource}\n{injection}\ndef capability_registrations():\n  return ()\n''', encoding='utf-8')


def test_matrix_has_exactly_47_unique_catalog_ids():
    assert len(EXPECTED_OPTIONAL_IDS) == 47
    assert 'MOD-IT-HELPDESK' in EXPECTED_OPTIONAL_IDS
    assert 'MOD-AVATAR-STUDIO' in EXPECTED_OPTIONAL_IDS
    assert 'MOD-INTERACTION' not in EXPECTED_OPTIONAL_IDS


def test_generated_names_fit_Platform_package_rule():
    assert package_id_proposal('MOD-IT-NETWORK') == 'mod.it.network'
    assert package_id_proposal('MOD-3D-PRINT') == 'mod.3d.print'
    with pytest.raises(ValueError):
        package_id_proposal('MOD-INTERACTION')


def test_missing_sources_must_never_mark_beta(tmp_path):
    r = audit_optional_source_tree(tmp_path)
    assert r['expected_optional_modules'] == 47
    assert r['source_unobserved'] == 47
    assert r['beta_verified'] == 0
    assert all(item['beta_gate'] == 'NOT_VERIFIED' for item in r['candidates'])


def test_valid_ast_is_read_only_and_not_BETA(tmp_path):
    fake_module(tmp_path, 'MOD-DEV')
    r = audit_optional_source_tree(tmp_path)
    item = next(x for x in r['candidates'] if x['module_id'] == 'MOD-DEV')
    assert item['source_issues'] == []
    assert item['capability_id'] == 'sample.check.v1'
    assert item['source_scope'] == 'locally_parsed_ast'
    assert item['source_sha256'] and len(item['source_sha256']) == 64
    assert r['beta_verified'] == 0
    assert r['source_locally_parsed'] == 1
    json.dumps(r)


def test_ast_does_not_execute_top_level_code(tmp_path):
    fake_module(tmp_path, 'MOD-DEV', injection='''raise RuntimeError("MUST NOT EXECUTE")''')
    assert audit_optional_source_tree(tmp_path)['source_locally_parsed'] == 1


def test_invalid_profile_resources_and_version_flagged(tmp_path):
    fake_module(tmp_path, 'MOD-DEV', resource='RESOURCES=(("cpu_millicores",True),)')
    path = next(tmp_path.glob('src/sofia/modules/sample/*.py'))
    value = path.read_text().replace('MODULE_VERSION="0.1.0"','MODULE_VERSION="v1"').replace('PROFILE="OBSERVE"','PROFILE="EXECUTE_ALL"')
    path.write_text(value)
    item = next(x for x in audit_optional_source_tree(tmp_path)['candidates'] if x['module_id'] == 'MOD-DEV')
    assert set(item['source_issues']) == {'invalid_or_missing_semver', 'invalid_or_missing_profile', 'invalid_or_missing_resources'}


def test_static_capability_collision_is_an_issue(tmp_path):
    fake_module(tmp_path,'MOD-DEV')
    fake_module(tmp_path,'MOD-RESEARCH')
    r = audit_optional_source_tree(tmp_path)
    assert 'capability_collision:sample.check.v1' in r['cross_module_issues']


def test_direct_effect_import_requires_review(tmp_path):
    fake_module(tmp_path,'MOD-DEV',injection='import socket\nimport subprocess')
    item = next(x for x in audit_optional_source_tree(tmp_path)['candidates'] if x['module_id'] == 'MOD-DEV')
    assert 'direct_effect_dependency_requires_review:socket' in item['source_issues']
    assert 'direct_effect_dependency_requires_review:subprocess' in item['source_issues']


def test_remote_metadata_does_not_count_as_locally_verified(tmp_path):
    r=audit_optional_source_tree(tmp_path,remote_observations={
        'MOD-IT-HELPDESK':{'catalog_id':'MOD-IT-HELPDESK','source_path':'src/sofia/modules/it_helpdesk/triage.py'}
    })
    item=next(x for x in r['candidates'] if x['module_id']=='MOD-IT-HELPDESK')
    assert item['source_scope']=='remote_source_report_not_locally_parsed'
    assert 'local_source_unavailable' in item['source_issues']
    assert item['source_sha256'] is None
    assert r['beta_verified']==0


def test_no_fake_profile_bypassing_resources():
    assert _resources((('gpu_mib', 0),)) == (('gpu_mib', 0),)
    assert _resources((('ram_mib', -1),)) is None
    assert _resources((('cpu_millicores', True),)) is None
    assert _resources((('ram_mib', 32),('ram_mib', 64))) is None


def test_url_parsing_is_not_network_access(tmp_path):
    fake_module(tmp_path, 'MOD-BROWSER', injection='from urllib.parse import urlsplit')
    item = next(x for x in audit_optional_source_tree(tmp_path)['candidates'] if x['module_id'] == 'MOD-BROWSER')
    assert item['source_issues'] == []


def test_urllib_request_does_require_review(tmp_path):
    fake_module(tmp_path, 'MOD-BROWSER', injection='from urllib.request import urlopen')
    item = next(x for x in audit_optional_source_tree(tmp_path)['candidates'] if x['module_id'] == 'MOD-BROWSER')
    assert 'direct_effect_dependency_requires_review:network_urllib' in item['source_issues']


def test_complete_checkout_is_auditable_without_running_modules():
    """Exercise all 47 actual sources in full repository CI when present.

    The small standalone audit archive does not contain the entire repository;
    there the fixture-only tests still run, and this integration check skips.
    """
    root = Path(__file__).resolve().parents[1]
    if not (root / 'docs/sofia2/MODULE_OWNERSHIP_MATRIX.md').is_file():
        pytest.skip('full Sofía repository checkout not available in isolated audit workspace')
    audit = audit_optional_source_tree(root)
    assert audit['expected_optional_modules'] == 47
    assert audit['source_locally_parsed'] == 47
    assert audit['source_unobserved'] == 0
    assert audit['source_issues'] == 0
    assert not audit['cross_module_issues']
    assert audit['beta_verified'] == 0  # Only canonical Platform can certify readiness.
