# V18 GitHub production-path reconciliation: 2026-10-10

**Examined:** `main` parent `8f0745cd`; source tree (1,361 tracked objects), `ROADMAP.md`, `docs/development/phase00-16-coding-progress-2026-10-10.md`, and current production entry points. This is a **phase-by-phase source crosswalk, not verification of all 700 V18 task IDs**.

The separate `Sofia_Companion_Autonomy_Master_Roadmap_V18_Priority_Phases.md` from the prior conversation was **not found in this repository or attached Library/Project file search**. The repository's ROADMAP contains extensive narrative acceptance requirements but not 700 itemized checkboxes. A numeric per-task completion count is therefore **not supported**. No claims about artificial consciousness have been verified.

| Phase | Production-reachable source already present | Remaining full-production gap |
|---|---|---|
| 00 Architecture | Canonical `SofiaApplication`, v2 Turn Kernel, state plane, decision traces | Exact causal correlation and independent cross-service live traces |
| 01 Verification/release | Release candidate workflow, 22 package families, Windows DB cleanup, new atomic replica seed | Pinned-head CI still unverified; prior release/package failure and Venus/Artemis canaries |
| 02 SAFE | `PermissionStore`, exact `ExecutionApprovalVerifier`, private grants | Complete actor/receipt audit and host-authorized negative gates |
| 03 State mobility | Discovery, full backup restore stage, nonactive signed pointer | Authenticated privileged fencing broker, true single-writer cutover, rollback proof |
| 04 Offline | Encrypted draft journal with authenticated host-receipt interface | Mobile offline queue, signed authenticated host ingestion, conflict/replay handling |
| 05 Lifelong Main | Canonical `LifelongThreadStore` and `SofiaApplication.main_thread_page`; **this change wires read-only audience-scoped Main history through mobile HTTPS → Android UI and separates mobile session storage by privacy mode** | Verified mobile build, Discord/desktop historical screens and independently reviewed cross-channel disclosure |
| 06 Memory | Indexed source SQL, optional FTS5, temporal candidates | Measured large-history recall, correction/revocation review and full composition |
| 07 Archives | AES-GCM `SealedArchiveSegmentStore` | Rotation, retention, source indexing and verified lifecycle/erasure |
| 08 Emotion | Existing emotion journal/expression/presence | Longitudinal recall and real renderer/voice delivery verification |
| 09 LIFE | Canonical LIFE coordinator, Project Forge, source-validated objectives | Reviewed critique-revision completion loop and resource/host acceptance |
| 10 Skills | Capability-scoped skill candidate review | Host-verified skill activation/import/rollback and safe adapters |
| 11 LLM | Role trials, guarded proposal, production model lifecycle | Exact-grant live model promotion, reproducible trials and rollback |
| 12 Vision | Screen-observation admission/receipt contract | Windows/Hyprland real capture, VLM, privacy indicator and revocation |
| 13 Hephaestus | Approved VM experiment budget contracts | Actual isolated guest provisioning, teardown and recovery |
| 14 Adaptation | LoRA/QLoRA plan validation | Training execution, held-out eval, operator promotion |
| 15 NEURO | Circuit motifs and provenance inventory | Controlled ablation experiments and resource/outcome analysis |
| 16 Research | Falsifiable consciousness-research criteria | Peer-reviewable protocol/measurements; subjective experience cannot be guaranteed |

### P05 implementation and boundaries

- Android mobile UI calls a new exact-schema authenticated `POST /v1/mobile/main/page` endpoint. Gateway derives identity and audience from the already-authenticated device/mode context and delegates source-linked retrieval to the canonical `SofiaApplication.main_thread_page`. Never accepts a caller-supplied principal or arbitrary cross-audience thread.
- The existing gateway accidentally keyed sessions by device alone, so toggling private/shared mode risked resuming a conversation bound to the wrong audience. A versioned mode-specific session binding stores distinct sessions and reuses legacy sessions **only** after validating the exact original social principal/audience binding. Stored conflicting identities are denied, not migrated.
- Private Main reads additionally enforce the durable host private-chat grant and return HTTP 403 when denied. Android `Private mode` change refuses in-flight switches and clears currently displayed chat, history and unsent text, preventing retained private content on a shared screen.
- Five regression scenarios were authored: session-bound Main pagination, audience separation, invalid cursor rejection, authenticated HTTP endpoint, mode/session rebinding denial. Regression code is **unexecuted** per user no-tests instruction.

### Honest exit state

Code above is intended production path, not a verified production deployment. Phases 00–16 are still NOT individually finished or accepted. No CI/test run, host deployment, state-home cutover, model promotion, or external authority change occurred. Any [skip ci] commit intentionally defers verification. Further production work must close real end-to-end gaps in dependency order instead of marking partial source stubs as done.

### Permission/transition hardening

Private Main endpoint denies reads without durable host private-chat permission (HTTP 403); an Android private/shared toggle is disabled while requests are in flight and scrubs chat, Main history and the composer on a successful switch. This prevents an outstanding private response from repainting a shared-screen view.
