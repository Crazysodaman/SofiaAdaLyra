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
