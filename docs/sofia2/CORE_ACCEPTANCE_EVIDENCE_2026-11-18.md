# Five-Core Packaging and Acceptance Evidence â€” 2026-11-18

**Subagent:** D (packaging and acceptance)  
**Worktree:** `C:\Users\kenny\AppData\Local\Temp\opencode\core5-wt\packageqa`  
**Branch:** `aegis/core5-packageqa`  
**Base commit:** `de0ea92c` (`main`)  
**Scope:** source/package-data composition and inert registration only.

## Status vocabulary

| Status | Meaning in this document |
| --- | --- |
| DESIGNED | Approved catalog/spec/package shape exists in repository docs or code. |
| CODED | Implementation or test code exists in this worktree. |
| SOURCE_TESTED | Source-level tests passed in this worktree. |
| PACKAGED | Package-data declarations compose the asset sets. No wheel was built or installed for this evidence. |
| INSTALLED | Installed-artifact behavior was observed. **NOT CLAIMED.** |
| LIVE_VERIFIED | Live host/runtime behavior was observed. **NOT CLAIMED.** |

No test below installs a wheel, activates a Core, starts a process, mutates
`state/sofia.db`, signs a production package, or accesses owner-protected
runtime identity.

## Files changed

| File | Change |
| --- | --- |
| `src/sofia/core/multicore/packages.py` | Additive helpers only: `manifest_from_core_profile` and `blank_unwritten_package`. Existing `CorePackageManifest` schema, strict payloads and registry behavior are unchanged. |
| `test/test_core_package_five_core_acceptance.py` | New five-Core packaging/acceptance tests. |
| `docs/sofia2/CORE_ACCEPTANCE_EVIDENCE_2026-11-18.md` | This evidence record. |

## Per-Core acceptance

| Core | Design | Code | Source tested | Packaged | Installed | Live verified |
| --- | --- | --- | --- | --- | --- | --- |
| #1 SofÃ­a | Canonical constitution/identity/embodiment/personality assets exist. | Canonical owners unchanged. | Asset presence, JSON readability, constitution digest and package-data declarations tested. | Declared under `sofia.core.constitution`, `sofia.core.identity`, `sofia.core.embodiment`, `sofia.core.personality`. | NOT CLAIMED | NOT CLAIMED |
| #2 Mack | `MACK_PROFILE` and canonical assets exist. | Populated manifest composed from validated `CoreProfile`. | Manifest round-trip, asset verification, registry lookup and inert lifecycle registration tested. | Declared under `sofia.core.cores.mack` and generic `sofia.core.cores` patterns. | NOT CLAIMED | NOT CLAIMED |
| #3 Nova | `NOVA_PROFILE` and canonical assets exist. | Same populated-manifest path as Mack. | Same source tests as Mack. | Declared under `sofia.core.cores.nova` and generic patterns. | NOT CLAIMED | NOT CLAIMED |
| #4 Twin A | No approved definition. | No package/profile definition. | Absence asserted; a test-only absent-asset manifest is rejected at the lifecycle asset boundary. | NOT PACKAGED | NOT CLAIMED | NOT CLAIMED |
| #5 Twin B | No approved definition. | No package/profile definition. | Same absence/rejection tests as Twin A. | NOT PACKAGED | NOT CLAIMED | NOT CLAIMED |
| #6 Vera | `VERA_PROFILE`, `vera.py` and canonical assets exist. | Populated manifest composed from validated `CoreProfile`. | Manifest round-trip, asset verification, registry lookup and inert lifecycle registration tested. | Declared under `sofia.core.cores.vera` and generic patterns. | NOT CLAIMED | NOT CLAIMED |
| #7 Unwritten | Approved blank identity spec and neutral constitution exist. | Blank manifest helper reserves number 7 and slug `unwritten` with no descriptor or personal assets. | Blank payload, immutability conflicts, neutral constitution digest and absence of personality/avatar/voice assets tested. | Neutral `constitution.md` declared under `sofia.core.cores.unwritten`; no personal assets. | NOT CLAIMED | NOT CLAIMED |

## Observed package-data declarations

`pyproject.toml` and `packaging/components.toml` both declare:

- `sofia.core.constitution` â€” `constitution.md`, `constitution.sha256`
- `sofia.core.identity` â€” `identity.json`
- `sofia.core.embodiment` â€” `avatar.json`
- `sofia.core.personality` â€” `personality.json`
- `sofia.core.cores.mack` â€” constitution, personality, avatar, voice
- `sofia.core.cores.nova` â€” constitution, personality, avatar, voice
- `sofia.core.cores.vera` â€” constitution, personality, avatar, voice
- `sofia.core.cores.unwritten` â€” neutral `constitution.md` only
- `sofia.core.cores` â€” generic patterns for constitution, personality, avatar and voice

`sofia.platform.verify.component_artifacts.CORE_ASSET_FILES` includes all five
approved Core asset sets: canonical SofÃ­a assets, Mack, Nova, Vera and the Core
#7 neutral constitution. No Twin A/Twin B paths are present.

## Inertness observations

- Registering a package manifest or verifying assets performs no installation,
  activation, process start, stop, removal or reconciliation.
- A successful source-level lifecycle definition registration records inert
  metadata only. The test double observed zero `install`, `activate`, `stop`,
  `remove` and `reconcile` calls, and zero authorization callback calls.
- Manifest `lifecycle` remains `defined` after registration. No active lifecycle
  state is claimed.
- Blank Core #7 cannot produce a `CoreProfile` or `CoreDefinition` while blank.
- Blank Core #7 completion is constrained to the same UUID, number and slug.

## Commands and results

Environment prepared per worktree instructions:

```powershell
$env:PYTHONPATH=(Resolve-Path src).Path
& "\\Artemis\Hestia\Users\Crazysodaman\Programing\SofiaAdaLyra\.venv\Scripts\python.exe" -m pytest -q test/test_core_package_five_core_acceptance.py
```

Result:

```text
......                                                                   [100%]
6 passed in 1.91s
```

Required targeted suite:

```powershell
$env:PYTHONPATH=(Resolve-Path src).Path
& "\\Artemis\Hestia\Users\Crazysodaman\Programing\SofiaAdaLyra\.venv\Scripts\python.exe" -m pytest -q test/test_core_package_five_core_acceptance.py test/test_core_multicore_packages.py test/test_aegis_five_core_completion.py test/test_core_multicore_profiles.py test/test_core_multicore_vera.py
```

Result:

```text
....................................................                     [100%]
52 passed in 7.55s
```

Breakdown: 6 new acceptance tests plus 46 pre-existing tests in the four
required adjacent suites. Pre-existing tests were not modified.

Related component-artifact probe (not required by this subagent, run for
evidence; it exercises wheel staging):

```powershell
$env:PYTHONPATH=(Resolve-Path src).Path
& "\\Artemis\Hestia\Users\Crazysodaman\Programing\SofiaAdaLyra\.venv\Scripts\python.exe" -m pytest -q test/test_component_artifact_separation.py
```

Result:

```text
1 failed, 1 passed, 14 errors in 47.73s
```

Observed cause: `component_artifacts._stage_component` treats the generic
`sofia.core.cores` package-data patterns (`*/constitution.md`,
`*/personality.json`, `*/avatar.json`, `*/voice.json`) as literal asset paths,
so component wheel staging stops at
`missing declared asset: ...\src\sofia\core\cores\*\constitution.md`. This is a
pre-existing packaging-plumbing issue in files outside this subagent's ownership
(`packaging/components.toml` and
`src/sofia/platform/verify/component_artifacts.py`), not caused by these
additive helpers. It blocks wheel-level `PACKAGED` verification.

## Environment note

The Windows checkout materializes `src/sofia/core/constitution/constitution.md`
with CRLF line endings. The recorded `constitution.sha256` value
(`f30afedf195f77907d32a108ca35d4db751646bde3fd902be66e7b78f4b89dc0`) matches the
canonical LF Git blob, not the CRLF working-tree bytes
(`67167e585c6da08559fe22065db5c75b9a18318867ecb1cbedc30ac8c1111565`). The
acceptance test compares the digest after canonical LF normalization. This is a
checkout representation note, not an installed-wheel observation.

## Blockers and limits

- No wheel was built successfully for this evidence, so `PACKAGED` is limited to
  source package-data declarations. `test_component_artifact_separation.py`
  currently fails during wheel staging because generic `sofia.core.cores`
  package-data patterns are interpreted as literal paths by
  `src/sofia/platform/verify/component_artifacts.py`. Those files are outside
  this subagent's ownership and were not modified.
- `INSTALLED` and `LIVE_VERIFIED` are not claimed.
- Canonical production UUIDs, model/provider defaults, signing and activation
  authority remain outside this work.
- Twins #4/#5 remain unapproved, unassembled and unpackaged.
- Core #7 personal identity remains intentionally unselected.

