# PKG-AVATAR · Offline wardrobe and virtual-object review

**Status:** isolated headless domain code on `feature/pkg-avatar-offline-wardrobe-scene`; no base mesh, garment artwork, renderer, physical touch, deployment or completed avatar package. This is AVATAR, not the Discord/NET package. Review alongside draft AVATAR design PR #4 and current INTERACT PR #2 before integration.

## Offline code prepared

- `src/sofia/avatar/wardrobe.py`: metadata-only underwear/base/mid/outer/accessory layers, collision by layer/slot, fox-ear and tail clearance and covered default appearance. Public/default readiness checks coverage, declared asset refs and a trusted host-supplied renderer verification flag; metadata **does not** verify asset existence or coverage on a real moving mesh. Restricted previews default-denied and need independently established adult, owner, private-local-session, opt-in and no-stop facts.
- `src/sofia/avatar/scene.py`: headless virtual props with separate propose and trusted acknowledgment steps, holder/offer transitions, accept/decline/cancel/stop, optimistic revisions, operation replay rejection and validated snapshots. Tests use simulated receipt booleans; the module cannot authenticate an actor or verify real rendering by itself.
- `test/test_avatar_wardrobe_metadata.py` and `test/test_avatar_scene.py`: isolated positive, invalid, blocked, concurrent and recovery fixtures.

**Verification:** staged equivalent UI + AVATAR source ran in a separate Python 3.13.5 / pytest 9.0.2 workspace with `PYTHONPATH=src`: **96 passed** across three test files; AVATAR accounts for 58 of these. This is not GitHub CI, not a Windows repo-wide run, and not live renderer acceptance. GitHub blob hashes for `wardrobe.py` and `scene.py` matched the staged tested sources. Run `python -m pytest -q test/test_avatar_wardrobe_metadata.py test/test_avatar_scene.py` on this branch and record its revision before integration.

## Deferred package review and evidence required

1. Pin canonical `src/sofia/data/avatar.json` and approved anatomy/measurements. Produce a licensed, reviewable adult base mesh/rig with mapped anatomical regions and a properly dressed default. No change to her canonical appearance, protected identity or Constitution without separate authorization.
2. Author and validate actual garments from underwear to outerwear including real geometry, texture, ear/tail openings, coverage under pose/deformation, occlusion, license/provenance and safe fallback. A metadata `asset_ref` or `assets_verified_by_renderer=True` in untrusted input is never adequate evidence.
3. Select and implement an actual isolated renderer and trusted input/ack adapter. Verify authenticated Sparks vs Sofía actor, operation ID, scene/asset revision, renderer origin, result and timestamp *outside LLM output*. Cross-check against INTERACT event semantics and SAFE consent/stop. No click-through, duplicate motion or fabricated completed handoff.
4. Add authorized persistent per-scene storage, resource/VRAM limits, snapshot versioning/migrations, resume and rollback, outfit presets and durable object inventory using MEM/SAFE privacy. Test crash while operation pending, late acknowledgment after cancel, viewport disconnect and stop.
5. Reconcile package roadmap owner and dependency: AVATAR provides assets/scene, UI renders, INTERACT parses/actions, MEM stores, SAFE enforces, ACT/REL propose expression. Avatar remains optional for chat; Discord D0–D4 and 24/7 RUN do not wait for art. No unrestricted internet/search or physical robot/desktop control comes from virtual objects.
6. Before broader audiences, test restricted-view leakage through thumbnails, logs, screenshots, cache, notification previews and other client sessions; general multi-user is explicitly deferred while Sofía serves Sparks only.

**Not run:** source checkout tests on Windows 3.12.9, coordinated INTERACT/application/full pytest, actual base/clothes/renderer visual inspection, live click/gesture/hand-off acknowledgments, GPU/CPU profiling, real restart recovery and production privacy assessment. Rollback is to omit/revert only the new avatar modules/tests/docs; do not touch production `state/sofia.db` or protected files.
