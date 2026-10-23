"""AVATAR 2D geometry regression, with no untrusted UI event promoted to touch."""
from pathlib import Path

import pytest

from sofia.modules.avatar.presentation import AudienceScope, PrivatePresentationGrant
from sofia.modules.avatar.vtuber_hit_test import (
    LayerTransform, RenderedHitFrame, RenderedHitLayer, hit_test_avatar,
)
from sofia.core.embodiment.store import EmbodimentStore
from sofia.modules.interaction.core import InteractionEngine


AVATAR = Path(__file__).resolve().parents[1] / "src/sofia/core/embodiment/avatar.json"
DIGEST = "a" * 64


def regions():
    return InteractionEngine(EmbodimentStore(AVATAR).load()).regions


def layer(name, region, *, mask=b"\xff" * 4, z=0,
          audience=AudienceScope.PUBLIC, transform=None, garment_id=None):
    return RenderedHitLayer(
        layer_id=name, region_id=region,
        z_index=z, mask_width=2, mask_height=2,
        alpha_mask=mask,
        transform=transform or LayerTransform(), audience=audience,
        garment_id=garment_id,
    )


def frame(*layers, audience=AudienceScope.PUBLIC):
    return RenderedHitFrame(
        frame_id="visible.frame.6", presentation_revision=6,
        bundle_digest=DIGEST, audience=audience,
        layers=tuple(layers),
    )


def resolve(rendered, *, x=0.3, y=0.3, grant=None, revision=6, fid="visible.frame.6"):
    return hit_test_avatar(
        rendered, viewport_x=x, viewport_y=y, expected_frame_id=fid,
        expected_revision=revision, canonical_regions=regions(),
        private_grant=grant,
    )


def grant():
    return PrivatePresentationGrant(
        adult_verified=True, owner_verified=True,
        private_session=True, explicit_current_opt_in=True,
        external_stop_active=False,
    )


def test_exact_visible_fox_ear_and_tail_tip():
    ears = frame(layer("fox.ear.left", "left-ear-tip"))
    assert resolve(ears).region_id == "left-ear-tip"
    tail = frame(layer("fox.tail.tip", "tail-tip"))
    assert resolve(tail).region_id == "tail-tip"
    assert resolve(ears).status == "hit"
    assert resolve(ears, x=1.05).status == "miss"


def test_true_painted_z_order_and_transparency():
    body = layer("torso.base", "torso", z=1)
    # The top layer's top-left pixel is transparent; click passes to body.
    hair = layer("hair.fringe", "hair", z=8, mask=b"\x00\xff\xff\xff")
    rendered = frame(body, hair)
    assert resolve(rendered, x=0.2, y=0.2).region_id == "torso"
    assert resolve(rendered, x=0.8, y=0.2).region_id == "hair"


def test_garment_occlusion_keeps_item_identified_without_claiming_skin_touch():
    rendered = frame(
        layer("body.visible", "torso", z=1),
        layer("jacket.front", "torso", z=7, garment_id="engineer.jacket"),
    )
    found = resolve(rendered)
    assert found.status == "hit"
    assert found.region_id == "torso"
    assert found.garment_id == "engineer.jacket"
    assert found.layer_id == "jacket.front"


def test_affine_mirror_and_translation_follow_painted_geometry():
    # x viewport = 0.8 - 0.5*local_x; y = 0.1 + 0.6*local_y.
    t = LayerTransform(a=-0.5, b=0.0, c=0.8, d=0.0, e=0.6, f=0.1)
    rendered = frame(layer("ear.flipped", "right-ear", transform=t))
    assert resolve(rendered, x=0.7, y=0.3).region_id == "right-ear"
    assert resolve(rendered, x=0.2, y=0.3).status == "miss"


def test_stale_presentation_or_frame_cannot_resolve_contact():
    rendered = frame(layer("tail", "tail-base"))
    assert resolve(rendered, revision=5).status == "stale"
    assert resolve(rendered, fid="last.frame.5").status == "stale"
    stale = resolve(rendered, fid="last.frame.5")
    assert stale.region_id is None and stale.layer_id is None


def test_private_waist_up_region_never_leaks_to_public_or_without_grant():
    protected = layer(
        "private.torso", "chest",
        audience=AudienceScope.PRIVATE,
    )
    with pytest.raises(ValueError, match="private layer"):
        frame(protected)
    rendered = frame(protected, audience=AudienceScope.PRIVATE)
    denied = resolve(rendered)
    assert denied.status == "restricted"
    assert denied.region_id is None
    assert denied.layer_id is None
    assert resolve(rendered, grant=grant()).region_id == "chest"
    denied_again = resolve(
        rendered,
        grant=PrivatePresentationGrant(True, True, True, True, True),
    )
    assert denied_again.status == "restricted"
    assert denied_again.region_id is None


def test_public_region_private_classification_still_requires_grant():
    # Even a faulty public layer marking cannot expose a canonical private region.
    rendered = frame(layer("misclassified.chest", "chest"))
    result = resolve(rendered)
    assert result.status == "restricted"
    assert result.region_id is None
    assert result.garment_id is None


def test_unknown_geometry_and_missing_actual_alpha_fail_closed():
    rendered = frame(layer("unmapped", "unknown-for-avatar"))
    assert resolve(rendered).status == "miss"
    with pytest.raises(ValueError, match="dimensions do not match"):
        layer("ear", "left-ear", mask=b"\xff")
    with pytest.raises(ValueError, match="invertible"):
        LayerTransform(a=0, e=0)
    with pytest.raises(ValueError, match="duplicate"):
        frame(layer("same", "hair"), layer("same", "tail"))
    with pytest.raises(ValueError, match="bundle digest"):
        RenderedHitFrame(
            frame_id="f", presentation_revision=1, bundle_digest="bad",
            audience=AudienceScope.PUBLIC, layers=(),
        )


def test_hit_test_never_converts_a_click_into_a_pat_or_consent():
    found = resolve(frame(layer("left.shoulder", "left-shoulder")))
    assert found.status == "hit"
    assert found.region_id == "left-shoulder"
    assert not hasattr(found, "gesture")
    assert not hasattr(found, "accepted")
    assert not hasattr(found, "emotion")
