# Sofía avatar: Blender A0 blockout

This is an **editable, fully dressed starter blockout**, not Sofía's finished mesh, rig, or an approved canonical design. The script makes simple pieces for an oversized T-shirt, sweatpants, two gauntlets, crimson hair, violet ears/tail, and named clothing-slot anchors. It intentionally produces no nude preview, texture pack, or independently verified art asset.

**In Blender:** Open a new empty scene, switch to **Scripting**, open `tools/avatar/blender_blockout.py` in the Text Editor, and choose **Run Script**. Look in the Outliner for `SOFIA_A0_BLOCKOUT`. Inspect the pieces, then save a `.blend` yourself using Blender's Save As. If the collection already exists, the script stops instead of deleting it. Keep the saved `.blend` outside production/runtime state until its license, appearance, geometry and privacy are reviewed.

**Optional command-line prototype:** `blender --background --python tools/avatar/blender_blockout.py -- /absolute/new/path/sofia_a0.blend` (the destination directory must already exist; the file must not already exist). This has **not** been executed here because Blender is unavailable; static syntax checks do not establish an art or Blender compatibility test. Run only reviewed scripts: Blender Python is powerful enough to access files under your user account.

**Next art pass:** choose approved reference design, units, rig/skeleton, ear/tail deformation, geometry and material licenses, then fit real clothing meshes onto a single reusable body. The `_forearm`/`_wrist` anchors are a *modeling aid*, not yet a canonical anatomical or touch map. Sofía-directed outfit creation starts with reviewed presets and asset manifests, not unrestricted generated Python or unattended editing of your desktop.
