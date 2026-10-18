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


## Batch 14 groundwork: reproducible approved hair/ear placement

The approved Batch 06 hair and Batch 07 fox-ear assets were originally
created on differing effective subject sizes, even though source package
frames are fixed. A new **review-only** head+hair/ears compositor was
added to `src/sofia/avatar/vtuber_hair_ear_review.py` and a geometry
regression test to `test/test_avatar2d_hair_ear_review.py`.

It checks the exact SHA256 values of four original user-approved source
layers (`hair_back_main.png`, `hair_front_bangs.png`,
`ear_pose_01.png`, `ear_pose_06.png`) rather than trusting a filename.
It checks Batch 09, Batch 10/11 and Batch 12/13 dependencies before
constructing a composite. The canonical body is drawn **over** back
hair, preventing the fading collarbone/neck seam observed when only
the cropped head artwork was used.

**Review-only anchors (x, y, width, height on 2048×2560):**
- back hair `(800, 0, 440, 610)`
- front bangs `(900, 14, 218, 258)`
- left-ear candidate `(827, 0, 123, 170)`
- right-ear candidate `(1070, 0, 123, 170)`

Generate the comparison on Venus (choose an unused new output directory):

```powershell
$P = Join-Path $env:LOCALAPPDATA 'SofiaAdaLyra\Avatar2D\Private-Source'
$R = Join-Path $P 'Reviewed-Candidates'
$Dest = Join-Path $P 'Review\HairEarsCandidate-v1'
python -m sofia.avatar.vtuber_hair_ear_review --source-root (Join-Path $P 'CoreLayers\v1') --foundation-root (Join-Path $R 'Batch09-ModularFoundation-v3') --features-root (Join-Path $R 'Batch10_11_IndependentEyesBrows-v1') --mouths-root (Join-Path $R 'Batch12_13_MouthsVisemes-v1') --canonical-body (Join-Path $P 'CanonicalBody\v1\sofia_body_base_2048x2560.png') --output "$Dest"
Start-Process (Join-Path $Dest 'hair_ear_alignment_candidate.png')
pytest -q test/test_avatar2d_hair_ear_review.py
```

**NOT YET APPROVED:** left/right ear assignment, alternate hair styles,
hair root/strands, garment and tail occlusion. No body artwork, source
sprite or public runtime is modified.


## 2026-10-17 Venus visual proof and optional full-character preview

The owner supplied three real screenshots of the Tk owner-review player
showing a changing open mouth and closed/neutral mouth on a head with
independently authored eyes and brows. This **confirms the player is running
and facial sprite switching is visible on Venus**, but it is not proof of
audio-synchronized speaking or Sofía's live desktop renderer. The screenshots
also expose blurred nose/cheek shading, rough head/neck contours, and
unfinished mouth/jaw style blending. Do not declare these art issues closed.

The base review player previously showed the **bald** head because it
intentionally composited only foundation, eyes, brows and mouth sprites.
Commit `243fdee3` added **optional approved hair + fox ears + canonical body**
to that SAME local review window without changing the live Tk renderer.

Generate the fuller review after `git pull --ff-only`:

```powershell
$P = Join-Path $env:LOCALAPPDATA 'SofiaAdaLyra\Avatar2D\Private-Source'
$R = Join-Path $P 'Reviewed-Candidates'
$B09 = Join-Path $R 'Batch09-ModularFoundation-v3'
$B1011 = Join-Path $R 'Batch10_11_IndependentEyesBrows-v1'
$B1213 = Join-Path $R 'Batch12_13_MouthsVisemes-v1'
$Source = Join-Path $P 'CoreLayers\v1'
$Body = Join-Path $P 'CanonicalBody\v1\sofia_body_base_2048x2560.png'

python -m sofia.avatar.vtuber_review_player `
  --foundation-root "$B09" `
  --features-root "$B1011" `
  --mouths-root "$B1213" `
  --source-root "$Source" `
  --canonical-body "$Body"
```

Both new arguments are optional **as a pair**. Omit both to retain the
previous bald-head troubleshooting view. Pinned SHA256 values for approved
back hair, front bangs and two selected ear poses are enforced. The Batch09
verifier also binds the selected full body to its exact previously approved
hash. Back hair is painted **behind** the canonical body, selected ears
above it, then facial frames and front bangs. The image is cropped for the
review window after assembly. Per-expression scaled images are cached to
avoid repeated full-size decoding on every 130ms blink.

Source art is never copied to `Public-V2` by this player. It is not a
release of a new rig, a completed nose/neck art pass, approved independent
ear poses, voice-triggered lip sync, or wardrobe fit. Next steps are
cleanup of nose/jaw/neck pixels and registered hair/ear/tail pose
acceptance, then public-safe 320×400 character pack compilation and
actual production tests.
