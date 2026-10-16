"""Produce an actual transparent PNG draft for ALL 295 source JSON garments.

The source JSON and canonical GarmentBlueprint stay authoritative. Art is
DETERMINISTIC PROCEDURAL DRAFT, never claimed professional/anatomically exact
2D illustration. A nonempty *reviewed* asset folder is never overwritten.

Public assets and private garment-only study assets go to separate roots.
Private worklist generation requires a fresh SAFE resolver + owner principal
and opt-in; a private sprite file alone NEVER confers display authorization.
No private material is committed to Git, CI artifacts or public catalog.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path

from .vtuber_starter_art import Sprite, _garment, _hex, _shade, WIDTH, HEIGHT
from .vtuber_wardrobe_production import (
    wardrobe_production_queue, wardrobe_production_coverage,
    protected_work_orders,
)
from .vtuber_art_fidelity import brief_from_blueprint
from .wardrobe_catalog import build_starter_wardrobe
from .wardrobe import Layer, normalize_slots
from .vtuber_layer_stack import WAIST_UP_SLOTS
from .private_grant import PrivatePresentationGrantResolver
from sofia.social.principals import local_sparks_principal


SCHEMA = "sofia.avatar2d.wardrobe_candidate_batch.v1"
# These are visual drafts, NOT final item fidelity or real production rig assets.
DRAFT_STATUS = "generated_procedural_candidate_visual_review_required"


@dataclass(frozen=True)
class BatchReport:
    items: int
    images: int
    public: bool
    root: str


def _art_color(design):
    primary = _hex(design.primary)
    accent = _hex(design.accent) if design.accent else (123, 91, 175, 255)
    return primary, accent


def _draw_accessory(category, design, color, accent):
    s=Sprite()
    name=design.name.casefold()
    if category=="accessories_ear":
        for x in (95,213):
            if "ribbon" in name:
                s.polygon(((x,104),(x-17,88),(x-19,121)),color)
                s.polygon(((x,104),(x+18,85),(x+22,121)),accent)
            elif "chain" in name:
                s.path(((x-8,104),(x+3,126),(x+17,142)),3,accent)
                s.ellipse((x+10,140,x+20,149),color)
            else:
                s.ellipse((x-13,91,x+14,121),color)
                s.ellipse((x-8,98,x+10,115),accent)
    elif category=="accessories_tail":
        # Standalone view of a band/sleeve around one tail, not extra tails.
        s.path(((95,306),(155,279),(215,277),(261,232)),25,color)
        s.ellipse((152,265,190,298),accent)
        if "ribbon" in name:
            s.polygon(((160,275),(132,250),(131,294)),accent)
            s.polygon(((174,276),(203,253),(201,299)),accent)
    elif category=="accessories_neck":
        if "pendant" in name or "necklace" in name:
            s.path(((120,145),(150,181),(181,145)),4,color)
            s.polygon(((150,172),(140,190),(153,205),(163,188)),accent)
        else:
            s.path(((105,153),(152,163),(208,153)),13,color)
            s.ellipse((149,152,163,165),accent)
    elif category=="accessories_waist":
        s.rectangle((76,249,245,269),color)
        s.rectangle((142,246,178,273),accent)
        s.rectangle((151,250,170,269),color)
        if "chain" in name:
            s.path(((83,268),(140,301),(215,268)),3,accent)
    elif category=="accessories_hand_wrist":
        for x in (86,203):
            if "glove" in name:
                s.polygon(((x,230),(x+40,230),(x+43,290),
                           (x+30,309),(x-3,290)),color)
                if "fingerless" in name:
                    s.rectangle((x+4,286,x+36,296),accent)
            else:
                s.rectangle((x,267,x+39,283),color)
                s.rectangle((x+4,272,x+35,277),accent)
    elif category=="accessories_legwear":
        for x in (92,190):
            s.polygon(((x,100),(x+45,100),(x+39,346),
                       (x+26,358),(x,340)),color)
            s.rectangle((x-1,99,x+45,113),accent)
            if "rib" in name or "warm" in name:
                for y in range(141,340,22):
                    s.path(((x+2,y),(x+39,y)),2,_shade(color,1.27))
    return s.png()


def _draw_bottoms(category, design, color, accent):
    s=Sprite()
    shape=design.garment_type.casefold()
    length=design.length.casefold()
    is_skirt="skirt" in shape or "skirt" in design.name.casefold()
    end=170 if length in ("short","micro","brief","minimal") else (
        230 if length in ("above_knee","mid_thigh","knee","hipster") else 367
    )
    if category=="accessories_legwear":
        return _draw_accessory(category,design,color,accent)
    if category=="footwear":
        for x in (83,190):
            tall="boot" in shape or "boot" in design.name.casefold()
            if tall:
                s.polygon(((x+4,120),(x+47,120),(x+46,304),
                           (x+68,325),(x+71,352),(x-5,352)),color)
                s.path(((x+9,143),(x+14,270)),3,accent)
            else:
                s.polygon(((x,287),(x+46,287),(x+51,316),
                           (x+68,329),(x+70,353),(x-5,353)),color)
            s.path(((x-3,348),(x+67,348)),5,accent)
        return s.png()
    if category in ("underlayers_lower","bottoms"):
        if is_skirt:
            s.polygon(((108,102),(211,102),(251,end),
                       (72,end)),color)
            s.path(((109,113),(210,113)),5,accent)
            if "pleat" in design.name.casefold():
                for x in (105,132,160,188,216):
                    s.path(((160,119),(x,end-5)),2,_shade(color,1.27))
        elif length in ("brief","minimal","hipster") and "short" not in shape:
            s.polygon(((108,110),(209,110),(201,176),
                       (177,165),(158,187),(140,165),(119,179)),color)
            s.path(((111,119),(209,119)),4,accent)
        else:
            s.polygon(((106,108),(213,108),(213,168),
                       (199,end),(170,end),(160,175),
                       (149,end),(115,end),(107,170)),color)
            s.path(((108,119),(209,119)),4,accent)
            s.path(((155,172),(149,end-3)),3,_shade(color,1.33))
            if "pocket" in design.features:
                s.path(((110,139),(132,153),(140,138)),3,accent)
                s.path(((180,138),(188,153),(209,138)),3,accent)
        return s.png()
    raise ValueError("unknown lower garment family")


def _draw_one_piece(design,color,accent,view):
    s=Sprite()
    name=design.name.casefold()
    t=design.garment_type.casefold()
    long_outfit="dress" in t or "gown" in name
    sleeves=design.sleeve_length
    large=design.fit in ("relaxed","oversized")
    l=115 if design.length=="cropped" else 135
    side=87 if large else 102
    s.polygon(((side,l),(135,108),(183,108),(320-side,l),
               (215,268),(229,390),(90,390),(106,268)),color)
    if "strap" in name or "tank" in name or sleeves=="sleeveless":
        s.path(((116,118),(126,92)),6,accent)
        s.path(((203,118),(194,92)),6,accent)
    if long_outfit:
        s.polygon(((106,250),(212,250),(257,388),(69,388)),color)
        s.path(((102,268),(215,268)),4,accent)
        for x in (108,141,175,206):
            s.path(((160,270),(x,387)),2,_shade(color,1.2))
    if sleeves=="long":
        for left in (True,False):
            x=84 if left else 218
            s.polygon(((x,132),(x+24,131),(x+32,334),
                       (x+6,334)),color)
    if "zip" in name or "zip" in " ".join(design.features):
        s.path(((160,114),(160,306)),3,accent)
    if "pocket" in " ".join(design.features):
        s.rectangle((110,246,141,269),_shade(color,.81))
        s.rectangle((180,246,211,269),_shade(color,.81))
    if "tail_clearance" in design.features and view=="back":
        # A tail-accessible hem aperture, not a body/anatomy depiction.
        s.ellipse((146,266,175,285),(0,0,0,0))
        s.path(((146,275),(177,275)),3,accent)
    return s.png()


def _draw_upper(bp,view,color,accent):
    design=bp.design
    slots=frozenset(normalize_slots(bp.garment.slots))
    # For tops/outerwear/underlayers, keep exactly the same spatial anchors
    # as the existing 320x400 compositing renderer.
    if bp.garment.layer in (Layer.BASE,Layer.MID,Layer.OUTER,Layer.UNDERWEAR):
        art=_garment(
            name=design.name,category=design.garment_type,
            layer=bp.garment.layer,
            slots=frozenset(slots & WAIST_UP_SLOTS),
            color=color,
            accents=(f"#{accent[0]:02X}{accent[1]:02X}{accent[2]:02X}",),
        )
    else:
        art=None
    s=Sprite()
    if art is not None:
        # _garment already returns PNG; geometry is augmented by an optional
        # transparent detail overlay but not decoded here, so the base remains
        # the compatible source. Generated draft does not pretend visual fidelity.
        return art
    return s.png()


def _draft_png(bp,category,view):
    d=bp.design
    color,accent=_art_color(d)
    if category in ("accessories_ear","accessories_hand_wrist",
                    "accessories_legwear","accessories_neck",
                    "accessories_tail","accessories_waist"):
        return _draw_accessory(category,d,color,accent)
    if category in ("footwear","bottoms","underlayers_lower"):
        return _draw_bottoms(category,d,color,accent)
    if category=="one_pieces":
        return _draw_one_piece(d,color,accent,view)
    if category in ("tops","outerwear","underlayers_upper","intimate_underlayers"):
        return _draw_upper(bp,view,color,accent)
    raise ValueError("source category has no art renderer")


def build_draft_batch(
    *,
    public_root: Path,
    private_root: Path | None = None,
    resolver: PrivatePresentationGrantResolver | None = None,
    owner_opt_in: bool = False,
    catalog=None,
) -> tuple[BatchReport, ...]:
    """Generate 244 public and, only with live owner authority, 51 private.

    Do not use this command as a substitute for actual owner visual approval.
    """
    if catalog is None:
        catalog=build_starter_wardrobe()
    queue=wardrobe_production_queue(catalog=catalog)
    coverage=wardrobe_production_coverage(queue)
    # Counts are deliberately dynamic: adding/removing items automatically
    # changes the batch, instead of silently keeping a stale 275 cap.
    if coverage.total != len(queue):
        raise ValueError("incomplete canonical wardrobe inventory")
    targets=[(False,Path(public_root))]
    if private_root is not None:
        if not isinstance(resolver, PrivatePresentationGrantResolver):
            raise PermissionError("trusted SAFE private resolver required")
        if not owner_opt_in:
            raise PermissionError("private sprite generation requires current opt-in")
        protected=protected_work_orders(
            resolver=resolver,
            principal=local_sparks_principal(),
            explicit_current_opt_in=True,
            catalog=catalog,
        )
        if len(protected)!=coverage.private:
            raise ValueError("private wardrobe inventory incomplete")
        targets.append((True,Path(private_root)))
    resolved=[target.resolve() for _,target in targets]
    if len(resolved)>1 and (
        resolved[0]==resolved[1]
        or resolved[0].is_relative_to(resolved[1])
        or resolved[1].is_relative_to(resolved[0])
    ):
        raise ValueError("private artwork root must be physically separate")
    blueprints={bp.garment.item_id:bp for bp in catalog.blueprints}
    reports=[]
    for is_private,root in targets:
        if root.is_symlink() or (root.exists() and any(root.iterdir())):
            raise FileExistsError("art output must be a fresh empty directory")
        subset=[item for item in queue if item.private_only==is_private]
        # A private root is host controlled. Caller must configure OS ACLs,
        # protected backup, and no public cloud sync BEFORE using this.
        root.mkdir(parents=True,exist_ok=True)
        art_dir=root/"items"
        art_dir.mkdir()
        records=[]
        image_count=0
        for item in subset:
            bp=blueprints[item.item_id]
            brief=brief_from_blueprint(bp,allow_private=is_private)
            for view in item.required_views:
                png=_draft_png(bp,item.source_file.removesuffix(".json"),view)
                # A separate file for every canonical item and required view.
                rel=f"items/{item.item_id}.{view}.png"
                with (root/rel).open("xb") as file:
                    file.write(png)
                records.append({
                    "item_id":item.item_id,
                    "view":view,
                    "relative_path":rel,
                    "sha256":sha256(png).hexdigest(),
                    "source_sha256":brief.source_sha256,
                    "garment_type":bp.design.garment_type,
                    "category":item.source_file.removesuffix(".json"),
                    "wardrobe_layer":bp.garment.layer.name,
                    "slots":list(normalize_slots(bp.garment.slots)),
                    "material":bp.design.material,
                    "primary_hex":brief.fields["primary_hex"],
                    "accent_hex":brief.fields["accent_hex"],
                    "visual_review":"required",
                    "exact_source_match":False,
                })
                image_count+=1
        result={
            "schema":SCHEMA,
            "audience":"private" if is_private else "public",
            "quality":"procedural_draft_not_image_generated_or_reviewed",
            "rendering_mode":"garment_only_on_transparent_canvas",
            "canvas":{"width":WIDTH,"height":HEIGHT},
            "expected_items":len(subset),
            "image_count":image_count,
            "items":records,
        }
        (root/"manifest.json").write_text(
            json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8",
        )
        reports.append(BatchReport(
            items=len(subset),
            images=image_count,
            public=not is_private,
            root=str(root),
        ))
    return tuple(reports)


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description="Generate all source-linked clothing draft PNGs")
    parser.add_argument("--public-root",type=Path,required=True)
    parser.add_argument("--private-root",type=Path,
                        help="restricted local root; requires current SAFE owner authority")
    parser.add_argument("--state",type=Path,
                        help="existing approved canonical sofia.db for private authority only")
    parser.add_argument("--owner-opt-in",action="store_true")
    args=parser.parse_args(argv)
    if args.private_root and not args.state:
        parser.error("--private-root requires --state")
    resolver=(PrivatePresentationGrantResolver(state_path=args.state)
              if args.private_root else None)
    reports=build_draft_batch(
        public_root=args.public_root,private_root=args.private_root,
        resolver=resolver,owner_opt_in=args.owner_opt_in,
    )
    for report in reports:
        print(
            f"{'PUBLIC' if report.public else 'PRIVATE'}: "
            f"{report.items} canonical items, {report.images} actual draft PNGs "
            f"at {report.root}; exact-design review STILL REQUIRED"
        )
    return 0


if __name__=="__main__":
    raise SystemExit(main())
