# Public 2D wardrobe image production (244 garments)

**Current source of truth:** `src/sofia/avatar/wardrobe_data/*.json`, not
invented fashion descriptions or a UI illustration.

On 2026-10-17 the public inventory is 244 garments in 13 categories; the 51
`private_only=true` rows are not exported. Each image in the initial public
atlas is associated with the exact garment item ID, material/color/pattern,
source description fingerprint, and a SHA-256 image checksum.

## Evidence and honest production status

- **244/244** public per-item transparent **first-pass vector drafts** can
  be generated automatically by
  `python -m sofia.avatar.wardrobe_public_sprite_batch --output C:\\Temp\\sofia-public-wardrobe-draft`.
- **9** previously generated high-detail illustrations are preserved as
  `illustrated_references/<item_id>.png` in the CI output where the earlier
  illustrated ZIP is available. These were produced without shared
  character-body anchors and are **not interchangeable rig sprites yet**.
- **0/244** public garments are *automatically accepted as professional,
  fitting illustrated items*. Per-item authored fit work and visual review
  remain necessary. Existing procedural starter PNGs are likewise not
  production-quality illustrated garments.
- Full outfit portraits (including Night Lounge and Autumn Cyber) belong to
  a **separate static portrait workflow**. Never count an outfit portrait as
  proof that its individual jacket, top, boots, and accessory are separable.
- The generator does **not** import the resulting draft folder into the
  public 2D renderer. Doing so would silently replace improved character
  visuals with placeholders.

## Reproducible artifact

The `Avatar2D Public Wardrobe Draft PNGs` Windows Actions workflow builds
and tests the whole public draft set on `main`. The artifact named
`sofia-public-wardrobe-244-DRAFT-NOT-LIVE` includes a `manifest.json`,
`items/*.png`, and the nine separately labeled original illustrated
references (when present). The artifact is downloadable from its workflow run.

The file manifest intentionally includes:

- `item_id`: exactly the source garment ID
- `source_description_sha256`: stable SHA-256 of the garment's design fields
- `sprite_sha256`: SHA-256 of the candidate image bytes
- `art_status`: `procedural_first_pass_NOT_REVIEWED`
- `rig_status`: `NOT_FITTED_FOR_LIVE_REUSE`
- `private_only`: always `false`

## Production-grade acceptance required for EACH garment

1. Author on the SAME full-body 2D template and anchor geometry with correct
   head/neck, shoulders, torso, sleeves, hips, legs and footwear.
2. Match all source-defined garment design fields, including fabric,
   fit, sleeve length, primary/accent color, pattern, graphic, hardware,
   pocket placement, hem/rise, slots and ear/tail clearance.
3. Export native transparent RGBA artwork without baked-in character body,
   hair, face, floor, backdrop or another clothing item.
4. Check normal/outer/accessory z-order, occlusion, compatibility,
   animation-safe rest pose and consistent alignment on the exact runtime
   viewport (prefer full-body high-res before deriving 320x400 waist-up).
5. Give each rendered sprite its own reviewed manifest, design hash, and
   approval state. Never report live garment swapping from metadata alone.
6. Run compositing, pixel-boundary, full outfit and real Venus display tests
   on actual hardware. Keep private materials outside this pipeline.

## Next implementation

The first production art batch should use the existing nine high-resolution
illustrations as style references and re-author them around a frozen character
rig template, **not** simply resize them or treat the entire artwork poster
as individual garment sprites. Then work category by category across all 244,
with one reviewed slot/quality gate per item.

The image-generation concept poster with 'all 295 created' headings is a
visual mockup, not an asset-count proof.
