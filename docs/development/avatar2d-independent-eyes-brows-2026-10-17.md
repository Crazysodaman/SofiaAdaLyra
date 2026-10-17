# Batch 10 + 11: independent eyes and eyebrows (2026-10-17)

**Status:** packaged review art and source verifier on `main`, **not yet
installed or demonstrated in the production 2D renderer**. The owner has
already installed Batch 09 v3 head foundation on Venus. This release
deliberately follows that foundation without modifying it.

## Actual source split

The approved Batch 02 sources contain **two eyes in each PNG**. The new
review set preserves their pixels and exact canonical coordinates while
cutting at the transparent centerline `x=1024`. Each of the 10 eye poses
now has independently addressable `eye_left` and `eye_right` RGBA layers
on the full `2048×2560` canvas, **20 exported eye PNGs total**. No
mirroring or fake single-eye filename references.

The approved Batch 03 brow sources similarly contain both eyebrows; the
new set makes six left and six right RGBA layers (12 total). The
approved **C / `brows_soft`** shape is recommended for neutral. Old
near-invisible source fringe (alpha <=15) is excluded from crop bounds;
the corrected brows are registered above the matching eye. Other
expression-brow placements remain candidates pending review.

Both sets are source-fingerprinted (SHA256) and are paired to the
`head_base.png` and `face_shading.png` hashes from Batch 09 v3.
The pack has its own manifest, Windows installer and four review-only
actions plus a rollback. It **does not overwrite** original art.

## Package layout

```text
Sofia_Batch10_11_Independent_Eyes_Brows_v1/
  manifest.json
  README.txt
  layers/eyes/eye_left/<10 state names>.png
  layers/eyes/eye_right/<10 state names>.png
  layers/brows/brow_left/<6 state names>.png
  layers/brows/brow_right/<6 state names>.png
  Preview_Eyes_Brows_Independent_v1.png
  Install-Batch10_11.ps1
  Check-Batch10_11.cmd
  Stage-Batch10_11.cmd
  Verify-Batch10_11.cmd
  Preview-Batch10_11.cmd
  Rollback-Batch10_11.cmd
```

The preview shows independently selected neutral open, two-eye blink,
left-eye wink, left gaze, skeptical, and happy closed. It deliberately
**does not include hair or mouth**, which are subsequent art stages, so
the preview's face looks unfinished. This is not a defect in the
individual eye separations.

## Installation on Venus

1. Extract `Sofia_Batch10_11_Independent_Eyes_Brows_v1.zip` into a
   separate directory.
2. Run `Check-Batch10_11.cmd` and require green `CHECK PASS`.
3. Run `Stage-Batch10_11.cmd` and require green `STAGE PASS`.
4. Run `Verify-Batch10_11.cmd` and require green `VERIFY PASS`.
5. Run `Preview-Batch10_11.cmd` to see six expression examples.

The script uses `$PSScriptRoot`, never a quoted trailing backslash
argument. It verifies all 40 package file hashes and the two exact
Batch 09 SHA256 values. If staging already exists it refuses overwrite.
`Rollback-Batch10_11.cmd` moves only this review folder aside with a
dated name.

Destination:
```text
%LOCALAPPDATA%\SofiaAdaLyra\Avatar2D\Private-Source\Reviewed-Candidates\Batch10_11_IndependentEyesBrows-v1
```

With latest `main`, independently verify:

```powershell
git pull --ff-only
$Base = Join-Path $env:LOCALAPPDATA 'SofiaAdaLyra\Avatar2D\Private-Source\Reviewed-Candidates'
$Features = Join-Path $Base 'Batch10_11_IndependentEyesBrows-v1'
$Foundation = Join-Path $Base 'Batch09-ModularFoundation-v3'
python -m sofia.avatar.vtuber_independent_features --root "$Features" --foundation-root "$Foundation"
pytest -q test/test_avatar2d_independent_features.py
```

The above `pytest` tests are committed but have not been executed on
exact `main` or on Venus in this release. The package itself underwent
local SHA256, PNG RGBA, left/right alpha-box, and ZIP CRC checks.

## Next gates

- Owner visual approval of new eyebrows and eye spacing on Batch09 base.
- Correct independently-painted neutral/smile/talking mouths and six
  visemes, including masking of any earlier baked mouth shape.
- Real back/front hair and **fox** ears with independently registered
  anchors. Never reintroduce human ears.
- Seven tail poses on a common master canvas with stable attachment root.
- Public-safe covered body/outfit, suitable 320×400 exports, strict
  existing runtime manifest/role mapping and independent animation tests.
- Full Venus production acceptance. Nothing in this review manifest
  authorizes public renderer changes or private adult art exposure.
