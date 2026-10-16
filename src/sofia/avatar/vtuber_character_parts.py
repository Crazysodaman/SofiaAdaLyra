"""Separate 2D Sofía face, eye, hair, fox-ear and tail *starter* sprites.

All RGBA sprite options share the waist-up 320x400 canvas used by existing
public outfits. Expression and pose variants are real independent PNG layers,
not pictures of an entire outfit. This is procedural bootstrap artwork, not
an approved professional Live2D rig. It does not alter canonical anatomy.

Canonical colors and topology are verified from embodiment/avatar.json.
Facial features whose shape is unspecified remain authoring choices, not
new authoritative measurements or permanently altered identity.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path

from sofia.embodiment.store import EmbodimentStore

from .vtuber_starter_art import Sprite, WIDTH, HEIGHT, _shade


_PUBLIC_GROUPS = {
    "face": ("neutral", "freckles"),
    "eyes": ("open", "half", "closed", "looking_left", "looking_right"),
    "brows": ("neutral", "skeptical"),
    "mouth": ("closed", "smile", "talk_small", "talk_wide"),
    "hair_back": ("long_layered", "tied_back"),
    "hair_front": ("long_layered", "tied_back"),
    "ear_left": ("perked", "relaxed"),
    "ear_right": ("perked", "relaxed"),
    "tail": ("calm", "raised", "flick"),
}
# Character parts aren't wardrobe slots. They attach to a stable puppet
# skeleton; the painter selects at most one active sprite per visual group.
_Z = {
    "tail": 10, "hair_back": 20,
    "ear_left": 25, "ear_right": 25,
    "face": 50, "eyes": 55, "brows": 60, "mouth": 65,
    "hair_front": 90,
}
_ANCHOR = {
    "face": "head", "eyes": "head", "brows": "head", "mouth": "head",
    "hair_back": "head", "hair_front": "head",
    "ear_left": "left_fox_ear", "ear_right": "right_fox_ear",
    "tail": "tail_root",
}


def _rgb(value: str) -> tuple[int, int, int, int]:
    if not isinstance(value, str) or len(value) != 7 or not value.startswith("#"):
        raise ValueError("canonical avatar color hex unavailable")
    return (
        int(value[1:3], 16), int(value[3:5], 16),
        int(value[5:7], 16), 255,
    )


@dataclass(frozen=True)
class CharacterPartReport:
    parts: int
    groups: int
    manifest_sha256: str


def character_part_options() -> dict[str, tuple[str, ...]]:
    return dict(_PUBLIC_GROUPS)


def _paint(group: str, variant: str, *, appearance: dict) -> bytes:
    if group not in _PUBLIC_GROUPS or variant not in _PUBLIC_GROUPS[group]:
        raise ValueError("unapproved face/fox sprite group or variant")
    hair = _rgb(appearance["hair_hex"])
    tail = _rgb(appearance["tail_hex"])
    skin = _rgb(appearance["skin_hex"])
    wine = _shade(hair, .72)
    violet_light = (165, 116, 188, 255)
    ink = (36, 28, 53, 255)
    iris = (121, 62, 193, 255)
    white = (251, 242, 249, 255)
    s = Sprite()

    if group == "face":
        if variant == "neutral":
            # Face shape is an illustration choice, not a measured datum.
            s.ellipse((108, 88, 212, 237), skin)
            s.ellipse((109, 149, 119, 170), skin)
            s.ellipse((201, 149, 211, 170), skin)
            s.ellipse((151, 176, 168, 182), _shade(skin, .93))
        elif variant == "freckles":
            for x,y in ((125,174),(131,177),(136,175),
                        (184,174),(190,176),(197,172)):
                s.ellipse((x,y,x+3,y+3),_shade(skin,.78))
    elif group == "eyes":
        for x in (123,175):
            if variant == "closed":
                s.path(((x,137),(x+12,140),(x+26,137)),3,ink)
            else:
                eyelid = (x,124,x+29,145 if variant != "half" else 136)
                s.ellipse(eyelid,white)
                if variant == "half":
                    s.rectangle((x,123,x+29,131),skin)
                else:
                    gaze = -4 if variant == "looking_left" else (
                        4 if variant == "looking_right" else 0
                    )
                    s.ellipse((x+9+gaze,126,x+21+gaze,141),iris)
                    s.ellipse((x+13+gaze,128,x+18+gaze,138),ink)
                    s.ellipse((x+11+gaze,128,x+14+gaze,131),white)
                s.path(((x,128),(x+14,123),(x+28,127)),2,ink)
    elif group == "brows":
        if variant == "neutral":
            s.path(((122,116),(140,113),(151,116)),3,wine)
            s.path(((175,116),(188,113),(200,116)),3,wine)
        else:
            s.path(((121,117),(139,111),(151,113)),3,wine)
            s.path(((175,116),(192,119),(202,116)),3,wine)
    elif group == "mouth":
        if variant == "closed":
            s.path(((151,199),(161,202),(171,199)),2,(146,74,103,255))
        elif variant == "smile":
            s.path(((146,197),(158,205),(173,197)),3,(161,64,95,255))
        elif variant == "talk_small":
            s.ellipse((154,196,166,207),(154,64,102,255))
        else:
            s.ellipse((150,192,170,215),(127,44,91,255))
            s.rectangle((155,194,167,197),white)
    elif group in ("hair_back","hair_front"):
        if variant == "long_layered":
            if group == "hair_back":
                s.ellipse((94,61,225,348),wine)
                s.ellipse((101,83,220,333),_shade(hair,.86))
            else:
                s.ellipse((104,66,216,125),hair)
                s.polygon(((110,102),(140,109),(159,150),
                           (170,101),(208,93)),hair)
                s.polygon(((106,102),(119,109),(113,326),(92,348)),hair)
                s.polygon(((200,105),(218,103),(228,343),(202,320)),hair)
                s.path(((111,101),(135,86),(169,88)),3,_shade(hair,1.22))
        else:  # Hair tied back, with recognizable canonical crimson texture.
            if group == "hair_back":
                s.ellipse((112,78,219,179),wine)
                s.ellipse((188,128,242,268),_shade(hair,.8))
                s.path(((207,133),(238,170),(224,240)),15,hair)
            else:
                s.ellipse((109,69,213,122),hair)
                s.polygon(((109,104),(148,114),(163,144),
                           (182,111),(207,103)),hair)
                s.path(((113,102),(155,87),(196,103)),3,_shade(hair,1.18))
    elif group.startswith("ear_"):
        left = group == "ear_left"
        if left:
            base = ((110,111),(102,18),(149,105)) if variant=="perked" else (
                (111,112),(75,65),(148,108)
            )
            inner = ((117,101),(110,46),(135,102)) if variant=="perked" else (
                (113,105),(91,75),(132,104)
            )
        else:
            base = ((177,105),(221,18),(210,115)) if variant=="perked" else (
                (179,107),(246,63),(212,114)
            )
            inner = ((186,101),(213,46),(204,105)) if variant=="perked" else (
                (188,103),(230,76),(205,107)
            )
        s.polygon(base,tail)
        s.polygon(inner,violet_light)
    elif group == "tail":
        if variant == "calm":
            points=((220,320),(254,327),(280,301),(281,277))
        elif variant == "raised":
            points=((222,323),(262,293),(279,248),(258,215))
        else:
            points=((217,317),(252,313),(288,320),(304,302))
        s.path(points,29,tail)
        end=points[-1]
        s.ellipse((end[0]-15,end[1]-19,end[0]+15,end[1]+14),violet_light)
    return s.png()


def generate_public_character_parts(
    destination: Path,
    *, embodiment_seed: Path | None = None,
) -> CharacterPartReport:
    """Export every declared group/variant; never overwrite reviewed art."""
    if not isinstance(destination, Path) or destination.is_symlink():
        raise ValueError("invalid character art target")
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError("existing character art must not be overwritten")
    if embodiment_seed is None:
        embodiment_seed = Path(__file__).resolve().parents[1] / "embodiment" / "avatar.json"
    embodiment = EmbodimentStore(embodiment_seed).load()
    # Validate fixed fox anatomy in canonical source, not from a model prompt.
    if "fox ears" not in embodiment.additional_features or "fox tail" not in embodiment.additional_features:
        raise ValueError("canonical fox morphology missing")
    # Read the appearance JSON directly only to obtain original palette keys,
    # not to promote generated face measurements or mutate embodiment.
    text = embodiment_seed.read_text(encoding="utf-8-sig")
    raw = json.loads(text)["physical_self"]
    appearance = raw["appearance"]
    for key in ("hair_hex","tail_hex","skin_hex"):
        _rgb(appearance[key])
    destination.mkdir(parents=True, exist_ok=True)
    entries = []
    for group,variants in _PUBLIC_GROUPS.items():
        folder = destination / group
        folder.mkdir(exist_ok=True)
        for variant in variants:
            blob = _paint(group,variant,appearance=appearance)
            file = folder / (variant+".png")
            with file.open("xb") as fp:
                fp.write(blob)
            entries.append({
                "id":f"{group}.{variant}",
                "path":f"{group}/{variant}.png",
                "sha256":sha256(blob).hexdigest(),
                "group":group,
                "variant":variant,
                "anchor":_ANCHOR[group],
                "z":_Z[group],
                "audience":"public",
            })
    manifest = {
        "schema":"sofia.avatar2d.character_parts.v1",
        "canvas":{"width":WIDTH,"height":HEIGHT},
        "source":"canonical avatar.json appearance baseline",
        "fixed_topology":{"ears":2,"tails":1},
        "face_geometry":"illustrative_not_a_canonical_measurement",
        "quality":"procedural_starter_unreviewed",
        "render_mode":"one_per_group_optional_overlays",
        "groups":{group:list(variants) for group,variants in _PUBLIC_GROUPS.items()},
        "parts":entries,
    }
    encoded = json.dumps(manifest,indent=2,sort_keys=True).encode()
    with (destination/"manifest.json").open("xb") as f:
        f.write(encoded)
    return CharacterPartReport(len(entries),len(_PUBLIC_GROUPS),sha256(encoded).hexdigest())


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser=argparse.ArgumentParser(description="Make independent public face/fox sprite layers")
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args(argv)
    result=generate_public_character_parts(args.output)
    print(f"{result.parts} RGBA character part sprites in {result.groups} "
          f"groups, manifest SHA256 {result.manifest_sha256}")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
