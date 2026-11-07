"""Platform release metadata is independent of any individual Core."""
from hashlib import sha256
from dataclasses import replace
import pytest

from sofia.sdk.artifact import ArtifactReference
from sofia.sdk.platform_release import PlatformReleaseManifest, PlatformReleaseAsset, PlatformReleaseTarget
from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.sdk.core_definition import CoreAssetReference


def release():
    roles = ['sdk','platform','service','python-runtime','dependency-lock','sbom','provenance']
    return PlatformReleaseManifest('aegis-platform-rc1', '0.1.0', 1, 'a'*40,
        PlatformReleaseTarget.DEBIAN12_X86_64, SDK_PROTOCOL_VERSION, '3.12.16',
        tuple(PlatformReleaseAsset(role, ArtifactReference(role+'.bin',sha256(role.encode()).hexdigest(),len(role)))
            for role in roles))


def test_platform_release_has_no_personal_core_dependencies():
    manifest = release()
    assert PlatformReleaseManifest.from_payload(manifest.to_payload()) == manifest
    assert 'constitution' not in manifest.to_payload()
    assert 'core' not in [asset.kind for asset in manifest.assets]
    assert len(manifest.digest) == 64
    with pytest.raises(ValueError):
        PlatformReleaseManifest.from_payload(manifest.to_payload() | {'constitution_sha256':'0'*64})


def test_existing_core_asset_limit_remains_compatible():
    generic = ArtifactReference('runtime/python.zip','a'*64,20*1024*1024)
    assert generic.size_bytes > 16*1024*1024
    with pytest.raises(ValueError):
        CoreAssetReference(generic.path,generic.sha256,generic.size_bytes)
    core = CoreAssetReference('constitution.txt','b'*64,20)
    assert core.to_payload() == {'path':'constitution.txt','sha256':'b'*64,'size_bytes':20}


@pytest.mark.parametrize('changes', [dict(revision=True),dict(revision=0),dict(source_sha='bad'),dict(version='01.0.0'),dict(python_version='3.11.9')])
def test_release_rejects_ambiguous_or_unsupported_contract_fields(changes):
    with pytest.raises((TypeError,ValueError)):
        replace(release(),**changes)


def test_release_rejects_missing_duplicate_and_core_assets():
    manifest = release()
    with pytest.raises(ValueError): replace(manifest,assets=manifest.assets[:-1])
    with pytest.raises(ValueError): replace(manifest,assets=manifest.assets+(manifest.assets[0],))
    with pytest.raises(ValueError): PlatformReleaseAsset('core',ArtifactReference('core.whl','a'*64,1))
