"""Render the entire approved PUBLIC wardrobe to versioned candidate sprites.

This is a bounded FIRST-PASS art atlas, not finished illustrated rigging.
Each entry has its exact canonical item ID, description fingerprint, style,
category and slots; images are never automatically promoted as live art.
Use a human-reviewed, fitted illustration before marking an item production.
The private wardrobe is never read into image generation.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
from importlib.resources import files
from io import BytesIO
import json
import math
from pathlib import Path
import re
import zipfile

from PIL import Image, ImageDraw, ImageFilter, ImageChops, ImageOps

WIDTH, HEIGHT = 640, 800
SCHEMA = "sofia.avatar2d.public_candidate_atlas.v1"
COLORS = {
    "black": (34, 31, 43), "charcoal": (62, 65, 77),
    "dark_violet": (75, 39, 104), "soft_violet": (176, 132, 192),
    "crimson": (144, 35, 72), "cyan": (52, 191, 203),
    "silver": (171, 173, 192),
}
CATEGORIES = (
    "tops", "outerwear", "bottoms", "footwear", "one_pieces",
    "underlayers_upper", "underlayers_lower", "accessories_ear",
    "accessories_hand_wrist", "accessories_legwear", "accessories_neck",
    "accessories_tail", "accessories_waist",
)
PRIVATE_FILES = ("intimate_underlayers",)
SAFE_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$")


def public_garment_data(source_root: Path | None = None):
    """Read the canonical authoring files and reject duplicate/unexpected IDs."""
    source = source_root or Path(str(files("sofia.avatar").joinpath("wardrobe_data")))
    all_rows = []
    seen = set()
    for category in CATEGORIES:
        doc = json.loads((source / (category + ".json")).read_text(encoding="utf-8"))
        if not isinstance(doc, dict) or not isinstance(doc.get("garments"), list):
            raise ValueError("invalid wardrobe source file: " + category)
        for row in doc["garments"]:
            if not isinstance(row, dict) or not isinstance(row.get("private_only"), bool):
                raise ValueError("invalid privacy classification")
            if row["private_only"]:
                continue
            item_id = row.get("item_id")
            if not isinstance(item_id, str) or not SAFE_ID.fullmatch(item_id) or item_id in seen:
                raise ValueError("invalid or duplicate public garment ID")
            seen.add(item_id)
            all_rows.append((category, row))
    return all_rows


def _c(name, default="black"):
    return COLORS.get(name or default, COLORS[default])


def _poly(draw, points):
    draw.polygon(points, fill=255)


def mask_for_garment(category, row):
    """Draw an aligned front-view slot silhouette; no private body illustration."""
    m = Image.new("L", (WIDTH, HEIGHT))
    d = ImageDraw.Draw(m)
    typ = row["garment_type"]
    features = set(row.get("features") or ())
    if category in ("tops", "outerwear", "underlayers_upper", "one_pieces"):
        short = typ in ("t_shirt", "crop_top", "tank_top", "base_tank", "bralette",
                         "wireless_bra", "sports_bra", "longline_bralette",
                         "triangle_bralette", "plunge_bra", "bandeau", "camisole")
        sleeveless = typ in ("tank_top", "base_tank", "bralette",
                              "wireless_bra", "sports_bra", "longline_bralette",
                              "triangle_bralette", "plunge_bra", "bandeau", "camisole",
                              "utility_vest", "puffer_vest") or "sleeveless" in features
        hem = 305 if typ in ("bralette", "wireless_bra", "sports_bra",
                             "triangle_bralette", "plunge_bra", "bandeau") else (
                 345 if typ == "crop_top" else 410)
        _poly(d, [(243,203),(283,190),(297,215),(343,215),(359,190),
                  (399,203),(414,238),(400,hem),(240,hem),(226,238)])
        d.ellipse((298,177,342,231), fill=0)
        if not sleeveless:
            cuff = 290 if typ in ("t_shirt", "base_tee") else (372 if short else 417)
            _poly(d,[(240,205),(226,209),(170,235),(142,cuff),(201,cuff),
                     (228,267),(255,236)])
            _poly(d,[(400,205),(414,209),(470,235),(498,cuff),
                     (439,cuff),(412,267),(385,236)])
        if category == "one_pieces" and typ not in ("bodysuit",):
            if typ in ("dress",):
                _poly(d,[(242,396),(399,396),(464,620),(177,620)])
            elif typ in ("romper",):
                _poly(d,[(242,397),(398,397),(405,497),(335,495),
                         (320,447),(303,495),(236,497)])
            else:
                _poly(d,[(242,397),(399,397),(395,709),(339,709),
                         (321,449),(302,709),(244,709)])
        if category == "outerwear" and typ in ("trench_coat","long_coat","parka","coat","cape"):
            _poly(d,[(242,388),(395,388),(429,585),(211,585)])
    elif category in ("bottoms","underlayers_lower"):
        top=411
        if typ in ("skirt",):
            _poly(d,[(241,top),(401,top),(444,580),(194,580)])
        elif typ in ("briefs","hipster","boyshort","bikini_brief","cheeky_brief",
                      "thong","athletic_brief"):
            _poly(d,[(241,top),(399,top),(379,472),(339,468),(321,446),
                     (301,468),(261,472)])
        else:
            leg_end = 505 if typ in ("running_shorts","athletic_shorts",
                "denim_shorts","cargo_shorts","lounge_shorts","bike_shorts",
                "compression_shorts","liner_shorts","slip_shorts") else 717
            _poly(d,[(241,top),(399,top),(397,leg_end),(336,leg_end),
                     (321,455),(305,leg_end),(243,leg_end)])
    elif category == "footwear":
        high = typ in ("work_boots","combat_boots","knee_boots","rain_boots",
            "winter_boots","hiking_boots","heeled_boots","ankle_boots")
        y0 = 644 if high else 722
        if typ=="knee_boots": y0=548
        for xx in (255,341):
            _poly(d,[(xx-24,y0),(xx+26,y0),(xx+25,766),
                     (xx+43,770),(xx+45,789),(xx-40,789),(xx-40,776),
                     (xx-24,760)])
    elif category == "accessories_legwear":
        for x in (270,363):
            _poly(d,[(x-23,505),(x+23,505),(x+18,722),(x-22,722)])
    elif category == "accessories_neck":
        if typ == "necklace":
            d.arc((282,183,359,267),start=0,end=180,fill=255,width=7)
            d.ellipse((317,242,326,262),fill=255)
        else:
            d.rounded_rectangle((291,185,349,215),radius=8,fill=255)
    elif category == "accessories_waist":
        d.rounded_rectangle((239,402,400,424),radius=6,fill=255)
        d.rectangle((305,399,338,430),fill=255)
    elif category == "accessories_ear":
        _poly(d,[(222,143),(179,39),(266,93),(272,143)])
        _poly(d,[(368,143),(461,39),(414,143)])
    elif category == "accessories_tail":
        d.arc((410,334,585,548),start=235,end=83,fill=255,width=21)
        d.ellipse((548,321,601,368),fill=255)
    elif category == "accessories_hand_wrist":
        if typ in ("gloves","fingerless_gloves"):
            for x in (162,475):
                d.rounded_rectangle((x-23,362,x+23,422),radius=10,fill=255)
        else:
            for x in (162,475):
                d.rounded_rectangle((x-25,352,x+25,368),radius=7,fill=255)
    if m.getbbox() is None:
        raise ValueError("empty mask for " + row["item_id"])
    return m


def _render_vector_candidate(category, row):
    """Shaded first-pass template, NOT verified finished illustrated artwork."""
    mask=mask_for_garment(category,row)
    primary=_c(row.get("primary"))
    accent=_c(row.get("accent") or "soft_violet")
    base=Image.new("RGBA",(WIDTH,HEIGHT),primary+(0,))
    # Continuous fabric shading, plus a narrow rim light and seams.
    shading=Image.linear_gradient("L").resize((WIDTH,HEIGHT))
    shading=shading.rotate(90,expand=False)
    dark=tuple(round(v*.56) for v in primary)
    light=tuple(min(255,round(v*1.4+17)) for v in primary)
    mapped=ImageOps.colorize(shading, dark, light)
    base.paste(mapped,(0,0),mask)
    d=ImageDraw.Draw(base)
    bbox=mask.getbbox()
    edge=ImageChops.subtract(mask,mask.filter(ImageFilter.MinFilter(7)))
    border=Image.new("RGBA",(WIDTH,HEIGHT),accent+(0,))
    border.putalpha(edge.point(lambda x: min(160,x)))
    base=Image.alpha_composite(base,border)
    d=ImageDraw.Draw(base)
    x0,y0,x1,y1=bbox
    if category in ("tops","outerwear","one_pieces","underlayers_upper"):
        # Seams run along the torso and practical jackets have visible zips.
        if category=="outerwear" or "front_zip" in (row.get("features") or []):
            d.line((320,222,320,min(y1,582)),fill=accent+(210,),width=3)
            for yy in range(245,min(y1,555),44):
                d.ellipse((316,yy-3,323,yy+4),fill=(185,186,200,220))
        d.line((254,240,250,min(y1,410)),fill=accent+(140,),width=2)
        d.line((386,240,390,min(y1,410)),fill=accent+(140,),width=2)
        if "pockets" in " ".join(row.get("features") or []):
            for xx in (258,348):
                d.rounded_rectangle((xx,345,xx+34,375),radius=3,
                                    outline=accent+(200,),width=2)
    elif category in ("bottoms","underlayers_lower"):
        d.line((241,425,398,425),fill=accent+(190,),width=4)
        if y1>565:
            d.line((321,451,321,y1-18),fill=accent+(160,),width=2)
        if "pockets" in " ".join(row.get("features") or []):
            for xx in (251,352):
                d.arc((xx,431,xx+25,469),0,150,fill=accent+(170,),width=2)
    elif category=="footwear":
        for xx in (255,341):
            for yy in range(max(680,y0 if (y0:=y1-132)>680 else 680),769,13):
                d.line((xx-9,yy,xx+12,yy),fill=accent+(210,),width=2)
    elif category in ("accessories_neck","accessories_waist"):
        cx=(x0+x1)//2;cy=(y0+y1)//2
        d.rounded_rectangle((cx-9,cy-7,cx+9,cy+7),radius=3,
                             outline=accent+(240,),width=3)
    # Source-linked fashion pattern, not arbitrary item name as garment text.
    pat=row.get("pattern") or ""
    if "circuit" in pat or "circuit" in " ".join(row.get("features") or []):
        marks=Image.new("RGBA",(WIDTH,HEIGHT),(0,0,0,0))
        md=ImageDraw.Draw(marks)
        for i in range(6):
            x=x0+23+i*max(12,(x1-x0)//9)
            y=y0+42+i*11
            md.line((x,y,x+12,y,x+12,y+9),fill=accent+(155,),width=2)
        marks.putalpha(ImageChops.multiply(marks.getchannel("A"),mask))
        base=Image.alpha_composite(base,marks)
    return base


def _contact_sheets(output_dir: Path, records: list[dict]):
    """Exactly what CI generated, not a concept illustration or storefront."""
    previews=output_dir/"preview"
    previews.mkdir(exist_ok=True)
    for category in CATEGORIES:
        group=[row for row in records if row["category"]==category]
        if not group:
            continue
        cols=5
        cell_w,cell_h=190,226
        rows=(len(group)+cols-1)//cols
        sheet=Image.new("RGB",(cols*cell_w,84+rows*cell_h),(15,17,28))
        d=ImageDraw.Draw(sheet)
        d.text((20,13),category.upper()+" • PUBLIC PNG CANDIDATES",
               fill=(218,197,241))
        d.text((20,43),"DRAFT VECTOR • NOT FINISHED ILLUSTRATION • NOT LIVE",
               fill=(237,151,151))
        for index,row in enumerate(group):
            x=(index%cols)*cell_w
            y=84+(index//cols)*cell_h
            tile=Image.new("RGBA",(cell_w-10,cell_h-8),(27,29,46,255))
            sprite=Image.open(output_dir/row["sprite_file"]).convert("RGBA")
            sprite.thumbnail((172,183),Image.Resampling.LANCZOS)
            tile.alpha_composite(sprite,((tile.width-sprite.width)//2,2))
            sheet.paste(tile.convert("RGB"),(x+4,y+4))
            d.text((x+8,y+193),row["item_id"][:25],fill=(240,230,250))
        sheet.save(previews/(category+".png"),"PNG",optimize=True)


def make_batch(output_dir: Path, *, source_root: Path | None = None,
               replace=False) -> dict:
    output_dir=Path(output_dir)
    if output_dir.exists() and any(output_dir.iterdir()) and not replace:
        raise FileExistsError("refusing to overwrite existing wardrobe atlas")
    items=public_garment_data(source_root)
    output_dir.mkdir(parents=True,exist_ok=True)
    output_items=output_dir/"items"
    output_items.mkdir(exist_ok=True)
    records=[]
    for category,row in items:
        identifier=row["item_id"]
        image=_render_vector_candidate(category,row)
        raw=BytesIO(); image.save(raw,"PNG",optimize=True)
        sprite=raw.getvalue()
        (output_items/(identifier+".png")).write_bytes(sprite)
        design_fields={k:row.get(k) for k in (
            "item_id","name","garment_type","fit","rise","length",
            "sleeve_length","material","primary","accent","pattern","graphic",
            "features","style_tags","description","private_only"
        )}
        signature=sha256(json.dumps(design_fields,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        records.append({
            "item_id":identifier,"name":row["name"],"category":category,
            "garment_type":row["garment_type"],
            "source_description_sha256":signature,
            "sprite_file":"items/"+identifier+".png",
            "sprite_sha256":sha256(sprite).hexdigest(),
            "canvas":[WIDTH,HEIGHT],"private_only":False,
            "art_status":"procedural_first_pass_NOT_REVIEWED",
            "rig_status":"NOT_FITTED_FOR_LIVE_REUSE",
        })
    # Preserve the previously generated high-resolution illustrated garment
    # REFERENCES where their exact canonical IDs exist. Their native placement
    # is not a rig, so keep these separate from wearable 640x800 drafts.
    reference_archive=Path(__file__).resolve().parents[3] / (
        "assets/avatar2d/illustrated_public_v1/"
        "sofia2d_public_illustrated_candidates_v1.zip"
    )
    reference_count=0
    if reference_archive.is_file():
        approved={record["item_id"]:record for record in records}
        with zipfile.ZipFile(reference_archive) as archive:
            for name in sorted(archive.namelist()):
                if not name.startswith("illustrated_drafts/") or not name.endswith(".png"):
                    continue
                item_id=Path(name).stem
                if item_id not in approved:
                    continue
                image=archive.read(name)
                with Image.open(BytesIO(image)) as artwork:
                    artwork.load()
                    if artwork.width*artwork.height>4_000_000:
                        raise ValueError("unsafe illustrated reference dimensions")
                refs=output_dir/"illustrated_references"
                refs.mkdir(exist_ok=True)
                (refs/(item_id+".png")).write_bytes(image)
                approved[item_id]["illustrated_reference"]={
                    "path":"illustrated_references/"+item_id+".png",
                    "sha256":sha256(image).hexdigest(),
                    "status":"UNFITTED_ILLUSTRATED_REFERENCE_NOT_LIVE",
                }
                reference_count+=1
    manifest={
        "schema":SCHEMA,"public_only":True,"canvas":[WIDTH,HEIGHT],
        "art_status":"DRAFT_VECTOR_NOT_PRODUCTION",
        "illustrated_unfitted_reference_count":reference_count,
        "count":len(records),"items":records,
    }
    _contact_sheets(output_dir, records)
    (output_dir/"manifest.json").write_text(
        json.dumps(manifest,indent=2,ensure_ascii=False)+"\n",encoding="utf8"
    )
    return manifest


def main(argv=None):
    parser=argparse.ArgumentParser(description="Produce full public wardrobe DRAFT PNG atlas")
    parser.add_argument("--output",required=True,type=Path)
    parser.add_argument("--source-root",type=Path)
    parser.add_argument("--replace",action="store_true")
    args=parser.parse_args(argv)
    data=make_batch(args.output,source_root=args.source_root,replace=args.replace)
    print(json.dumps({"count":data["count"],"public_only":True,
                      "status":data["art_status"],"output":str(args.output)}))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
