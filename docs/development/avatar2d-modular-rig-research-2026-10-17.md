# Sofía 2D modular rig: research-led art and runtime plan

**2026-10-17 | Owner-installed Batch 09 earless head | Branch: main**

**Research scope:** Official Live2D Cubism, Inochi2D, and Krita manuals; cross-checked against Sofía's `src/sofia/avatar/vtuber_character_parts.py`, `vtuber_character_bundle.py`, `vtuber_character_selection.py`, `ui/avatar2d_renderer.py`, `vtuber_external_core.py` and `vtuber_core_alignment_preview.py`.

**Evidence status:** research and reviewed code paths, **NOT** a production-ready modular rig, texture separation proof, or Windows CI result. Owner already installed the earless Batch 09 candidate, but the `CoreLayers\v1` inventory and the separate Batch 09 staging install are different assets. No deployment, artist review of new rig, or host tests are implied by this document.

## Executive decision

**Keep the existing verified Python/Tk 2D sprite renderer for first delivery.**
Create an **editable, layered art master** (Krita `.kra` plus PSD export where practical), render its independent layers to full-canvas RGBA PNGs, then build a separately verified and genuinely compatible **320×400 public sprite pack**. The existing Tk renderer already uses 12 character groups, deterministic outfit matrices, expression receipts, sprite hashing, and safe symbolic fallback. Replacing it with a new animation engine before repairing the art would introduce a second project and would not correct mismatched facial layers.

Investigate **Inochi Creator/Inochi2D** later for mesh deformation if Sofía needs continuous hair and ear physics or body angles. Do not embed Inochi into the Tk UI without a tested host/window/integration bridge. Live2D Cubism is a mature professional reference for rigging and separations, but adopting its SDK adds distinct integration/licensing and runtime choices; it does not convert uncut images into usable parts automatically. Choose an advanced rig only after the 2D still-frame acceptance passes.

## What independent riggers do differently

1. **Separate and repaint covered pixels.** Live2D specifically separates face contour, eye whites, iris, eyelids/lashes, nose, eyebrows and upper/lower lips/mouth inside. Parts that will move need extra hidden material drawn behind them. A portrait flattened to one PNG cannot be split by naming files alone.
2. **Maintain an editable master and import copy.** Official Live2D guidance uses a layered editable separation PSD, plus a flattened-per-part import PSD. Preserve editable masks/paint in the master, then combine each part's fill and line art for export. Krita supports layer groups, alpha inheritance and masking for this workflow. For Cubism compatibility export RGB, 8-bit/channel sRGB PSD and one merged layer per final part.
3. **Bind parts to one coordinate system and explicit draw order.** Live2D includes per-mesh draw order, clipping, and opacity, because a correct image set still renders incorrectly when a back-hair lock floats in front of the eyes or a tail covers clothing.
4. **Rig after reference art passes.** Begin with verified eye open/closed, independently drawn left/right blink, brows, mouth, ears and tail. Advanced deformers and automated mouth motion are subsequent phases.

Sources:
- Live2D material separation: https://docs.live2d.com/en/cubism-editor-manual/divide-the-material/
- Live2D illustration/eye/face/mouth processing: https://docs.live2d.com/4.2/en/cubism-editor-tutorials/psd/
- Live2D current PSD import: https://docs.live2d.com/en/cubism-editor-manual/psd-import/
- Live2D PSD color/depth/mask guidance: https://docs.live2d.com/en/cubism-editor-manual/precautions-for-psd-data/
- Live2D draw order, masking: https://docs.live2d.com/en/cubism-editor-manual/inspector-palette/
- Krita layer groups/alpha inheritance: https://docs.krita.org/en/reference_manual/dockers/layers.html
- Inochi2D overview: https://docs.inochi2d.com/en/latest/
- Inochi Creator: https://docs.inochi2d.com/en/latest/creator/about.html
- Inochi2D PSD caveats / licensing / incompatibility with Cubism: https://docs.inochi2d.com/en/latest/inochi2d/faq.html

## Specific flaws in our installed batches

| Existing artifact | Evidence / defect | Required repair |
| --- | --- | --- |
| Canonical 2048×2560 body + original face base | Both provided opaque head silhouettes; produced jaw/neck seam | Exactly one head silhouette and authored shoulder/neck occlusion; **do not just stack the new whole bust on existing body** |
| New Batch 09 earless `head_base.png` | Owner staged, human ears removed; featureless base is expected | Verify **no residual human-ear geometry** by visual review; match skin, head/neck outline and anchors to canonical body; mark as unapproved until accepted |
| Face shading | Earlier candidate carried broad skin texture and mouth hints | Export *only* needed shading/highlights on true transparent RGBA, without another face/bust silhouette |
| Eyes: ten source images | Previous inspection found images containing both eyes in one sprite | Create independent `eye_left` and `eye_right` layers/poses; do not report per-eye autonomy from a double-eye PNG |
| Brows: six images | Long near-transparent fringe and wrong crop; C/`brows_soft` approved for neutral look | Preserve C expression, clean alpha fringes, lock full-canvas left/right anchors |
| Mouth / six visemes | Source art not registered to rebuilt head; some baked features in one-piece reference | Paint dedicated mouth shapes, underlying neutral skin, and phoneme shapes only; map lip sync to **actual audio playback events** |
| Hair variants | Some parts were generated as whole hair pieces and cropped into source canvas | Redraw/re-export genuinely separable back, bangs, side locks and hairstyle swaps with filled gaps |
| Ears: ten images, 1254² | Individual pose samples, not guaranteed left/right pairs; source size differs | Validate root location and five **actual** independent poses per ear on common canvas. No human ears on head |
| Tail: seven images, 1122×1402 | Cannot attach by simply centering each sprite; root moves across poses | Define stable tail root, z-order and coverage/occlusion under garments for all seven poses |
| Current Tk public renderer | Expects 320×400 PNG per authored part and exact `character/manifest.json` with 12 groups/33 variants | Export explicit compatible **public-only** pack from a curated private master, verify hashes, do not scan `Private-Source` |

### Geometry truth

The master and runtime aspect ratios **do match exactly**:
`2048/2560 = 320/400 = 0.8`; coordinate scale is
`320/2048 = 400/2560 = 0.15625` (the full-resolution master is 6.4× either runtime dimension).
This eliminates a need for nonuniform stretching **if** the parts are actually aligned to the master canvas. Ear and tail inputs first need authored placement on the full-size master. Avoid independent tight bounding-box centering as an export strategy: it loses pivots, offsets and neighboring part alignment. Keep all approved source originals and bake the explicitly reviewed registration into new output copies only.

Suggested metadata for each new output: `role`, `source_file`, `source_sha256`, `master_canvas`, `runtime_canvas`, `alpha_bbox`, `pivot_px`, `z_order`, `audience`, `visual_review_sha`, `generated_from`, `output_sha256`, `review_status`. This is a **proposal**, not a replacement for the strict existing `character_parts.v1` runtime manifest.

## Recommended draw order (back-to-front)

1. Scene/background (not a character part).
2. Tail **behind** body, unless a specific pose requires a separately reviewed front segment.
3. Hair **back** layers.
4. Fox-ear root/art layer in the approved relation to back hair.
5. Canonical body with exactly one registered head/neck. If the new head replaces canonical head pixels, do so via a specifically reviewed mask and an actual single continuous silhouette.
6. Face contour/shading and independent eye whites/irises/eyelids; brows; mouth/viseme.
7. Garments from canonical wardrobe matrix with per-slot coverage/occlusion.
8. Hair **front/bangs**, with reviewed exceptions where clothing goes in front.
9. Front accessories/gesture overlays if specifically verified.

Exact z values must match the existing renderer and the active garment coverage plan, not this prose list alone. An apparently pleasing front-hair preview is not proof of correct mask/occlusion with every outfit.

## Rig and behavior contract

- **Neutral/smile/skeptical:** choose *existing reviewed sprite variants*. Keep C-brow shape for neutral only after it exists as independent left and right artwork.
- **Blink:** three frames open/closed/open with both eyes actually changing. **Wink:** one closed eye only, independent eye sprites.
- **Gaze:** center/left/right look requires independent eyes/irises and explicit bounds; don't infer camera tracking.
- **Mouth:** closed/smile/open and later A/E/O/M visual cues. Mark speaking frames only when tied to confirmed speech output, not by reading text.
- **Ears:** five reviewed poses *each* (left/right independently), no human-ear geometry.
- **Tail:** seven reviewed frames with stable pelvis attachment and tail clearance for clothes.
- **State:** existing canonical `sofia.db` remains sole authority for wardrobe, avatar state, permissions. The art never directly grants private or adult access.
- **Stop/failure:** cancel pending animation; never claim a frame displayed after stop; missing/hash-mismatched parts trigger the existing public symbolic fallback rather than mixing unchecked private sprites.

## Production gates

| Gate | Required proof | Current evidence |
| --- | --- | --- |
| A. Source integrity | 57 original PNGs present and uncorrupt; staged Batch 09 verified | Owner reported 57/57 original files OK; staged Batch 09 install reported, not newly tested here |
| B. Master topology | One head/neck, **no human ears**, no extra outlines, no baked eye/mouth/hair/ear layers, separate shading; owner compares full-body overlay | **Open** |
| C. Independent art | Per-eye/blink, per-brow, separate mouths, visemes, hair, 5×2 ears, 7 tails; transparent full-size canvas, matching style | **Open** |
| D. Runtime compatibility | 320×400 reviewed runtime pack with exact current schema/IDs/sha256 and covered public garment bundle | **Open** |
| E. Animation integration | Authentic 3-frame blink/wink/ear/tail/speech receipts; exact active state and stop, missing asset fallback | Existing procedural support, **new art unverified** |
| F. Windows CI / Venus | Reproducible scripts, integrity tests, CPU/RAM, full-body alignment at multiple outfits, no private/public leakage | **Open** |
| G. Wardrobe | Only after core reaches E/F; preserve existing garment IDs/coverage and do clothing fit per exact item description | **Next after core** |

## Priority work order

1. Turn the approved earless Batch 09 into a **single-head** compositional baseline. Build clean `head_base` and *true shading-only* layer from the same illustration source, without duplicating shoulders. Show contact sheet at full body.
2. Separate/correct real left/right eyes and C brows against that baseline. Test blink and wink without any fused eye pair.
3. Separate mouth and visemes, plus hair front/back, preserving C-brow visual proportions. Show open/half/closed, smile/smirk and speech shapes.
4. Re-register independent ears with stable root and orientation, then tail variants with root/garment occlusion.
5. Convert *approved* full-res parts to 320×400 and compile checked manifests **without** modifying `Public-V2` until reversible installation, safe fallback and owner sign-off are demonstrated.
6. Commit implementation/test evidence on `main`, run focused then CI tests, supervised Venus session. Proceed to the wardrobe only after the character rig behaves correctly.

**Avoid misleading shortcuts:** no contact sheet treated as standalone PNGs, no one-piece image passed off as a sprite stack, no stretching differently sized tail poses independently, and no test claimed passed without actually running it.
