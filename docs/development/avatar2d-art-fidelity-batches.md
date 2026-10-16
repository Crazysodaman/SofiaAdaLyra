# Sofía 2D wardrobe: fidelity batches

**Source:** canonical src/sofia/avatar/wardrobe_data/*.json and reviewed in-code garment blueprints.
**Status:** Art brief creation and unreviewed source-fingerprinted procedural sprite manifests are coded on main. The detailed AI-generated pictures remain *candidates*, not exactly validated production sprites.

## Source-locked artwork workflow

New code in src/sofia/avatar/vtuber_art_fidelity.py:
- Derives a source-linked SHA256 art brief from each validated garment blueprint.
- Preserves type, fit, rise, hem, sleeve length, material, primary/accent colors, pattern, graphic enablement and placement, item features, description, authoritative layer, occupied slots, coverage and privacy.
- Marks waist-up visible slots separately from the full wardrobe so a shoe is not falsely represented as a waist-up garment.
- Exports every public brief to JSON; keeps protected private descriptions out of public exports.
- Prints item-specific image-production instructions with prohibited invented features.
- Validates source + asset-hash review metadata, but **does not** prove that the picture is faithful or that the reviewer is the owner.

Existing src/sofia/avatar/vtuber_starter_art.py continues making lightweight renderable starter sprites; new manifest entries carry source_sha256 and visual_review_status=unreviewed_procedural_starter. Top-level manifest has fidelity_status=unreviewed_not_exact. Those attributes are deliberate: a PNG with the right item ID is not by itself an accepted exact match.

## Windows art-brief generation

    python -m sofia.avatar.vtuber_art_fidelity --output ./sofia-public-art-briefs
    python -m sofia.avatar.vtuber_art_fidelity --output ./unused --item day.engineer_jacket
    python -m sofia.avatar.vtuber_art_fidelity --output ./unused --item night.lounge_tee

The single-item route only prints instructions; the bulk route creates one JSON file per public item and refuses a nonempty output directory. Neither route writes production state or generates protected artwork.

## Explicit image mismatches found

| Item ID | Canonical description | Current generated image | Verdict |
| --- | --- | --- | --- |
| day.technical_top | Fitted black long-sleeve hip-length technical top, crimson shoulder/side seam accents and *small cyan circuit mark on left chest* | Some generated pictures are cropped, have electric pink rather than crimson piping, or show a generic cyan tab | Rework |
| day.engineer_jacket | Tailored hip-length black jacket, asymmetric front zip, crimson edging, small cyan hardware, reinforced shoulder/forearm panels and shaped tail-clearance rear | Generated jacket looks techwear but is cropped, front-open/symmetrical in places and does not prove rear geometry | Rework + rear view |
| night.lounge_tee | Oversized black short-sleeve brushed cotton-modal T-shirt, dropped shoulders, upper-thigh hem, largely plain FRONT, cyan/violet circuit-fox on upper BACK | Image puts prominent fox graphic on the front and shortens the hem | Reject as exact; make separate front/back |
| outer.technical_utility_vest | Fitted black light-ripstop vest, cyan zip details, compact low-profile pockets | Vest concept approximates colors, but has oversized pockets and improvised seams | Rework + aligned fitting |

These are visual observations, not automated fidelity guarantees. The earlier contact sheets are for inspiration only and do not constitute correctly separated RGBA garment layers.

## Corrected production gate per item

1. Pick original canonical item ID, never infer details from an image or filename.
2. Use the FULL exported source brief, keeping canonical color values and graphics on the stated side.
3. Generate transparent, separate front/back garment artwork when needed, using a common body pose, transparent canvas and known anchors.
4. Compare against every mandatory specification: type, fit, hem length, sleeves, textile impression, trim color, printed mark and location, closures, tail/ear cutouts, pockets and accessories.
5. Reject any wrong feature; a flattering image that contradicts the file is a draft.
6. Bind manually accepted art bytes SHA256, source fingerprint, versioned layer transforms, garment IDs/slots and applicable audience; do not forge owner review.
7. Verify actual compositing, occlusions and interactive masks, then run UI/AVATAR/SAFE tests and supervised Venus acceptance.
8. If a wardrobe record changes, invalidate previous exactness review through its changed source fingerprint.

## Scope and open work

The source contains 275 JSON garment definitions and a handful of in-code canonical garments. Every public garment can receive a source brief; only *visible* wardrobe parts need waist-up sprite art now. The 47 private-only JSON designs are not eligible for public art generation.

High-quality source-exact 2D art for the complete wardrobe is **not yet done**, neither is a fully rigged 2D avatar. Continue artwork in small item batches and show two representative candidate/reviewed images for each slot category as available. Use public covered fallback until private art and authorization are independently verified. This documentation and new source code do not move any V18 task to Gate 4.
