# PKG-AVATAR | A0 importable, dressed GLB previews

**2026-09-21. Draft PR #7 only.** This milestone adds `tools/avatar/export_stylized_blockouts.py` and `test/test_avatar_stylized_export.py` on the **existing AVATAR branch**, independent of INTERACT. It does not change protected avatar JSON, identity, Constitution, `state/sofia.db`, runtime dependencies, network permissions, renderer, or production installation.

## Delivered and evidence

- Pure offline Python art-authoring script requiring **optional** `trimesh` and `numpy`, with no `bpy` dependency. It reads the existing `src/sofia/data/avatar.json` **without changing it**, validates expected canonical subject/fox features and known crimson-hair, warm-ivory-skin and teal accent fields; any deviation requires review, not an automatic canonical edit.
- Generates **two separate, clothed GLB model previews** (`sofia_a0_engineer.glb`, `sofia_a0_lounge.glb`). Both have named modular mesh pieces for face/hair, two ears, tail, top, trousers, boots and hands. Engineer includes a jacket, gauntlets, utility belt and pouch; lounge uses lighter T-shirt/sweatpants proxies. These are deliberately coarse visual meshes, not final anatomy, fitted clothing or animation.
- Beside each GLB writes a JSON **authoring/evidence manifest** with SHA-256 of the exact input canonical JSON and output GLB, variant, node-to-authoring-slot names, provisional anchor coordinates, review flags and explicit `not_verified` items. A text `asset_ref`, an asset hash or GLB import does **not** prove that an actual runtime renderer accepted the mesh or that the avatar is displayed.
- Refuses unknown/unclothed variants, changed canonical color fields, nonexistent/symlink output directories and existing output paths. It never overwrites a previous preview. The tested fixture produces two actual GLBs, round-tripped with `trimesh.load(..., force="scene")`, and **10 focused offline tests passed on Linux Python 3.13.5 with trimesh 4.11.1**. The GitHub-branch checkout, Windows Python 3.12.9 and **Blender GUI/import** have not yet been run. Existing AVATAR/INTERACT results are separate historical evidence; do not add test totals across revisions.

## Generate from Sofía's actual canonical data on Windows

In the repository checkout on the AVATAR branch, use a **separate optional art virtual environment** to avoid changing the Sofía runtime dependencies. Make a **new, empty** output directory outside protected state. Example PowerShell commands, from the repository root:

```powershell
py -3.12 -m venv .venv-avatar
.\.venv-avatar\Scripts\python.exe -m pip install "trimesh>=4,<5" "numpy>=1.26,<3" pytest
New-Item -ItemType Directory -Path .\avatar-a0-review -ErrorAction Stop
.\.venv-avatar\Scripts\python.exe tools/avatar/export_stylized_blockouts.py --canon src/sofia/data/avatar.json --output-dir .\avatar-a0-review
.\.venv-avatar\Scripts\python.exe -m pytest -q test/test_avatar_stylized_export.py
```

Generated artifacts in `avatar-a0-review` are **unreviewed**, not a production asset or an approved Git commit; never put credentials, conversations or a production DB there. Use another empty directory for subsequent runs because output paths cannot be overwritten.

## Inspect in Blender

1. In Blender choose **File > Import > glTF 2.0 (.glb/.gltf)**; import `sofia_a0_engineer.glb` from the generated output. Inspect *front, side and back*, face/ear/tail placement, silhouette, clothing, proportions and mesh naming in the Outliner. Check the JSON manifest GLB hash against the actual binary before accepting any art review.
2. Import `sofia_a0_lounge.glb` into a **separate Blender scene**, or hide one variant's mesh objects when comparing. Imported nodes are geometry proxies, not a skin-weighted outfit switch, physics, canonical anatomy/hit-testing or autonomous clothing changes.
3. Optionally save new `.blend` projects using **Save As** after visually inspecting. No `.blend` was produced or tested in this environment. Do not replace an existing scene or silently authorize private preview/export.

## Decisions and next real implementation gates

**A0 review:** compare the generated *real-canonical* export with the approved reference concept; check face style, adult presentation, anatomical proportions, heights/units, hair, ear/tail shape, handedness, node mapping and garment colors against the actual canonical JSON. Choose a Blender version, reusable A1 topology/rig plan and runtime render format. Decide licensed textures/material sources and which art may be published. No automatic avatar changes to make a test fixture appear canonical.

**A1/A2:** author one approved reusable base and skeleton with facial/ear/tail controls, apply actual weights, design/fitting of engineer and lounge layers, deformation, asymmetrical gauntlets, ear/tail clearance and covered default/fallback. Validate occlusion, clipping, textures, accessibility and GPU budget on actual hardware. **A3:** use independent SAFE/INTERACT/UI authorization and real renderer acknowledgments before recording any outfit as worn; disable nude/private visuals on unknown audiences and through thumbnails, caches and streams. Optional future Sofía-designed garments begin with approved manifests and supervised sandboxed Blender drafts, never unrestricted generated Python.

**Release status:** export generator and standalone unit tests prepared; fixture GLBs inspected structurally only; actual canonical GLBs, Blender execution/inspection, final art, rigging, Windows/full-suite tests and real avatar acceptance **NOT RUN**. No merge or deployment.
