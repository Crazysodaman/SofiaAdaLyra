# Phases 00 + 01: canonical owners and release/CI source audit

**Review date:** 2026-10-10  
**Reviewed ref:** `main` at `e85c52f01a6fc4ec67c05ed4dade2752755bcf0b` before these changes  
**Status:** Targeted source repairs and architecture inventory implemented; **no tests, CI jobs or live checks manually run**. This is not an acceptance certificate.  
**Work policy:** No new branches; source edits on `main`. Phases 00 and 01 progress concurrently; do not represent all 131 V18 items as complete.

## Phase 00: source-of-truth and reuse map

| Concern | Canonical owner found in current source | Reuse decision / boundary |
| --- | --- | --- |
| Application composition | `src/sofia/application/bootstrap.py` (`SofiaApplication`) | Reuse one process-owned runtime and channel adapters; avoid a second companion brain. |
| Cognition and model selection | `src/sofia/cognition/routing.py`, `src/sofia/composition/engines.py`, `src/sofia/cognition/model_lifecycle.py` | Reuse primary/secondary routing and residency; distinct provider models must not own identity or authority. |
| Conversation truth | `src/sofia/conversation/store.py`, `src/sofia/application/conversation_service.py` | Reuse durable sessions, message IDs and explicit resume. The service currently loads complete session history in some paths; decades-scale paged recall is future work, not this patch. |
| Principal/audience policy | `src/sofia/social/store.py`, `src/sofia/social/principals.py` | Preserve principal AND audience binding. A future cross-device Main thread needs an authenticated projection, not silent identity conflation. |
| Durable state | `src/sofia/state/sqlite_plane.py`, `src/sofia/config/layout.py` | `sofia.db` is the configured canonical state plane; `SOFIA_STATE_ROOT` is already supported. Do not fork writers or copy an open WAL database by hand. |
| Backup and protected identity | `src/sofia/ops/backup.py`, `src/sofia/ops/backup_topology.py` | Reuse staged verified SQLite snapshots and encrypted state bundle. This is distinct from live failover or safe relocation. |
| Emotion and relationship | `src/sofia/emotion/journal.py`, `src/sofia/application/emotional_conversation.py`, `src/sofia/rel/store.py` | Keep one source-linked emotional timeline. Never treat a model reaction as proven physical feeling or consent. |
| Memory promotion | `src/sofia/application/conversation_learning.py`, `src/sofia/application/memory_review.py`, `src/sofia/memory/system.py` | Reuse proposed/reviewed provenance; candidates are not trusted facts until promoted. |
| Independent LIFE and goals | `src/sofia/life/coordinator.py`, `src/sofia/application/bootstrap.py` | Reuse GOALS/RUN/SAFE receipt path; still require independent critique and live completion proof. |
| Operator authority | `permission.md`, `src/sofia/safe/permissions.py` | SAFE decisions remain external to LLM text. Never grant model-based permission from a conversation or observation. |
| Fleet and workload migration | `src/sofia/distributed/state_paths.py`, `src/sofia/ops/migration.py` | Reuse canonical fleet state + existing workload migration leases; *workload* migration is not a verified canonical SQLite database relocation. |
| Verification and release | `src/sofia/verify/gate.py`, `src/sofia/dev/release_cli.py`, `.github/workflows/*` | Reuse existing deterministic verification and evidence schema. No alternative CI owner needed. |

### Architectural constraints confirmed

1. **One canonical persistent identity, state database and permission authority.** Desktop, Discord, mobile and later Linux appliance are authenticated interfaces or workers, not independent companions.
2. **One accepted semantic decision owner per turn.** Preserve current Cognition v2 / Matrix ownership; verify production call chains later rather than reviving legacy ones.
3. **Lifelong Main + optional project threads**, source-linked memory tiers, modeled emotions and user corrections remain separate persistent objects but share one canonical authority.
4. **Option A is current:** AI operating layer on normal OS services. **Option B is future:** a dedicated Linux appliance only after compatibility/recovery gates. No custom kernel.
5. **Consequence != observation:** successful action requires verified executor evidence; visual observations, NEURO suggestions and model opinions are not permission or execution receipts.

### Reuse vs removal review

- **Reuse now:** configuration, SQLite state plane, backups, source-linked journals, reviewed memories, SAFE grants, Cognition v2, current verification gate.
- **Defer deletion:** v1 compatibility paths, older tests, archive/import adapters, fallback projections and apparent duplicate utilities. No static grep is enough to prove they are unused across Windows services, serialized data, CLI entry points or Fleet.
- **Candidate cleanup (audit required):** historical status claims in the root `ROADMAP.md` and duplicated narrative documents; do not delete references needed for forensics. Classify each future removal by `unreachable / compatibility / serialized owner / still wired` and preserve migration/replay evidence.
- **Missing production guarantees:** one user Main timeline across transport types, lifelong indexed paged history, single-writer failover with independent fencing, human-guided canonical DB relocation, screen vision and self-governed LLM promotion. These remain future phase work.

## Phase 01: current CI and Windows source findings

**Observed GitHub Actions at reviewed ref:**
- Package matrix **20/22 jobs passed**; `pkg_verify` and `pkg_body` failed: https://github.com/Crazysodaman/SofiaAdaLyra/actions/runs/38093964817
- Release Candidate Build failed: https://github.com/Crazysodaman/SofiaAdaLyra/actions/runs/38093964828
- Matrix and Platform Compatibility passed; Manual Verification was cancelled. No fresh green assertion is made here.

### Source repairs in this commit (untested)

1. **Release source isolation:** GitHub workflow's clean tracked `release-source/test` inside checkout becomes `$RUNNER_TEMP/sofia-release-source`; the two wheels and evidence construct use the same external source root. The checkout's pytest collection can no longer discover its own nested archived test tree. Check archive extraction errors explicitly.
2. **BODY package ownership:** `test/conftest.py` now maps `test_body_*` to `pkg_body`. Existing `test/test_body_matrix.py` contains two real tests but previously imported only the cognition domain, resulting in `pkg_core` ownership and zero collected BODY-marked tests.
3. **Windows database cleanup:** `src/sofia/verify/cognition_v2_baseline.py::_database_counts` now explicitly closes the SQLite connection using `contextlib.closing`. The previous `with sqlite3.connect(...)` handled transaction commit/rollback **but did not close the handle**, leaving Windows temporary directory cleanup vulnerable to `WinError 32`.

### Deferred, no tests yet

- Check whether **other** code paths leak SQLite connections or non-daemon workers at shutdown; the baseline fix corrects one demonstrated suspect, not every possible WinError 32 cause.
- Do not claim `pkg_body`, `pkg_verify` or release candidate accepted until a subsequent exact-SHA CI run is recorded, with any remaining failures classified.
- Run selected Windows package gates, full release candidate and Venus/Artemis live proofs at the user-requested later verification stage. Do not modify the user's canonical production `sofia.db` for tests.
- The project roadmap is broad: this commit does not complete all 65 Phase 00 items or all 66 Phase 01 items.

**Commit instruction:** `[skip ci]` by explicit user request to code now but defer testing. Later verification needs an explicit, deliberate run; skipped checks are **not** green checks.
