# Phases 00–16: coded/source-audited vs live/accepted ledger

**GitHub `main` source checkpoint:** `2a56339615ecbbe48aaf3941ec4fcda58a26a457` (2026-10-10); subject to subsequent status-document commit.  
**User's active direction:** code in dependency order, no tests yet, only `main`, reuse existing canonical packages.  
**Critical meaning:** A Phase row being touched does NOT imply its V18 checklist is fully coded. `[skip ci]` commits are not passing CI, and nothing below is a production acceptance certificate.

| Phase | Source work present or added | Unfinished implementation / proof |
| --- | --- | --- |
| 00 Architecture | Canonical source ownership and autonomous decision contract; read-only architecture scanner and Matrix decision-trace projection | Exact causal cross-service IDs, API boundaries, independent live traces |
| 01 CI / release / LIFE | External release staging, package provenance, BODY marker, Windows SQLite shutdown closures, hardened Artemis wheel/dependency and exact IPv4 ingress policy; original tool-free creative drafts, independent artifact structural inspection, uncertain receipt handling, daily draft admission | New CI run, all 22 test families, release, live Artemis PowerShell/ACL proof, independent evaluation and genuinely autonomous completion/revision |
| 02 SAFE | Empty-scope standing grants fail closed; UI reflects blocked legacy grants; read-only registration/grant review | All capability access paths and real execution receipts, full independent evaluation and consent regression suite |
| 03 State mobility | Canonical `sofia.db` discovery candidates; Settings read-only relocation preflight; unclassified assets warning | **No actual database move/cutover**; bootstrap pointer, fenced single writer, all assets/secrets, restore/rollback and OS ACL verification |
| 04 Offline | Encrypted device-local offline draft journal | Offline transport sync, authenticated host acknowledgments, event conflict handling and proven recovery |
| 05 Lifelong Main | Canonical `LifelongThreadStore` with Main/project metadata and source-scoped event IDs; hooked into saved user/assistant messages | Per-device Main timeline display, reviewed cross-audience visibility, project UI, concurrency and client replay |
| 06 Memory scaling | Cursor/page reads, bounded recent messages in model request, bounded older source-specific recall, dated candidate records | FTS5 performance, retrieval quality, corrections and full lifetime context composition |
| 07 Archive | AES-GCM sealed segment writer/recovery using existing backup cipher; encrypted ciphertext integrity and authenticated manifest | Source archive indexing, consistent DB/assets/archives backup epochs, retention and erasure tombstones |
| 08 Emotion | Existing `EmotionalJournal` reused; explicit historical-scope recall added without treating old emotions as current | Long-term memory promotion and rendering/voice delivery evidence |
| 09 LIFE | Existing GOALS/RUN/LIFE reused; tool-free original text/story drafts, per-day budgets, actual RUN receipt checks; recurring tick now source-validates and evaluates settled personal artifacts, retries failed typed objectives at most three times, and completes only independently checkable objectives | Real host acceptance, quality/subjective review, other native formats and longitudinal benchmarks |
| 10 Skills | Digest/evidence/capability-scoped procedural candidate review | Explicit approval, executable skill runtime and safe imports |
| 11 LLMs | Measured baseline/candidate eligibility policy with safety, accuracy and CPU-memory/latency limits | Autonomous discovery, permitted actual model switching, reproducible benchmarks and rollback |
| 12 Vision | Exact time-scoped screen observation policy and minimal receipt contract | Real Windows/Hyprland interactive capture and redaction; UI indicators; actual VLM frames |
| 13 Hephaestus | Isolated hypervisor experiment admission/resource-policy contract | Actual approved Hyper-V provisioning, installed guest and recovery infrastructure |
| 14 Adaptation | LoRA/QLoRA data-use and VRAM-hour plan validation | Actual fine-tuning, held-out benchmarking and approved deployment |
| 15 NEURO | Existing prototype circuit motifs reused, read-only provenance/ablation inventory | Real experimental ablations, measurable outcome comparisons and resource budgets |
| 16 Research | Falsifiable preregistration checks without claims of achieved consciousness | Actual research protocol, independently reviewed results; subjective experience not guaranteed |

## Current coding checkpoint (2026-10-10 evening, later main-only pass)

- Database candidate discovery now checks the exact SQLite magic header and looks for the original conversation and authenticated social-session schema in a **read-only** database connection. It compares protected identity digests without exposing identity contents. The active configured state home remains authoritative.
- Model-role swaps have a review-only proposal function using current `RuntimeUserSettings` and existing independently measured `ModelTrialEvidence`; the current model is retained as the rollback target. The proposal **does not install/switch/save** any model.
- Main/project timeline views and lifetime-message lists are exposed through canonical `SofiaApplication` methods; the original source audience remains the read boundary. Concurrent Git collaborators also added authenticated session-aware paging and source checks, reused here rather than duplicated.
- Historical recall uses bounded source SQL and opt-in, host-approved SQLite FTS5. An FTS rebuild requires an externally verified operator approval and fenced writer, not an LLM-supplied boolean.
- Signed state-home pointers are prepared as nonactive `*.pending.json` files; no automatic cutover. Protected backup completeness checks were added to staging.
- LIFE success requires actual independent source byte validation for every original project objective. Unsupported subjective criteria remain unverified.
- **No tests, CI workflows, deployments, canonical DB moves, model changes or host changes were performed.** No claim of production acceptance.

## Follow-up coding slice: 2026-10-10 evening, no tests

- **P02 SAFE:** Settings audits the complete statically grantable catalog, configured standing capabilities and orphaned grants rather than only already-configured standing names. Runtime execution acceptance remains open.
- **P03 recovery:** Existing `BackupEngine` and `stage_verified_state_home` were reused. Staging now rejects persistent root files omitted from the authenticated backup manifest. `prepare_pending_state_pointer` writes only an operator-reviewable HMAC-authenticated `*.pending.json` outside the new home. It **never publishes an active pointer, restarts service, alters the old writer or performs a production cutover**. Verified external fencing and restore proof remain mandatory.
- **P04 offline:** `OfflineDraftJournal` now binds a pending draft read to principal as well as device/audience and requires a verified canonical-host acknowledgement matching the original encrypted draft before marking it exported. It is not a second transcript database.
- **P05 Main:** `LifelongThreadStore` rechecks original session principal/audience kind on reads; supplies bounded original-message and thread listings. `SofiaApplication` now exposes authenticated thread/message facade methods. Existing Cognition v2 focus store retains durable topic bookmarks, no second topic manager. No unreviewed cross-channel disclosure.
- **P06 memory:** conversation recall scans all matching source messages with SQL-side ranking/limit, instead of dropping everything outside the newest 256. Optional FTS5 in canonical SQLite uses an explicitly authorized, fenced **offline** rebuild, source-table triggers and current-session queries; normal conversation uses it if ready and falls back to original SQL when unavailable.
- **P09 LIFE:** technical validity and goal completion recheck every original objective against actual current artifact bytes and the independent closed objective validator. Model-supplied booleans alone cannot complete a project; subjective original objectives remain unverified pending review.
- **Removal audit:** `ConversationStore.list_messages` and other legacy paths still have callers (including original-archive and acceptance adapters). No source files were deleted on search-only evidence.
- **No tests or CI jobs run.** No live host/VM, canonical DB, grant or model transition was performed. `[skip ci]` used for commits. This audit describes coded changes, not acceptance.

## Source safety requirements

1. **No test execution**: Every new code path remains untested. Old failed `pkg_verify`, `pkg_body` and Release Candidate statuses are not resolved by source edits alone.
2. **No production cutover**: no `sofia.db` move, model replacement, screen capture, VM provisioning or grant escalation occurred during this coding pass.
3. **No second authority**: Main metadata links canonical saved messages; offline drafts are explicitly not a second canonical database; NEURO suggestions, screen receipts, and model evaluations cannot grant action authority.
4. **Artemis restoration audit**: on initial source editing an unsafe string replacement duplicated the script and corrupted a wheel-hash check. The script was rebuilt from commit `37dc8338` and replaced at `2a563396`. Source-structure checks on the replacement found one phase switch, one Artemis function, one Verify function, one pinned pip dependency invocation, and no LocalSubnet rule. **No PowerShell parser or host tests were executed.**
5. **Model and training research**: role/model can change only through separately approved and measured promotion. A pass on a synthetic benchmark is not user consent or identity replacement.
6. **No artificial task completion**: the implementation of source-level foundations on several phases is not proof that every item in the 700-task roadmap has been coded. Remaining work is tracked above.

## Required exact-revision verification, intentionally deferred

- Python/module import and migration compatibility; static code parsing, Windows PowerShell parse, YAML parse; source audit checks
- Targeted regressions for authorization, LIFE, file corruption, UI and journal close
- All 22 package families, full Release Candidate and Matrix/Platform/Windows gates
- Real Venus, Discord, Terra and Artemis canary behavior, memory/voice/renderer and synchronized owner threads
- Offline restore and complete state-bundle migration using one fenced writer; multi-day resource/companionship acceptance

**Next coding dependencies:** Phase 03 single-writer relocation and long-lived source integrity, Phase 05 cross-channel review and topic continuity, Phase 06 memory/correction quality and Phase 09 objective evaluation. Later experimental phases are not a substitute for these foundational requirements.

## Phase 09 source coding continuation, 2026-10-10 (no tests)

The existing application-owned LIFE background tick now follows settled canonical RUN receipts into real source-byte structural/objective evaluation, idempotent stored judgments, allowed revisions, and exact-goal completion. It refuses to equate subjective criteria or a model's assertion with independently verified objective PASS. See `docs/development/phase09-life-followthrough-2026-10-10.md`; production acceptance remains open until the end-of-coding test campaign and host verification.
