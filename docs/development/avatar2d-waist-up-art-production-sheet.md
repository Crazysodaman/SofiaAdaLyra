# Sofía 2D VTuber | Waist-up art production and rigging handoff

**Companion document:** avatar2d-waist-up-implementation-spec.md.
**Scope:** Draw and export one coherent waist-up Sofía as (A) always-available covered PUBLIC puppet, and (B) independently gated owner-PRIVATE art additions that reuse the same proportions, face and motion coordinate system. Private wardrobe and optional nude torso assets are **separate optional production sets**.
**Status:** Production sheet, NOT delivered artwork, valid layer PNGs, a rig, or a deployed private renderer.

## 1. Approved character reference lock

- **Identity:** Sofía Ada Lyra, adult virtual human-form character with exactly two fox ears, one fox tail, two human arms and two legs. Waist-up visual crop must not suggest extras.
- **Face:** feminine anime-inspired face, bright violet eyes, expressive eyebrows and lips. Exact unmeasured facial landmarks should be decided from a user-approved reference sheet, not randomly inferred from stored measurements.
- **Hair:** long layered deep crimson with violet undertones. Primary #8B1E3F, darker wine shadows, lighter controllable violet accents; renderer may offer reversible cuts, colors and styling.
- **Fox ears and tail:** outer dark violet #3A245C; lighter violet inner ears and tail tip. Fluffy texture expressed through illustrated tufts, masks and later deformation, not mandatory expensive fur simulation.
- **Skin:** warm ivory #F1E9D8 with editable undertone/lighting layers.
- **Clothing silhouette:** black/charcoal technical engineer/scientist, #0B0D12 and #171A21 base, violet circuitry accents, electric teal #19D3C5 details. Light practical construction, shoulder movement and layered jacket.
- **Default face:** calm, curious, confident rather than fixed smiling. Gentle asymmetry allowed in expression, not permanent topology.
- **Canonical body baseline:** existing avatar.json remains authoritative. Do not invent shoulder width, arm circumference, breast placement, tail thickness or any unstated dimensions from textual spec. Image art is design, not a new anatomical measurement ledger.

Review and approve **one front-facing canonical concept sheet** before separating art. Ensure she remains visually recognizable after changing hairstyle, eye color and clothing. Generate a face/ear/tail identity turn sheet with neutral lighting and baseline outfit; art previews are NOT usable animation layers.

## 2. Canvas, naming and delivery

**Master source:** layered PSD or KRA, non-destructive. **Export:** independent RGBA PNGs at aligned 2048x2048 source coordinates (or documented common-bounds cropped sprites with correct pivots). All assets use the same canvas, zero-offset reference pose, same neck/shoulder alignment and documented transform origin. Content outside crop should be preserved only when necessary for sway, without opening an alternate silhouette.

**Target display:** 384x512 to 768x1024 on normal desktop; preserve full-resolution masters. Color profile sRGB, premultiplied-alpha treatment consistent with chosen renderer (prefer straight alpha on input). Avoid white fringes and opaque rectangular backgrounds.

**Folder plan (logical names):**

    assets/avatar2d/public/
      manifest.json
      reference/
      base/
      face/
      eyes/
      mouth/
      brows/
      ears/
      tail/
      hair/
      outfits/
      overlays/
      accessories/
      poses/
      source-art/  [excluded from runtime bundle, include separately if licensed]

Private packages are NOT placed under public source root. Treat private KRA/PSD, renders and previews as restricted artifacts outside public Git and distributable bundles.

**File rule:** every image exported separately, sorted with stable layer IDs, with correct pivot/parent/z-order, alpha bounds, content hash, creator/license/provenance. Don't name assets from prompts only; inspect every actual file. Prefer one explicit neutral texture and an independent tint mask per recolorable component.

## 3. Required PUBLIC art layers

| Group | Minimum independent exported parts | Purpose / anchors |
| --- | --- | --- |
| Torso | neck, torso, left and right shoulders, upper arms/hands when in crop | Head neck pivot, shoulder L/R pivots; skin/tops can move independently |
| Face | face base, nose detail, cheek zones, chin/neck shadow | Static identity structure separate from dynamic expressions |
| Hair | back volume, left/right side locks, crown, front/bangs, 2 loose strand clusters | hair follows head; front/back z-order correct around ears |
| Eyes | sclera L/R, iris L/R, pupil L/R, catchlights L/R, upper/lower eyelids L/R | blinking and gaze independent; tint iris mask only |
| Eyebrows | independent brow L/R, neutral/up/furrow shapes or a deformable base | skeptical asymmetry |
| Mouth | closed, small open, medium open, wide open, smile, smirk and frown | controlled by real talk/expression state |
| Fox ears | ear L/R outer shell, inner fur L/R, tufts, optional ear-shadow | head anchors support perk, tilt and flatten |
| Fox tail | visible base, mid section, lighter tip; segment seam coverage | root anchored behind torso, visible in waist-up crop |
| Surface | blush, freckles, eyeliner, subtle cheek shadows, optional under-eye detail | toggle/tint without repainting face |
| Outfits | default technical shirt, default jacket, collar and shoulder layers | actual covered fallback with independent arms and hair overlap |
| Accessories | glasses, headset, hair clip, earring/stud, temporary tattoo overlay | selectively render only when compatible |
| Silhouette | clean matching shadow/occlusion and contact planes | hide segmentation gaps on motion |

Do not bake irises into the eye whites, eyebrows into the face, ears into hair, or the tail into the jacket. Face must remain the same underlying character between variants.

## 4. Required pose and expression sheets

**Face expression set v1:** neutral; soft smile; happy; skeptical (one raised brow); focused; annoyed; thinking; relaxed/tired; subtle blush. Additional playful/confident and affectionate expressions are useful but not mandatory at baseline.

**Eyes:** open, 50% and closed lids; gaze left/center/right; independent irises/pupils and highlights. For any eye color, colorize the iris/tint mask only. Eye-tracking is synthetic screen-relative movement initially, **not** camera tracking.

**Mouth:** closed; talk small/medium/wide; smile/smirk; frown. Create geometry that is coherent when head tilts and can be driven from actual audio playback. Silence uses a closed or expressive non-speaking mouth.

**Fox ears:** left and right relaxed, perked, angled curious, flattened, asymmetric interest. Each independently rotatable around own root; inner-fur motion stays synchronized.

**Tail:** root behind torso; calm curve, slight raised, left flick, right flick, wag keyframe 1/2/3; avoid jump cuts at base and ensure the tail stays one tail. Base, mid and tip should overlap enough to avoid alpha seams.

**Upper body:** neutral/breathing, lean forward, relaxed shift and small shoulder movement. No fake walking full-body sprite in v1. A waist-up rendering may acknowledge pose/sway, not invisible leg motions.

**Hair:** canonical long-layered plus initial work ponytail and relaxed loose variant if artwork can be delivered consistently. A hairstyle change is an actual different set of strands, not just renaming a parameter. Hair color changes via tint masks; significant hair length changes require new art. Ensure ponytail layers do not cut through fox ears or shoulder clothing.

## 5. Outfit packages

**Public v1 (real sprites):**
1. Signature engineer: closed/covered undershirt, charcoal asymmetrical practical jacket with violet/teal engineering accent.
2. Late-night lounge: fully covered relaxed top, shoulder/hair collision-free. Must map to a catalog outfit that is actually allowed public.
3. Stretch: lab/smart technical top, once independently illustrated and mapped.

Each visible outfit requires separate front/back layers, collar, sleeve/upper arm interaction, jacket closure and torso occlusion. Map to existing wardrobe IDs rather than inventing a new outfit authority. An existing wardrobe blueprint without approved art cannot be marked renderable.

**Private wardrobe asset package:**
- May contain owner-approved private-only upper-body garment sprites from Sofía's current private wardrobe, respecting garments' actual slots and layers. Examples: private lingerie-type tops, special lounge garments or other existing private-only catalog categories, only where they already exist and are approved.
- Supply garment cutouts compatible with canonical skin/torso/neck/head rig, preserving occlusions and proper layering.
- Mark every private variant, its original garment ID and license/provenance private; never automatically mirror or downgrade private layers into public fallback.

**Optional nude waist-up variant:**
- A distinct **restricted**, adult virtual avatar torso base aligned to the same head, ear, tail and posture rig; covered public art remains completely separate.
- Only the anatomically visible waist-up features need authoring. Confidential full-body color metadata and other unshown anatomy have **no reason to enter** this sprite package.
- Drawn and previewed solely under explicit private-mode opt-in and verified adult/avatar authorization. The nude torso is not included in automatic public style packs, generic preview carousels, public assets or generated training examples.
- If artist cannot deliver a compliant, reviewed private sprite, leave the variant unavailable. Never use public placeholder art to claim nudity was rendered.

## 6. Self-made look recipe combinations

Sofía may build from approved layers:
- independently choose a hair variant and tint, eye tint, expression, ear/tail stance;
- attach a public wardrobe-compatible top/jacket, makeup, freckles or approved reversible cosmetic overlays;
- save recipes with stable asset references and bundle digest, reason/provenance, audience class and compatible rig version;
- revisit favorites and compare their style history without changing the canonical face/body.

**Keep concept artwork separate from production sprites.** For newly imagined hair, outfit or private item:
1. Generate a concept proposal (safe preview scoped to audience, not a new real item).
2. Confirm identity consistency, garment coverage/compatibility, licensing, allowed audience, source and provenance.
3. Produce actual **aligned separated layers**, approved masks, matching cutouts, correct pivots and transparent edges.
4. Validate manifest hashes, layer IDs, occlusion/pose and safe fallback.
5. Promote an accepted bundle and only then allow renderer selection. Missing parts remain unavailable, not selected.

Private proposals may be created in a protected workspace, but Sofía **cannot** self-grant private visibility or start a nude render from mood/autonomy rules. Use exact current scope/opt-in required by the existing SAFE authority.

## 7. Asset QA checklist

- [ ] Face proportions and eye placement match approved reference across all variants.
- [ ] Exactly two visible fox ears and one tail; both ears can pose independently.
- [ ] Public fallback is fully covered at every rendered frame and rest pose.
- [ ] Transparency clean at ears/hair/tail and sleeves; no cropped pixels exposed by pivots.
- [ ] Each sprite has declared pivot/z-index/parent and correct canvas; no hidden baked background.
- [ ] Hair, iris and outfit tint layers do not recolor skin or neighboring art.
- [ ] Blink works on both eyes independently; mouth and talk shapes look coherent.
- [ ] Ear flatten and tail wag do not detach or change topology.
- [ ] Public and private packages have separate manifests and file roots, plus no private thumbnails in public cache.
- [ ] Nude/private set has authorized scope and completely absent public fallback path.
- [ ] At least 2 public hairstyles and 2 public outfits **actually exist as renderable files** before they count as shipped.
- [ ] Test safe portrait with all private art absent, corrupted, or revoked.
- [ ] Verify exported source/assets have license/provenance and SHA256, plus size/decompression limits.
- [ ] Review expressions in neutral and dark-mode backgrounds at small display scale.
- [ ] Verify outfit swaps preserve avatar's face/ears/tail and the exact displayed look revision.

## 8. Handoff and future evolution

Deliver an approved canonical reference, layered source project, independent transparent exports, packed manifests with checked digests, tint masks, pivots/anchors, compatible outfit mapping, public fallback test image, and a per-asset review sheet. Private art is delivered solely to the protected asset pipeline. Production acceptance requires actual runtime screenshots/renderer receipts **from authorized host testing**, separate from artistic mockups.

Later: more hairstyles and outfits, richer mouth visemes, independent tuft/strand deformation, mesh-style 2D rig, articulated hands/props, and optional full-body/3D. None require a new Sofía identity or consent authority.
