"""Deterministic starter 2D waist-up sprites for existing public wardrobe.

Produces ACTUAL separately layered, transparent RGBA PNG images and checked
manifests using Python's standard library. This is functional bootstrap art,
NOT a professional Live2D/artist-quality model. No network, generative model,
new outfit IDs, private assets, or canonical state mutation.

Example (on a host with Sofía installed and a configured state database):
    python -m sofia.avatar.vtuber_starter_art --output ./avatar2d-public

The CLI generates all current PUBLIC outfit presets under
output/outfits/<outfit_id>/, not nude or protected private wardrobe sprites.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import struct
import zlib

from .wardrobe_catalog import build_starter_wardrobe
from .wardrobe_matrix import build_wardrobe_matrix
from .vtuber_layer_stack import WAIST_UP_SLOTS
from .wardrobe import Layer, normalize_slots


WIDTH, HEIGHT = 320, 400
PNG_HEADER = b"\x89PNG\r\n\x1a\n"
_DEFAULT_HAIR = (139, 30, 63, 255)
_VIOLET = (58, 36, 92, 255)
_SKIN = (241, 217, 203, 255)
_CYAN = (25, 211, 197, 255)


def _hex(value: str, *, default=(38, 37, 52, 255)) -> tuple[int, int, int, int]:
    if isinstance(value, str) and len(value) == 7 and value[0] == "#":
        try:
            return (int(value[1:3], 16), int(value[3:5], 16),
                    int(value[5:7], 16), 255)
        except ValueError:
            pass
    return default


def _shade(color: tuple[int, int, int, int], amount: float) -> tuple[int, int, int, int]:
    return (*(
        max(0, min(255, int(component * amount)))
        for component in color[:3]
    ), color[3])


def _png_chunk(tag: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data)) + tag + data
        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    )


class Sprite:
    """Tiny dependency-free alpha image with basic polygon/ellipse primitives."""

    def __init__(self) -> None:
        self.pixels = bytearray(WIDTH * HEIGHT * 4)

    def rectangle(self, box: tuple[int, int, int, int], color) -> None:
        x0, y0, x1, y1 = box
        for y in range(max(0, y0), min(HEIGHT, y1)):
            for x in range(max(0, x0), min(WIDTH, x1)):
                self.pixels[(y * WIDTH + x) * 4:(y * WIDTH + x) * 4 + 4] = bytes(color)

    def ellipse(self, box: tuple[int, int, int, int], color) -> None:
        x0, y0, x1, y1 = box
        rx, ry = (x1-x0)/2, (y1-y0)/2
        if rx <= 0 or ry <= 0:
            return
        cx, cy = x0 + rx, y0 + ry
        for y in range(max(0, y0), min(HEIGHT, y1)):
            v = ((y+.5-cy) / ry) ** 2
            if v > 1:
                continue
            dx = rx * (1-v)**.5
            self.rectangle((max(x0,int(cx-dx)), y, min(x1,int(cx+dx+1)), y+1), color)

    def polygon(self, vertices: tuple[tuple[int,int], ...], color) -> None:
        if len(vertices) < 3:
            return
        min_y = max(0, min(y for _,y in vertices))
        max_y = min(HEIGHT, max(y for _,y in vertices)+1)
        # Scanline fill avoids per-pixel ray casting for every garment polygon.
        for y in range(min_y, max_y):
            at = y + .5
            crossings = []
            for (x1,y1),(x2,y2) in zip(vertices, vertices[1:]+vertices[:1]):
                if (y1 <= at < y2) or (y2 <= at < y1):
                    crossings.append(x1 + (at-y1) * (x2-x1)/(y2-y1))
            crossings.sort()
            for index in range(0, len(crossings)-1, 2):
                x0, x1 = crossings[index:index+2]
                self.rectangle((int(x0),y,int(x1)+1,y+1),color)

    def path(self, points: tuple[tuple[int,int], ...], width: int, color) -> None:
        radius = max(1, width//2)
        for (ax,ay),(bx,by) in zip(points,points[1:]):
            steps = max(abs(bx-ax),abs(by-ay),1)
            for i in range(steps+1):
                x = int(ax+(bx-ax)*i/steps)
                y = int(ay+(by-ay)*i/steps)
                self.ellipse((x-radius,y-radius,x+radius,y+radius),color)

    def png(self) -> bytes:
        raw = b"".join(
            b"\x00" + bytes(self.pixels[y*WIDTH*4:(y+1)*WIDTH*4])
            for y in range(HEIGHT)
        )
        return (
            PNG_HEADER +
            _png_chunk(b"IHDR", struct.pack(">IIBBBBB", WIDTH,HEIGHT,8,6,0,0,0)) +
            _png_chunk(b"IDAT", zlib.compress(raw,6)) +
            _png_chunk(b"IEND", b"")
        )


def _base(part: str) -> bytes:
    s = Sprite()
    if part == "back":
        # Tail, long back hair, inner ear bases, all behind the body.
        s.path(((231,332),(260,319),(291,283),(280,252),(266,259)),25,_VIOLET)
        s.path(((276,252),(290,264)),12,(156,118,183,255))
        s.polygon(((116,124),(100,28),(146,105)),_VIOLET)
        s.polygon(((176,102),(216,30),(210,136)),_VIOLET)
        s.polygon(((118,103),(112,54),(139,107)),(155,116,175,255))
        s.polygon(((187,104),(207,53),(203,110)),(155,116,175,255))
        s.ellipse((99,86,221,357),_shade(_DEFAULT_HAIR,.7))
    elif part == "body":
        s.polygon(((100,232),(137,218),(183,218),(222,232),(252,400),(68,400)),_SKIN)
        s.rectangle((145,203,176,250),_SKIN)
        s.ellipse((65,233,108,389),_SKIN)
        s.ellipse((211,233,254,389),_SKIN)
        s.path(((77,366),(87,282)),4,_shade(_SKIN,.86))
        s.path(((243,366),(232,282)),4,_shade(_SKIN,.86))
    elif part == "face":
        s.ellipse((111,94,210,238),_SKIN)
        s.ellipse((114,123,146,143),(251,245,245,255))
        s.ellipse((175,123,207,143),(251,245,245,255))
        s.ellipse((127,127,141,140),(116,70,174,255))
        s.ellipse((180,127,194,140),(116,70,174,255))
        s.ellipse((131,129,138,138),(43,28,80,255))
        s.ellipse((183,129,190,138),(43,28,80,255))
        s.path(((123,118),(146,117)),3,_shade(_DEFAULT_HAIR,.64))
        s.path(((176,117),(198,119)),3,_shade(_DEFAULT_HAIR,.64))
        s.path(((144,196),(159,201),(174,196)),3,(146,72,106,255))
        s.ellipse((154,177,166,181),_shade(_SKIN,.91))
        s.ellipse((118,167,139,173),(225,146,155,255))
        s.ellipse((182,167,202,173),(225,146,155,255))
    elif part == "front":
        s.ellipse((107,74,214,133),_DEFAULT_HAIR)
        s.polygon(((111,104),(148,116),(161,158),(168,105),(204,92)),
                  _DEFAULT_HAIR)
        s.polygon(((105,104),(116,106),(119,340),(96,361)),_DEFAULT_HAIR)
        s.polygon(((206,105),(220,110),(230,352),(207,336)),_DEFAULT_HAIR)
        s.path(((111,109),(132,95),(159,94)),3,_shade(_DEFAULT_HAIR,1.24))
        s.path(((197,108),(183,94),(173,94)),3,_shade(_DEFAULT_HAIR,1.24))
        s.ellipse((131,88,140,96),_shade(_DEFAULT_HAIR,1.34))
    else:
        raise ValueError("unknown canonical base part")
    return s.png()


def _garment(*, name: str, category: str, layer: Layer,
             slots: frozenset[str], color: tuple[int,int,int,int],
             accents: tuple[str, ...]) -> bytes:
    """Render a consistent flat waist-up garment silhouette in exact slots.

    Category, layering and garment metadata inform the silhouette, while the
    underlying wardrobe matrix alone authorizes what the clothing *is*.
    """
    s = Sprite()
    accent = _hex(accents[0], default=_CYAN) if accents else _CYAN
    darker = _shade(color,.76)
    upper = bool(slots & {
        "torso", "back", "left_shoulder", "right_shoulder",
        "left_upper_arm", "right_upper_arm",
    })
    low = "waist" in slots and not upper
    lname = (name+" "+category).casefold()
    is_outer = layer in (Layer.OUTER,Layer.MID) and (
        any(term in lname for term in (
            "jacket","coat","vest","shell","parka","cardigan","bomber","trench",
        )) or layer is Layer.OUTER
    )
    if upper:
        if layer is Layer.UNDERWEAR:
            # The reviewed outer shirt goes above this layer.
            s.polygon(((120,245),(144,234),(176,234),(199,245),
                       (201,288),(118,288)),color)
            s.path(((120,245),(144,237),(176,237),(199,245)),3,accent)
        elif is_outer:
            # Open-front jacket with collar + visible base underneath.
            s.polygon(((97,232),(138,224),(152,267),(148,400),(81,400),(73,254)),
                      darker)
            s.polygon(((182,224),(223,232),(247,254),(238,400),(172,400),
                       (167,267)),color)
            s.polygon(((139,227),(153,268),(157,333),(151,340),(121,249)),
                      accent)
            s.polygon(((181,227),(167,268),(163,333),(169,340),(199,249)),
                      accent)
            s.path(((102,274),(98,386)),3,_shade(accent,.75))
            s.path(((218,273),(225,386)),3,_shade(accent,.75))
        else:
            # Shirt, dress top, hoodie, tank, technical work top.
            s.polygon(((97,236),(136,224),(144,235),(176,235),(184,224),
                       (223,236),(241,250),(220,288),(222,400),
                       (99,400),(100,288),(78,250)),color)
            s.polygon(((136,224),(144,233),(176,233),(184,224),
                       (176,252),(144,252)),darker)
            s.path(((123,278),(144,290),(178,290),(198,278)),3,_shade(accent,.85))
            if "technical" in lname or "circuit" in lname:
                s.path(((128,310),(155,310),(173,299),(202,299)),3,accent)
                s.ellipse((192,293,203,303),accent)
            if "hoodie" in lname:
                s.path(((139,229),(152,259)),3,accent)
                s.path(((181,229),(169,259)),3,accent)
    if slots & {"left_shoulder","left_upper_arm","left_forearm"}:
        s.ellipse((78,245,104,315),color)
        s.path(((82,251),(81,295)),3,accent)
    if slots & {"right_shoulder","right_upper_arm","right_forearm"}:
        s.ellipse((218,245,242,315),color)
        s.path(((236,251),(237,295)),3,accent)
    if "neck" in slots:
        s.path(((139,222),(158,228),(181,222)),6,color)
        s.ellipse((153,224,165,236),accent)
    if "waist" in slots and not low:
        s.rectangle((99,376,222,389),darker)
    if low:
        s.polygon(((97,355),(223,355),(232,400),(89,400)),color)
        s.path(((98,356),(222,356)),4,accent)
    if "left_hand" in slots or "left_wrist" in slots:
        s.polygon(((67,345),(98,345),(95,373),(66,373)),color)
        s.path(((68,347),(97,347)),3,accent)
    if "right_hand" in slots or "right_wrist" in slots:
        s.polygon(((224,345),(253,345),(253,373),(225,373)),color)
        s.path(((225,347),(250,347)),3,accent)
    if "left_ear" in slots:
        s.path(((103,49),(122,91)),7,color)
    if "right_ear" in slots:
        s.path(((216,51),(202,92)),7,color)
    if "tail" in slots:
        s.ellipse((267,261,282,279),color)
    if "hair" in slots or "head" in slots:
        s.path(((120,100),(132,80),(190,80),(207,100)),6,color)
    return s.png()


@dataclass(frozen=True, slots=True)
class ArtGenerationReport:
    outfit_id: str
    asset_count: int
    bytes_written: int
    manifest_digest: str


def _safe_root(folder: Path, *, create: bool) -> Path:
    if folder.is_symlink():
        raise ValueError("asset output root must not be a symlink")
    if create:
        folder.mkdir(parents=True, exist_ok=True)
    if not folder.is_dir():
        raise ValueError("asset output root missing")
    return folder


def _write_new(path: Path, content: bytes) -> None:
    """No overwrite: previous reviewed artwork must never be destroyed."""
    if path.is_symlink() or path.exists():
        raise FileExistsError("avatar art already exists; refusing overwrite")
    path.write_bytes(content)


def generate_public_outfit_art(
    catalog,
    *,
    outfit_id: str,
    destination: Path,
) -> ArtGenerationReport:
    """Generate a complete PUBLIC waist-up sprite bundle for one known outfit.

    No private artwork, nude bodies, image generation, network, or modification
    of the existing canonical wardrobe/presentation is permitted.
    """
    if not isinstance(outfit_id,str) or not outfit_id or not all(
        ch.isalnum() or ch in "._-" for ch in outfit_id
    ):
        raise ValueError("invalid canonical outfit ID")
    plan = catalog.preset(outfit_id)
    if plan.private_only:
        raise PermissionError("protected outfits need a separate authorized art workflow")
    matrix = build_wardrobe_matrix(catalog, plan.item_ids)
    if not matrix.covered_default or matrix.private_only:
        raise ValueError("public outfit must retain approved clothing coverage")
    folder = _safe_root(Path(destination),create=True)
    if (folder/"manifest.json").exists():
        raise FileExistsError("existing art bundle cannot be overwritten")
    images: list[tuple[str,str,bytes,dict[str,object]]] = []
    for role,part,order in (
        ("base_back","back",0),("base_body","body",0),
        ("base_face","face",0),("base_front","front",0),
    ):
        asset_id = "sofia."+part
        rel = "base/"+part+".png"
        images.append((asset_id,rel,_base(part),{"role":role,"order":order}))
    visible: dict[tuple[str,Layer],list] = {}
    for cell in matrix.cells:
        if cell.slot in WAIST_UP_SLOTS:
            visible.setdefault((cell.garment_id,cell.layer),[]).append(cell)
    for index,((garment_id,layer),cells) in enumerate(sorted(
        visible.items(),key=lambda pair:(int(pair[0][1]),pair[0][0])
    )):
        slots = sorted({c.slot for c in cells})
        first = cells[0]
        payload = _garment(
            name=first.name,category=first.category,layer=layer,
            slots=frozenset(slots),color=_hex(first.primary_hex),
            accents=first.accent_hexes,
        )
        images.append((
            "item."+garment_id,
            "garments/"+garment_id+".png",payload,
            {
                "role":"garment","order":index,"garment_id":garment_id,
                "slots":slots,"wardrobe_layer":layer.name,
            },
        ))
    # At least one shirt/jacket has visible torso coverage.
    if not any(
        "torso" in metadata.get("slots",[]) for _,_,_,metadata in images
    ):
        raise ValueError("public outfit has no waist-up torso garment")
    layers=[]
    for asset_id,relative,payload,metadata in images:
        layers.append({
            "id":asset_id,"path":relative,
            "sha256":sha256(payload).hexdigest(),**metadata,
        })
    manifest = json.dumps({
        "schema":"sofia.avatar2d.asset_bundle.v1",
        "bundle_id":"starter."+outfit_id,
        "audience":"public","attire":"clothed",
        "outfit_id":outfit_id,"art_quality":"procedural_starter",
        "canvas":{"width":WIDTH,"height":HEIGHT},
        "layers":layers,
    },sort_keys=True,separators=(",",":")).encode()
    written=0
    for _,relative,payload,_ in images:
        file=folder/relative
        _safe_root(file.parent,create=True)
        _write_new(file,payload)
        written+=len(payload)
    _write_new(folder/"manifest.json",manifest)
    return ArtGenerationReport(outfit_id,len(images),written,sha256(manifest).hexdigest())


def generate_public_wardrobe_library(catalog, *, destination: Path) -> ArtGenerationReport:
    """Generate one real reusable waist-up PNG for each visible PUBLIC item.

    There are many lower-body items in the canonical wardrobe; they remain
    valid clothing, but do not need invented art outside a waist-up viewport.
    This library is a candidate asset store for future self-created outfit
    combinations; each item retains the original catalog ID, slot and layer.
    """
    root = _safe_root(Path(destination), create=True)
    library = _safe_root(root / "library", create=True)
    if (library/"items.json").exists():
        raise FileExistsError("reviewed wardrobe sprite library cannot be overwritten")
    items=[]
    total=0
    for bp in sorted(catalog.blueprints, key=lambda b:b.garment.item_id):
        garment=bp.garment
        if bp.private_only or garment.private_only:
            continue
        slots=frozenset(normalize_slots(garment.slots)) & WAIST_UP_SLOTS
        if not slots:
            continue
        art=_garment(
            name=garment.name, category=bp.category,
            layer=garment.layer, slots=slots,
            color=_hex(bp.primary_hex), accents=bp.accent_hexes,
        )
        _write_new(library/(garment.item_id+".png"),art)
        total+=len(art)
        items.append({
            "garment_id":garment.item_id,
            "asset":garment.item_id+".png",
            "sha256":sha256(art).hexdigest(),
            "slots":sorted(slots),
            "wardrobe_layer":garment.layer.name,
            "source":"canonical reviewed wardrobe",
            "private_only":False,
        })
    manifest=json.dumps({
        "schema":"sofia.avatar2d.public_sprite_library.v1",
        "quality":"procedural_starter",
        "viewport":"waist_up",
        "assets":items,
    },sort_keys=True,separators=(",",":")).encode()
    _write_new(library/"items.json",manifest)
    return ArtGenerationReport(
        "public.wardrobe.library", len(items),total,sha256(manifest).hexdigest(),
    )


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description="Generate safe public 2D wardrobe PNG assets")
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--state",type=Path,
                        help="optional existing state path for reviewed generated wardrobe metadata; read only")
    parser.add_argument("--outfit",default="all",
                        help="existing public outfit ID, or all")
    parser.add_argument("--library", action="store_true",
                        help="generate every visible public garment as a reusable item sprite")
    args=parser.parse_args(argv)
    # Read existing garment/outfit definitions only; do not bootstrap or write
    # the canonical database merely to make artwork.
    catalog = build_starter_wardrobe(state_path=args.state)
    if args.library:
        result = generate_public_wardrobe_library(catalog, destination=args.output)
        print(f"{result.asset_count} public item sprites, "
              f"{result.bytes_written} bytes, SHA256 {result.manifest_digest}")
        return 0
    selected=[
        o.outfit_id for o in catalog.presets if not o.private_only
    ] if args.outfit=="all" else [args.outfit]
    # Idempotent safety: never overwrite or silently modify a reviewed art pack.
    for outfit_id in selected:
        target=args.output/"outfits"/outfit_id
        result=generate_public_outfit_art(
            catalog,outfit_id=outfit_id,destination=target,
        )
        print(f"{result.outfit_id}: {result.asset_count} real PNG layers, "
              f"{result.bytes_written} bytes, SHA256 {result.manifest_digest}")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
