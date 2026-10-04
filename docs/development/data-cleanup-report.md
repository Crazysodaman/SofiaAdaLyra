# Phase 6: data asset cleanup

## What was there / what it does

Two JSON assets, no Python functions/classes/imports. Original Git blobs: avatar.json `50b32d0723a2eb9eb59b5075af514070d4931f6c`; identity.json `5dd46845b92495885ad6ccf5ee44b9292cf0dd5b`. Avatar asset keys include subject, physical_self, appearance, clothing, available/current representation metadata; it is the canonical embodiment design baseline, not mutable live presentation. The identity asset contains name and a UUID different from the protected identity seed.

## File decisions

| File | Decision | Evidence |
|---|---|---|
| `avatar.json` | MOVE | RuntimeStorageLayout.provision seeds configured embodiment design from this asset; EmbodimentStore and runtime/test fixtures load it. Move unchanged to embodiment/avatar.json, beside its design owner. |
| `identity.json` | DELETE | No source/test provisioning or import path reads this duplicate UUID. Canonical protected provisioning uses identity/identity.json, which remains unchanged. |

## What was wrong / merged / deleted / renamed or moved

Data was an ownerless asset folder with an active embodiment baseline and an unused second identity. Moved the baseline to embodiment/avatar.json. Deleted the unused duplicate identity and retired the now-empty folder. No merge or content rewrite occurred.

## What I fixed

Repaired storage provisioning, all source/test baseline paths, and current artist/wardrobe documentation. Development change-review protection now targets the relocated avatar asset; its model source continues to require ordinary independent review. Added a regression proving the moved baseline remains blocked as protected while the neighboring implementation remains reviewable. Production protected identity and configured runtime-state paths are unchanged.

## What remains

Identity baseline belongs to identity, embodiment design belongs to embodiment, and live wardrobe/presentation belongs to avatar state. Asset relocation does not alter anatomy, measurements, appearance, wardrobe specification, UUID or mutable runtime presentation.

Baseline byte preservation: original and relocated avatar SHA-256 both `8b499cb73e32ca217503131b8c55857765b99c9ddc60ae42a5a8b38f605fff29`.

## Tests / checkpoint

Compile, diff and retired-path searches passed. Avatar/embodiment, environment, composition/matrix, development review and desktop application/worker gate: **504 passed**. Final full suite: **3470 passed, 8 failed, 2 skipped** (113.04s). Five failures require unavailable Ollama; three existing platform-assumption failures remain in filesystem/config/UI. Compile and dependency checks passed; no new failure remains.

Checkpoint: `git log -1 --format=%H -- docs/development/data-cleanup-report.md` identifies the containing commit.
