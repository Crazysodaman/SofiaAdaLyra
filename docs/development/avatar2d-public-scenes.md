# Sofía 2D scenes: public-only compositing, editor, verified wardrobe

**Branch:** main; **production database:** unchanged. The 2D scene editor is
an explicit owner-operated UI, not an autonomous screen or image editor.

## Phase A: compose full outfits over backgrounds

- `scene_compositor.py` renders a SHA-256 verified, source-bound public
  320x400 outfit portrait onto an independently imported public background.
- Exports a PNG with adjustable placement, scale, crop (cover/contain), blur,
  dimming and alpha shadow. Aspect ratios are preserved.
- The result is **static**. A gesture or blinking state cannot claim to have
  animated a flattened character; the existing modular renderer handles
  animated older artwork only where authored sprites exist.
- No filenames are inferred from descriptions, and private outfits cannot
  be rendered through the public compositor.

## Phase B: editable scenes and reusable settings

- `python -m sofia.avatar.scene_editor --outfit outfit.autumn_cyber` opens the
  Tk editor with sliders, background import, previews, explicit save and export.
- In the live Windows desktop, click **Scene…** when a public outfit is active.
- Backgrounds import as normalized RGBA PNGs with SHA-256 manifests under
  `Public-V2/scenes/backgrounds/<id>/`.
- One public-scene JSON preset per outfit lives under
  `Public-V2/scenes/presets/<outfit_id>.json`, retaining exact canonical
  garment IDs. The live 2D renderer reads it on the next presentation update
  or restart. The editor refuses silent overwrite and the main desktop does
  not write to `sofia.db` to save art.
- You can export offline, without starting the desktop, with:
  `python -m sofia.avatar.scene_editor --outfit outfit.autumn_cyber --export "C:\\Users\\Public\\Pictures\\sofia-scene.png"`.

## Phase C: wardrobe layering

- A complete illustrated portrait takes priority if present and verified.
- If there is no illustrated portrait, existing **real, validated** modular
  public wardrobe layers are assembled through the authoritative
  `vtuber_layer_stack` and `wardrobe_matrix` contracts, including optional
  independent face, eye, hair, ear and tail PNG layers.
- Private art is excluded. Fitted garments need correct coverage, assets and
  geometry; the 9 high-res unfitted garment drafts are NOT automatically
  turned into interchangeable live layers.
- Dynamic outfit variants not matching a trusted preset remain unavailable,
  not falsely presented with someone else's garment image.

## One-time Autumn Cyber scene installation on Venus

First download the separate archive
`sofia2d_scene_autumn_cyber_v1.zip` from the ChatGPT attachment. The earlier
`sofia2d_public_illustrated_candidates_v1.zip` remains installed.

From the Sofia checkout on main, in PowerShell:

```powershell
git pull --ff-only origin main
.\scripts\install_public_autumn_scene.ps1 -Archive 'E:\Downloads\sofia2d_scene_autumn_cyber_v1.zip' -PublishToGit
python -m sofia
```

The script checks the known complete ZIP digest and verifies the internal
public outfit/garments, portrait hash, independent background hash and
scene composition **before** adding the files under
`%LOCALAPPDATA%\SofiaAdaLyra\Avatar2D\Public-V2`. It refuses overwrite
and touches no private assets or production state.

The optional `-PublishToGit` copies the same binary asset ZIP into
`assets/avatar2d/scenes/public_autumn_v1/`, commits it to `main`, and pushes
using the owner's Git credentials. Omit the switch for local-only installation.
Code commits alone do not imply that the binary archive exists on GitHub.

Autumn Cyber's approved public garment list is:

- `under.upper.wireless_contour`
- `under.lower.hipster`
- `top.fitted_technical_sweater`
- `bottom.black_stretch_jeans`
- `outer.black_leather_jacket`
- `foot.violet_ankle_boots`

The supplied portrait/background pair is an **unreviewed visual candidate**,
not a verified faithful illustration of every seam. It is full-body static
character art over a separate stylized autumn-neon background, both reusable.
Existing wardrobe authority determines which outfit may be shown.

## Test and acceptance limits

Run `pytest -q test/test_avatar2d_scene_compositor.py
test/test_avatar2d_scene_install.py` for scene unit/integration coverage.
The existing Windows avatar2d CI workflow also includes these tests. Real
Venus screenshot acceptance, per-item visual fidelity, fully interchangeable
high-quality clothing for the 244 public JSON garments, and animated
illustrated expressions remain independent open work. No Gate-4 evidence is
asserted for those unfinished art tasks.
