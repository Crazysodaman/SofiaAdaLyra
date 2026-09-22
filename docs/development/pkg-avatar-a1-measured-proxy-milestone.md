# PKG-AVATAR A1b-0 | Measurement-calibrated body authoring proxy

**2026-09-21 | draft PR #7 only | NOT a finished adult sculpt, Blender-verified asset, rig or renderer.** This milestone implements the measurement step in [A1 proportions plan](pkg-avatar-a1-proportions-measurement-plan.md) using `tools/avatar/measure_calibrated_body.py` and `test/test_avatar_measured_body.py`. `src/sofia/data/avatar.json` is read without modification; INTERACT, identity, Constitution, main, and production state are untouched.

## What the code actually creates

- An actual **20-part, modular GLB authoring-only proxy**, with a closed/winding-consistent *torso loft* built from the canonical **33-inch bust, 30-inch underbust, 26-inch waist and 37-inch hips**. The 67-inch standing human crown height is a reference in the head geometry; ears extend above it. Weight and the 30C clothing-fit label do not become geometric inferences.
- Real mesh-plane perimeter measurement with `trimesh.section`, **not bounding-box width**, at four explicit planes. A 0.5 mm tolerance applies to the torso circumference errors before export. The JSON manifest stores canonical input SHA-256, GLB SHA-256, the target/measured girths, plane heights, named objects, units/axes, artist estimates and unimplemented requirements. The actual export's torso was remeasured after GLB import in tests.
- Artist-estimated body lengths, ring heights, cross-section aspect ratios, limbs, head, ears and separate posterior tail pieces remain **unapproved blockout guides**. They are not additional canonical measurements and are not accurate or finalized anatomy. The authoring GLB does **not** implement the required detailed nipples, vulva or anus, merged topology, face sculpt, bones, skin weights, actual garment fit or any runtime visibility permission. A real anatomically complete adult female sculpt is still A1b work, not delivered by this proxy.

## Run in an actual AVATAR checkout

```powershell
python -m pip install numpy trimesh
New-Item -ItemType Directory -Path .\avatar-a1-output
python tools/avatar/measure_calibrated_body.py --canonical src/sofia/data/avatar.json --output-dir .\avatar-a1-output
pytest -q test/test_avatar_measured_body.py
```

Output: `sofia_a1_measured_body_proxy.glb` plus `sofia_a1_measured_body_proxy.json` in the explicitly created empty directory. The tool refuses to overwrite and denies symlink destination directories. Treat the GLB as a **controlled private modeling asset**, never the default renderer asset. No preview permissions are implemented by this tool. For Blender inspection: File → Import → glTF 2.0, select the GLB, then inspect frontal, side and rear silhouettes, foot-to-human-crown stature (ears excluded), torso planes, tail-root placement, transforms, mesh normals and whether a refined sculpt can reuse the envelope. Blender execution and any `.blend` save remain **NOT RUN** here.

## Evidence and limitations

- Isolated Linux/Python authoring environment with `numpy` and `trimesh 4.11.1`: **11 focused tests passed**, including reject-invalid-canonical, distinct circumference vs width, closed/winding-consistent loft, four real plane girths, crown/ear distinction, true GLB round trip, manifest SHA binding and fail-closed output paths. GitHub script blob `15e89bb9f0c486931cd408aad931289bc6478269` and test blob `0a287397cc3c7a86c180ef5f57d4b56a26effb07` matched the corresponding isolated tested sources. **NOT RUN**: pinned complete GitHub checkout, Windows, full project tests, Blender import/render, actual full canonical JSON export, advanced anatomy, clothing coverage or live renderer.
- A separate downloadable example ZIP is generated from a **minimal canonical-shaped test fixture with the same measurement values**, NOT from the repository's complete `avatar.json`. Its manifest identifies the fixture's own SHA. Do not present it as approved final Sofía art or as proof the full canonical JSON was exercised.
- Height/girth numbers prove only the calibrated *torso proxy*, not real-body accuracy, sex-specific anatomical completeness, garment opacity, clothing fit, real world weight or visual likeness. The torso's horizontal girths will change after individual breast modeling, shoulder/waist sculpting or mesh retopology: rerun surface measurements and visual review on the final sculpt. These authoring landmarks do not create touch targets or sensory evidence.

**Next gate:** run in the real checkout and inspect in Blender, then refine a continuous adult female body with the user's required external detail and approved reference, keeping the calibrated measurement planes verifiable. After silhouette approval, build the rig and fit independently verified clothes. Ordinary display remains clothed with a safe non-body fallback. No merge or deployment authorized.
