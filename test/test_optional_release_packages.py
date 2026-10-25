"""Offline release-preparation regression; native Platform tests run in full checkout."""
from __future__ import annotations

import ast
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys

import pytest

from sofia.modules.optional_release_audit import (
    EXPECTED_OPTIONAL_IDS, audit_optional_source_tree, package_id_proposal,
)
from sofia.modules.optional_release_packages import (
    OwnerReviewedReleasePolicy, ReleasePreparationError,
    prepare_release_draft, materialize_unsigned_draft, verify_operator_signature,
)

SOURCE_ROOT = Path(__file__).resolve().parents[1]
MODULE_ROOT = SOURCE_ROOT / 'src/sofia/modules'
SNAPSHOT = 'a' * 64  # Test-only, not verified Git identity.


def policy_for(rows, *, package_ids=None, schemas=None, classes=None):
    ids = dict(package_ids if package_ids is not None else {r['module_id']: package_id_proposal(r['module_id']) for r in rows})
    caps = dict(schemas if schemas is not None else {r['capability_id']: f'test-reviewed:{r["capability_id"]}' for r in rows})
    data = dict(classes if classes is not None else {r['module_id']: ('supplied_unverified',) for r in rows})
    return OwnerReviewedReleasePolicy(
        package_ids=ids, capability_schema_refs=caps, publisher='test-operator',
        trust_ref='test-trust:untrusted', platform_api_minimum='1.0.0',
        supported_os_arch=('test-linux-x86_64',), isolation_profile='test-isolated',
        allowed_host_classes=('MODULE_HOST',), data_classes=data,
        review_receipt='test-only:not-an-owner-approval',
    )


@pytest.fixture(scope='module')
def rows():
    scan = audit_optional_source_tree(SOURCE_ROOT)
    assert not scan['cross_module_issues']
    return [row for row in scan['candidates'] if row['source_scope'] == 'locally_parsed_ast']


@pytest.fixture(scope='module')
def policy(rows):
    return policy_for(rows)


def test_source_scan_has_bound_metadata(rows):
    assert len(rows) >= 40
    assert all(not r['source_issues'] for r in rows)


def test_all_available_candidate_manifests_are_digest_locked(rows, policy):
    seen = set()
    for row in rows:
        draft = prepare_release_draft(SOURCE_ROOT, catalog_id=row['module_id'],
                                      policy=policy, source_revision_sha=SNAPSHOT)
        assert draft.package_id not in seen
        seen.add(draft.package_id)
        assert draft.manifest_unsigned['module_id'] == policy.package_ids[row['module_id']]
        assert draft.manifest_unsigned['profiles'][0]['available_capability_ids'] == [row['capability_id']]
        assert draft.manifest_unsigned['profiles'][0]['profile_id'] == row['profile']
        assert draft.manifest_unsigned['maintenance_profile']['module_id'] == draft.package_id
        assert draft.manifest_unsigned['maintenance_profile']['module_version'] == row['version']
        assert draft.manifest_unsigned['maintenance_profile']['health_probe_ids'] == []
        assert draft.manifest_unsigned['placement_mode'] == 'PORTABLE_STATELESS'
        assert draft.manifest_unsigned['schema_version'] == 1
        assert draft.manifest_unsigned['profiles'][0]['permission_ceiling'] == 1
        assert draft.manifest_unsigned['kind'] == 'optional'
        assert draft.manifest_unsigned['maintenance_profile']['artifact_digest']
        assert 'signature_b64' not in draft.manifest_unsigned
        assert draft.signature_request()['signature_present'] is False
        assert draft.signature_request()['platform_readiness'] == 'NOT_VERIFIED'
        assert draft.package_digest == sha256(draft.signing_bytes).hexdigest()
        assert len(draft.artifact_digests) == 2
        for path, digest in draft.artifact_digests:
            assert sha256((SOURCE_ROOT / path).read_bytes()).hexdigest() == digest


def test_materialization_exact_paths_and_no_overwrite(rows, policy, tmp_path):
    draft = prepare_release_draft(SOURCE_ROOT, catalog_id=rows[0]['module_id'],
                                  policy=policy, source_revision_sha=SNAPSHOT)
    destination = materialize_unsigned_draft(draft, repo_root=SOURCE_ROOT,
                                             output_root=tmp_path / 'candidate')
    actual = {p.relative_to(destination).as_posix() for p in destination.rglob('*') if p.is_file()}
    assert actual == {p for p, _ in draft.artifact_digests} | {'UNSIGNED_REVIEW_ONLY.json'}
    assert json.loads((destination/'UNSIGNED_REVIEW_ONLY.json').read_text())['signature_present'] is False
    with pytest.raises(FileExistsError):
        materialize_unsigned_draft(draft, repo_root=SOURCE_ROOT, output_root=destination)


def test_reject_missing_reviewed_package_id(rows, policy):
    row=rows[0]
    other = policy_for(rows, package_ids={})
    with pytest.raises(ReleasePreparationError,match='missing owner-reviewed'):
        prepare_release_draft(SOURCE_ROOT, catalog_id=row['module_id'],policy=other,
                              source_revision_sha=SNAPSHOT)


def test_reject_missing_capability_schema(rows):
    other=policy_for(rows,schemas={'unused.thing':'not-a-schema'})
    with pytest.raises(ReleasePreparationError,match='missing reviewed capability'):
        prepare_release_draft(SOURCE_ROOT,catalog_id=rows[0]['module_id'],policy=other,
                              source_revision_sha=SNAPSHOT)


@pytest.mark.parametrize('wrong', ['', 'not-a-sha', 'Z'*64, 12])
def test_invalid_revision_denied(wrong,rows,policy):
    with pytest.raises(ReleasePreparationError):
        prepare_release_draft(SOURCE_ROOT,catalog_id=rows[0]['module_id'],policy=policy,
                              source_revision_sha=wrong)


def test_invalid_catalog_id_denied(policy):
    with pytest.raises(ReleasePreparationError):
        prepare_release_draft(SOURCE_ROOT,catalog_id='RM-DESKTOP',policy=policy,
                              source_revision_sha=SNAPSHOT)


def test_reject_duplicate_package_ids(rows):
    with pytest.raises(ReleasePreparationError,match='collision'):
        policy_for(rows,package_ids={r['module_id']:'mod.same' for r in rows})


def test_reject_unreviewed_effect_profile(rows,policy,tmp_path):
    row=rows[0]
    copy=tmp_path/'copy'
    source=SOURCE_ROOT/row['source_path']
    target=copy/row['source_path']
    target.parent.mkdir(parents=True)
    target.write_text(source.read_text().replace("PROFILE = 'ADVISORY'", "PROFILE = 'SUPERVISED'")
                      .replace("PROFILE='ADVISORY'", "PROFILE='SUPERVISED'"))
    (target.parent/'__init__.py').write_text('')
    # Other candidates are absent from temp copy; no privileged profile can be admitted.
    with pytest.raises(ReleasePreparationError):
        prepare_release_draft(copy,catalog_id=row['module_id'],policy=policy,
                              source_revision_sha=SNAPSHOT)


def test_symlink_artifact_rejected(rows,policy,tmp_path):
    row=rows[0]
    source=SOURCE_ROOT/row['source_path']
    temp=tmp_path/'temp'
    target=temp/row['source_path']
    target.parent.mkdir(parents=True)
    target.symlink_to(source)
    (target.parent/'__init__.py').write_text('')
    with pytest.raises((ReleasePreparationError, OSError)):
        prepare_release_draft(temp,catalog_id=row['module_id'],policy=policy,
                              source_revision_sha=SNAPSHOT)


def test_different_publisher_changes_package_digest(rows,policy):
    row=rows[0]
    other=OwnerReviewedReleasePolicy(
        package_ids=policy.package_ids,capability_schema_refs=policy.capability_schema_refs,
        publisher='second-test-operator',trust_ref=policy.trust_ref,
        platform_api_minimum=policy.platform_api_minimum,
        supported_os_arch=policy.supported_os_arch,isolation_profile=policy.isolation_profile,
        allowed_host_classes=policy.allowed_host_classes,data_classes=policy.data_classes,
        review_receipt=policy.review_receipt)
    draft1=prepare_release_draft(SOURCE_ROOT,catalog_id=row['module_id'],policy=policy,source_revision_sha=SNAPSHOT)
    draft2=prepare_release_draft(SOURCE_ROOT,catalog_id=row['module_id'],policy=other,source_revision_sha=SNAPSHOT)
    assert draft1.package_digest!=draft2.package_digest


def test_real_platform_manifest_signature_and_tamper_denial(rows,policy,tmp_path):
    # This is the essential native Platform integration test; in a complete
    # repo it must execute, not use simulated manifest parsers or signatures.
    pytest.importorskip('sofia.platform.modules.package')
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    from base64 import b64encode
    row=rows[0]
    draft=prepare_release_draft(SOURCE_ROOT,catalog_id=row['module_id'],policy=policy,
                                source_revision_sha=SNAPSHOT)
    destination=materialize_unsigned_draft(draft,repo_root=SOURCE_ROOT,
                                           output_root=tmp_path/'candidate')
    test_only_key=Ed25519PrivateKey.generate()
    public=test_only_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,format=serialization.PublicFormat.Raw)
    signature=b64encode(test_only_key.sign(draft.signing_bytes)).decode('ascii')
    package=verify_operator_signature(draft,signature_b64=signature,
                                      package_root=destination,trusted_public_key=public)
    assert package.package_digest==draft.package_digest
    with pytest.raises(Exception):
        verify_operator_signature(draft,signature_b64=signature,
                                  package_root=destination,trusted_public_key=bytes(32))
    artifact=destination/draft.artifact_digests[0][0]
    artifact.write_bytes(artifact.read_bytes()+b'\n# changed after signing\n')
    with pytest.raises(Exception):
        verify_operator_signature(draft,signature_b64=signature,
                                  package_root=destination,trusted_public_key=public)


def test_batch_denies_incomplete_review(rows):
    from sofia.modules.optional_release_packages import prepare_release_batch
    incomplete=policy_for(rows)
    with pytest.raises(ReleasePreparationError,match='all 47'):
        prepare_release_batch(SOURCE_ROOT,policy=incomplete,source_revision_sha=SNAPSHOT)


def test_batch_rejects_missing_local_sources(rows):
    from sofia.modules.optional_release_packages import prepare_release_batch
    all_ids={key:package_id_proposal(key) for key in EXPECTED_OPTIONAL_IDS}
    data={key:('supplied_unverified',) for key in EXPECTED_OPTIONAL_IDS}
    complete=policy_for(rows,package_ids=all_ids,classes=data)
    # Local isolated workspace intentionally lacks the earlier two IT sources.
    # A complete Git checkout runs the native complete-batch positive test below.
    if len(rows) < 47:
        with pytest.raises(ReleasePreparationError):
            prepare_release_batch(SOURCE_ROOT,policy=complete,source_revision_sha=SNAPSHOT)
    else:
        assert len(prepare_release_batch(SOURCE_ROOT,policy=complete,
                    source_revision_sha=SNAPSHOT))==47


def test_batch_materialization_requires_all_modules():
    from sofia.modules.optional_release_packages import materialize_unsigned_batch
    with pytest.raises(ReleasePreparationError,match='47'):
        materialize_unsigned_batch((),repo_root=SOURCE_ROOT,output_root=SOURCE_ROOT/'should-not-exist')


def test_cli_rejects_incomplete_policy_document(tmp_path):
    from sofia.modules.optional_release_cli import _policy
    file=tmp_path/'policy.json'
    file.write_text(json.dumps({'package_ids':{}}))
    with pytest.raises(ValueError,match='precisely'):
        _policy(file)


def test_release_kit_does_not_sign_or_access_execution_boundary():
    import sofia.modules.optional_release_packages as kit
    import sofia.modules.optional_release_cli as cli
    forbidden={'subprocess','socket','sqlite3','ctypes','winreg','requests'}
    for mod in (kit,cli):
        ast_tree=ast.parse(Path(mod.__file__).read_text(encoding='utf-8'))
        dependencies={alias.name.split('.')[0] for n in ast.walk(ast_tree)
                      if isinstance(n,ast.Import) for alias in n.names}
        assert not dependencies.intersection(forbidden)
        assert not any(isinstance(n,ast.ImportFrom) and
                       n.module and n.module.split('.')[0] in forbidden
                       for n in ast.walk(ast_tree))


def test_unicode_publisher_uses_native_artifact_identity_serialization(rows,policy):
    row=rows[0]
    reviewed=OwnerReviewedReleasePolicy(
        package_ids=policy.package_ids,capability_schema_refs=policy.capability_schema_refs,
        publisher='Sofía release steward',trust_ref=policy.trust_ref,
        platform_api_minimum=policy.platform_api_minimum,
        supported_os_arch=policy.supported_os_arch,isolation_profile=policy.isolation_profile,
        allowed_host_classes=policy.allowed_host_classes,data_classes=policy.data_classes,
        review_receipt=policy.review_receipt,
    )
    draft=prepare_release_draft(SOURCE_ROOT,catalog_id=row['module_id'],
                                policy=reviewed,source_revision_sha=SNAPSHOT)
    native_identity=sha256(json.dumps({
        'artifacts':[list(pair) for pair in draft.artifact_digests],
        'module_id':draft.package_id,'publisher':reviewed.publisher,
        'version':draft.manifest_unsigned['version'],
    },sort_keys=True,separators=(',',':')).encode()).hexdigest()
    assert draft.manifest_unsigned['maintenance_profile']['artifact_digest']==native_identity
