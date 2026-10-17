# Sofía avatar 2D Batch 12+13: real mouth and viseme repairs + frame preview

**Date:** 2026-10-17. **Branch:** `main` only.

**Production status:** 12 individual 2048×2560 RGBA source-art layers are packaged and
locally inspected, but **not activated in the live Sofía desktop renderer**.
Batch 09 foundation and Batch 10/11 independent eye/brow layers must
already be staged and verified on Venus.

## Why this batch matters

Audit of the approved original Batch 05 revealed an integrity failure that
file hashes alone could not detect. `mouth_viseme_A.png` and
`mouth_viseme_O.png` were **hair illustrations**, not mouth sprites.
The old `mouth_viseme_M.png` depicted an open mouth, inappropriate for
the usual closed-lips `M` pose. The images were valid RGBA PNG files and
their hashes were internally consistent; only **semantic** inspection
exposed the wrong content.

The repaired package replaces all six viseme frames with versions made
from the previously approved mouth illustration source. Original Batch 04
mouth pixels are preserved in six separate registered files. A/E/O/M
now have visibly different geometry, with `M` closed. `A` and `O` no
longer render hair. The original source folders remain unchanged.

The registration and validation checks require a nonempty alpha bbox
inside the head's actual mouth zone:
`945 <= x_min < x_max <= 1075` and
`280 <= y_min < y_max <= 355`.
Every export is 2048×2560 transparent RGBA on the canonical canvas.

## Review package

`Sofia_Batch12_13_Mouths_Visemes_REPAIRED_v1.zip`

Contents:
- 6 mouth poses: `neutral`, `small_smile`, `smile`, `smirk`,
  `frown`, `open_small`
- 6 visemes: `open_medium`, `open_wide`, `A`, `E`, `O`, `M`
- `Preview_Mouths_Visemes_And_Expressions.png`: 12 real combinations
  with the independently selected left/right eye and brow assets
- `Preview_Frame_Swaps_Review_Only.gif`: eight changing sprite frames,
  **offline demonstration only, not proof of audio lip sync**
- `Preview_320x400_Source_Scale.png`: aspect/scale illustration, NOT a
  valid public character bundle or finished wardrobe fit
- explicit hashed manifest, license-free private source-art notes,
  installer, check, stage, verify, preview, and rollback CMD scripts

## On Venus

Extract the ZIP into a fresh directory, then run:

```text
Check-Batch12_13.cmd
Stage-Batch12_13.cmd
Verify-Batch12_13.cmd
Preview-Batch12_13.cmd
```

The installer uses `$PSScriptRoot`, no trailing-slash path parameter,
SHA256 verification and a temporary directory for atomic staging.
Existing targets cause a refusal instead of overwrite. The optional
`Rollback-Batch12_13.cmd` moves only the specific review-stage folder
to a timestamped backup. No changes are made to original `CoreLayers`,
canonical body, `Public-V2`, `sofia.db`, owner permissions or watchdog.

Destination:

```text
%LOCALAPPDATA%\SofiaAdaLyra\Avatar2D\Private-Source\Reviewed-Candidates\Batch12_13_MouthsVisemes-v1
```

After `git pull --ff-only`, verify exact staged art and dependency hashes:

```powershell
$R = Join-Path $env:LOCALAPPDATA 'SofiaAdaLyra\Avatar2D\Private-Source\Reviewed-Candidates'
$B09 = Join-Path $R 'Batch09-ModularFoundation-v3'
$B1011 = Join-Path $R 'Batch10_11_IndependentEyesBrows-v1'
$B1213 = Join-Path $R 'Batch12_13_MouthsVisemes-v1'

python -m sofia.avatar.vtuber_mouth_viseme_review --root "$B1213" --foundation-root "$B09" --features-root "$B1011"
pytest -q test/test_avatar2d_mouth_viseme_review.py test/test_avatar2d_review_player.py
```

### Actually **watch** the separated layers animate

The new `vtuber_review_player.py` is an independently launched, local
Tk owner-review window, not Sofía's production UI. It verifies installed
packages, draws real independent eyes/brows/mouth frames, supports
Play/Pause/Previous/Next and cached animation frames:

```powershell
python -m sofia.avatar.vtuber_review_player --foundation-root "$B09" --features-root "$B1011" --mouths-root "$B1213"
```

No real speech-output receipts are connected. This is intentional:
**frame swapping** is demonstrated; authentic audio-driven lip sync,
mouth timings, gesture cancellations and production live acceptance
are still open.

To emit twelve full-canvas static review frames in a new private review
folder without opening Tk:

```powershell
$Frames = Join-Path $R 'ReviewFrames-12_13-v1'
python -m sofia.avatar.vtuber_mouth_viseme_review --root "$B1213" --foundation-root "$B09" --features-root "$B1011" --frames-output "$Frames"
```

The output folder must not already exist.

## Evidence and next gates

**Proven locally for package:** all 22 packaged files match hashes; ZIP
passes CRC; twelve RGBA images are distinct and inside the mouth-slot
bounds; pinned Batch 09 and 10/11 dependencies match the packaged
originals; preview GIF has eight frames. This is *not* a claim of a
successful Windows installation.

**Code on `main`:**
- `src/sofia/avatar/vtuber_mouth_viseme_review.py` (hashes, alpha zone,
  dependency pinning, fixed frame selections, offline proof generator)
- `src/sofia/avatar/vtuber_review_player.py` (real local Tk frame swaps
  with cache)
- `test/test_avatar2d_mouth_viseme_review.py` and
  `test/test_avatar2d_review_player.py` (regressions, semantic
  wrong-art rejection and no false production/voice claims)

The newly committed regression tests and Windows launcher have **not
been run on Venus or exact `main` in this session**, so their
final execution status is unresolved.

**Remaining before the existing public `TkLayered2DRenderer` can use
this artwork:** 1) owner-reviewed facial fit and real hair front/back,
2) both fox ears with independently authored stable anchors, 3) seven
tail states with stable tail root / clothing occlusion, 4) complete
320×400 compatible verified public character pack and approved public
outfit manifest, 5) switch with safe rollback and test frame receipts
on actual Venus desktop, 6) optional authenticated speech playback
timing, 7) wardrobe refit of the original catalog. Private source
art **must never** be loaded directly by public rendering code.
