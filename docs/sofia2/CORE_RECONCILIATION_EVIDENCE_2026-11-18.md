# Core Reconciliation Evidence — 2026-11-18

**Audit type:** Phase 1 evidence-only reconciliation audit  
**Worktree audited:** `C:\Users\kenny\AppData\Local\Temp\opencode\core5-wt\reconcile`  
**Branch:** `aegis/core5-reconcile`  
**Evidence classes used:** OBSERVED, INFERRED, UNKNOWN  
**Authority:** This document records repository evidence only. It does not create
owner decisions, grant authority, install packages, or claim live verification.

An observation is a file read, Git object inspected, hash computed, or command
executed in this worktree. Inference is limited to what those observations
support. No claim of nonexistence is made from denied access.

## 1. Repository and baseline observed

OBSERVED via `git remote -v`:

- `origin` fetch: `https://github.com/Crazysodaman/SofiaAdaLyra.git`
- `origin` push: `https://github.com/Crazysodaman/SofiaAdaLyra.git`

OBSERVED via `git rev-parse` and `git log`:

| Ref | SHA | Note |
| --- | --- | --- |
| `aegis/core5-reconcile` HEAD | `de0ea92cb0da6e39e32c0802e5991594c3a74e43` | Audit branch |
| local `main` | `de0ea92cb0da6e39e32c0802e5991594c3a74e43` | Same commit as audit branch |
| local ref `origin/main` | `aeef1559dc6eb58fa0b829aca73476d76a6f9eb4` | Remote tip observed by `git fetch` before the final five-Core push |
| parent of `de0ea92c` | `aeef1559dc6eb58fa0b829aca73476d76a6f9eb4` | Commit is one commit ahead of the parent |

OBSERVED commit:

- `de0ea92c feat(multicore): reconcile five Core identities and add blank Core #7 bootstrap`
- Author/commit date shown by Git: `2026-11-18 18:33:57 -0600`

OBSERVED documentation baselines differ:

- `docs/sofia2/CORE_CATALOG_V1.md:5` records baseline main as `aeef1559`.
- `docs/sofia2/AEGIS_CORES_6_7_IMPLEMENTATION_V1.md:7` records baseline main as `7ea80fb3`.
- The current worktree HEAD is `de0ea92c`.

OBSERVED: a later `git fetch origin` before the final push still reported
`origin/main = aeef1559`. The catalog documents the parent baseline and the
integration document documents an older workstream baseline. Neither is a
claim about installed or live deployment.

## 2. Per-Core matrix

Column meanings:

- **DESIGN_PRESENT:** an approved or revision-controlled design/specification
  exists in Git.
- **CODE_PRESENT:** Core-specific source or canonical profile code exists in Git.
- **TESTED:** committed test code exists and asserts the behavior. Targeted
  tests were executed in this audit where listed in section 8. No installed,
  signed, live-host, model-process, or GPU test was executed.
- **PACKAGED:** source/package-data or package-manifest coverage is declared in
  Git. This is not a built wheel, signed artifact, installation, or activation.

| Core | DESIGN_PRESENT | CODE_PRESENT | TESTED | PACKAGED |
| --- | --- | --- | --- | --- |
| #1 Sofía Ada Lyra | Yes | Yes | Yes: canonical core/application tests observed; not re-executed in this audit | Yes: `sofia.core.constitution`, `sofia.core.identity`, `sofia.core.embodiment`, `sofia.core.personality` package data |
| #2 Mack Fuller | Yes | Yes | Yes: profile/personality/emotion/memory/identity tests; 13 profile/roster tests and 40 personality/emotion/memory/identity tests passed in this audit | Yes: `sofia.core.cores.mack` package data; `CorePackageManifest` pattern |
| #3 Nova Arden | Yes | Yes | Yes: same suites as Mack; same targeted passes | Yes: `sofia.core.cores.nova` package data; `CorePackageManifest` pattern |
| #4 Twin A | No approved Core-specific definition in main; catalog says UNDER DESIGN | No Core-specific implementation | N/A | No |
| #5 Twin B | No approved Core-specific definition in main; catalog says UNDER DESIGN | No Core-specific implementation | N/A | No |
| #6 Vera S-039 | Yes | Yes | Yes: Vera suite plus armor/roster/package tests; 16 Vera tests and supporting suites passed in this audit | Yes: `sofia.core.cores.vera` package data; `CorePackageManifest` pattern |
| #7 Unwritten | Yes | Yes | Yes: blank identity, growth, STOP, package, integration tests; 29 Unwritten tests and supporting suites passed in this audit | Yes: blank package manifest plus `sofia.core.cores.unwritten` neutral constitution package data; no personal assets |

OBSERVED caveat for #1: there is no `SOFIA_PROFILE` entry in
`src/sofia/core/multicore/profiles.py`; `DEFAULT_CORE_PROFILES` registers only
Mack, Nova, and Vera (`profiles.py:594-597`). Sofía's identity is owned by the
canonical core packages (`src/sofia/core/identity`, `constitution`,
`personality`, `embodiment`), and #1 is supplied separately to the universal
roster.

## 3. Exact evidence paths

### Core #1 — Sofía

- Constitution: `src/sofia/core/constitution/constitution.md`
- Constitution digest: `src/sofia/core/constitution/constitution.sha256`
- Identity asset: `src/sofia/core/identity/identity.json`
  - OBSERVED literal: `"instance_id": "a9a0a604-a4e7-4a88-a985-3f071e2c8e7d"`.
  - UNKNOWN: whether this `instance_id` is the canonical Core UUID. The catalog
    separately calls the Core UUID protected runtime state.
- Personality asset: `src/sofia/core/personality/personality.json`
- Embodiment asset: `src/sofia/core/embodiment/avatar.json`
- Plan: `docs/sofia2/CORE_1_0_PLAN.md`
- Tests (observed, not all re-executed):
  `test/test_constitution.py`, `test/test_constitution_integrity.py`,
  `test/test_identity.py`, `test/test_personality.py`,
  `test/test_embodiment.py`, `test/test_aegis_five_core_completion.py`
- Packaging:
  `pyproject.toml:36-42`, `packaging/components.toml` `[components.core]`
  package data, and `src/sofia/platform/verify/component_artifacts.py:31-49`.

### Core #2 — Mack Fuller

- Profile: `src/sofia/core/multicore/profiles.py:145-154` (`MACK_PROFILE`,
  full name `Mack Fuller`, core number 2).
- Assets: `src/sofia/core/cores/mack/constitution.md`,
  `personality.json`, `avatar.json`, `voice.json`.
- Numeric personality profile: `src/sofia/core/multicore/personality.py:403`
  (`MACK_FULLER_PROFILE`).
- Numeric emotion profile: `src/sofia/core/multicore/emotion.py:231`
  (`MACK_EMOTION_PROFILE`).
- Voice: `src/sofia/core/cores/mack/voice.json:10` records
  `"assets_created": false` and `"model_id": null`.
- Tests: `test/test_core_multicore_profiles.py`,
  `test/test_core_multicore_personality.py`,
  `test/test_core_multicore_emotion.py`,
  `test/test_core_multicore_memory.py`,
  `test/test_core_multicore_identity.py`,
  `test/test_aegis_five_core_completion.py`.
- Packaging: `pyproject.toml:43-48`, `packaging/components.toml`
  (`sofia.core.cores.mack`), and `component_artifacts.py` `CORE_ASSET_FILES`.

### Core #3 — Nova Arden

- Profile: `src/sofia/core/multicore/profiles.py:156-168` (`NOVA_PROFILE`,
  full name `Nova Arden`, core number 3).
- Assets: `src/sofia/core/cores/nova/constitution.md`,
  `personality.json`, `avatar.json`, `voice.json`.
- Numeric personality profile: `src/sofia/core/multicore/personality.py:426`
  (`NOVA_ARDEN_PROFILE`).
- Numeric emotion profile: `src/sofia/core/multicore/emotion.py:245`
  (`NOVA_EMOTION_PROFILE`).
- Voice: `src/sofia/core/cores/nova/voice.json:10` records
  `"assets_created": false` and `"model_id": null`.
- Tests: same multicore suites as Mack, plus roster/packaging tests in
  `test/test_aegis_five_core_completion.py`.
- Packaging: `pyproject.toml:49-54`, `packaging/components.toml`
  (`sofia.core.cores.nova`), and `component_artifacts.py` `CORE_ASSET_FILES`.

### Cores #4 and #5 — Twin A and Twin B

- No directories under `src/sofia/core/cores/` for #4 or #5. OBSERVED directory
  set: `mack`, `nova`, `vera`, `unwritten`.
- No profile specs for #4/#5: `DEFAULT_CORE_PROFILES.specs()` covers `{2, 3, 6}`
  (`test/test_aegis_five_core_completion.py:289-301`).
- `src/sofia/platform/social/universal.py:64-65`:
  `INTENDED_CORE_NUMBERS = frozenset({1, 2, 3, 6, 7})` and
  `PROHIBITED_CORE_NUMBERS = frozenset({4, 5})`.
- The same test asserts `build_universal_participant` raises for numbers 4 and 5.
- No #4/#5 package manifest or package data is declared in `pyproject.toml`,
  `packaging/components.toml`, or `component_artifacts.py`.
- No design specification for either twin was found in `docs/sofia2`; only the
  catalog says UNDER DESIGN. Absence of other design material is UNKNOWN.

### Core #6 — Vera S-039

- Profile: `src/sofia/core/multicore/profiles.py:171-...` (`VERA_PROFILE`,
  core number 6).
- Core module: `src/sofia/core/multicore/vera.py` (identity, appearance
  authority, asset loading, callsign metadata, authority boundary).
- Assets: `src/sofia/core/cores/vera/constitution.md`,
  `personality.json`, `avatar.json`, `voice.json`.
- Voice: `src/sofia/core/cores/vera/voice.json` records text-only mode,
  `"assets_created": false`, `"model_id": null`.
- Armor: `src/sofia/core/cores/vera/avatar.json` closes with an external,
  reference-only armor hook. Canonical armor configurations are in
  `src/sofia/modules/avatar/wardrobe_equipment.py:1116-1150`:
  `cqb`, `mark_iv`, `odst`.
- Tests: `test/test_core_multicore_vera.py` (16 test functions),
  `test/test_core_multicore_v6_v7_integration.py`, and
  `test/test_aegis_five_core_completion.py`.
- Packaging: `pyproject.toml:55-60`, `packaging/components.toml`
  (`sofia.core.cores.vera`), and `component_artifacts.py` `CORE_ASSET_FILES`.

### Core #7 — Unwritten

- Specification: `docs/sofia2/CORE_7_UNWRITTEN_SPEC_V1.md`.
- Implementation: `src/sofia/core/multicore/unwritten.py`,
  `src/sofia/core/multicore/packages.py`,
  `src/sofia/core/multicore/v6_v7_acceptance.py`.
- Neutral constitution: `src/sofia/core/cores/unwritten/constitution.md`.
- Blank package contract: `CorePackageManifest(blank_identity=True)` rejects a
  descriptor, personal assets, avatar/voice presence, and active lifecycle
  (`packages.py:260-272`, `414-415`).
- Tests: `test/test_core_multicore_unwritten.py` (29 test functions),
  `test/test_core_multicore_packages.py`,
  `test/test_core_multicore_v6_v7_integration.py`,
  `test/test_aegis_five_core_completion.py`.
- Packaging: `pyproject.toml:61-63` ships only `constitution.md`;
  `packaging/components.toml` mirrors that; `component_artifacts.py`
  `CORE_ASSET_FILES` includes `sofia/core/cores/unwritten/constitution.md`.

### Asset hash observations

OBSERVED SHA-256 prefixes computed in this worktree:

| Asset | SHA-256 prefix |
| --- | --- |
| `src/sofia/core/cores/mack/constitution.md` | `7EC3198238D67B31` |
| `src/sofia/core/cores/mack/personality.json` | `B0F8E939CBEACA36` |
| `src/sofia/core/cores/mack/avatar.json` | `B9171A28D7F88CC2` |
| `src/sofia/core/cores/mack/voice.json` | `AE86413ACC754348` |
| `src/sofia/core/cores/nova/constitution.md` | `54D9DAFF138032BC` |
| `src/sofia/core/cores/nova/personality.json` | `533A65F65CBD77B2` |
| `src/sofia/core/cores/nova/avatar.json` | `DA8568EC992B07B9` |
| `src/sofia/core/cores/nova/voice.json` | `E183A5CDF49A945F` |
| `src/sofia/core/cores/vera/constitution.md` | `25528BDA02EEDD72` |
| `src/sofia/core/cores/vera/personality.json` | `76E255322503EE2C` |
| `src/sofia/core/cores/vera/avatar.json` | `286409243DD7C24F` |
| `src/sofia/core/cores/vera/voice.json` | `B7D33B5CC755946F` |
| `src/sofia/core/cores/unwritten/constitution.md` | `8F33136FAC4493C7` |

## 4. Missing owner decisions

These are not inferred or filled in by this audit.

1. **Canonical production UUID for Core #7 — OWNER DECISION REQUIRED.**
   `docs/sofia2/CORE_7_UNWRITTEN_SPEC_V1.md:22` says no production UUID is
   recorded in Git. Source tests use disposable IDs, e.g.
   `test/test_aegis_five_core_completion.py:54-60` uses
   `77777777-7777-4777-8777-777777777777`.
2. **Canonical production UUIDs for Cores #2, #3, #6 — OWNER DECISION
   REQUIRED / UNKNOWN.** The profile factories require a caller-supplied UUID
   and tests assert no hardcoded production UUID
   (`profiles.py:437`; `test/test_core_multicore_profiles.py:197`). No
   versioned production UUID for these Cores was found.
3. **Sofía Core UUID status — UNKNOWN.** `identity.json` contains an
   `instance_id` literal (section 3), but whether that is the canonical Core
   UUID or a separate installation instance identifier is not proven by the
   inspected evidence.
4. **Canonical per-Core model/provider defaults — OWNER DECISION REQUIRED.**
   `continuity.py` records runtime `model_id`/`provider_id`, and
   `profiles.py` embeds no model. No per-Core default model/provider was found
   in the audited core/multicore source. A global runtime default was not
   located in the inspected paths; its existence elsewhere is UNKNOWN.
5. **Any personal identity choices for #7 — intentionally unselected.**
   Name, nickname, gender, species, age, avatar, voice, measurements, colors,
   hobbies, personality archetype, autobiography, relationships, and
   preferences must remain unselected until evidence and owner-approved
   revision. None were invented here.
6. **Vera personal choices.** Surname remains `null` and
   `surname_selected: false` (`src/sofia/core/cores/vera/personality.json`).
   Voice is text-only/deferred. `personality.json` contains numeric
   `inspiration` percentages (50/50/0 for named references). Whether those
   percentages are the approved final values or an undocumented provisional
   choice is UNKNOWN; no owner authorization record was found in the inspected
   material.
7. **Voice/avatar/renderer assets — OWNER/HOST DECISION REQUIRED for
   production.** Mack/Nova/Vera voice files are metadata only with
   `assets_created: false`; avatar files are descriptive JSON geometry/material
   metadata, not rendered meshes. No per-Core voice model or renderer asset was
   observed. A shared 2D candidate archive exists at
   `src/sofia/modules/avatar/assets/sofia2d_public_illustrated_candidates_v1.zip`,
   but no evidence ties it to an installed Core avatar.
8. **Signing, install, and live activation — OWNER DECISION REQUIRED.**
   `CORE_7_UNWRITTEN_SPEC_V1.md:106-108` states PACKAGED is source/package-data
   only and that INSTALLED and LIVE_VERIFIED are not claimed.
   `AEGIS_CORES_6_7_IMPLEMENTATION_V1.md:181-189` lists no real signed package
   install or live host. This audit confirmed no signed/installed/live claim.
9. **Mack/Nova Constitution amendment authorization — OWNER/PROTECTED
   PROCESS DECISION REQUIRED.** See section 5.

## 5. Protected amendment issue: Mack/Nova Constitution framing

OBSERVED text in `src/sofia/core/cores/mack/constitution.md:4-6` and
`src/sofia/core/cores/nova/constitution.md:4-6`:

> This is [Core]'s personal constitution. It governs [Core]'s own conduct and
> continuity. It does not replace, amend or outrank the canonical constitution
> of Sofía Ada Lyra, the Platform's authority boundary, or the owner's
> legitimate administrative authority.

OBSERVED claim in `docs/sofia2/CORE_CATALOG_V1.md:40-41`:

> Mack/Nova Constitution text frames Sofía's personal Constitution as superior...
> amendment requires the protected review process.

Audit finding:

- The observed text contains a **deference/subordination clause** ("does not
  replace, amend or outrank") rather than the literal word "superior."
- Whether this clause is the intended "superiority framing" and whether it
  requires amendment is an **owner decision under the protected amendment
  process**.
- This audit does not edit, reinterpret, or silently correct the text.
- INFERRED scope note: the same deference clause also appears in
  `src/sofia/core/cores/vera/constitution.md:4-6` and
  `src/sofia/core/cores/unwritten/constitution.md:8-10`. If amendment is
  required, the catalog's stated scope (Mack/Nova only) may be narrower than the
  actual textual pattern. That is a question for the owner, not a change.

## 6. GitHub issue access status

OBSERVED: `gh auth status` returned:

> You are not logged into any GitHub hosts. To log in, run: `gh auth login`

Therefore:

- Issue **#260** and all other GitHub issue evidence are **OUTSIDE SCOPE /
  UNKNOWN**.
- No issue was accessed, quoted, or characterized.
- This audit does not claim that issue #260 or any other issue is nonexistent,
  closed, or resolved.
- No push, PR, or GitHub API mutation was attempted.

## 7. Cores #4 and #5 confirmation

OBSERVED:

- `DEFAULT_CORE_PROFILES` contains only Mack (#2), Nova (#3), and Vera (#6).
- The `src/sofia/core/cores` directory contains only `mack`, `nova`, `vera`,
  and `unwritten`.
- `universal.py` explicitly prohibits numbers 4 and 5 and tests assert
  participant construction raises for both.
- The five-Core package test registers manifests only for #2, #3, #6, and #7.
- No #4/#5 source module, profile, asset directory, package manifest, or
  package-data entry was found.

INFERRED: #4/#5 are placeholder numbers only. No Core-specific identity,
personality, asset, package, or test contract may be inferred for them.

RESOLVED inconsistency (not a #4/#5 issue):
The audit observed `universal.py` still defining
`DESIGN_ONLY_CORE_NUMBERS = frozenset({6})`. The lead integrator subsequently
removed the permanent design-only label after all five approved Cores gained
source implementations. `DESIGN_ONLY_CORE_NUMBERS` is now empty; tests assert
Vera is not design-only. This is a source decision recorded in the merged
commit, not a claim of installed activation.

## 8. Test-command appendix

All tests below were run from the audit worktree with the project virtual
environment interpreter. They use temporary state (`canonical_state_path`
writes `tmp_path/sofia.db`) and do not touch production `state/sofia.db`.

OBSERVED results in this audit:

```text
python -m pytest -q test/test_core_multicore_profiles.py \
  test/test_aegis_five_core_completion.py::test_five_distinct_immutable_identities_compose_without_cloning \
  test/test_aegis_five_core_completion.py::test_twins_and_unapproved_numbers_have_no_core_definitions \
  test/test_aegis_five_core_completion.py::test_packaging_covers_all_five_approved_cores

13 passed
```

```text
python -m pytest -q test/test_core_multicore_unwritten.py \
  test/test_core_multicore_vera.py \
  test/test_core_multicore_packages.py \
  test/test_core_multicore_v6_v7_integration.py

71 passed
```

```text
python -m pytest -q test/test_core_multicore_personality.py \
  test/test_core_multicore_emotion.py \
  test/test_core_multicore_memory.py \
  test/test_core_multicore_identity.py

40 passed
```

Total observed in this audit: **124 passed**, 0 failed.

Inspection commands used (not tests):

```text
git -c safe.directory=<worktree> -C <worktree> rev-parse --abbrev-ref HEAD
git -c safe.directory=<worktree> -C <worktree> rev-parse HEAD
git -c safe.directory=<worktree> -C <worktree> remote -v
git -c safe.directory=<worktree> -C <worktree> log --oneline -20
git -c safe.directory=<worktree> -C <worktree> log --oneline <branch>
git -c safe.directory=<worktree> -C <worktree> log --all --oneline --grep=...
Get-FileHash -Algorithm SHA256 <asset>
gh auth status
```

Not executed:

- No installed-wheel or `SOFIA_VERIFY_INSTALLED_ONLY=1` suite.
- No live Ollama/model, GPU, Fleet, or Platform host test.
- No signed package build, install, activation, or recovery.
- No production state mutation.
- No push or PR.

## 9. History evidence for Cores #4/#5/#6/#7 and named branches

OBSERVED commits/branches relevant to this reconciliation:

| Branch | Tip observed | Relevant commit |
| --- | --- | --- |
| `aegis/v7-unwritten` | `2ce9e40e` | `feat(multicore): add blank evidence-developed Core #7 identity` |
| `aegis/v6-core-package` | `499afdda` | `feat(core): add inert installable Core package manifests` |
| `aegis/v6-v7-final` | `af69872f` | `fix(packaging): include Vera assets in Core component manifest` |
| `aegis/v6-vera-identity` / related | (observed in history) | `feat(multicore): add Vera Core #6 identity, assets and appearance autonomy` |
| current branch | `de0ea92c` | Five-Core reconciliation and #7 bootstrap |

OBSERVED integration history includes:
`2ce9e40e` (#7 blank identity), `499afdda` (inert package manifests),
`0da40ce7` (Vera assets/blank package integration), `3ed8b309` (Core #6/#7
integration QA), `af69872f` (Vera packaging fix), `1a1c13b9` (Vera identity in
mainline history), and `de0ea92c` (five-Core reconciliation).

No commit was found that introduces Core-specific #4/#5 definitions, assets, or
packages. A search for twin/Core #4/Core #5 commit messages returned unrelated
"digital twin" operations work, not Aegis Cores #4/#5.

## 10. Audit conclusion

- The five approved Core identities in the audited HEAD are #1, #2, #3, #6, and
  #7.
- #2, #3, #6, and #7 have committed design, Core-specific code, tests, and
  source/package-data coverage. #1 has canonical core assets, code, tests, and
  package data outside the multicore profile registry.
- #4 and #5 remain prohibited placeholders with no Core-specific definitions and
  must not be inferred.
- The largest open items are owner decisions, not code defects: #7's production
  UUID, all production Core UUIDs, per-Core model/provider defaults, and
  voice/avatar/signing/install authorization.
- Mack/Nova Constitution framing is a protected amendment question. It was
  flagged, not silently changed.
- GitHub issue evidence (including #260) is OUTSIDE SCOPE / UNKNOWN because
  `gh` is unauthenticated.
