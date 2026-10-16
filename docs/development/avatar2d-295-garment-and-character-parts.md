# Sofía 2D: every wardrobe item + face/eyes/hair/ears/tail

**Owner direction, 2026-10-16:** Produce artwork for the entire source wardrobe with the previously accepted illustration quality; make separate public/private asset roots, preserve exact garment file descriptions and send two reviewed image samples per slot. Also prepare permanently layered face, eyes, hair, ears and tail.

## Correct source count

A new source inventory audit counted **295 JSON-defined garments** across 14 source files, **244 public** and **51 private**. An earlier 275/47 claim missed entries. This is the actual work scope for the JSON catalogue (in-code built-in starter pieces are not included in the 295 count).

The implementation in src/sofia/avatar/vtuber_wardrobe_production.py:
- Reads every source JSON garment and rejects duplicate/missing IDs or privacy mismatch.
- Cross-checks source against the canonical WardrobePrebuild, computes a full-description fingerprint from vtuber_art_fidelity, and records required front and rear views (including graphics placed on the back and tail-clearance garment designs).
- Marks each work order source_brief_ready_art_unverified; a work order is **not** a created image or proof of exact artwork.
- Outputs a public JSON work queue with all 244 public IDs and **only aggregate** protected counts. It cannot expose the 51 private art briefs by default.
- Requires a real trusted PrivatePresentationGrant to list private work order identities; a trusted host must separately bind it to authenticated owner, private session, expiration, screen context and active STOP. This source does not mint a grant or produce private images.
- Test/test_avatar2d_wardrobe_production.py checks all 295 IDs, 244/51 split, safe public output, protected access, and front/back requirements.

**Public progress:** 244 public work orders defined and source-fingerprinted, with separate public procedural starter art support already present from prior batches. **Private progress:** 51 source-linked protected work orders accounted for, NOT generated or visible. **High-quality verified image count:** do not infer from source-brief count; none of these new work orders establishes an accepted high-quality illustration.

Command (installed Sofía checkout):

    python -m sofia.avatar.vtuber_wardrobe_production --output ./avatar2d-public-work-orders.json

The JSON reports exact source coverage and explicitly says that final sprite completion has NOT been asserted. Do not treat image-generated gallery captions or contact sheets as evidence of completion. Some generated posters claimed “275/275 complete” while containing no individually validated sprite files; that claim is false.

## Face and fox-character visual modules

New src/sofia/avatar/vtuber_character_parts.py authors **26 independent public RGBA starter sprites**, all on the SAME canonical 320 × 400 waist-up canvas, with declared anchor, group, variant, z-order and checked PNG digest:

| Logical group | Authored starter options | Future high-quality art required |
| --- | --- | --- |
| Face | neutral, soft | Single approved facial identity with expressions driven by layered overlays |
| Freckles overlay | off, on | Optional overlay, never replace face |
| Eyes | open, half, closed, looking_left, looking_right | Independently movable iris/pupil/lid layers, blinks and verified eye recolor |
| Brows | neutral, skeptical | Independently poseable left/right brows |
| Mouth | closed, smile, talk_small, talk_wide | Lip-sync viseme assets and real audio activity binding |
| Hair back | long_layered, tied_back | Natural moving back locks and braid/ponytail variants |
| Hair front | long_layered, tied_back | Bang/side-lock separation and tint masks |
| Left fox ear | perked, relaxed | Inner/outer ear, tilt and flat ears |
| Right fox ear | perked, relaxed | Separate mirror-aware ear, no extra ears |
| Tail | calm, raised, flick | Root/mid/tip motion and lighter tip, always one tail |

The sprite design uses canonical hair #8B1E3F, tail #3A245C and skin #F1E9D8 from avatar.json and preserves 2 fox ears/1 tail. Exact facial proportions are unspecified in canonical identity: illustration does NOT invent measured anatomical facts.

Command:

    python -m sofia.avatar.vtuber_character_parts --output ./avatar2d-public-character-parts

This creates real PNG bytes, one per component option, but they are **procedural starter drawings**, not yet the refined AI-generated look and not a Live2D rig. They must be visually reviewed against an approved character reference.

src/sofia/avatar/vtuber_character_selection.py provides a pure state-to-sprite selector for public projections. It maps expression, gaze, pose, optional freckles, hairstyle and *actual* speaking state to variant IDs. Unknown hairstyle or eye/hair/tail recolor reports a warning instead of pretending a missing asset was displayed. These groups are not yet connected to actual desktop image composition.

## Final integration requirements

1. Pick one reviewed reference model for Sofía's face/ears/hair, front and needed turn poses.
2. Make polished separate PNG or rig-compatible art, not a single image atlas with pretend checkerboard transparency.
3. Produce source-exact individual wardrobe layers across all required views. Preserve original fit, hems, fabrics, graphics/placement, closures, sleeves, tail clearance, item IDs, slot layers and private policy.
4. Fit each clothing layer to the exact body/neck/shoulder anchors of the *same* character rig. Off-camera garments should not falsely claim a waist-up rendered sprite; can be made for the later full-body atlas.
5. Maintain protected private art outside public Git/release and never auto-display private/nude from emotion or style autonomy.
6. Add expressive brows/lips/blink, ears/tail motion, hair deformation, visible-frame receipts and exact hit masks to the public renderer. Future 3D backend can reuse same canonical data.
7. Verify each image's actual transparency, content/shape, source SHA, image SHA, reviewer decision, size, alignment, occlusion and canonical audience before marking any item production-ready.
8. Run focused tests, package CI and supervised Venus real rendering. A passed test for a generator cannot certify professional artwork; Gate 4 needs actual proof.

**Status:** Source-mapped all 295; basic separate character part generator and selection implementation committed. Do not claim 295 polished image assets, a fully clickable rig, autonomous image generation or private protected renders are completed.
