"""Read-only signed Core definition verification; no install/start authority."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import stat

from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.sdk.core_definition import CoreDefinition
from sofia.sdk.identity import AegisIdentity, IdentityKind
from sofia.platform.ops.component_install import Ed25519ComponentSignatureVerifier, CoreComponentInstallError
from sofia.platform.state.private_file import assert_no_redirected_components
from sofia.platform.state.artifact_file import read_artifact_file as _read_file


class CoreDefinitionRejected(PermissionError):
    pass


def _bounded_file(path, size):
    return _read_file(path, size)[0]


class CoreDefinitionVerifier:
    def __init__(self, trusted_keys):
        self.signatures = Ed25519ComponentSignatureVerifier(trusted_keys)

    def verify(self, payload, *, signature_b64, signer_key_id, assets_root,
               expected_core_id, expected_runtime_sha256, minimum_revision):
        try:
            definition = CoreDefinition.from_payload(payload)
            expected = AegisIdentity.from_uuid_text(IdentityKind.CORE, expected_core_id)
            if definition.identity != expected:
                raise CoreDefinitionRejected('definition belongs to another Core identity')
            if definition.runtime_release_sha256 != expected_runtime_sha256:
                raise CoreDefinitionRejected('definition runtime release differs')
            if type(minimum_revision) is not int or minimum_revision < 1 or definition.revision < minimum_revision:
                raise CoreDefinitionRejected('definition revision is below the trusted floor')
            if definition.sdk_protocol.major != SDK_PROTOCOL_VERSION.major or definition.sdk_protocol.minor > SDK_PROTOCOL_VERSION.minor:
                raise CoreDefinitionRejected('definition requires an unsupported SDK protocol')
            # Signature and expected target are verified before observing assets.
            self.signatures.verify_digest(definition.digest, signature_b64=signature_b64, signer_key_id=signer_key_id)
            root = Path(assets_root).absolute()
            assert_no_redirected_components(root, include_leaf=True)
            if not root.is_dir(): raise CoreDefinitionRejected('definition package root unavailable')
            for asset in (definition.constitution, definition.personality):
                target = root.joinpath(*asset.path.split('/'))
                if _bounded_file(target,asset.size_bytes) != asset.sha256:
                    raise CoreDefinitionRejected('personal asset digest differs')
            return definition  # inert metadata, never a permit or selected Core
        except CoreDefinitionRejected:
            raise
        except (CoreComponentInstallError, OSError, ValueError, TypeError, KeyError) as exc:
            raise CoreDefinitionRejected('signed Core definition rejected') from exc


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--definition',type=Path,required=True)
    parser.add_argument('--assets-root',type=Path,required=True)
    parser.add_argument('--trusted-public-key',type=Path,required=True)
    parser.add_argument('--signer-key-id',required=True)
    parser.add_argument('--signature',required=True)
    parser.add_argument('--expected-core-id',required=True)
    parser.add_argument('--expected-runtime-sha256',required=True)
    parser.add_argument('--minimum-revision',type=int,required=True)
    args = parser.parse_args(argv)
    try:
        assert_no_redirected_components(args.definition.absolute(),include_leaf=True)
        details = args.definition.stat(follow_symlinks=False)
        if not stat.S_ISREG(details.st_mode) or not 1 <= details.st_size <= 16_384:
            raise ValueError('definition must be a regular file within 16-KiB bound')
        _, raw = _read_file(args.definition.absolute(), details.st_size, include_data=True)
        def unique(pairs):
            result = {}
            for key,value in pairs:
                if key in result: raise ValueError('duplicate definition field')
                result[key]=value
            return result
        payload = json.loads(raw,object_pairs_hook=unique)
        verified = CoreDefinitionVerifier({args.signer_key_id:args.trusted_public_key}).verify(payload,
            signature_b64=args.signature,signer_key_id=args.signer_key_id,assets_root=args.assets_root,
            expected_core_id=args.expected_core_id,expected_runtime_sha256=args.expected_runtime_sha256,
            minimum_revision=args.minimum_revision)
        print(json.dumps({'result':'VERIFIED_DEFINITION','core_id':verified.identity.canonical_uuid,
            'serial':verified.identity.serial,'revision':verified.revision,'definition_sha256':verified.digest},sort_keys=True))
        return 0
    except (OSError,ValueError,TypeError) as exc:
        print(json.dumps({'result':'REJECTED','reason':str(exc)}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
