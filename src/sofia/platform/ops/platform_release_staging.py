"""Stage signed Platform code candidates; never install, select or activate."""
from __future__ import annotations

import json
import os
from pathlib import Path

from sofia.platform.ops.platform_release import PlatformReleaseVerifier, PlatformReleaseRejected
from sofia.platform.state.artifact_file import read_artifact_file
from sofia.platform.state.private_file import (
    assert_no_redirected_components, assert_owner_private_path,
    restrict_new_owner_private_path,
)
from sofia.platform.verify.python_runtime import materialize_python_runtime


def _write_new(path, data):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    assert_no_redirected_components(path, include_leaf=True)
    descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
    with os.fdopen(descriptor,'wb') as output:
        restrict_new_owner_private_path(path,directory=False)
        output.write(data)
        output.flush()
        os.fsync(output.fileno())


def _json(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')


def _sync_directories(destination):
    if os.name=='nt':
        return
    directories=[p for p in destination.rglob('*') if p.is_dir()]
    for path in sorted(directories,key=lambda p:len(p.parts),reverse=True)+[destination,destination.parent]:
        assert_no_redirected_components(path,include_leaf=True)
        descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_DIRECTORY',0))
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def stage_platform_release(*, verifier, payload, signature_b64, signer_key_id,
        assets_root, destination, expected_source_sha, expected_target, minimum_revision,
        expected_parent_manifest_sha256=None, state_schema_revision=1):
    """Copy verified bytes and materialize their runtime in a fresh private tree.

    The configured verifier supplies release trust, not installation authority.
    The caller supplies the trusted revision floor; this stage is not a durable
    anti-rollback store. Activation must recheck current release/owner authority.
    No state identity, environment installation or OS service is created here.
    Failure leaves a new partial candidate quarantined, never silently reset.
    """
    if not isinstance(verifier,PlatformReleaseVerifier):
        raise TypeError('configured Platform release verifier required')
    scope=dict(signature_b64=signature_b64,signer_key_id=signer_key_id,
        expected_source_sha=expected_source_sha,expected_target=expected_target,
        minimum_revision=minimum_revision,
        expected_parent_manifest_sha256=expected_parent_manifest_sha256,
        state_schema_revision=state_schema_revision)
    # Authenticate exact release scope before observing either candidate paths
    # or the artifact root. The existing verifier checks signature before I/O.
    manifest=verifier.verify(payload,assets_root=assets_root,**scope)
    destination=Path(destination).absolute()
    assert_no_redirected_components(destination,include_leaf=True)
    assert_owner_private_path(destination.parent,directory=True)
    if destination.exists():
        raise FileExistsError('candidate staging must not replace existing data')
    destination.mkdir(mode=0o700)
    restrict_new_owner_private_path(destination,directory=True)
    source=Path(assets_root).absolute()
    assets=destination/'assets'
    assets.mkdir(mode=0o700)
    for item in manifest.assets:
        reference=item.reference
        digest,data=read_artifact_file(source.joinpath(*reference.path.split('/')),
            reference.size_bytes,include_data=True)
        if digest!=reference.sha256:
            raise PlatformReleaseRejected('release source changed before staging')
        _write_new(assets.joinpath(*reference.path.split('/')),data)
    # Reverify copied bytes, not their original path or a cached boolean result.
    verifier.verify(manifest.to_payload(),assets_root=assets,**scope)
    runtime=next(item.reference for item in manifest.assets if item.kind=='python-runtime')
    inventory=materialize_python_runtime(assets.joinpath(*runtime.path.split('/')),
        destination/'runtime',expected=runtime,target=manifest.target,
        python_version=manifest.python_version)
    _write_new(destination/'release-manifest.json',manifest.canonical_bytes)
    _write_new(destination/'release-signature.json',_json(dict(
        signer_key_id=signer_key_id,signature_b64=signature_b64)))
    receipt=dict(schema='aegis.platform.code-stage.v1',result='VERIFIED_PLATFORM_CODE_STAGED',
        source_sha=manifest.source_sha,release_id=manifest.release_id,
        revision=manifest.revision,target=manifest.target.value,
        manifest_sha256=manifest.digest,signer_key_id=signer_key_id,
        asset_count=len(manifest.assets),runtime_file_count=len(inventory.files),
        activated=False,os_service_registered=False,state_initialized=False,
        service_health_verified=False)
    _write_new(destination/'stage-receipt.json',_json(receipt))
    _sync_directories(destination)
    return receipt
