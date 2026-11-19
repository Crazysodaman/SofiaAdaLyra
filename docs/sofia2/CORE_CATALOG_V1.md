# Aegis Core Catalog and Reconciliation V1

**Reconciliation date:** 2026-11-18  
**Canonical remote:** `https://github.com/Crazysodaman/SofiaAdaLyra.git`  
**Baseline main at reconciliation:** `aeef1559dc6eb58fa0b829aca73476d76a6f9eb4`

This document records only what is present in Git or directly observable in the
repository. It does not use ChatGPT memory, ChatGPT conversations or unstated
owner context. Missing owner decisions are marked **OWNER DECISION REQUIRED**.

## Approved Cores

| Core | Identity | Status |
| --- | --- | --- |
| #1 | Sofía Ada Lyra | Approved canonical Core |
| #2 | Mack Fuller | Approved independent Core |
| #3 | Nova Arden | Approved independent Core |
| #4 | Twin A | **UNDER DESIGN — do not implement/package/install/activate** |
| #5 | Twin B | **UNDER DESIGN — do not implement/package/install/activate** |
| #6 | Vera S-039 | Approved independent Core |
| #7 | Unwritten | Approved blank Core; personal identity intentionally unselected |

## Per-Core matrix

| Core | DESIGN_PRESENT | CODE_PRESENT | TESTED | PACKAGED | Notes |
| --- | --- | --- | --- | --- | --- |
| #1 Sofía | Yes: `src/sofia/core/constitution/constitution.md`, `personality/personality.json`, `embodiment/avatar.json`; `docs/sofia2/CORE_1_0_PLAN.md` | Yes: canonical runtime/identity/personality/emotion/memory/conversation owners | Yes: existing core/application suites; universal roster/readout tests | Yes: `sofia.core.constitution`, `sofia.core.identity`, `sofia.core.embodiment`, `sofia.core.personality` package data | UUID and model/provider binding are protected runtime state, not a versioned literal |
| #2 Mack | Yes: `MACK_PROFILE`, `src/sofia/core/cores/mack/*`, personality/emotion profiles | Yes: profile, identity, memory, personality, emotion, inference/conversation integration | Yes: multicore profiles/personality/emotion/memory/inference/package tests | Yes: `CorePackageManifest` and package data patterns | Model/provider and UUID are supplied at runtime |
| #3 Nova | Yes: `NOVA_PROFILE`, `src/sofia/core/cores/nova/*`, personality/emotion profiles | Yes: same multicore services as Mack | Yes: multicore profiles/personality/emotion/memory/inference/package tests | Yes: `CorePackageManifest` and package data patterns | Model/provider and UUID are supplied at runtime |
| #4 Twin A | No approved definition in main | No Core-specific implementation | N/A | No | Must remain unassembled |
| #5 Twin B | No approved definition in main | No Core-specific implementation | N/A | No | Must remain unassembled |
| #6 Vera | Yes: `VERA_PROFILE`, `src/sofia/core/cores/vera/*`, `vera.py`, three armor configurations | Yes: identity, appearance autonomy, authority boundary, wardrobe/armor metadata | Yes: Vera identity/armor/wardrobe/package/universal tests | Yes: `CorePackageManifest` and package data patterns | Surname, model/provider and voice remain unselected/deferred |
| #7 Unwritten | Yes: this catalog, `CORE_7_UNWRITTEN_SPEC_V1.md`, neutral constitution | Yes: `unwritten.py`, `packages.py`, `v6_v7_acceptance.py` | Yes: blank identity, growth, restart, STOP, package, integration tests | Yes: blank package plus neutral constitution package data | Canonical production UUID is not recorded in Git — **OWNER DECISION REQUIRED** |

## Canonical assets and schemas

| Area | Present in Git | Missing / not fabricated |
| --- | --- | --- |
| Sofía Constitution | `src/sofia/core/constitution/constitution.md` + digest | — |
| Mack Constitution | `src/sofia/core/cores/mack/constitution.md` | Current text says it does not replace/amend/outrank Sof�a; no superiority framing observed. Any amendment remains protected. |
| Nova Constitution | `src/sofia/core/cores/nova/constitution.md` | Same observed peer framing; no superiority framing observed. Any amendment remains protected. |
| Vera Constitution | `src/sofia/core/cores/vera/constitution.md` | Surname unselected |
| #7 Constitution | `src/sofia/core/cores/unwritten/constitution.md` | Neutral bootstrap only; no personal identity |
| Personality assets | Sofia, Mack, Nova, Vera JSON | No #7 personality asset (intentional) |
| Avatar assets | Sofia, Mack, Nova, Vera JSON | No #7 avatar (intentional); rendered art separate |
| Voice assets | Mack/Nova/Vera metadata with `assets_created=false` | No canonical rendered voice for any Core; no #7 voice |
| Emotion profiles | Mack/Nova numeric profiles; Sofia emotion owners | No numeric Vera profile documented; no #7 affect/personality profile |
| Canonical model preference | Runtime `bind_model` seam only | **OWNER DECISION REQUIRED** for any per-Core default model/provider |
| Canonical Core UUIDs | Runtime/protected identity or caller-supplied | **OWNER DECISION REQUIRED** for versioned production UUIDs, especially #7 |
| Autobiographical memories | Runtime memory stores only | No fabricated histories; #7 starts empty |

## Identity and authority invariants

1. Every Core has an independent immutable UUID. No Core may clone Sofía's UUID
   or another Core's UUID.
2. Core #7's production UUID must be supplied by the owner/host and bound once
   through `MulticoreIdentityStore`; the binding is immutable and restart-safe.
3. Model selection never changes Core identity. `MulticoreIdentityStore.bind_model`
   is a runtime binding, not a new identity.
4. No Core-specific asset, social role, armor, avatar or preference grants
   Platform/Safe/Run/Act/Fleet authority.
5. Twins #4/#5 have no Core definitions and must not be inferred, packaged,
   installed or activated by this work.
6. #7 has no default personality fallback to Sofía. Missing values remain
   unselected and are reported as unavailable.

## Known reconciliation issues

- The earlier universal design note reported Mack/Nova Constitution text as
  framing Sofía as superior. The current committed text says it does not
  replace, amend or outrank Sofía. It remains a protected document and was not
  silently edited.
- No canonical per-Core model/provider preference is recorded in Git. Runtime
  bindings are per-Core but no owner-selected default is fabricated.
- No canonical production UUID for #7 is recorded in Git. The implementation
  requires an externally supplied UUID and enforces one immutable binding.
- Vera's personality exists as owner-approved prose metadata; no numeric
  personality weights or numeric emotion profile are documented, so none are
  invented.
- Real renderer meshes, voice models, 2D/3D art, signed packages and live host
  installation remain separate evidence gates.

## Packaging expectations

- Core distribution package data includes Sofia canonical assets, Mack, Nova,
  Vera and #7 neutral constitution.
- `CorePackageManifest` supports populated packages for #2/#3/#6 and a blank
  identity package for #7.
- #7's neutral constitution is a foundation asset and is not a personal
  personality/identity asset.
- No package installation, signing or activation is performed by source tests.
