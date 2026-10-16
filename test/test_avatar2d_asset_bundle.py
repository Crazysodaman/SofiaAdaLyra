"""Verified 2D artwork is data, never an adult permission or visual receipt."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import zlib

import pytest

from test.owner_auth_fixture import private_with_signed_owner

from sofia.avatar.private_grant import PrivatePresentationGrantResolver
from sofia.avatar.presentation import AttireMode
from sofia.avatar.presentation_runtime import load_or_bootstrap_presentation
from sofia.avatar.vtuber_asset_bundle import (
    Avatar2DAssetError, Avatar2DAssetGateway,
)
from sofia.embodiment.store import EmbodimentStore
from sofia.safe.permissions import PermissionStore
from sofia.social.principals import local_sparks_principal


SEED = Path(__file__).resolve().parents[1] / "src/sofia/embodiment/avatar.json"


def _chunk(name: bytes, value: bytes) -> bytes:
    return (
        len(value).to_bytes(4, "big")
        + name + value
        + (zlib.crc32(name + value) & 0xFFFFFFFF).to_bytes(4, "big")
    )


def rgba_png() -> bytes:
    # Genuine tiny 1x1 RGBA PNG with scanline filter byte + red pixel.
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", (1).to_bytes(4, "big") * 2 + bytes((8, 6, 0, 0, 0)))
        + _chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00\xff"))
        + _chunk(b"IEND", b"")
    )


def write_bundle(
    root: Path, *, audience="public", attire="clothed",
    outfit_id="day.default", png=None, reported_hash=None,
    image_path="base/torso.png",
):
    root.mkdir(parents=True, exist_ok=True)
    payload = rgba_png() if png is None else png
    # Test fixtures must never write outside their owned temporary root.
    if image_path == "base/torso.png":
        relative = root / image_path
        relative.parent.mkdir(parents=True, exist_ok=True)
        relative.write_bytes(payload)
    manifest = {
        "schema": "sofia.avatar2d.asset_bundle.v1",
        "bundle_id": "public.default" if audience == "public" else "private.owned",
        "audience": audience, "attire": attire, "outfit_id": outfit_id,
        "layers": [{
            "id": "torso",
            "path": image_path,
            "sha256": reported_hash or sha256(payload).hexdigest(),
        }],
    }
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def gateway(tmp_path):
    state_path = tmp_path / "sofia.db"
    bundle = load_or_bootstrap_presentation(
        embodiment=EmbodimentStore(SEED).load(),
        state_path=state_path,
    )
    resolver = PrivatePresentationGrantResolver(state_path=state_path)
    public_root = tmp_path / "art_public"
    private_root = tmp_path / "protected" / "art_private"
    write_bundle(public_root)
    return (
        Avatar2DAssetGateway(
            authority=bundle.authority,
            grant_resolver=resolver,
            public_root=public_root,
            private_root=private_root,
        ),
        bundle,
        state_path,
        public_root,
        private_root,
    )


def enter_private_nude(bundle, state_path):
    private_with_signed_owner(
        PermissionStore(state_path),
        private_chat=True, adult_chat=False, adult_avatar=True,
        adult_external_delivery=False,
    )
    grant = PrivatePresentationGrantResolver(state_path=state_path).resolve(
        principal=local_sparks_principal(),
        explicit_current_opt_in=True,
    )
    assert grant is not None
    current = bundle.authority.current
    bundle.authority.propose_nude(
        operation_id="avatar2d.private.test",
        expected_revision=current.revision,
        reason="test-only explicit private portrait",
        grant=grant,
    )
    bundle.authority.commit_text(
        operation_id="avatar2d.private.test",
        renderer_unavailable=True, grant=grant,
    )


def test_public_art_loads_and_clear_zeroizes_without_private_assets(tmp_path):
    loader, _, _, _, _ = gateway(tmp_path)
    selection = loader.public()
    assert selection.status == "public"
    art = selection.bundle
    assert art is not None and art.audience.value == "public"
    before = art.images["torso"][:]
    assert before.startswith(b"\x89PNG")
    assert "images" not in repr(art)
    art.close()
    assert art.images == {}
    with pytest.raises(Avatar2DAssetError, match="closed"):
        with art:
            pass


def test_private_request_without_real_host_authority_uses_public_fallback(tmp_path):
    loader, _, _, _, private_root = gateway(tmp_path)
    # Even if private files are present, a request alone can never expose them.
    write_bundle(
        private_root / "nude", audience="private",
        attire="nude", outfit_id=None,
    )
    selected = loader.private(
        principal=local_sparks_principal(),
        explicit_current_opt_in=True,
    )
    assert selected.status == "public_fallback"
    assert selected.bundle is not None
    assert selected.bundle.audience.value == "public"
    selected.bundle.close()


def test_private_art_requires_matching_current_authorized_nude_state(tmp_path):
    loader, bundle, state, _, private_root = gateway(tmp_path)
    write_bundle(
        private_root / "nude", audience="private",
        attire="nude", outfit_id=None,
    )
    enter_private_nude(bundle, state)

    selected = loader.private(
        principal=local_sparks_principal(),
        explicit_current_opt_in=True,
    )
    assert selected.status == "private"
    assert selected.projection.attire is AttireMode.NUDE
    assert selected.bundle is not None and selected.bundle.audience.value == "private"
    assert loader.private_still_authorized(
        selected, principal=local_sparks_principal(),
        explicit_current_opt_in=True,
    )
    assert not loader.private_still_authorized(
        selected, principal=local_sparks_principal(),
        explicit_current_opt_in=False,
    )
    assert selected.bundle.images == {}


def test_revoke_durable_private_authority_mid_session_clears_loaded_art(tmp_path):
    loader, bundle, state, _, private_root = gateway(tmp_path)
    write_bundle(
        private_root / "nude", audience="private",
        attire="nude", outfit_id=None,
    )
    enter_private_nude(bundle, state)
    selected = loader.private(
        principal=local_sparks_principal(), explicit_current_opt_in=True,
    )
    assert selected.status == "private"
    private_with_signed_owner(
        PermissionStore(state),
        private_chat=True, adult_chat=False, adult_avatar=False,
        adult_external_delivery=False,
    )
    assert not loader.private_still_authorized(
        selected, principal=local_sparks_principal(),
        explicit_current_opt_in=True,
    )
    assert selected.bundle is not None and selected.bundle.images == {}
    after = loader.private(
        principal=local_sparks_principal(), explicit_current_opt_in=True,
    )
    assert after.status == "public_fallback"
    after.bundle.close()


@pytest.mark.parametrize("relative", [
    "../outside.png", "/tmp/file.png", "base/../torso.png",
    "base\\torso.png", "C:/secret.png", "torso.png",
])
def test_invalid_image_paths_never_escape_bundle(tmp_path, relative):
    loader, _, _, public_root, _ = gateway(tmp_path)
    write_bundle(public_root, image_path=relative)
    selection = loader.public()
    assert selection.status == "unavailable"
    assert selection.bundle is None


def test_symlinked_asset_is_rejected(tmp_path):
    loader, _, _, public_root, _ = gateway(tmp_path)
    art = public_root / "base" / "torso.png"
    external = tmp_path / "external.png"
    external.write_bytes(rgba_png())
    art.unlink()
    try:
        art.symlink_to(external)
    except (NotImplementedError, OSError):
        pytest.skip("this platform does not allow test symlinks")
    selection = loader.public()
    assert selection.status == "unavailable"


def test_hash_and_png_container_enforced(tmp_path):
    loader, _, _, public_root, _ = gateway(tmp_path)
    write_bundle(public_root, reported_hash="0" * 64)
    assert loader.public().status == "unavailable"
    write_bundle(public_root, png=b"not actually an RGBA image")
    assert loader.public().status == "unavailable"


def test_private_bundle_mismatch_falls_back_without_private_path_disclosure(tmp_path):
    loader, bundle, state, _, private_root = gateway(tmp_path)
    write_bundle(
        private_root / "nude", audience="public",
        attire="clothed", outfit_id="day.default",
    )
    enter_private_nude(bundle, state)
    selected = loader.private(
        principal=local_sparks_principal(), explicit_current_opt_in=True,
    )
    assert selected.status == "public_fallback"
    assert "private" not in selected.reason
    selected.bundle.close()


def test_public_and_private_roots_must_be_distinct(tmp_path):
    loader, bundle, state, public_root, _ = gateway(tmp_path)
    with pytest.raises(ValueError, match="separate"):
        Avatar2DAssetGateway(
            authority=bundle.authority,
            grant_resolver=PrivatePresentationGrantResolver(state_path=state),
            public_root=public_root, private_root=public_root / "private",
        )
