# Owner-approved 2D artwork: renderer integration gate

The eight installed batches total 57 2D **source** assets. Their location
under `%LOCALAPPDATA%\SofiaAdaLyra\Avatar2D\Private-Source\CoreLayers\v1\layers`
is not the public character pack used by the desktop renderer.

`TkLayered2DRenderer` already loads the verified public 320×400
`Public-V2\character\manifest.json`, together with the wardrobe layer
matrix. It must not scan Private-Source or bypass SAFE audience checks.

## Audit the installed artwork on Venus

After pulling latest main and activating Sofía's Python environment:

```powershell
$Base = Join-Path $env:LOCALAPPDATA 'SofiaAdaLyra\Avatar2D\Private-Source'
$Source = Join-Path $Base 'CoreLayers\v1'
python -m sofia.avatar.vtuber_external_core --source-root "$Source" --check
```

To generate a **review-only** contact sheet and asset inventory, choose a
**new** location:

```powershell
$Review = Join-Path $Base 'Review\core-v1'
python -m sofia.avatar.vtuber_external_core --source-root "$Source" --stage "$Review"
Start-Process (Join-Path $Review 'review_contact_sheet.png')
```

The audit checks exactly 57 expected filenames, refuses symlinks, hashes
and validates RGBA PNGs, reports missing/corrupt art and detects mismatched
canvas sizes. The review sheet and JSON inventory do not enable public
rendering or change any existing asset or canonical database.

## Measured blockers from the eight supplied ZIPs

- Face, eyes, eyebrows, mouth and hair are 2048×2560 RGBA.
- The approved ears are 1254×1254, tails 1122×1402, not the canonical
  2048×2560. Their root anchors/offsets need actual calibration.
- At least one eyebrow bounding box lies below the face bounding box.
  Placing both images directly on the canvas produces a visibly wrong face.
- The current public renderer selects 12 distinct character groups with
  33 defined group/variant pairs. The owner ZIPs contain different
  filename/pose groupings; ears need left/right extraction, tails need a
  single calibrated root, and visemes need verified speech events.
- A contact-sheet crop is **not** an alignment transformation.

The review gate deliberately reports `production_activated: false` even
when all PNGs pass integrity checks. Before importing any owner art into
a production renderer, obtain a reviewed **covered public** composition,
a per-sprite alignment map, exact output hashes, verified complete public
manifest, and live Venus frame evidence. A private rendering pipeline
requires separate SAFE owner authorization; never make it a toggle on the
public renderer. The canonical database and wardrobe records remain unchanged.

## Next integration milestones

1. Establish baseline face/eye/brow/mouth positions at 2048×2560.
2. Normalize source canvas and anchors with a reviewed calibration map.
3. Export public-safe 320×400 sprites only after geometry and owner
   approval, preserving the existing verified wardrobe matrix.
4. Map actual approved variants to independent animation frames. Test
   blink, wink, talking, emotion, ear and tail motions, safe fallback,
   stop, and garment occlusion.
5. Verify rendering on Venus, then begin finished-quality wardrobe art.

Existing procedural public renderer and older tested animated
sprites remain active until this work passes its production gate.


## Repeatable head alignment preview (review-only)

After the `--check` reports **57 expected, zero missing, zero invalid**,
create a NEW preview directory. This command never writes into the original
CoreLayers folder or the public renderer assets.

```powershell
git pull --ff-only
$Base = Join-Path $env:LOCALAPPDATA 'SofiaAdaLyra\Avatar2D\Private-Source'
$Source = Join-Path $Base 'CoreLayers\v1'
$Body = Join-Path $Base 'CanonicalBody\v1\sofia_body_base_2048x2560.png'
$Candidate = Join-Path $Base 'Review\head_alignment_candidate_v1'
python -m sofia.avatar.vtuber_core_alignment_preview --source-root "$Source" --canonical-body "$Body" --output "$Candidate"
Start-Process (Join-Path $Candidate 'head_alignment_candidate.png')
```

Outputs: `head_alignment_candidate.png`,
`tail_pose_contact_sheet.png`, and `alignment_candidate.json`.
If the target directory already exists, the tool refuses overwrite. Use
a new suffix (e.g. `_v2`) for subsequent review rounds.

**Calibration status:** New face/eyebrow/hair/ear positions are provisional
visual review only. Eye sprites include both eyes together, so independent
L/R eye movement is not proven by these source images. Ear pairs use
distinct numbered source poses but still need owner-reviewed left/right
registration. Tail root placement and wardrobe coverage have not been
accepted. Do not enable the static candidate image as production animation.

Focused source tests:

```powershell
pytest -q test/test_avatar2d_external_core.py test/test_avatar2d_core_alignment_preview.py
```


## Registration preview v2: eyebrow fringe and ear proportions

An owner screenshot of v1 revealed severely shrunken brows. The original
approved eyebrow PNG contains almost-transparent pixels hundreds of pixels
outside the visible strokes. The v1 `Image.getbbox()` crop included those
pixels and squashed both brows into a small steep expression.

The v2 **review-only** preview removes alpha <= 15 from the crop *decision*
without modifying the original artwork. It uses the owner's already-approved
`brows_soft.png` as a neutral-looking candidate, slightly enlarges ear
placements and shortens the bangs. Do not silently substitute `brows_soft`
for the runtime neutral expression before separate owner approval.

To generate v2 after pulling `main`, use a **fresh** target:

```powershell
$Base = Join-Path $env:LOCALAPPDATA 'SofiaAdaLyra\Avatar2D\Private-Source'
$Source = Join-Path $Base 'CoreLayers\v1'
$Body = Join-Path $Base 'CanonicalBody\v1\sofia_body_base_2048x2560.png'
$Output = Join-Path $Base 'Review\head_alignment_candidate_v2'
python -m sofia.avatar.vtuber_core_alignment_preview --source-root "$Source" --canonical-body "$Body" --output "$Output"
Start-Process (Join-Path $Output 'head_alignment_candidate.png')
pytest -q test/test_avatar2d_external_core.py test/test_avatar2d_core_alignment_preview.py
```

What remains unverified: the exact high-resolution head-to-body visual
acceptance, independent left/right pose masks, believable face/detail
consistency, talking visemes, garment occlusion, and actual animation
receipts on Venus. `production_activated` remains false.


## Owner review: C eyebrows approved; composite face rejected

**Owner review, 2026-10-17:** The eyebrow shape from alignment
comparison **C** (`brows_soft.png`) is approved as the resting look.
The head and neck composite shown in that candidate is explicitly NOT
approved for release. The nose is effectively absent/blurred, facial art
styles differ, and a visibly double-drawn jaw and neck seam remain.

Root cause of one seam: the earlier preview composited the approved
`face_base.png` opaque oval **over the canonical body's own head**.
The corrected preview now uses only the body's head silhouette and overlays
the shading/eyes/C brows/mouth/hair. This is a staging correction, not
proof of finished face art.

The machine-readable preview report records:
`head_quality: REJECTED_needs_cohesive_head_and_nose_art`,
`owner_approved.brow_variant: brows_soft`,
`owner_approved.full_face: false`, and
`head_base: canonical_body_only`.

**Do not advance to production from this preview.** Author a coherent
matching face-and-neck base with visible nose and compatible shading,
preserving approved eyebrows and eye design. Validate jaw/neck edge
transitions, facial expressions, mouth position, covered public
silhouette, hair/ear attachment, and tail/wardrobe occlusion separately.
Neither smoothing a PNG nor another transform alone resolves mismatched
face and body illustration styles.

For an optional post-fix DIAGNOSTIC (not a release candidate), after
`git pull --ff-only` generate a new review folder, e.g.
`Private-Source\\Review\\head_alignment_candidate_v3`. The
`head_quality` failure is expected until replacement art passes review.


## Coherent face-and-neck replacement v1 (new artwork candidate)

The earlier v1-v3 assembled previews were rejected for double-drawn head
edges, a blurred/absent nose, and incompatible facial shading. The owner
approved **only** the C/soft eyebrow shape, not those completed faces.

An entirely new cohesive static portrait was authored for visual review.
It includes a defined nose, naturally continuous jaw and neck shading,
violet eyes, crimson/violet hair, and fox ears with lavender inner fur.
It is **not** independent modular sprite animation.

The downloadable owner package `Sofia_Cohesive_Face_Candidate_v1.zip`
contains the full-resolution original RGBA art, an explicitly registered
2048x2560 transparent composite head, a body-head suppression mask to avoid
duplicate underlying head silhouettes, a cropped preview, per-file SHA256
manifest and non-destructive Windows check/stage/verify scripts.

The Windows stage action copies files only into:

```text
%LOCALAPPDATA%\SofiaAdaLyra\Avatar2D\Private-Source\Reviewed-Candidates\CohesiveHead\v1
```

It refuses overwrites. It does **not** replace the 57 CoreLayers sprites,
edit the canonical body, write sofia.db, copy art into Public-V2, or
enable the Tk renderer.

After downloading and extracting the archive, run in order:
`Check-SofiaFace.cmd`, `Stage-SofiaFace.cmd`, `Verify-SofiaFace.cmd`.
To run an additional code-level check after pulling `main`:

```powershell
$Candidate = Join-Path $env:LOCALAPPDATA 'SofiaAdaLyra\Avatar2D\Private-Source\Reviewed-Candidates\CohesiveHead\v1'
python -m sofia.avatar.vtuber_cohesive_candidate --root "$Candidate"
pytest -q test/test_avatar2d_cohesive_candidate.py
```

The candidate is **static** and currently unapproved as a live avatar.
Do not overlay existing full-frame eyes, brow, mouth, hair or ear layers
over the baked-in portrait: that would duplicate features again.
After visual acceptance, derive separately painted clean skin/face,
eye, brow, mouth, hair and ear assets with exact alpha/anchors, and
verify expression/viseme animation, garment occlusion, fallback, and
public/private scope before enabling production.
