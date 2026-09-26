> **Project status update — 2026-09-23:** PKG-INTERACT was accepted by Sparks and merged to `main` via PR #2 (merge commit `d6658d0`). Verified Windows evidence includes 97 focused tests, a four-turn disposable real-application/Qwen probe, a qualified repository run of **1665 passed, 2 skipped, 1 deselected** (the deselected case was Sparks's unrelated local Ollama expectation mismatch), and a final **60/60** closure audit including both SQLite writer orders, source attestation, boundary revocation, restart-persistent state, stop behavior, authentication and tool authority. Staged offers remain off by default; production interaction-policy schema provisioning is a separate reviewed migration. **Next dependency gate: PKG-MEM.**

# Sofía Ada Lyra: PKG-AVATAR delivery roadmap

**Reconciled 2026-09-25. Status:** AVATAR remains an unmerged package candidate in stale draft PR #7; rebuild it from current `main` rather than merging the old branch directly. The authoritative project roster is now the **20-package** [ROADMAP.md](ROADMAP.md). AVATAR remains package 11; PKG-ENVIRONMENT is package 20, UI owns presentation/transport, and INTERACT owns interaction semantics. Current presentation direction includes mutable wardrobe, hairstyle, hair color and tail color; emotion may influence presentation but must not control it or override established preferences, privacy, renderer truthfulness or authority.

## Ownership boundary

**AVATAR owns:** canonical virtual-body art assets, mesh/topology, rig, hair/face/eyes/ears/tail representation, clothing assets and layering, fit anchors, region-compatible geometry, virtual props/scenes, authoring/export pipeline, and renderer-ready animation assets.

**INTERACT owns:** canonical interaction events, text/avatar input semantics, boundaries/consent, contextual reaction coordination, and lab behavior.

**UI owns:** actual client rendering, transport, input routing, accessibility, and acknowledged playback.

**BODY owns:** real sensors, motors, and physical embodiment.

**ENVIRONMENT owns:** authoritative shared time/timezone/location/season/daylight/weather/ambient evidence, freshness and provenance. AVATAR consumes that evidence; it does not fetch or infer current weather/location itself.

No avatar event proves physical sensation, and no virtual interaction grants Gaia authority.

## Current candidate state

Draft PR #7 contains substantial offline body/wardrobe/scene/tooling work, including:
- wardrobe metadata and routines,
- fine clothing/body slots,
- modeled preference metadata,
- virtual scenes/props,
- dressed GLB/blockout tooling,
- canonical body/fit contracts,
- a measured proxy/export workflow.

Its reported tests are **isolated revision-specific evidence**, not one integrated release suite. Finished canonical art, production rig, live renderer, authenticated animation receipts, and whole-system acceptance remain open.

## Stage map

| Stage | Delivery | Current boundary |
| --- | --- | --- |
| **A0 · Canon/asset architecture** | Audit canonical appearance/measurements, editable pipeline, licenses, region/fit mapping | Candidate metadata/tooling exists; actual reviewed production asset pipeline still open |
| **A1 · Canonical adult modeling base** | Complete adult art mesh, face/hair/eyes/ears/tail, rig-ready topology, stable regions/anchors | Measured proxy/contracts exist; finished production model and rig are not accepted |
| **A2 · Full layered wardrobe** | Canonical engineer outfit plus reviewed additional garments, layering, tail/ear fit, presets/undo, and optional environment-aware presentation policy | Metadata/routines exist; real fitted assets, clipping/motion/coverage review and PKG-ENVIRONMENT integration remain |
| **A3 · Renderer/animation** | Face/eyes/ears/tail/hands/posture, clothes behavior, input hit tests, trusted animation receipts | Not live accepted |
| **A4 · Shared interactive scene** | Versioned virtual objects/desk/props, offer/accept/decline, persistent scene state | Headless candidates exist; production persistence/renderer integration remain |
| **A5 · Expansion/polish** | More garments/props, accessibility, LOD/GPU caps, vetted imports, reviewed authoring | Future reviewed expansion |

## Privacy and representation

The underlying adult modeling base exists for clothing fit/rigging and is not a default public display mode. Unknown/public audiences default to an appropriate covered representation. Restricted previews require independently verified audience/session policy and must not leak through thumbnails, caches, streams, or shared workbench objects.

Wardrobe or avatar output may influence **represented** comfort/confidence/embarrassment/excitement cues when supported by context, but never proves subjective bodily sensation.

## Sequence

- A0/A1/A2 offline asset work may continue. INTERACT is now merged; the active dependency chain is MEM → SOCIAL minimum → Discord → OPS/RUN.
- Text/headless INTERACT must remain functional without AVATAR.
- A3/A4 now have the accepted INTERACT foundation, but still require UI + SAFE + MEM boundaries and real renderer acknowledgements.
- Wardrobe consumes only PKG-ENVIRONMENT snapshots. ENVIRONMENT can provide offline time/location/timezone/season/daylight and may accept trusted local Home Assistant observations through INTEGRATE; AVATAR never fetches weather itself. Direct internet weather/geocoding remains unavailable until separately authorized NET/web access.
- Real-world prop/device actions require separate BODY/NET/SAFE authorization.

## Review decisions still open

Renderer/2D-vs-3D stack, canonical fine geometry, licensed art sources, Blender/runtime versions, rig/physics fidelity, private-preview UX, garment catalogue, scene persistence, GPU budget, import provenance, environment-aware wardrobe policy/override behavior, and exactly who may access restricted representations.

No protected identity/Constitution change, production DB mutation, package merge, or deployment is implied by AVATAR documentation.
