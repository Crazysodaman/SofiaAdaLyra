# Sofía Pre-Multi-Core Preservation Audit

**Audit ID:** AEGIS-PHASE-A-PRESERVATION-2026-11-18
**Audit type:** Read-only Git forensic / preservation audit
**Worktree:** `C:\Users\kenny\AppData\Local\Temp\opencode\forensic-wt\audit`
**Branch:** `aegis/forensic-audit`
**HEAD:** `93d61a3fea58ad05e4d0bb611480b81a840c6128`
**Remote observed:** `https://github.com/Crazysodaman/SofiaAdaLyra.git`
**Lead baseline tag:** `aegis/core-audit-baseline-2026-11-18` -> `93d61a3fea58ad05e4d0bb611480b81a840c6128` (annotated tag)

**Evidence classes:** OBSERVED, INFERRED, UNKNOWN. Observations are limited to
Git objects and commands run in this worktree. No wheel, installer, service,
model provider, database, protected store or live host was touched. No tests
were executed because this audit was constrained to read-only Git inspection.
A green test suite is not claimed. Nothing in this document grants authority or
reverts multi-Core work.

---

## 1. Pre-multi-Core baseline determination

### 1.1 Candidate commits

| Candidate | Date (observed) | Role | Paths under `src/sofia/core/multicore`, `platform/chat`, `platform/social`, `platform/federation`, `core/cores` |
| --- | --- | --- | --- |
| `4a2d8b1f` | 2026-11-16 22:42 | Earlier mainline commit before `1914e5d0` | 0 / 0 / 0 / 0 / 0 |
| **`1914e5d0`** | 2026-11-17 16:57 | **Selected pre-multi-Core baseline** | **0 / 0 / 0 / 0 / 0** |
| `7c2f26f4` | 2026-11-17 17:02 | Branch merge: federation + shared social contract | 0 / 0 / 2 / 7 / 0 |
| `c2e8d308` | 2026-11-17 17:11 | Mainline merge: social/chat/inference/clients | 0 / 4 / 10 / 7 / 0 |
| `56668f00` | 2026-11-17 17:17 | Mentor evidence merge after social | 0 / 4 / 10 / 7 / 0 |
| `cc225f6f` | 2026-11-17 17:20 | First mainline multicore package | 2 / 4 / 10 / 7 / 0 |
| `c6c47dda` | 2026-11-17 18:21 | First mainline Core asset packages | 18 / 4 / 10 / 7 / 11 |
| `aeef1559` | 2026-11-18 17:58 | Docs/universal facade baseline used by later docs | 20 / 4 / 19 / 7 / 16 |
| `93d61a3f` | 2026-11-18 19:10 | Audit HEAD | 23 / 4 / 19 / 7 / 18 |

OBSERVED path counts were produced with `git ls-tree -r --name-only <rev> -- <path>`.

### 1.2 Selected baseline and justification

**Baseline: `1914e5d0e4204a8cdb5f97ea2be93923495dcfb0`.**

Evidence:

1. `git show -s --format='%H %P %s' 7c2f26f4` shows parents
   `1914e5d0e4204a8cdb5f97ea2be93923495dcfb0` and
   `71a9f4c6cd6be1b591662de488c14eb0fc93df69`. The first parent is `1914e5d0`.
2. `git show -s --format='%H %P %s' c2e8d308` shows parents
   `1914e5d0e4204a8cdb5f97ea2be93923495dcfb0` and
   `e6db2a9f20c25823ac6c2f04e60d922d3f9a3f8e`. `c2e8d308` is the mainline
   merge that first makes the social/chat/federation packages reachable from
   the first-parent history.
3. `git merge-base --is-ancestor 1914e5d0 93d61a3f` exits `0`; the baseline is
   an ancestor of the audit HEAD.
4. At `1914e5d0`, all five candidate paths are absent:
   - `src/sofia/core/multicore` — ABSENT
   - `src/sofia/platform/chat` — ABSENT
   - `src/sofia/platform/social` — ABSENT
   - `src/sofia/platform/federation` — ABSENT
   - `src/sofia/core/cores` — ABSENT
5. `4a2d8b1f` is earlier and also lacks the paths, but `1914e5d0` is the latest
   mainline commit before the first introduction. `git log --first-parent
   4a2d8b1f..1914e5d0` contains exactly one commit, `1914e5d0` itself.
6. `c2e8d308` and `7c2f26f4` only add files relative to `1914e5d0`; neither
   modifies or deletes a baseline path. `git diff --name-status 1914e5d0
   c2e8d308` is additions only.
7. First mainline introduction points:
   - `platform/chat`, `platform/social`, `platform/federation`: `c2e8d308`
   - `core/multicore`: `cc225f6f`
   - `core/cores`: `c6c47dda`
   - `aeef1559`, cited as a baseline in some later docs, is already
     post-multi-Core (20 multicore files, 16 Core asset files).
8. The lead tag `aegis/core-audit-baseline-2026-11-18` points to audit HEAD
   `93d61a3f`, not to the pre-multi-Core baseline. It is an audit checkpoint,
   not the preservation baseline.

**UNKNOWN:** Why later documents call `aeef1559` or `7ea80fb3` their baseline.
Those labels are documentation baselines, not the pre-multi-Core boundary.

### 1.3 Change surface from baseline to HEAD

OBSERVED: `git diff --name-status 1914e5d0 93d61a3f` contains:

| Status | Count |
| --- | ---: |
| Added (`A`) | 173 |
| Modified (`M`) | 14 |
| Deleted (`D`) | 0 |
| **Total entries** | **187** |

Baseline tree: 3,037 files. HEAD tree: 3,210 files.

There are **no deletions** and **no modifications under `src/sofia/core`**.
All 41 files added under `src/sofia/core` are in the new `core/multicore` or
`core/cores` trees.

---

## 2. Inventory and classification

Classification used below:

- **SOFÍA-SPECIFIC** — canonical Core #1 identity/behavior/data and files that
  exist only to serve the Sofía persona or application. This includes the
  sensitive avatar, private-behavior and voice surfaces.
- **SHARED INFRASTRUCTURE** — generic contracts, packaging, verification,
  transport or platform runtime that is not itself Sofía's identity or memory.
- **UNCERTAIN** — mixed generic/named-Core ownership, or ownership that cannot
  be resolved from the path alone.

### 2.1 Canonical Core #1 — SOFÍA-SPECIFIC

| Path group | Baseline files | Classification | Notes |
| --- | ---: | --- | --- |
| `src/sofia/core/constitution/` | 4 | SOFÍA-SPECIFIC | Immutable Constitution + digest + store (`constitution.md`, `constitution.sha256`, `__init__.py`, `store.py`). |
| `src/sofia/core/identity/` | 4 | SOFÍA-SPECIFIC | Canonical identity asset/model/store (`identity.json`, `model.py`, `store.py`, `__init__.py`). |
| `src/sofia/core/personality/` | 16 | SOFÍA-SPECIFIC | Canonical personality JSON plus boundaries, expression, evolution, modulation, reflection and delivery. |
| `src/sofia/core/embodiment/` | 5 | SOFÍA-SPECIFIC | Canonical avatar JSON plus measurement query/model/store. |
| `src/sofia/core/cognition/` | 61 | SOFÍA-SPECIFIC | Single-Core cognitive runtime, context assembly, providers, tools, guards, model admission/lifecycle and V2 kernel. |
| `src/sofia/core/emotion/` | 7 | SOFÍA-SPECIFIC | Appraisal, catalog, journal, projection and model. |
| `src/sofia/core/memory/` | 26 | SOFÍA-SPECIFIC | Autobiography, provenance, significance, retrieval, deletion ledger and ChatGPT import/export. |
| `src/sofia/core/rel/` | 6 | SOFÍA-SPECIFIC | Relationship model, impressions, nicknames, repair and store. |
| `src/sofia/core/life/` | 12 | SOFÍA-SPECIFIC | Life coordinator, hobbies, outreach, ideation and fulfillment. |
| `src/sofia/core/agency/` | 2 | SOFÍA-SPECIFIC | Agency ledger/init. |
| `src/sofia/core/security/` | 3 | SOFÍA-SPECIFIC | Protected-resource boundary and protected-state policy. |
| `src/sofia/core/social/` | 5 | SOFÍA-SPECIFIC | Single-Core social/affect/model/principal/store foundation. |
| `src/sofia/core/conversation/` | 6 | SOFÍA-SPECIFIC | Conversation model/store/search/offline drafts/lifelong behavior. |
| `src/sofia/core/communication/` | 3 | SOFÍA-SPECIFIC | Communication service and shorthand. |
| `src/sofia/core/self_model/` | 3 | SOFÍA-SPECIFIC | Self-model and operational state. |
| `src/sofia/core/continuity/` | 2 | SOFÍA-SPECIFIC | Continuity model/init. |
| `src/sofia/core/beliefs/` | 3 | SOFÍA-SPECIFIC | Beliefs state/model. |
| `src/sofia/core/mentor/`, `goals/`, `habits/`, `learning/`, `know/`, `knowledge/`, `creative/`, `environment/`, `generalization/`, `modreg/` | — | SOFÍA-SPECIFIC | Remaining single-Core cognitive/personal subsystems; not individually enumerated here. |
| `src/sofia/modules/avatar/` | 75 | SOFÍA-SPECIFIC | Canonical Sofía embodiment/wardrobe surface, including `private_grant.py`, `presentation*`, `scene_compositor.py`, `split_scene`, `wardrobe_data/intimate_underlayers.json` and VTube/asset tooling. |
| `src/sofia/modules/voice/` | 11 | SOFÍA-SPECIFIC | Sofía voice factory, prosody, TTS/STT, SAPI, Qwen-local and receipts. |
| `src/sofia/modules/body/` | 1 | SOFÍA-SPECIFIC | Body module namespace. |
| `src/sofia/platform/authority/model.py` | 2 | SOFÍA-SPECIFIC | Docstring explicitly describes authority for “Sofía”; single-Core operation authority. |
| `src/sofia/platform/application/bootstrap.py` | 1 of 30 | SOFÍA-SPECIFIC | Application bootstrap and controlled lifecycle for Sofía; the rest of `platform/application` is mixed. |
| `src/sofia/platform/application/voice_expression_bridge.py` | 1 of 30 | SOFÍA-SPECIFIC | Bridges Sofía voice expression to the shared SDK contract. |
| `src/sofia/platform/application/autonomous_work.py`, `presence.py`, `personality_evolution.py`, `emotional_conversation.py`, `memory_review.py`, `idle_reflection.py` | — | SOFÍA-SPECIFIC | Single-Core autonomy, presence, personality, emotion and memory application behavior. |
| `test/test_constitution*.py`, `test/test_identity.py`, `test/test_personality.py`, `test/test_embodiment.py`, `test/test_avatar_*.py`, `test/test_voice_*.py` | — | SOFÍA-SPECIFIC | Preservation tests for Core #1 assets and behavior. |

### 2.2 Shared infrastructure — SHARED INFRASTRUCTURE

| Path group | Baseline files | Notes |
| --- | ---: | --- |
| `src/sofia/platform/authorization/` | 3 | Generic filesystem/authorization evaluator; consumes principal context; not Sofia identity data. |
| `src/sofia/platform/composition/` | 5 | Composition root/engines/authorization/split topology; shared wiring. |
| `src/sofia/platform/runtime/` | 8 | Clock, evidence, hot state, internal workspace, model, response, runtime. |
| `src/sofia/platform/run/` | 51 | Service, supervisor, leases, release/rollout, management, systemd/Windows service, startup and watchdog plumbing. Host/platform infrastructure. |
| `src/sofia/platform/filesystem/`, `net/`, `safe/`, `state/`, `machine/`, `distributed/`, `core_link/`, `core_worker/`, `inference_worker/` | — | Platform/transport/state/worker infrastructure. |
| `src/sofia/sdk/` | 29 | Portable Aegis contracts. `sdk/identity.py`, `sdk/core_definition.py`, `sdk/runtime.py`, `sdk/principals.py`, `sdk/voice_expression.py` are Core-neutral. |
| `src/sofia/platform/cli.py` | 1 | Operator CLI surface; read-only truth/fail-closed mutation behavior. Now also exposes multi-Core definitions. |
| `src/sofia/platform/verify/` | — | Component artifact, release and cognition-baseline verification. |
| `packaging/`, `pyproject.toml` | — | Distribution and package-data declarations. |
| `test/conftest.py` | 1 | Shared test environment and package markers. |

### 2.3 UNCERTAIN / mixed

| Path group | Classification | Reason |
| --- | --- | --- |
| `src/sofia/platform/application/` (remaining 29 files) | UNCERTAIN | Mixes Sofia-specific bootstrap/presence/personality with reusable application/service plumbing. |
| `src/sofia/platform/authority/` | UNCERTAIN | `model.py` is Sofía-specific; package boundary is a general authority contract. |
| `src/sofia/modules/avatar/fit.py` | UNCERTAIN | Generic external wearer/body fit contract, historically part of Sofía avatar; does not own canonical body data. |
| `src/sofia/core/cognition/routing.py`, `providers/`, `model_lifecycle.py` | UNCERTAIN | Model routing is provider-agnostic infrastructure but is currently the single-Core Sofía cognitive path. |
| `src/sofia/core/social/` vs new `src/sofia/platform/social/` | UNCERTAIN | Same word “social” denotes different layers: Core #1 social state vs platform multi-Core social/federation. |
| `src/sofia/core/cores/` and `src/sofia/core/multicore/` | UNCERTAIN | Post-baseline additions. Generic multi-Core engine and named-Core assets are mixed at package level (Section 8). |

### 2.4 New post-baseline multi-Core paths

These are not pre-multi-Core preservation candidates; they are recorded so that
preservation work does not accidentally treat them as baseline Sofia files.

| Path group | Added files | Classification | Reason |
| --- | ---: | --- | --- |
| `src/sofia/core/multicore/` | 23 | SHARED INFRASTRUCTURE | Generic contracts/state/lifecycle/memory/routing/conversation/emotion engine for independent Cores. Five files are mixed or Core-named (Section 8). |
| `src/sofia/core/cores/mack/` | 5 | SOFÍA-SPECIFIC (Core-family asset) | Core #2 personal Constitution/personality/avatar/voice. Not Core #1. |
| `src/sofia/core/cores/nova/` | 5 | SOFÍA-SPECIFIC (Core-family asset) | Core #3 personal assets. Not Core #1. |
| `src/sofia/core/cores/vera/` | 5 | SOFÍA-SPECIFIC (Core-family asset) | Core #6 personal assets. Not Core #1. |
| `src/sofia/core/cores/unwritten/` | 2 | SOFÍA-SPECIFIC (Core-family asset) | Core #7 neutral bootstrap only; intentionally no personal assets. |
| `src/sofia/platform/chat/`, `chat_clients/` | 15 | SHARED INFRASTRUCTURE | Multi-Core canonical chat engine and client adapters. |
| `src/sofia/platform/social/` | 19 | SHARED INFRASTRUCTURE | Social contracts, autonomy, governance, universal composition. |
| `src/sofia/platform/federation/` | 7 | SHARED INFRASTRUCTURE | Core federation transport/node/store. |
| `src/sofia/platform/inference/` | 11 | SHARED INFRASTRUCTURE | Shared inference scheduler, residency, budget, identity and telemetry. |
| `src/sofia/modules/avatar/` additions | 6 | SHARED INFRASTRUCTURE | Universal armor catalog, inventory contract/store, wardrobe equipment. |
| `src/sofia/sdk/core_capabilities.py`, `gesture_contract.py` | 2 | SHARED INFRASTRUCTURE | Portable capability and gesture contracts. |
| Multi-Core tests | 60 | SHARED INFRASTRUCTURE | Evidence tests/support files for the new packages. |

---

## 3. Rename-aware and history evidence

OBSERVED `git log --follow` results:

| Path | Rename-aware history |
| --- | --- |
| `src/sofia/core/constitution/constitution.md` | `R100 src/sofia/constitution/constitution.md -> src/sofia/core/constitution/constitution.md` in `e10fb9c0`; originally `A` in `7f2e7d2e`. |
| `src/sofia/core/identity/identity.json` | `R100 src/sofia/identity/identity.json -> src/sofia/core/identity/identity.json` in `e10fb9c0`; originally added in `e76e84fb`. |
| `src/sofia/core/personality/personality.json` | `R100 src/sofia/personality/personality.json -> src/sofia/core/personality/personality.json` in `e10fb9c0`. |
| `src/sofia/core/embodiment/avatar.json` | `R100 src/sofia/data/avatar.json -> src/sofia/embodiment/avatar.json` in `67e71789`; then `R100` to `src/sofia/core/embodiment/avatar.json` in `e10fb9c0`. |
| `src/sofia/modules/avatar/fit.py` | `R100 src/sofia/avatar/fit.py -> src/sofia/modules/avatar/fit.py` in `f3075b81`; originally added in `ca61a00f`. |
| `src/sofia/platform/cli.py` | No rename in recent history; modified in `69be2f90`, `fb528417`, `154a96c6`. |
| `src/sofia/sdk/__init__.py` | No rename in recent history; lazy SDK facade expanded in `aef8e8ad`, `dca0ab5a`, `2f79acc4`. |
| `test/conftest.py` | No rename in recent history; modified in `bfd3bb7b`, `fb528417`, `a94af2ee`. |

No rename in `1914e5d0..93d61a3f` affects the canonical assets. The path moves
predate the baseline; content blobs are unchanged across the audit range.

Core asset history is also addition-only:

| Asset | First commit |
| --- | --- |
| `src/sofia/core/cores/mack/constitution.md` | `161a7aa3` (A) |
| `src/sofia/core/cores/nova/constitution.md` | `161a7aa3` (A) |
| `src/sofia/core/cores/vera/constitution.md` | `1a1c13b9` (A) |
| `src/sofia/core/cores/unwritten/constitution.md` | `de0ea92c` (A) |
| `src/sofia/core/multicore/profiles.py` | `161a7aa3` (A), later modified by `1a1c13b9` |

---

## 4. Modified-file semantic impact

All 14 modified paths are listed here. The six files explicitly required by the
audit are analyzed individually.

| Path | Baseline blob -> HEAD blob | Verdict |
| --- | --- | --- |
| `docs/mentor_exchange/outbox/latest.json` | `3c4872157c963cb7009e0152830c40dfd82b4fb9` -> `017b3f51ec565f4ab7e350a5d25cef7f7c539139` | Unrelated mentor evidence refresh; timestamp/source revision only. |
| `docs/operations/AEGIS_GUIDED_INSTALLER.md` | `4f7a3913875ea5e9a49a274c9a6e78a642a79220` -> `f26ecea0d03b06d26427b76a450c5fc7c8e8caef` | Approved installer-trust documentation; unrelated to Sofia identity. |
| `packaging/components.toml` | `3cded9a1d22b87b5ef8c668476ce992e822ed485` -> `77dbb97eee2687aaf1335205097d70138e81d187` | Additive Core package-data declarations; no Sofía asset change. |
| `packaging/installers/install-aegis.sh` | `5191e4d86fdb1678a3b7387b2207d07eea393e34` -> `edde9acc09fe584f97870dcdbc2a1b0ef98b25be` | Approved installer bundle-root resolution; unrelated. |
| `pyproject.toml` | `a4d1dd06d3f72359418760c380b95b32ff4fe20e` -> `cb5c897c6fd63bd0b4e243404e788121e1f0b3bb` | Additive Core package data; no Sofía asset change. |
| `src/sofia/modules/avatar/fit.py` | `9f4e7243725a71aa0ac89b412f7fbafd01605854` -> `8afccb945592af031a4f6d2ab4e49db946310d5b` | Additive external wearer-fit gate; legitimate enhancement. |
| `src/sofia/platform/cli.py` | `ec9d450215d6067488200b8af987b9d95857ad04` -> `a0f037955cb3cdae8f7ced7c4f48ef0bbd775eb3` | Additive read-only `core profiles` command. |
| `src/sofia/platform/ops/platform_installer_guided.py` | `86c2a94b3e29ee8861f36d35427bb2821956474c` -> `dcba7c881b0bf4a5db60cc578d7479f48bad282f` | Unrelated approved installer-trust/no-color work. |
| `src/sofia/platform/verify/component_artifacts.py` | `0f7bdc54a8a66c3c327eb3a6d6ddfba9f6d8389a` -> `33aae2683ef1f2142b0d10619ec83386bf886fdd` | Additive Core assets plus bounded package-data glob support. |
| `src/sofia/sdk/__init__.py` | `39cdcd40ac1a1d067f3f42d41a6b21a26a5a1829` -> `c56f215b7f0de64da21bc546700962cbf8ea820e` | Additive lazy exports; no removals. |
| `test/conftest.py` | `77d2e3058732f46040062d2c451b785506606b18` -> `bc73609620a64edd3f5e95f20de7fb96d0403f37` | Additive package markers for `chat`/`chat_clients`. |
| `test/test_aegis_cli.py` | `4a6d44676da3990e9ab1a6cdb17a0e7004ed5d3a` -> `df73daab9b21e3ff3f91d72f61fc948fcbdea3f5` | Additive test; incidental UTF-8 BOM at file start. |
| `test/test_component_artifact_separation.py` | `0a76d7226dd194b9d4f94e2090b9e1d8a0e1ce90` -> `cb96f2b8031a7b1f6505b4f294d218eb2c8f75a1` | Test updated for glob semantics; equality assertion retained. |
| `test/test_ops_platform_installer_guided.py` | `9496eb2f16292a7d07354047e2ff971621e987e3` -> `58fa1a69b70f11780296315978a0733e06b37e08` | Installer test harness updated; denial behavior retained. |

### 4.1 `src/sofia/modules/avatar/fit.py`

OBSERVED diff is insertion-only before `DEFAULT_FIT_ANCHORS`; existing
`FitAnchor`, `BodyRegion` and fit constants are not edited. Added:

- `WearerFitStatus`
- `WearerProfile` (`fit.py:129`) — external host-supplied wearer facts
- `WearerFitResult` — explicit metadata-only / no-canonical-mutation result
- `evaluate_wearer_fit()` (`fit.py:238`) — requires body profile, rig, anchors,
  anatomy clearance, reviewed asset reference, verified asset and external fit
  evidence before returning `FITTED`

The new code imports `.wardrobe_equipment.WardrobeDesign` (`fit.py:14`).
`wardrobe_equipment.py` was added by `061c1984`; `fit.py` was then extended by
`5a7823b3` (armor catalog, wearer fit gate and scoped visibility). It never writes
canonical body/avatar/measurement state and its docstring explicitly says the
profile cannot mutate canonical body data.

**Verdict:** additive, legitimate enhancement; not an identity/personality/
memory/security regression. It does add coupling from avatar fit to the new
wardrobe equipment module; that is expected for the approved wardrobe work.

### 4.2 `src/sofia/platform/cli.py`

OBSERVED additions:

- `_core_profile_catalog()` (`cli.py:781`) imports
  `EXPECTED_CORE_IDENTITIES` and returns definition metadata plus
  `"installed": False`, `"runtime_verified": False`.
- New `core profiles` subcommand (`cli.py` around the core parser) with
  `--json`.
- Dispatch returns `EXIT_OK` without reading or writing Core state.

No existing CLI command, payload or mutation guard is changed in this diff.

**Verdict:** additive read-only CLI surface. It is not a preservation regression.
It does expose only three definitions because `EXPECTED_CORE_IDENTITIES` at
`management.py:89` contains Sofía, Mack and Nova only; see Section 9.

### 4.3 `src/sofia/platform/ops/platform_installer_guided.py`

OBSERVED change: the guided installer now requires an independent,
owner-controlled trust root outside the installer bundle:

- `_TRUST_ROOT_ENV = "AEGIS_INSTALLER_TRUST_ROOT"` (`:331`)
- `_independent_trust_root()` (`:385`) defaults to
  `%ProgramData%\Aegis\installer-trust` on Windows or
  `/etc/aegis/installer-trust` elsewhere, rejects relative paths, rejects a
  root inside the bundle and rejects a bundle/independent-root mismatch
- `_trust_anchor()` (`:413`) validates both provisioning copies and requires
  matching publisher key/pin/signer
- `run_guided`/`_installer_inputs` accept an optional `trust_root`
- `--trust-root` and `--no-color` are added to the module CLI

Attribution: `git log --oneline 1914e5d0..93d61a3f --` this file shows only
`6b3f8be6` (WIP) and `98bf382a` (fix), merged by `7ea80fb3`; `6b3f8be6` has
first parent `1914e5d0`. This is a separate installer branch, not a multi-Core
change.

**Verdict:** unrelated approved installer/security hardening. It changes the
installer trust contract (a real behavior change for installers) but does not
touch Sofia identity, personality, memory or Core authorization. Installer
owners should treat the new independent-root provisioning requirement as an
operational change.

### 4.4 `src/sofia/platform/verify/component_artifacts.py`

OBSERVED additions:

- `CORE_ASSET_FILES` now includes 13 Mack/Nova/Vera/#7 asset paths
  (`component_artifacts.py:39`).
- `_package_data_assets()` (`:399`) expands reviewed package-data globs, rejects
  empty patterns, absolute paths and `..` escapes, and fails when a glob matches
  nothing.
- `_stage_component()` uses the helper for validation.

Existing literal-file validation is preserved. The new glob branch accepts
only matches under the declared package directory. The test update expands the
same declared assets and still asserts set equality with `CORE_ASSET_FILES`.

**Verdict:** additive shared packaging/verification infrastructure. No Sofia
asset is changed.

### 4.5 `src/sofia/sdk/__init__.py`

OBSERVED diff adds two lazy export groups, `core_capabilities` and
`gesture_contract` (`sdk/__init__.py:54` and `:65`). No existing export is
removed or changed.

**Verdict:** additive SDK surface; not a regression.

### 4.6 `test/conftest.py`

OBSERVED diff adds `"chat": ("pkg_social", "pkg_safe")` and
`"chat_clients": ("pkg_ui", "pkg_social", "pkg_net")` markers. No existing
marker is changed.

**Verdict:** additive test classification.

---

## 5. Canonical Sofia identity and immutable assets

OBSERVED `git diff --name-status 1914e5d0 93d61a3f -- src/sofia/core/constitution
src/sofia/core/identity src/sofia/core/personality src/sofia/core/embodiment`
is empty. Every blob below is identical at baseline and HEAD.

| Path | Git blob (both revisions) | SHA-256 (canonical git blob) | Status |
| --- | --- | --- | --- |
| `src/sofia/core/constitution/constitution.md` | `4cf05d7d7d1211dc634be9710b27d7a4e8060588` | `f30afedf195f77907d32a108ca35d4db751646bde3fd902be66e7b78f4b89dc0` | UNCHANGED |
| `src/sofia/core/constitution/constitution.sha256` | `edac902bf034a6db1ce1faaee039961a0a7dbefe` | content literal `F30AFEDF195F77907D32A108CA35D4DB751646BDE3FD902BE66E7B78F4B89DC0` | UNCHANGED |
| `src/sofia/core/identity/identity.json` | `fa0bae06a45c8994a129928a0ee49227f55e127c` | `8170c5ab140da7ed9e1fa081215702ded0709f10cb04ead41786831f642e0adb` | UNCHANGED |
| `src/sofia/core/identity/__init__.py` | `95daf27c5efc2793a5d7f15b9a8153f004c556ba` | — | UNCHANGED |
| `src/sofia/core/identity/model.py` | `a82d4f1e1a950cae1481035deb5e26098f586956` | — | UNCHANGED |
| `src/sofia/core/identity/store.py` | `79804efe55acb5838673079effb20f4f5a3b02fe` | — | UNCHANGED |
| `src/sofia/core/personality/personality.json` | `5cb5252da24827f19707d4b784e6775004ba9b00` | `8f616d7f9402946d6ec1d4302b812b256bbd457dbc14efaf18af6dc87b0cec84` | UNCHANGED |
| `src/sofia/core/embodiment/avatar.json` | `c7ba02a185e0029013b98ddcd24602afd96d6c3e` | `7ffa81ca846c039193ab0b17b211e816b0e5c5856672c8023ffc78fbb2d5f98d` | UNCHANGED |

Canonical values observed:

- `identity.json`: `"name": "Sofía Ada Lyra"`; `"instance_id":
  "a9a0a604-a4e7-4a88-a985-3f071e2c8e7d"`.
- `avatar.json`: `"subject": "Sofía Ada Lyra"`; human form with fox ears and
  fox tail; the existing canonical measurement/appearance/clothing data is
  unchanged.
- `personality.json`: `"name": "Sofía"`; the existing trait set is unchanged.

Constitution digest note: the recorded `constitution.sha256` value
`F30AFEDF...` matches the canonical LF Git blob (`f30afedf...`). On this Windows
checkout, `Get-FileHash` of the working-tree `constitution.md` is
`67167e585c6da08559fe22065db5c75b9a18318867ecb1cb1edc30ac8c1111565`
because the checkout materializes CRLF. This is a pre-existing checkout
representation note already documented in
`docs/sofia2/CORE_ACCEPTANCE_EVIDENCE_2026-11-18.md`; it is not drift in this
audit range. The Git blobs are identical at baseline and HEAD.

**Conclusion:** canonical Sofía identity, Constitution, personality and
embodiment assets are unchanged. No identity substitution, personality
rewrite, memory overwrite or canonical avatar edit was observed.

---

## 6. Reproducible semantic snapshot

### 6.1 Canonical manifest

OBSERVED manifest digest (sorted `git ls-tree -r <rev> -- <path>` lines for
`src/sofia/core/constitution`, `identity`, `personality`, `embodiment`, then
SHA-256 of the joined lines):

| Revision | Files | Manifest SHA-256 |
| --- | ---: | --- |
| `1914e5d0` | 29 | `a81aef8942b43b3d69511565a4ae6f7211d2ada183ade3f0e89badf24cbca187` |
| `93d61a3f` | 29 | `a81aef8942b43b3d69511565a4ae6f7211d2ada183ade3f0e89badf24cbca187` |

Identical manifest digest = identical path/blob set for the canonical assets.

### 6.2 New multi-Core tree manifest

Paths included: `src/sofia/core/multicore`, `src/sofia/core/cores`,
`src/sofia/platform/chat`, `src/sofia/platform/chat_clients`,
`src/sofia/platform/federation`, `src/sofia/platform/inference`,
`src/sofia/platform/social`.

| Revision | Files | Manifest SHA-256 |
| --- | ---: | --- |
| `1914e5d0` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` (empty SHA-256) |
| `93d61a3f` | 93 | `095012749520bbeb241a4f0b6e324d19bdd8eb54b3bd6310c5717dc5f5f53fa9` |

### 6.3 Key post-baseline files

| Path | Blob at `1914e5d0` | Blob at `93d61a3f` |
| --- | --- | --- |
| `src/sofia/core/multicore/profiles.py` | ABSENT | `888556b90719240ad4deeea0539dc90da2191a4a` |
| `src/sofia/core/multicore/personality.py` | ABSENT | `8302def2e0b3c6dd33f466b372681d71dfe23481` |
| `src/sofia/core/multicore/emotion.py` | ABSENT | `68dcabca062d1ad15d5f0c719f0c56fe46eb7728` |
| `src/sofia/core/multicore/vera.py` | ABSENT | `595c3b67409b8995941d67fc218a8793aa7b9b69` |
| `src/sofia/core/multicore/unwritten.py` | ABSENT | `4ccf3522b629dd11b89e2047fc8c09ceb9711685` |
| `src/sofia/core/multicore/management.py` | ABSENT | `3e3442b9d90763e30d6a25e4387cac1334b7983d` |
| `src/sofia/modules/avatar/fit.py` | `9f4e7243725a71aa0ac89b412f7fbafd01605854` | `8afccb945592af031a4f6d2ab4e49db946310d5b` |
| `src/sofia/platform/cli.py` | `ec9d450215d6067488200b8af987b9d95857ad04` | `a0f037955cb3cdae8f7ced7c4f48ef0bbd775eb3` |
| `src/sofia/platform/verify/component_artifacts.py` | `0f7bdc54a8a66c3c327eb3a6d6ddfba9f6d8389a` | `33aae2683ef1f2142b0d10619ec83386bf886fdd` |
| `src/sofia/platform/ops/platform_installer_guided.py` | `86c2a94b3e29ee8861f36d35427bb2821956474c` | `dcba7c881b0bf4a5db60cc578d7479f48bad282f` |
| `src/sofia/sdk/__init__.py` | `39cdcd40ac1a1d067f3f42d41a6b21a26a5a1829` | `c56f215b7f0de64da21bc546700962cbf8ea820e` |
| `test/conftest.py` | `77d2e3058732f46040062d2c451b785506606b18` | `bc73609620a64edd3f5e95f20de7fb96d0403f37` |

### 6.4 New Core assets (HEAD)

| Asset | Blob | SHA-256 |
| --- | --- | --- |
| `src/sofia/core/cores/mack/constitution.md` | `4679df6aca7bc034d3b403339f487fc8eee8121f` | `b4cc77c8fcb6b6af3edb276bb1cdadfa5790573e5ea279abd7a004a02a8fcee2` |
| `src/sofia/core/cores/mack/personality.json` | `85909517fe20665a62ae7d34ef21820ff53bd279` | `d84c2871c5e333bea9459aaca8618cc9c916e16fca565f614da916072f348d72` |
| `src/sofia/core/cores/mack/avatar.json` | `4707d8c11b405fc28a3d0bf01828a7cb63a66694` | `fa08f48625a1a31981560a85bb767125dc58bd8d298a444d15a75de040ba1d8e` |
| `src/sofia/core/cores/mack/voice.json` | `82bbcbd122da640122d5a1513837d1499a3d6348` | `094ab42b3e713aa0c7565aaa5ffdd85769f6b63d41a88452404ac1e0c338bc13` |
| `src/sofia/core/cores/nova/constitution.md` | `4c71969e3e9e07d5076d0fc3be0cadb4756ae99b` | `74c8a483a4bf0bfa0844c2017d6d7e74f305e21d20462a27f40f984824ebbcb3` |
| `src/sofia/core/cores/nova/personality.json` | `9dd81591f192c4e88193ad6c9c31d5db1494572f` | `385ff42715ced5e8b7f385dfcd863a5c0bcf388fcc10e1c97773c44eb531f6b8` |
| `src/sofia/core/cores/nova/avatar.json` | `d65d2aad751d69aaaea6ac6d93a3cc1662149d95` | `0019f79abb8dc2e891f6fd5e7b17cb1adc692a048d694a8e5d544f297e3d3def` |
| `src/sofia/core/cores/nova/voice.json` | `2acec1389c5b9bbd1129f74b5e644450622cf909` | `65ac1a5b56dc754c4de9ae3db1acdca73f684135c2474e9c0d6ada468484c1b8` |
| `src/sofia/core/cores/vera/constitution.md` | `465aa7efae499b7ecb885ee53a65e39b044de026` | `fe2c09bc5e5b8f391aaee9f1c5c5a67f27fbcc0f001855381f98fc49876898ee` |
| `src/sofia/core/cores/vera/personality.json` | `ff82728d42546f45bc37246706154da3eeda2b6b` | `8ec24ad7e3578fa1a47e9d5f383346ee08945860a4126496c62f6e3187fea9e0` |
| `src/sofia/core/cores/vera/avatar.json` | `aaa69faa59dc9db68a7300ec347aeb139269eb13` | `22ef7c6fdd8db79a941ed468516993a625223d40240680e8a7b3586f0fad532e` |
| `src/sofia/core/cores/vera/voice.json` | `be282fb39ea9c1ff3efdd6d7c157aca3574b6847` | `3606cd5d69efdf40a093e3ecdad5448ece3f5a44225b1b3bfbc593658d49d525` |
| `src/sofia/core/cores/unwritten/constitution.md` | `3ca2c32494107da6ea4ea27322c7760cb24ed6ce` | `469afcad1e40d5837dfefea2c2e6d3db3f68ef56bb465789629fb42095e109bd` |

---

## 7. Multi-Core migration commits

Counts are OBSERVED from first-parent diffs for merges and parent diffs for
non-merges. “A/M/D” means added/modified/deleted paths.

| Commit | Kind | A/M/D | Observed effect | Preservation verdict |
| --- | --- | --- | --- | --- |
| `7c2f26f4` | Branch merge (first parent `1914e5d0`) | 11/0/0 | Adds `platform/federation/*` (7), `platform/social/{__init__,contracts}.py` (2), two federation tests | Additive shared social/federation infrastructure |
| `124124db` | Branch merge | 9/0/0 | Adds `platform/chat/*` (4) and five chat tests | Additive canonical chat engine |
| `2d05f7aa` | Branch merge | 13/1/0 | Adds `platform/social/autonomy/*` (7) and tests; modifies only the newly added `social/__init__.py` | Additive autonomy layer |
| `4f413dc0` | Branch merge | 16/0/0 | Adds `platform/inference/*` (11) and five tests/support files | Additive shared inference/residency |
| `6b217d84` | Branch merge | 15/0/0 | Adds `platform/chat_clients/*` (11) and four Stage 6 tests | Additive social clients |
| `add2adfe` | Commit | 2/0/0 | Adds compatibility adapters | Additive |
| `e6db2a9f` | Commit | 1/0/0 | Stage 6 status document | Documentation only |
| `c2e8d308` | Mainline merge (first parent `1914e5d0`) | 67/0/0 | Integrates chat, clients, federation, inference, social/autonomy and tests from the social branch | Additive integration; no baseline path modified |
| `cc225f6f` | Commit | 2/0/0 | First `core/multicore` package: `__init__.py`, `contracts.py` | Additive generic contracts |
| `279be70c` | Branch merge | 17/3/0 | Adds Mack/Nova profiles, identity, lifecycle, memory, etc. and Core asset packages; modifies `packaging/components.toml`, `pyproject.toml`, `component_artifacts.py` only to add Mack/Nova assets | Additive Core packages; packaging additions |
| `1522a585` | Branch merge | 6/1/0 | Adds memory/learning/reflection; modifies only `core/multicore/__init__.py` exports | Additive exports |
| `579ec450` | Branch merge | 8/1/0 | Adds personality/emotion/relationships/continuity; modifies only `core/multicore/__init__.py` | Additive exports |
| `90dc2a7f` | Branch merge | 6/0/0 | Adds conversation/routing/social modules and tests | Additive |
| `e9717e13` | Branch merge | 7/0/0 | Adds inference/management/acceptance modules and tests | Additive |
| `a94af2ee` | Commit | 1/4/0 | Integrates canonical profiles/routing/package ownership; modifies `core/multicore/conversation.py`, `management.py`, `test/conftest.py`, `test/test_core_multicore_management.py` | Changes only new multi-Core code/tests |
| `154a96c6` | Commit | 0/2/0 | Adds `core profiles` to `platform/cli.py` and its test | Additive CLI projection; introduced roster limitation noted in Section 9 |
| `93d61a3f` | Commit (HEAD) | 0/10/0 | Final five-Core docs, `core/multicore/__init__.py` exports, `platform/social/universal.py` roster, `component_artifacts.py` glob support, tests | Finalization; no canonical Sofia asset modified |

Additional observed commits in the same workstream that are not in the supplied
list but affect the migration: `c6c47dda` (52 changed paths; Mack/Nova source
Core assets plus multicore modules), `1a1c13b9` (10 changed paths; Vera
assets/profile), `de0ea92c` (20 changed paths; Core #7 bootstrap and five-Core
reconciliation), and `aeef1559` (5 changed paths; universal composition
facade).

**Conclusion:** every multi-Core migration commit is addition-dominated. No
commit in `1914e5d0..93d61a3f` deletes or edits a pre-existing canonical Sofia
file. The only pre-existing source files modified are `avatar/fit.py`,
`platform/cli.py`, `platform/ops/platform_installer_guided.py`,
`platform/verify/component_artifacts.py` and `sdk/__init__.py`, all analyzed in
Section 4.

---

## 8. Mixed modules requiring directory normalization

The following are OBSERVED from HEAD content. These are structural ownership
issues, not evidence that Canonical Sofia data was modified.

| Module | Mixing evidence | Required normalization | Risk if left |
| --- | --- | --- | --- |
| `src/sofia/core/multicore/profiles.py` | Generic docstring, `CoreProfileSpec`, loader and registry, but also hardcoded `MACK_PROFILE` (`:145`), `NOVA_PROFILE` (`:156`), `VERA_PROFILE` (`:171`) and `DEFAULT_CORE_PROFILES` registration (`:594-597`). Asset validation for all Cores lives here. | Keep generic spec/registry/loader in `core/multicore`; move each named profile spec and its asset validation into `core/cores/<slug>/profile.py` (or a single per-Core catalog). | A generic runtime package becomes the de facto owner of named identities; adding a Core requires editing generic code. |
| `src/sofia/core/multicore/personality.py` | Generic change governance/state machine plus `MACK_FULLER_PROFILE` (`:403`) and `NOVA_ARDEN_PROFILE` (`:426`) trait seeds. | Keep `PersonalityState`/change classes generic; move named trait seeds into per-Core modules or assets. | Named personality data is coupled to generic policy; harder to preserve/audit one Core independently. |
| `src/sofia/core/multicore/emotion.py` | Generic appraisal/decay engine plus `MACK_EMOTION_PROFILE` (`:231`) and `NOVA_EMOTION_PROFILE` (`:245`). | Keep `SimulatedEmotionState`/appraisal generic; move numeric profiles to per-Core modules/assets. | Same as personality: generic affect engine owns named Core temperament. |
| `src/sofia/core/multicore/vera.py` | Entire module is Vera Core #6 (`VERA_PERSONAL_NAME` at `:33`, `VeraAuthorityBoundary` at `:75`), but it lives in the generic `multicore` package. | Move to `core/cores/vera/` (for example `appearance.py`/`authority.py`) with assets; update imports. | A named Core implementation is indistinguishable from generic multicore infrastructure. |
| `src/sofia/core/multicore/unwritten.py` | Entire module is Core #7 (`UNWRITTEN_CORE_NUMBER = 7` at `:56`, `MulticoreUnwrittenIdentity` at `:950`) inside generic `multicore`. | Move to `core/cores/unwritten/` (profile/service split) with its neutral constitution; update imports. | Same as Vera; also inflates the generic package with one Core's growth policy. |
| `src/sofia/core/multicore/__init__.py` | Re-exports generic contracts plus Mack/Nova/Vera/#7 named constants and classes (`MACK_PROFILE`, `VERA_*`, `UNWRITTEN_*`, etc.). | Keep a small generic facade; expose named Core modules through their per-Core packages. | Importing the generic package pulls named Core identity symbols. |
| `src/sofia/core/cores/` | Already per-Core asset directories: `mack/`, `nova/`, `vera/`, `unwritten/`. `unwritten/` intentionally has only a constitution. | Keep assets per Core. Add per-Core profile/personality/emotion modules alongside assets so data and behavior share ownership. Do not add Sofia Core #1 assets here. | Asset dirs are correct; behavior split is incomplete. |
| `src/sofia/core/cores/__init__.py` | Namespace docstring only; no registry. | Keep as namespace; do not add cross-Core imports. | Low risk today. |
| `src/sofia/platform/social/universal.py` | Shared social facade embeds `INTENDED_CORE_NUMBERS = {1,2,3,6,7}`, `SOFIA_DISPLAY_NAME` and `SOFIA_SLUG` (`:64`, `:69`), and validates the five-Core roster. | Keep roster policy in a platform-owned catalog/contract; avoid hardcoding the canonical display name in generic social code. | Roster/name changes require editing shared social code; duplicate source of truth with `management.py`. |
| `src/sofia/core/multicore/management.py` | Generic management snapshot embeds `EXPECTED_CORE_IDENTITIES` for only `Sofía #1`, `Mack #2`, `Nova #3` (`:89-93`). | Either extend to the approved five-Core roster or explicitly document that management covers only source Cores 1-3. Align CLI `core profiles` and tests. | Confirmed roster inconsistency; see Section 9. |

Sofia Core #1 assets must remain outside `core/cores`: Canonical Constitution,
identity, personality and avatar remain under `core/constitution`,
`core/identity`, `core/personality` and `core/embodiment`. No normalization
should move, rewrite or copy those assets into a multi-Core directory.

---

## 9. Findings

### 9.1 Confirmed drift / regressions

**No confirmed regression of Canonical Sofía identity, Constitution,
personality, emotion, memory, avatar, authorization or behavior was observed in
`1914e5d0..93d61a3f`.**

Observed facts supporting that conclusion:

- No `D` entries and no modifications under `src/sofia/core` in the audit range.
- Canonical asset blobs and manifest digest are identical at baseline and HEAD.
- `core/multicore` loads assets read-only; no write/rename/unlink operations were
  observed in `profiles.py`, `personality.py`, `emotion.py`, `vera.py` or
  `unwritten.py`.
- The new identity store explicitly protects a supplied Sofía instance UUID
  against being stored as another Core (`core/multicore/identity.py`,
  `SofiaIdentitySubstitution`).
- Modified existing source files are additive or unrelated installer work
  (Section 4).

Two confirmed **structural** issues, not baseline regressions:

1. **Roster source-of-truth mismatch.** `core/multicore/management.py:89`
   defines three expected identities (Sofía, Mack, Nova), while
   `platform/social/universal.py:64` defines five intended Core numbers
   `{1,2,3,6,7}` and the catalog documents five approved Cores. The new
   `core profiles` CLI therefore lists only three definitions, and
   `test/test_aegis_cli.py` asserts that three-item result. This is a real
   inconsistency at HEAD; it is not a change to Canonical Sofia data.
2. **Named-Core code in the generic multicore package.** `profiles.py`,
   `personality.py`, `emotion.py`, `vera.py`, `unwritten.py` and
   `core/multicore/__init__.py` mix generic infrastructure with named Core data
   as detailed in Section 8. This is ownership/structure drift, not an identity
   content change.

### 9.2 Legitimate approved enhancements

- Universal wardrobe/equipment/inventory, wearer-fit gate and gesture catalog.
- Multi-Core identity/state/lifecycle/memory/personality/emotion/routing,
  Core assets for Mack/Nova/Vera/#7, chat/social/federation/shared inference.
- SDK capability/gesture exports.
- Read-only `core profiles` CLI.
- Packaging/verification support for additional Core assets.
- Independent installer trust root and `--no-color` support (separate approved
  installer branch, not Sofia identity work).

### 9.3 Minimal corrective actions

1. **Do not modify or remove the canonical Sofia assets.** Preserve the
   existing blobs at `src/sofia/core/constitution`, `identity`, `personality`
   and `embodiment`.
2. **Add a preservation regression test** that pins the canonical asset blob
   hashes (or SHA-256 of Git blobs) at the approved baseline. This is evidence
   only and must not rewrite the assets.
3. **Normalize named-Core ownership in a separate approved change:** move
   `MACK_PROFILE`, `NOVA_PROFILE`, `VERA_PROFILE`, named personality/emotion
   profiles, `vera.py` and `unwritten.py` into `core/cores/<slug>/` modules or
   a per-Core catalog; keep only generic `CoreProfileSpec`, registry, state
   machines and asset-loading contracts in `core/multicore`. Update imports and
   tests in one bounded change.
4. **Resolve the roster source of truth:** either add Vera #6 and Unwritten #7
   to `EXPECTED_CORE_IDENTITIES` (and update the CLI test), or document and
   test that management intentionally covers only Core #1-#3. Do not silently
   change `INTENDED_CORE_NUMBERS`.
5. **Keep installer trust work separate.** The independent trust-root change is
   an approved installer behavior change; do not fold it into identity
   preservation work. Document the operational provisioning requirement.
6. **Preserve CRLF/LF digest handling:** use the canonical LF Git blob when
   verifying `constitution.sha256`; do not “repair” the checkout by rewriting
   the asset.

### 9.4 Unresolved questions

1. Should the pre-multi-Core preservation baseline be recorded as `1914e5d0`
   for all future audits, while `aegis/core-audit-baseline-2026-11-18`
   remains an audit-HEAD tag? This document uses `1914e5d0`.
2. Why do later documents cite `aeef1559` or `7ea80fb3` as their baseline, even
   though both are post-multi-Core? Are those documentation baselines or
   mistaken claims?
3. Is the three-entry `EXPECTED_CORE_IDENTITIES` intentional (only Cores with
   source profiles) or an incomplete update after the five-Core roster was
   approved?
4. Are Cores #4/#5 intentionally absent pending design, and does any later
   branch contain unmerged #4/#5 work? This audit did not claim absence outside
   the inspected refs.
5. Should `core/cores/unwritten/` ever receive personal assets, or is its
   constitution-only package permanently intentional?
6. Is `platform/installer` independent trust-root provisioning mandatory for
   existing installations, or only for new bundles? This audit records the code
   behavior, not the deployment decision.
7. Should `platform/social/universal.py` own the canonical display name, or
   should it consume a platform identity catalog? This is an ownership decision,
   not an observed failure.

---

## Appendix A — Command appendix

All commands below are read-only Git commands. They can be rerun in the audit
worktree.

```powershell
git rev-parse --abbrev-ref HEAD
git rev-parse HEAD
git log --oneline --first-parent -40
git show -s --format='%H%n%P%n%ci%n%s' 7c2f26f4
git show -s --format='%H%n%P%n%ci%n%s' c2e8d308
git merge-base --is-ancestor 1914e5d0 93d61a3f

# Absence at baseline
git ls-tree -r --name-only 1914e5d0 -- src/sofia/core/multicore
git ls-tree -r --name-only 1914e5d0 -- src/sofia/platform/chat
git ls-tree -r --name-only 1914e5d0 -- src/sofia/platform/social
git ls-tree -r --name-only 1914e5d0 -- src/sofia/platform/federation
git ls-tree -r --name-only 1914e5d0 -- src/sofia/core/cores

# First mainline introductions
git log --first-parent --reverse --format='%h %ci %s' -- src/sofia/core/multicore
git log --first-parent --reverse --format='%h %ci %s' -- src/sofia/platform/chat
git log --first-parent --reverse --format='%h %ci %s' -- src/sofia/platform/federation
git log --first-parent --reverse --format='%h %ci %s' -- src/sofia/core/cores

# Full change surface
git diff --name-status 1914e5d0 93d61a3f
git diff --stat 1914e5d0 93d61a3f -- src/sofia/core/

# Canonical asset identity
git diff --name-status 1914e5d0 93d61a3f -- `
  src/sofia/core/constitution src/sofia/core/identity `
  src/sofia/core/personality src/sofia/core/embodiment
git rev-parse 1914e5d0:src/sofia/core/constitution/constitution.md
git rev-parse 93d61a3f:src/sofia/core/constitution/constitution.md
git cat-file blob 93d61a3f:src/sofia/core/constitution/constitution.md > $env:TEMP\constitution.lf.md
Get-FileHash -Algorithm SHA256 $env:TEMP\constitution.lf.md

# Rename-aware history
git log --follow --oneline --name-status -- src/sofia/core/constitution/constitution.md
git log --follow --oneline --name-status -- src/sofia/core/identity/identity.json
git log --follow --oneline --name-status -- src/sofia/core/personality/personality.json
git log --follow --oneline --name-status -- src/sofia/core/embodiment/avatar.json
git log --follow --oneline --name-status -- src/sofia/modules/avatar/fit.py

# Migration commit shape (first parent for merges)
git diff --name-status 7c2f26f4^1 7c2f26f4
git diff --name-status 124124db^1 124124db
git diff --name-status 2d05f7aa^1 2d05f7aa
git diff --name-status 4f413dc0^1 4f413dc0
git diff --name-status 6b217d84^1 6b217d84
git diff --name-status c2e8d308^1 c2e8d308
git diff --name-status 279be70c^1 279be70c
```

Manifest digests were computed by sorting `git ls-tree -r <rev> -- <paths>`
lines, joining them with LF without a trailing newline, writing the text
UTF-8 without BOM, and applying SHA-256. Canonical paths used:
`src/sofia/core/constitution`, `identity`, `personality`, `embodiment`.
New multi-Core paths used: `src/sofia/core/multicore`, `src/sofia/core/cores`,
`src/sofia/platform/chat`, `chat_clients`, `federation`, `inference`, `social`.

## Appendix B — Evidence limits

- No test suite was run. Test behavior is inferred only from committed test
  source and the production code it imports.
- No wheel was built. `PACKAGED` claims in later docs were not re-verified.
- No installer, service, database, model provider, protected store or live
  host was touched.
- No claim is made about unmerged branches, remote-only objects or protected
  runtime state beyond the refs inspected here.
- The `constitution.md` working-tree CRLF digest differs from the canonical LF
  Git blob digest; this is a checkout representation issue, not an asset change.
- `git status` in this worktree was clean before this document was created; the
  only new path is this audit document.

---

## 10. Post-audit corrective actions applied

The lead integrator applied the following bounded changes after this audit:

1. **Roster source of truth corrected.** EXPECTED_CORE_IDENTITIES in
   src/sofia/core/multicore/management.py now contains the five approved
   Cores (#1 Sofía, #2 Mack, #3 Nova, #6 Vera, #7 Unwritten). The CLI
   core profiles projection and its test were updated accordingly. No
   canonical Sofía asset was changed.
2. **Named-Core ownership normalized.** Mack, Nova, Vera and Unwritten profile,
   personality, emotion and implementation files now live in
   src/sofia/core/{mack,nova,vera,unwritten}/; legacy imports remain through
   compatibility shims. Sofía's package now exists at src/sofia/core/sofia/
   with an inert definition factory that requires the protected runtime UUID.
3. **Canonical assets preserved.** Constitution, identity, personality and
   embodiment assets were not moved, rewritten or re-digested. A pinned
   preservation test (	est/test_sofia_preservation_snapshot.py) records the
   baseline blob digests.
4. **Per-Core database isolation added.** src/sofia/core/persistence/core_database.py
   provides UUID-keyed private databases and binds the existing memory,
   learning, reflection and continuity owners. It creates nothing at import
   time and does not migrate or touch sofia.db.
5. **Twins remain design-only.** No #4/#5 package, database or active registry
   identity was created.

These actions resolve the structural findings in Section 9. The canonical
Sofía identity/constitution/personality/avatar findings remain unchanged.
