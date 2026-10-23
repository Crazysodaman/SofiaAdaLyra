"""Full-batch candidate sprite production: scope, coverage, and real PNG pixels."""
from hashlib import sha256
import json
from pathlib import Path
import zlib

import pytest

from sofia.avatar.private_grant import PrivatePresentationGrantResolver
from sofia.avatar.wardrobe_catalog import build_starter_wardrobe
from sofia.avatar.vtuber_starter_art import PNG_HEADER
from sofia.avatar.vtuber_full_batch_art import (
    _draft_png, build_draft_batch, _art_color,
)
from sofia.avatar.vtuber_wardrobe_production import GARMENT_FILES
from sofia.platform.safe.permissions import PermissionStore
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite
from sofia.core.social.principals import local_sparks_principal
from test.owner_auth_fixture import private_with_signed_owner


def _rgba_alpha_present(blob):
    assert blob.startswith(PNG_HEADER)
    chunks=[]
    pos=8
    while pos<len(blob):
        n=int.from_bytes(blob[pos:pos+4],"big")
        tag=blob[pos+4:pos+8]
        data=blob[pos+8:pos+8+n]
        if tag==b"IDAT":
            chunks.append(data)
        pos+=12+n
    pixel=zlib.decompress(b"".join(chunks))
    width=int.from_bytes(blob[16:20],"big")
    height=int.from_bytes(blob[20:24],"big")
    return any(pixel[row*(1+width*4)+1+col*4+3]
               for row in range(height) for col in range(width))


def test_each_of_fourteen_source_categories_produces_real_visible_png():
    catalog=build_starter_wardrobe()
    blueprint_by_id={b.garment.item_id:b for b in catalog.blueprints}
    from sofia.avatar.vtuber_wardrobe_production import canonical_json_wardrobe_records
    entries=canonical_json_wardrobe_records()
    for filename in GARMENT_FILES:
        # Some canonical source categories are intentionally protected-only.
        # Rendering a representative in memory verifies category coverage; it
        # does not publish the record or weaken its private classification.
        _,item=next((f,g) for f,g in entries if f==filename)
        blueprint=blueprint_by_id[item["item_id"]]
        blob=_draft_png(blueprint,filename.removesuffix(".json"),"front")
        assert _rgba_alpha_present(blob), item["item_id"]
        assert sha256(blob).hexdigest()


def test_named_colors_match_canonical_hex_palette():
    catalog=build_starter_wardrobe()
    by_id={b.garment.item_id:b for b in catalog.blueprints}
    jacket=by_id["day.engineer_jacket"]
    color,accent=_art_color(jacket.design)
    assert color[:3] == (11,13,18)
    assert accent[:3] == (139,30,63)
    violet=by_id["ear.02.violet_ear_cuffs"]
    assert _art_color(violet.design)[0][:3] == (58,36,92)


def test_whole_public_batch_emits_every_unique_public_id_and_required_view(
    monkeypatch,tmp_path,
):
    from sofia.avatar import vtuber_full_batch_art
    from sofia.avatar.vtuber_starter_art import Sprite
    placeholder=Sprite()
    placeholder.rectangle((140,160,170,190),(100,100,100,255))
    blob=placeholder.png()
    monkeypatch.setattr(vtuber_full_batch_art,"_draft_png",lambda *args:blob)
    out=tmp_path/"public"
    reports=build_draft_batch(public_root=out)
    assert len(reports)==1
    assert reports[0].items==244
    data=json.loads((out/"manifest.json").read_text("utf-8"))
    assert data["expected_items"]==244
    assert data["quality"]=="procedural_draft_not_image_generated_or_reviewed"
    assert len({x["item_id"] for x in data["items"]})==244
    assert len(data["items"])==reports[0].images
    assert all(not x["exact_source_match"] for x in data["items"])
    assert all((out/x["relative_path"]).read_bytes()==blob for x in data["items"])
    assert not any("private" in x["item_id"] for x in data["items"])
    with pytest.raises(FileExistsError):
        build_draft_batch(public_root=out)


def test_private_batch_reuses_durable_safe_authority_and_separate_root(
    monkeypatch,tmp_path,
):
    from sofia.avatar import vtuber_full_batch_art
    from sofia.avatar.vtuber_starter_art import Sprite
    src=Sprite()
    src.ellipse((143,166,175,211),(40,30,52,255))
    monkeypatch.setattr(vtuber_full_batch_art,"_draft_png",lambda *args:src.png())
    state=bootstrap_canonical_sqlite(tmp_path/"sofia.db")
    resolver=PrivatePresentationGrantResolver(state_path=state)
    public=tmp_path/"public"
    private=tmp_path/"protected"/"private"
    with pytest.raises(PermissionError):
        build_draft_batch(
            public_root=public,private_root=private,resolver=resolver,
            owner_opt_in=True,
        )
    assert not public.exists() and not private.exists()
    private_with_signed_owner(
        PermissionStore(state),private_chat=True,
        adult_chat=False,adult_avatar=True,adult_external_delivery=False,
    )
    with pytest.raises(PermissionError):
        build_draft_batch(
            public_root=public,private_root=private,resolver=resolver,
            owner_opt_in=False,
        )
    reports=build_draft_batch(
        public_root=public,private_root=private,resolver=resolver,
        owner_opt_in=True,
    )
    assert len(reports)==2
    assert reports[0].items==244
    assert reports[1].items==51
    public_manifest=json.loads((public/"manifest.json").read_text("utf-8"))
    protected_manifest=json.loads((private/"manifest.json").read_text("utf-8"))
    assert public_manifest["audience"]=="public"
    assert protected_manifest["audience"]=="private"
    assert {x["item_id"] for x in public_manifest["items"]}.isdisjoint(
        {x["item_id"] for x in protected_manifest["items"]}
    )
    assert len({x["item_id"] for x in protected_manifest["items"]})==51
    assert public_manifest["expected_items"]+protected_manifest["expected_items"]==295


def test_private_paths_never_nested_in_public(tmp_path):
    root=tmp_path/"art"
    state=bootstrap_canonical_sqlite(tmp_path/"sofia.db")
    with pytest.raises(ValueError,match="separate"):
        build_draft_batch(
            public_root=root,
            private_root=root/"private",
            resolver=PrivatePresentationGrantResolver(
                state_path=state,
            ),
            owner_opt_in=True,
        )
