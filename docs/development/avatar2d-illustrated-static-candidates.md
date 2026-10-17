# Illustrated PUBLIC Sofía: static first, reviewed art later

**Status:** Working code and the reviewed public candidate archive are on
`main`. The archive is package-owned so source and installed-wheel runtimes
read the same bytes. These remain unreviewed image candidates, not fully
source-exact or independent garment rig layers.

## What the pack contains

The separately supplied `sofia2d_public_illustrated_candidates_v1.zip` contains:

- `portraits/<outfit_id>/portrait.png` + `manifest.json` for five public outfits:
  `day.default`, `night.lounge`, `outfit.violet_casual`,
  `outfit.rainy_engineer`, and `outfit.summer_violet`.
- Nine high-resolution garment candidate PNGs in `illustrated_drafts/`,
  indexed by canonical PUBLIC garment item ID, plus `sofia_base.png`.
- No protected/private designs or stored raw owner conversations.

Each static portrait is 320x400 transparent RGBA; its manifest stores
exact expected outfit and canonical item IDs plus a SHA-256 digest.
The renderer verifies the source-bound manifest and file bytes before
painting the picture. When a matching static portrait is present, it
replaces procedural art for that specific outfit only. Other outfits
retain the working modular/legacy renderer, and invalid art falls back
safely. Static art does not blink, talk, move ears or wag its tail;
never report a successful gesture from a single static picture.

## One-command installer (and optional Git asset publication)

The owner can download the separate ZIP from the ChatGPT artifact link and
place it in Downloads. In PowerShell from the Sofía checkout on **main**:

```powershell
git pull --ff-only origin main
.\scripts\install_illustrated_public2d.ps1 -Archive "$env:USERPROFILE\Downloads\sofia2d_public_illustrated_candidates_v1.zip" -PublishToGit
python -m sofia
```

The script checks the complete ZIP SHA-256, validates all five portrait
SHA-256 values, installs the public art without overwriting an existing
portrait directory, and (when `-PublishToGit` is set) copies the original
binary ZIP to `src/sofia/avatar/assets/`, commits and pushes
to `main` using the owner's normal authenticated Git client. Remove the
optional switch to install locally without publishing files. This is **not**
a remote push performed by CI/ChatGPT, and a real Venus visual acceptance
is still needed.

## Install on Venus without overwriting an existing reviewed pack

From the existing Sofía checkout with the repo updated to `main`,
using the usual Python environment:

```powershell
$Art = Join-Path $env:LOCALAPPDATA 'SofiaAdaLyra\Avatar2D\Public-V2'
$Zip = Join-Path $env:USERPROFILE 'Downloads\sofia2d_public_illustrated_candidates_v1.zip'

if (-not (Test-Path -LiteralPath $Art)) {
    python -m sofia.avatar.vtuber_public_setup --output "$Art" --all-public
}
if (Test-Path -LiteralPath (Join-Path $Art 'portraits')) {
    throw "An illustrated portrait pack already exists. Review or version it before replacement."
}
Expand-Archive -LiteralPath $Zip -DestinationPath $Art

python -m sofia
```

The desktop already discovers existing `Public-V2` installations on launch.
Choose 2D. The normal default public day outfit uses the illustrated
static portrait. Explicit `SOFIA_AVATAR2D_PUBLIC_ROOT` still wins.

Do not rerun the starter-art installer against this populated directory;
it intentionally refuses overwriting it. This workflow makes no
changes to the canonical `sofia.db`.

## If you want the actual binary assets committed into Git

The GitHub source integration does **not** upload PNG bytes by itself.
Copy the original ZIP into `src/sofia/avatar/assets/` via your Venus checkout,
then review the images and `git add`, `git commit`, `git push` on `main`.
Consider Git LFS for future large image revisions. CI cannot prove image
quality, visual fit, or original-source garment exactness from hashes alone.

## Remaining acceptance

- Visually fix shoulder, sleeve and collar fitting on each static portrait.
- Do not label the 9 high-resolution garments as mix-and-match ready:
  their transparent pixels/anchors are not yet a common modular rig.
- Check the intended canonical color/pattern, pocket/graphic placement,
  hem, sleeve, and hardware details against `wardrobe_data/*.json`.
- For changes in hair/body/outfit state that do not match static art,
  do not treat the art as a faithful dynamic representation.
- Do one supervised Venus screenshot/comparison at actual UI resolution.
- Full set of public wardrobe assets and expressive illustrated face,
  eye, ear and tail variants remain future work.
