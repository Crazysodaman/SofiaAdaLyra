"""Signed Core definition data never creates identity or activates a writer."""
from base64 import b64encode
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from uuid import uuid4
import json

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sofia.sdk.identity import AegisIdentity, IdentityKind
from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.sdk.core_definition import CoreAssetReference, CoreDefinition
from sofia.platform.ops.core_definition import CoreDefinitionVerifier, CoreDefinitionRejected


def fixture_definition(tmp_path, name='Synthetic Sofia'):
    directory = tmp_path / name.replace(' ', '_')
    directory.mkdir()
    constitution, personality = b'Test-only constitutional boundaries.', b'{"style":"test"}'
    (directory/'constitution.txt').write_bytes(constitution)
    (directory/'personality.json').write_bytes(personality)
    definition = CoreDefinition(
        identity=AegisIdentity(IdentityKind.CORE, uuid4()), name=name, revision=1,
        runtime_release_sha256='a'*64, sdk_protocol=SDK_PROTOCOL_VERSION,
        constitution=CoreAssetReference('constitution.txt', sha256(constitution).hexdigest(), len(constitution)),
        personality=CoreAssetReference('personality.json', sha256(personality).hexdigest(), len(personality)))
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    signature = b64encode(private.sign(definition.digest.encode('ascii'))).decode('ascii')
    return directory, definition, private, public, signature


@pytest.mark.parametrize('name', ['Synthetic Sofia','Synthetic Roland','Synthetic John'])
def test_independent_definitions_verify_without_generating_or_changing_identity(tmp_path, name):
    directory, definition, _, public, signature = fixture_definition(tmp_path, name)
    before = {p.name:p.read_bytes() for p in directory.iterdir()}
    verified = CoreDefinitionVerifier({'operator':public}).verify(definition.to_payload(), signature_b64=signature,
        signer_key_id='operator', assets_root=directory, expected_core_id=definition.identity.canonical_uuid,
        expected_runtime_sha256=definition.runtime_release_sha256, minimum_revision=1)
    assert verified == definition
    assert CoreDefinition.from_payload(definition.to_payload()) == definition
    assert verified.identity.serial.startswith('AEG-C-')
    assert before == {p.name:p.read_bytes() for p in directory.iterdir()}
    assert not any(p.suffix == '.db' for p in directory.iterdir())


@pytest.mark.parametrize('defect', ['signature','signer','core','runtime','revision','asset','extra_field','kind'])
def test_definition_verification_fails_closed(tmp_path, defect):
    directory, definition, _, public, signature = fixture_definition(tmp_path)
    payload = definition.to_payload()
    arguments = dict(signature_b64=signature, signer_key_id='operator', assets_root=directory,
        expected_core_id=definition.identity.canonical_uuid, expected_runtime_sha256='a'*64, minimum_revision=1)
    if defect == 'signature': arguments['signature_b64'] = b64encode(b'x'*64).decode()
    elif defect == 'signer': arguments['signer_key_id'] = 'unknown'
    elif defect == 'core': arguments['expected_core_id'] = str(uuid4())
    elif defect == 'runtime': arguments['expected_runtime_sha256'] = 'b'*64
    elif defect == 'revision': arguments['minimum_revision'] = 2
    elif defect == 'asset': (directory/'constitution.txt').write_bytes(b'Tampered')
    elif defect == 'extra_field': payload['owner_authenticated'] = True
    elif defect == 'kind': payload['identity']['kind'] = 'platform'
    with pytest.raises(CoreDefinitionRejected): CoreDefinitionVerifier({'operator':public}).verify(payload, **arguments)


@pytest.mark.parametrize('path', ['../outside','/absolute','C:drive','a\\b','a//b','a/./b','a/../b','NUL.txt','CONIN$','com1','a.','a '])
def test_definition_assets_cannot_escape_package(path):
    with pytest.raises(ValueError): CoreAssetReference(path, 'a'*64, 1)


def test_signed_asset_redirect_is_refused_on_each_platform(tmp_path):
    import os
    import subprocess
    directory, definition, private, public, _ = fixture_definition(tmp_path)
    outside = tmp_path/'outside'
    outside.mkdir()
    (directory/'constitution.txt').rename(outside/'constitution.txt')
    link = directory/'redirect'
    if os.name == 'nt':
        subprocess.run(['cmd','/c','mklink','/J',str(link),str(outside)],check=True,capture_output=True)
    else:
        link.symlink_to(outside,target_is_directory=True)
    definition = replace(definition, constitution=replace(definition.constitution,path='redirect/constitution.txt'))
    signature = b64encode(private.sign(definition.digest.encode('ascii'))).decode()
    with pytest.raises(CoreDefinitionRejected):
        CoreDefinitionVerifier({'operator':public}).verify(definition.to_payload(), signature_b64=signature,
            signer_key_id='operator', assets_root=directory, expected_core_id=definition.identity.canonical_uuid,
            expected_runtime_sha256='a'*64, minimum_revision=1)


def test_untrusted_signature_does_not_observe_personal_assets(tmp_path, monkeypatch):
    directory, definition, _, public, _ = fixture_definition(tmp_path)
    import sofia.platform.ops.core_definition as module
    def forbidden(*args, **kwargs): raise AssertionError('untrusted request observed personal assets')
    monkeypatch.setattr(module, '_bounded_file', forbidden)
    with pytest.raises(CoreDefinitionRejected):
        CoreDefinitionVerifier({'operator':public}).verify(definition.to_payload(), signature_b64=b64encode(b'x'*64).decode(),
            signer_key_id='operator', assets_root=directory, expected_core_id=definition.identity.canonical_uuid,
            expected_runtime_sha256='a'*64, minimum_revision=1)


def test_definition_cli_verifies_without_allocating_state(tmp_path, capsys):
    from sofia.platform.ops.core_definition import main
    directory, definition, _, public, signature = fixture_definition(tmp_path)
    path, key = tmp_path/'definition.json', tmp_path/'operator.pub'
    path.write_bytes(definition.canonical_bytes)
    key.write_bytes(public)
    assert main(['--definition',str(path),'--assets-root',str(directory),'--trusted-public-key',str(key),
        '--signer-key-id','operator','--signature',signature,'--expected-core-id',definition.identity.canonical_uuid,
        '--expected-runtime-sha256','a'*64,'--minimum-revision','1']) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['result'] == 'VERIFIED_DEFINITION' and result['core_id'] == definition.identity.canonical_uuid
    assert result['definition_sha256'] == definition.digest
    assert not list(tmp_path.rglob('*.db'))


def test_removing_definition_signer_rejects_previous_signature(tmp_path):
    directory, definition, _, _, signature = fixture_definition(tmp_path)
    replacement = Ed25519PrivateKey.generate().public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)
    with pytest.raises(CoreDefinitionRejected):
        CoreDefinitionVerifier({'replacement':replacement}).verify(definition.to_payload(), signature_b64=signature,
            signer_key_id='operator', assets_root=directory, expected_core_id=definition.identity.canonical_uuid,
            expected_runtime_sha256='a'*64, minimum_revision=1)


@pytest.mark.parametrize('defect', ['protocol','bool_revision','asset_alias','null_uuid','schema'])
def test_definition_strict_versioned_contract_rejects_ambiguous_data(tmp_path, defect):
    directory, definition, private, public, signature = fixture_definition(tmp_path)
    payload = definition.to_payload()
    if defect == 'protocol':
        from sofia.sdk.contracts import ProtocolVersion
        definition = replace(definition,sdk_protocol=ProtocolVersion(2,0))
        payload = definition.to_payload()
        signature = b64encode(private.sign(definition.digest.encode('ascii'))).decode()
    elif defect == 'bool_revision': payload['revision'] = True
    elif defect == 'asset_alias': payload['personality'] = payload['constitution']
    elif defect == 'null_uuid': payload['identity']['uuid'] = '00000000-0000-0000-0000-000000000000'
    else: payload['schema'] = 'unknown'
    with pytest.raises(CoreDefinitionRejected):
        CoreDefinitionVerifier({'operator':public}).verify(payload, signature_b64=signature,
            signer_key_id='operator', assets_root=directory, expected_core_id=definition.identity.canonical_uuid,
            expected_runtime_sha256='a'*64, minimum_revision=1)


def test_cli_rejects_non_regular_definition_file(tmp_path, capsys):
    from sofia.platform.ops.core_definition import main
    assert main(['--definition',str(tmp_path),'--assets-root',str(tmp_path),'--trusted-public-key',str(tmp_path/'absent'),
        '--signer-key-id','operator','--signature','x','--expected-core-id',str(uuid4()),
        '--expected-runtime-sha256','a'*64,'--minimum-revision','1']) == 2
    assert json.loads(capsys.readouterr().out)['result'] == 'REJECTED'
