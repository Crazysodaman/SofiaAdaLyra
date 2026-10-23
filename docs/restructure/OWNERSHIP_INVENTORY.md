# Repository restructure: Phase 1 ownership inventory

**Baseline commit (immutable):** `987859c9` ("Core 1 final", tag
`core-1-restructure-baseline`). Working tree clean at audit time
(2026-10-22, America/Chicago). Codex's worktree
(`SofiaAdaLyra-all-packages`, detached `1cf6e9e3`) contains only runtime
state churn (`sofia.db`, `state/*`), no source modifications — nothing
needs preservation beyond leaving that worktree untouched. Fleet
worktree (`test/fleet-tray-remote-controls`, `8b55a6c0`) likewise holds
only `state/sofia.db` churn and a pytest temp dir. The OpenCode temp
worktree `wt-1673fa8e` is a disposable scratch checkout (attaches to an
old `main` commit; preserves nothing unreproducible).

No destructive Git operations are used below; packages move with
`git mv` (history preserved), and imports are rewritten by a mechanical
sweep with old-path verification.

## Observed scale

- 63 top-level packages under `src/sofia`, 798 Python files.
- 776 Python test files under `test/`.
- 6,033 `sofia.<pkg>` import sites across code + tests.
- Packaging: single root package via `[tool.setuptools.packages.find]
  where=src`; interior package moves preserve the install model.
  Package-data globs referencing moved packages need one-time updates
  (constitution, identity, embodiment, personality, ui, avatar).
- No `[project.scripts]` console entry points exist.

## Classification (evidence-based)

Legend: **CORE** = identity/cognition/personality/memory/emotion/social/
perception/learning; **PLATFORM** = runtime/state/authority/execution/
fleet/releases/infrastructure; **CARDS** = functioning companion or
capability cards that the ownership matrix treats as modules (bundled
today, future standalone).

| Old path (sofia.*) | New path | Owner | Notes |
| --- | --- | --- | --- |
| modules | core.modreg | CORE | Core-side SMBA module registry/self-model/proposals/workshop (renamed first to free `modules` for real module cards) |
| application | platform.application | PLATFORM | Composition root + bootstrap (Platform owns composition/heartbeat per ARCHITECTURE §Platform) |
| state | platform.state | PLATFORM | canonical `sofia.db` writer |
| config | platform.config | PLATFORM | shared configuration infrastructure |
| composition | platform.composition | PLATFORM | |
| runtime | platform.runtime | PLATFORM | |
| run | platform.run | PLATFORM | supervision, leases, periodic work |
| operational | platform.operational | PLATFORM | |
| system | platform.system | PLATFORM | |
| clean | platform.clean | PLATFORM | workspace/runtime cleanup |
| authority | platform.authority | PLATFORM | |
| authorization | platform.authorization | PLATFORM | |
| safe | platform.safe | PLATFORM | |
| capability | platform.capability | PLATFORM | CapabilitySystem/Gateway (no duplicate gateways) |
| act | platform.act | PLATFORM | RUN/ACT effect broker |
| action | platform.action | PLATFORM | |
| verify | platform.verify | PLATFORM | release gate (PLAT-08) |
| ops | platform.ops | PLATFORM | fleet/ops control plane |
| machine | platform.machine | PLATFORM | |
| net | platform.net | PLATFORM | |
| distributed | platform.distributed | PLATFORM | |
| filesystem | platform.filesystem | PLATFORM | file-change observation infra |
| dev | platform.dev | PLATFORM | bounded engineering executor infrastructure |
| evolve | platform.evolve | PLATFORM | evolution lifecycle/approvals infrastructure |
| identity | core.identity | CORE | |
| constitution | core.constitution | CORE | |
| beliefs | core.beliefs | CORE | |
| personality | core.personality | CORE | |
| cognition | core.cognition | CORE | |
| conversation | core.conversation | CORE | |
| communication | core.communication | CORE | |
| memory | core.memory | CORE | |
| rel | core.rel | CORE | impressions/repair merge here |
| social | core.social | CORE | principals/audiences |
| emotion | core.emotion | CORE | |
| agency | core.agency | CORE | |
| self_model | core.self_model | CORE | personal self-model + limits |
| codebase | core.codebase | CORE | CORE-35 authorized code inspection |
| learning | core.learning | CORE | |
| habits | core.habits | CORE | |
| goals | core.goals | CORE | |
| life | core.life | CORE | |
| creative | core.creative | CORE | motivation/project intent (Forge effects stay model-side) |
| generalization | core.generalization | CORE | |
| environment | core.environment | CORE | ambient perception evidence |
| knowledge | core.knowledge | CORE | reviewed external references |
| know | core.know | CORE | |
| continuity | core.continuity | CORE | |
| mentor | core.mentor | CORE | evaluation feedback evidence |
| embodiment | core.embodiment | CORE | canonical avatar.json presentation data |
| body | core.body | CORE | body state aggregation (Gaia hardware stays card-side) |
| neuro | core.neuro | CORE | neuro state token plumbing |
| avatar | modules.avatar | CARDS | functioning RM-AVATAR2D implementation (2D renderer/wardrobe/scene) |
| ui | modules.ui | CARDS | functioning RM-DESKTOP client surfaces |
| discord | modules.discord | CARDS | functioning RM-DISCORD transport |
| voice | modules.voice | CARDS | functioning RM-VOICE speech runtime |
| vision | modules.vision | CARDS | consent-based screen/env perception card |
| interaction | modules.interaction | CARDS | avatar interaction semantics (MOD-INTERACTION) |
| integrations | modules.integrations | CARDS | typed service adapters |
| integrate | modules.integrate | CARDS | adapter stubs (JMRI/cloudflare etc.) |
| mobile | modules.mobile | CARDS | Android companion candidate |
| data | (removed from migration) | — | 0 files (unused empty dir; left untouched, recorded unused) |
| external | (removed from migration) | — | 0 files (unused; recorded) |

Known cross-area couplings to record (not silently broken):
- `platform.application` composes Core services and CARDS (guarded
  optional-module imports are a B08 goal; composition currently imports
  cards directly — recorded as a B08 acceptance item, not a migration
  regression).
- `core.cognition` may import `platform.state`/`platform.config` —
  allowed direction (Core consumes Platform infra; Platform never
  imports Core behavioral packages except the composition root's
  registration seams).
- `core.embodiment` data plus `modules.avatar`'s wardrobes: data stays
  canonical on Core; cards consume it.

## Sweep scope (mechanical rewrite)

- `src/**/*.py`, `test/**/*.py`, `scripts/*.py`
- `pyproject.toml` package-data globs
- `.github/workflows/*.yml` path references
- `docs/sofia2/*.md` (active specs only; historical ledger gets an
  append-only note, not a rewrite of history)

Verification per batch: `compileall`, import sweep (rg for stale
`sofia.<moved>` at old top-level), targeted affected suites, and one
full `pytest -q` after the final card batch.
