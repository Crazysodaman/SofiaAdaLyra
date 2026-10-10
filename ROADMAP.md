> **Autonomous work and governed self-improvement Phase 3 checkpoint — 2026-10-09:** The production application now owns one durable autonomous work coordinator over canonical `sofia.db`, using ordered plans, priority/resource admission, bounded concurrent workers, cancellation, deadlines, overload rejection, restart reconciliation, and explicit queued/running/blocked/waiting-approval/completed/failed/cancelled/uncertain states. Reviewed engineering diagnostics become immutable EVOLVE evidence and code proposals, then DEV builds and tests a candidate in its existing detached worktree; successful candidates stop at operator review and cannot apply, commit, push, release, or approve themselves. ACT/Presence reports candidate readiness and isolated build failure, while the EVOLVE tray page exposes plans, jobs, events, diagnostics, and DEV candidates. OpenCode errors now distinguish invalid configuration, missing executable, timeout, and scope violation; worker subprocesses receive a secret-scrubbed environment, fixed host pytest selectors, duration/output/change-size limits, and bounded retries. A detached worktree and scrubbed environment are **not a security sandbox**: the worker still runs with the host OS account and this cross-platform implementation does not claim kernel-enforced filesystem or network isolation. Production deployment should use a separately restricted service/container identity when stronger isolation is required. Exact current-revision gate results and live host OpenCode acceptance remain release evidence, not architecture assertions.

> **Presence, Initiative, and ACT outreach Phase 2 checkpoint — 2026-10-09:** The existing proactive path now has an application-owned, bounded Presence & Initiative engine over canonical `sofia.db`. It stores source-linked world observations with subject, predicate, time, freshness, confidence, epistemic state, availability, and audience; reviewed initiative classes feed the existing ACT queue and never create authority. Goal review requests use this path, while existing reflection/Fleet producers retain the same ACT owner. ACT now records a content-minimal durable lifecycle from queue through policy decision, transport attempt, transport acceptance/failure/unknown result, and separate desktop/mobile recipient acknowledgement. Quiet hours, busy state, recipient mismatch, quotas, disabled policy, operator stop, and missing transport remain explicit reasons rather than silent absence. Pending ACT work receives a bounded scheduling opportunity before routine background maintenance, fixing starvation without running an idle LLM. The tray ACT tab exposes outreach traces, initiative decisions, and world observations. Real Discord/mobile/Home Assistant delivery still requires separately configured host transports and live acceptance.

> **Cognition v2 Phase 1 correctness checkpoint — 2026-10-09:** Matrix v2 now plans bounded multi-predicate requests for CPU, GPU, RAM, storage, and utilization across every explicitly referenced machine. The reference resolver retains all explicit entities, the Turn Kernel persists one exact subject/predicate/audience request per evidence need, and settlement closes only the request proven by a current typed evidence atom; a valid Artemis CPU observation cannot settle Venus CPU or Artemis RAM. Fleet acquisition groups work per authenticated host/capability, rejects wrong-node and failed remote envelopes, and renders multi-host answers without borrowing values. Independently validated domain drafts can be combined for multi-question turns, while unhandled evidence requests remain explicitly unresolved and guarded wardrobe/private-presentation flows keep precedence. Desktop, Discord, owner-direct tools, and guarded conversation services all share the application-owned kernel and v2 answer path. Live Windows and dual-Ollama behavior remain host acceptance and are not claimed by this Linux checkpoint.

> **Cognition v2 Batch 12 production cutover — 2026-10-09:** The production Turn Kernel/Matrix v2 plan is now the single semantic owner for ordinary conversation, owner-direct tools, and guarded interaction/clarification/live-offer paths. The v1 phrase classifier, coordinator, evaluator registry, package evaluator stubs, evidence planner, and routing planner were physically removed. Retained Matrix components are deterministic privacy, authority, context, capability-exposure, evidence-resolution, response-validation, and trace safeguards projected from the v2 plan; they cannot broaden authority or manufacture evidence. Traces record one completed schema-v2 decision and are not shadow traces. This checkpoint supersedes older roadmap statements that call Matrix shadow-only, temporary, or partly production controlling. The revision-bound candidate gate passed **3,907 / 3,907**, with **5 skipped**, **6 deselected**, dependency integrity green, and semantic integrity accepted with zero findings. Windows launch and live dual-Ollama behavior remain host acceptance and are not claimed from Linux CI.

> **Cognition v2 Batch 6 checkpoint — 2026-10-09:** DEEP and VERIFY now run real overlapping Primary/Secondary inference intervals when the turn is tool-free, then join results deterministically through Primary synthesis. The Secondary worker receives a bounded tool-free task rather than the full transcript or capability surface; its output is non-authoritative review material. Role-local locks protect each configured model, per-conversation locks preserve same-session ordering without globally serializing Desktop and Discord, and shutdown drains already-started turns while rejecting new work. Tool-bearing turns stay single-worker, worker failures propagate explicitly, and cross-role fallback is disabled unless the operator separately enables `SOFIA_COGNITION_FALLBACK_ENABLED`. A barrier-based acceptance test proves interval overlap and clean executor shutdown; the V2/NEURO compute budget can disable overlap under observed pressure without reducing reasoning depth. The final focused routing/Matrix/conversation/canary gate is **120 passed** and the non-integration CORE gate is **2,232 passed / 4 skipped / 1,651 deselected**. Live two-model Ollama overlap remains a host acceptance step and is not claimed from this cloud runner.

> **Cognition v2 Batch 5 checkpoint — 2026-10-09:** Claim planning and exact evidence validation are production-owned for the first complete Fleet/Machine slice. Matrix v2 selects typed CPU, GPU, memory, storage, hardware, or CPU-utilization predicates; resolved Fleet identities supply host-owned node/host parameters; reads pass through the existing capability gateway and Matrix exposure; authenticated remote results are checked against the requested node; and only exact subject/predicate/scope evidence can render a deterministic answer. Artemis can never borrow Venus evidence, remote failure or wrong-node output stays unknown, CPU load uses durable OPS telemetry rather than inventing a processor model or utilization, and Desktop/Discord channel services share the same coordinator. The focused gate is **80 passed**, the cross-surface slice is **593 passed / 1 skipped** after rerunning its sole sandbox-denied socket test with localhost access, and the non-integration CORE/OPS gate is **2,662 passed / 4 skipped / 1,215 deselected**.

> **Cognition v2 Batch 4 checkpoint — 2026-10-09:** The production application now composes one append-only typed evidence ledger, exact subject/predicate/scope Evidence Graph, truth-maintenance correction cascade, and capability-result ingestion boundary over canonical `sofia.db`. Every atom carries value, source, observation/expiry time, scope, trust, epistemic state, acquisition state, and evidence ID. Venus cannot satisfy Artemis; private scopes/dependencies cannot cross; future/stale/weak/hypothetical/failed/unavailable/contradicted/revoked material cannot masquerade as current fact; assistant prose is not observed evidence; and execution predicates require receipt sources paired with matching successful capability results. Corrections atomically contradict targets and revoke dependent conclusions without deleting history. The focused gate is **38 passed**, the combined application/conversation/Matrix slice is **253 passed**, and the non-integration CORE gate is **2,219 passed / 4 skipped / 1,651 deselected**. Fleet/Machine payload normalization and claim-driven rendering remain Batch 5; legacy prefix evidence is not silently promoted.

> **Cognition v2 Batch 3 checkpoint — 2026-10-09:** Matrix v2 now produces the production turn's typed intent, domains, subject-scoped evidence needs, action class, response strategy, reasoning requirement, bounded compute/retrieval budget, and dependency-valid schedule. It uses normalized concepts plus structured focus instead of extending the phrase-regex classifier; exact mutation/verification checks remain deterministic safety boundaries. Current-turn NEURO state can promote depth, bound resources, select optional independent parallelism, and influence retrieval/background priority, but cannot add evidence, grant authority, execute work, or downgrade VERIFY. V2 reasoning now controls the live cognitive route; legacy Matrix context/evidence/authority/validation adapters remain downstream until their replacement batches. The focused V2 gate is **20 passed**, the combined conversation/Matrix/NEURO slice is **223 passed**, and the non-integration CORE gate is **2,201 passed / 4 skipped / 1,651 deselected**; live Ollama acceptance is unavailable here and is not claimed.

> **Cognition v2 Batch 2 checkpoint — 2026-10-09:** The application now composes one production-authoritative Turn Kernel for ordinary conversation and owner-direct tool turns. It commits structured session/audience-scoped ConversationFocus before sequencing Matrix planning and NEURO attention, resolves exact aliases, bounded typos, pronouns, ellipsis, corrections, subject switches, and concurrent topics, and durably tracks unresolved requests and pending actions across restart. Focus is discourse context only, remote focus cannot fall through to local hardware inspection, typed evidence is required to settle information requests, and execution receipts are required to settle actions. Focused tests are **14 passed**, the conversation/Matrix/NEURO/application continuity slice is **233 passed**, and the non-integration CORE/SOCIAL/OPS gate is **2,764 passed / 4 skipped / 1,082 deselected**. Live Ollama acceptance is unavailable on this cloud host and is not claimed. Existing Matrix v1 and NEURO are deliberate delegates behind the kernel until Batch 3 replaces Matrix planning; they are not competing turn coordinators.

> **Cognition v2 Batch 1 checkpoint — 2026-10-08:** The live Cognition v1 path has been traced from authenticated channel through conversation persistence, Matrix, NEURO, runtime context/evidence projection, model routing, provider/tool execution, response validation, and final persistence. Typed V2 hand-off contracts, a component ownership map, a dependency-aware V1 replacement/deletion map, a reproducible control-path benchmark harness, and honest baseline evidence are now in `docs/development/cognition-v2-*` and `sofia.cognition.v2`. These contracts are not a shadow engine and are not production-authoritative yet. Batch 2 introduces the first production V2 owner; later batches still replace Matrix, evidence, scheduling, routing, and validation before V1 removal.

> **NEURO + persistent goals implementation checkpoint — 2026-10-06:** `goals-v1` is now production-reachable from authenticated Matrix conversation and a conservative reviewed-fault coordinator. Accepted SELF candidates activate deterministically, scoped goals feed bounded NEURO attention, permitted diagnostics execute through the existing capability gateway inside RUN budgets, higher-impact work blocks on existing permission authority, typed receipts govern completion, and durable rechecks/expiration/recovery survive restart. NONE/DETERMINISTIC wake accounting, Goals/NEURO UI diagnostics, Gaia/voice sensory summary bridges, and a separate non-authoritative connectome research package are present. A second specification audit additionally made complete lifecycle-chain reconstruction fail closed on discontinuity, illegal transitions, duplicate event IDs, and invalid event time. Goals still grant no evidence, permission, consent, execution, or receipts. Final observed test counts belong in release evidence; live host behavior remains a separate acceptance gate.

> **HA / backup / workload-mobility / release foundation update — 2026-10-04:** The previously listed P2 implementation gaps are now source-complete foundations on `main`. State Plane has opt-in synchronous replication with an independent durable witness, exclusive monotonic writer lease epochs, stale-writer fencing revalidated around replica mutation and inside witness acknowledgement/commit/promotion transactions, durable operation/ack journaling, repair of partial commits, replica health, and caught-up target promotion. OPS has topology-aware encrypted multi-host backup coordination with explicit host/failure-domain identities, minimum independent-copy policy, per-target rotation, and durable backup-set evidence. Workload migration now has a concrete typed execution backend/catalog, durable workload lease epochs, checkpoint propagation, readiness verification, source fencing before singleton activation, required rollback bindings before execution, rollback before fence, exact Level-4 execution approval bound to the current source/target node identities plus the exact typed execution-profile hash and derived remote mutation scopes, short-lived exact remote grants revoked after execution, durable receipts, and fail-closed `outcome_uncertain` handling that never guesses/retries/rolls back an unknown remote result. Release/Integrity now has reproducible release-candidate evidence, protected Ed25519 bundle signing, host-side independent signature verification, canary → normal → delayed Fleet rollout, runtime restart/health convergence checks, rollback-on-wave-failure, exact protected rollout approval, and Fleet-agent JSON configuration for release inbox/trust. These are **coded foundations, not a claim of completed production HA**: real independent hosts/failure domains, partition/failover drills, clean restore drills, real workload adapters, signing-environment custody, artifact distribution, and supervised Fleet rollout acceptance remain required.

> **Current-main reconciliation — 2026-10-04:** Audited head `fc533aaf` closes the requested **Permissions → Fleet → Hardware → Network → Docker → Self-improvement** implementation chain. The canonical five-level permission engine and durable grants live in `sofia.db`; tray **Settings → Permissions** manages the same state; Level 1 reads and explicitly classified Level 2 autonomous actions are exposed without repeated approval; Level 3 uses scoped standing or exact grants; Level 4 requires exact approval; and Level 5 authority-changing operations cannot be self-authorized. Fleet discovery may automatically create/refresh **untrusted candidates only**. **Adding/trusting/enrolling a computer is Level 4 and requires exact one-time Sparks approval** bound to candidate/node/key/endpoint evidence. Local/enrolled-remote hardware inspection, independent approved-scope network discovery, local/enrolled-remote Docker/Portainer reads including bounded logs, and read-only/self-contained DEV inspection/build paths are implemented. On this head: Platform Compatibility is green on Windows/Linux Python 3.12/3.14; Matrix Tests are green; `pkg_safe`, `pkg_dev`, `pkg_ops`, `pkg_net`, and `pkg_integrate` are green. Full verification is **3375 passed / 1 failed / 6 deselected**; the single assertion failure is `test_environment_runtime_projection.py::test_runtime_preserves_partial_deterministic_multi_question_answers`. `pkg_core` is red only because that intentionally cross-owned ENVIRONMENT test is also CORE-marked. `pkg_body` is separately red because no BODY-owned tests are currently selected. Do not reclassify or hide either failure merely to make CI green.

> **Package roster correction — 2026-10-04:** Current `pyproject.toml`, `test/conftest.py`, and Package Tests define **22 package/test ownership families**, not 21: CORE, INTERACT, MEM, SOCIAL, NET, UI, **VOICE**, RUN, OPS, ACT, REL, AVATAR, DEV, BODY, EVOLVE, CLEAN, KNOW, INTEGRATE, ENVIRONMENT, HABIT, SAFE, VERIFY. Older 20/21-package passages are historical. VOICE is now a first-class package gate; live STT/TTS quality/device/channel acceptance remains separate from the existence of the VOICE package and matrix foundation.

> **Matrix block closed — 2026-10-02:** The focused M1–M7 matrix expansion is implemented on `main`, with the M8 Voice runtime/prosody matrix foundation also included. The dedicated Matrix Tests gate passed **405/405** on `130aa735`. M1 owns bounded tool exposure while host authority remains final; M2 enforces authenticated principal/audience privacy with cross-principal and cross-audience leakage tests; M3 provides evidence/freshness-gated emotion + weather + time/daypart + season influence including bounded post-eligibility memory reranking; M4 adds REL/HABIT; M5 adds DEV/KNOW/INTEGRATE/BODY; M6 covers release/schema/Fleet compatibility; M7 covers Fleet failure/recovery. SAFE and VERIFY remain cross-cutting constraints, UI remains a channel/parity surface, CLEAN remains an invoked operational capability, and CORE identity/Constitution remain invariants rather than optional matrix-selected truth. Older roadmap passages that describe M1–M7 as future work are historical and superseded by [`MATRIX_ROADMAP.md`](MATRIX_ROADMAP.md).

> **Contextual influence implementation update — 2026-10-02:** The M3 audit findings are now implemented and reconciled in [`CONTEXTUAL_INFLUENCE_AUDIT.md`](CONTEXTUAL_INFLUENCE_AUDIT.md). `ContextualInfluenceMatrix` is a typed decision-surface whitelist with provenance/freshness requirements. Context-aware wardrobe autonomy, reflection weather, seasonal theme, HABIT environmental/seasonal learning, bounded memory reranking, and separate interaction willingness/expression influence rules are wired. Context Matrix exclusions are authoritative at the runtime boundary and later conversation layers cannot silently re-add excluded EMOTION/ENVIRONMENT signals. Context may shape preference/salience/expression/timing, but returns NONE for SAFE/authority, factual truth, release verification, Fleet trust/fencing, DEV correctness, EVOLVE approval, and BODY safety.

> **AVATAR clothing-request autonomy implemented — 2026-10-02:** Natural-language forms such as `wear X`, `put on X`, `change your outfit to X`, `take off X`, and equivalent imperative grammar are **requests/suggestions to Sofía, not commands that directly control canonical presentation state**. `ClothingActionService` routes the validated candidate plus trusted current **emotion + fresh weather + time/daypart + season** context through privacy/grant/coverage checks and `WardrobeAutonomyPolicy`, which may **accept / decline / counter-propose**. Only an accepted transition may commit/persist canonical AVATAR state. Refusal leaves state untouched, and neither user wording nor LLM prose can prove a clothing change or create consent/authority.

> **Historical roster note — 2026-10-02:** At this checkpoint the roadmap tracked 21 families. This was superseded on 2026-10-04 when `pkg_voice` became a first-class package/test family. The current roster is 22; older 20/21-family passages below are historical.

> **Production wiring audit — live/deferred/dead classification started 2026-09-30:** The audit is now checking every subsystem through the chain **source exists → imported → composed → production configured → reachable from normal startup/channel → authority exposed correctly → real operation/evidence → response path → persistence → UI/Discord/terminal surface → automated test → supervised live canary**. First findings are concrete: (1) desktop remote-chat authority was LIVE-but-contradictory and is now removed from production composition; (2) Settings and tray still exposed/consumed parts of that obsolete split path and are repaired; (3) deferred remote mTLS chat selector/transport/runtime-authority primitives are retained for #10 but removed from the broad live UI public surface and explicitly labeled DEFERRED; (4) current RUN source contains a real host-neutral local supervisor/watchdog using the canonical state database, but the repository does **not** currently contain a Windows ServiceFramework/service-install wrapper for `SofiaAdaLyra` or a watchdog service. Therefore source-level supervisor logic is LIVE-CANDIDATE, while Windows service provisioning/recovery is **LIVE-ENVIRONMENT-UNVERIFIED** until the installed service command/configuration on Venus is inspected and tied back to current source. The audit will not promote “file exists” to “works” without the complete path and evidence.

> **P0 canonical single-database desktop authority + wiring-audit checkpoint — 2026-09-30:** Sparks requires one authoritative production `sofia.db` for live desktop conversation/state. Current-main now enforces `configuration.state_path` as that authority; on a normal Windows production launch this resolves to `C:\\ProgramData\\SofiaAdaLyra\\sofia.db` unless the centrally owned production storage layout is explicitly overridden. The desktop worker no longer selects a remote runtime for chat: it always composes one local `SofiaApplication` over the configured canonical database, the UI status bar reports `CANONICAL DB: <path> | session: <id>`, and Settings → Chat displays the same path. Legacy `fleet_auto`/pinned desktop-chat rows are migrated to LOCAL at desktop, Settings, and tray startup, and new non-local desktop-chat settings are rejected. The obsolete split-authority `remote_application.py` production selector and its acceptance test were removed. The tray no longer treats the old runtime-chat-authority record as permission to display/control a remote Sofía runtime; its Sofía Runtime controls now target the local canonical runtime owner. Fleet may still place LLM/cognitive work remotely, but conversation/state authority does not move independently until #10 redundancy/fencing/recovery provides a real single-writer mobility contract. Existing remote mTLS chat/client/authority primitives are therefore **deferred #10 infrastructure, not live desktop routing**. The state-topology audit also confirms core conversation, Discord, memory, operational, REL, SOCIAL, UI draft/control, RUN lease/supervisor, and State Plane stores can share the configured `sofia.db`; separate Fleet protocol ledgers and legacy JSON sidecars remain explicit audit/migration items rather than being mislabeled as the canonical conversation database. A real desktop-worker regression sends a message and opens the configured SQLite file directly to require persisted user/assistant rows. **Verification pending on the new focused gate and live Venus UI canary. This checkpoint supersedes the earlier split-storage wording below.**

> **6.5D–I matrix acceptance — COMPLETE 2026-10-01:** The matrix slice is accepted. Windows matrix regression passed **147/147** at `76a06cd`, covering Evidence/Authority/Response behavior, route selection, actual per-turn execution tracing, canonical model activity/residency diagnostics, tray/desktop route/model/host/intent/domain/validation exposure, and Desktop/Discord/Terminal channel provenance. A dedicated production live canary was then added on `main` and Sparks ran `python -m sofia.verify.dual_cognition --evidence-path dual-cognition-evidence.json` on Venus against the real configured Ollama roles. Live evidence returned `accepted: true`, zero failures, zero fallbacks, FAST → secondary `huihui_ai/qwen3.5-abliterated:4B`, DEEP → primary `qwen3.5:9b`, and VERIFY → primary `qwen3.5:9b` → secondary `huihui_ai/qwen3.5-abliterated:4B` → primary `qwen3.5:9b` with two verification passes. This closes **6.5D Evidence, 6.5E Authority/Action, 6.5F Response, 6.5G dual-LLM routing, 6.5H trace/tray diagnostics, and 6.5I Desktop/Discord/Terminal parity**. Voice parity remains intentionally deferred and does not block matrix acceptance. Broader package failures remain separate follow-up work and are not reclassified as matrix failures.

> **Matrix-first + AVATAR clothing-autonomy ordering — 2026-10-01:** Finish and verify **6.5D Evidence → 6.5E Authority/Action → 6.5F Response → 6.5G dual-LLM routing → 6.5H Matrix Trace/Tray diagnostics → 6.5I channel parity** before returning to conversational wording/quality repairs. Dual cognition must be observable rather than assumed: FAST uses the secondary role, STANDARD/DEEP use the primary role, and VERIFY records the actual primary → secondary critique → primary synthesis path, including model/host/residency diagnostics where evidence exists. Add a later **AVATAR clothing action + autonomy path**: a user may request an outfit or garment change, but Sofía may accept, decline, or propose an alternative; only an accepted host-authorized presentation transition may mutate canonical AVATAR state, LLM prose alone cannot claim a change, refusal leaves state untouched, accepted changes persist in `sofia.db`, and Desktop/Discord/Terminal share the same path. Renderer animation/receipts remain later AVATAR work.
> **6.5D/E/F execution-receipt hardening — 2026-09-30:** The action-response receipt gap found during the D/E/F/G source audit is repaired on `main`. `CognitiveToolBinding` now carries host-owned execution-receipt policy rather than inferring mutation from model text or capability names at response time. Successful marked tools emit separate `execution-receipt:<capability>` evidence in addition to ordinary `capability:<capability>` evidence; `SofiaRuntime.matrix_evidence_availability()` promotes only the explicit execution-receipt evidence into `action.execution_receipt`. Existing approved mutating DEV, local machine refresh, configured integration, and remote Fleet-manage surfaces are marked. Remote Fleet receipts are additionally gated on the durable remote result reporting `reported_success`; reported failure/unknown outcomes cannot become execution receipts. Response-matrix regression coverage now accepts an execution claim only when host authority is ALLOWED and receipt evidence is AVAILABLE, while capability evidence alone remains insufficient. A conversation-level regression covers receipt-backed action persistence. Missing D/E/F/G test imports found during the audit were repaired. **Verification pending; do not mark D/E/F complete until the focused delta gate passes.**

> **Live desktop-chat + persistence repair checkpoint — 2026-09-30:** The live Sofía desktop transcript exposed two issues while D/E/F/G hardening was underway: conversational AVATAR/follow-up wording could fall through to generic generation and invent outfit/sensation/context details, and the desktop UI did not make it obvious which SQLite file or remote runtime owned authoritative chat persistence. Repairs are now implemented on `main`. AVATAR self-fact normalization accepts conversational prefixes such as `so what are you wearing`; reviewed tonight-lounge forms such as `what would tonights lounge outfit be?` are deterministic and cannot invent wool, wear-history, or physical sensation; lounge/footwear/barefoot wording activates AVATAR context; `so question what can I touch` is a host-grounded INTERACT question with a deterministic response and no implied touch/consent; short follow-ups such as `tell me the why` use `LAST_TURN` history plus a trusted immediate-topic scope instruction; and unqualified `matrix/matrixs/matrices` in Sofía project discussion activates COGNITION with explicit project-architecture grounding rather than mathematical-matrix interpretation. Persistence visibility is now explicit: `ConversationStore` and `ConversationService` expose their exact database path; local `SofiaApplication` asserts the canonical conversation store equals `configuration.state_path`; local and remote desktop applications expose chat-storage mode; the desktop worker emits persistence identity; and the UI status line shows either `LOCAL chat DB: <path> | session: <id>` or `REMOTE authoritative chat | session: <id> | local UI state: <path>`. A desktop-worker regression opens the configured SQLite DB after a UI send and requires the user/assistant conversation rows to exist there. Remote mode intentionally does not claim that the local UI-state DB contains authoritative remote chat history. Fresh regression tests cover the exact live phrases and storage modes. **Verification pending; do not mark these repairs or D-G complete until the focused gate passes.**

> **6.5B/C passed; D/E/F/G implementation checkpoint — 2026-09-30:** Sparks pulled `0c58504`, first reran the two repaired failures (**2 passed in 22.75s**), then ran the full combined B/C matrix regression gate. Result: **165 passed in 1130.53s (18:50)**. **6.5B Domain Matrix and 6.5C Context Matrix are now gate-green.** Work then moved directly into 6.5D/E/F/G on `main`. D now derives typed evidence requirements, resolves only host-owned evidence requested by the active turn, separates weather/clock/location/calendar evidence, records successful operational capability receipts, and accepts trusted host INTERACT/EMOTION projections as evidence without trusting model text. E now plans NOT_REQUIRED / ALLOWED / REQUIRES_APPROVAL / DENIED / CLARIFY from existing host Authority; ambiguous `make X primary` fails to clarification, ordinary state-changing actions cannot expose execution tools without execution authority, and the existing narrow interaction stop/resume safety control remains host-enforceable. F now validates evidence/authority claims after the existing domain-specific grounding gate and before normal assistant persistence; a rejected draft gets one tool-free `VERIFY` rewrite, then a deterministic fallback if still invalid. Successful host capability calls carry evidence refs into the final cognitive response. Deterministic guarded interaction replies also complete F without an LLM retry. G now supplies validated FAST/STANDARD/DEEP/VERIFY route hints into the existing dual-engine router: FAST prefers secondary, STANDARD/DEEP primary, VERIFY uses primary draft + secondary critique + primary synthesis, while tool selection remains primary-only. Route hints are preserved through context assembly, tool rounds, EMOTION, INTERACT, context hygiene and response-quality/grounding retries. Durable matrix trace extensions now store evidence, authority, response contract/validation and requested route without duplicating user-message text. **Fresh D/E/F/G code is verification pending; do not mark D-G complete until the new focused and regression gates pass.** The transactional staged-offer path intentionally retains its existing independent atomic policy/expression release boundary rather than weakening that transaction for matrix integration.

> **Evidence correction — 2026-09-30:** Uploaded local pytest evidence supersedes the earlier conversational report that the broader post-repair matrix gate had fully passed. At `1162714`, that gate actually completed **147 passed, 1 failed in 1073.53s (17:53)**; the sole failure was the stale exact weather no-evidence string assertion while the deterministic resolver returned a more specific grounded no-location/provider explanation. The focused **104-pass** repair gate remains valid. This correction does not change the current B/C repair work; it makes the roadmap evidence exact.

> **6.5B/C combined gate checkpoint — 2026-09-30:** Sparks ran the combined matrix/context regression gate on `278ccbd`. Result: **163 passed, 2 failed in 1153.98s (19:13)**. The failures were narrow: (1) `change your outfit based on the weather` classified as ENVIRONMENT_QUERY before ACTION_REQUEST, so the baseline classifier precedence was corrected to resolve state-changing/action intent before informational environment/avatar intent while package evaluators still add ENVIRONMENT/AVATAR relevance; (2) the weather live-regression test expected the older short no-evidence string, while the deterministic environment resolver now correctly returns the more specific grounded explanation that no configured/current location evidence is available for a weather provider. The test now asserts the grounded prefix/detail and still requires zero LLM calls. Repair code is committed and **rerun pending**; 6.5B/C are not yet marked complete.

> **6.5B + 6.5C combined implementation checkpoint — 2026-09-30:** Sparks reported the broader post-repair matrix/Discord gate passed; exact pass count/time were not supplied in that message, so none are invented here. Building B and C together is now the active path. **6.5B** now composes package-owned SOCIAL, EMOTION, ENVIRONMENT, AVATAR, INTERACT, MEMORY, COGNITION, MACHINE, OPS, AUTHORITY and CONTINUITY relevance, including cross-domain turns (for example weather + outfit) and reviewed interaction grammar. **6.5C** now creates a typed `ContextPlan` from that relevance, persists the plan in the content-minimal matrix trace with an additive SQLite migration, actively selects provider-visible transcript history (`NONE=1`, `LAST_TURN=3`, `TOPIC_WINDOW=8`, `BOUNDED_RECENT=12`, `RETRIEVE_SPECIFIC=1`), and passes the plan into `SofiaRuntime`. For clearly standalone/targeted `NONE` or `RETRIEVE_SPECIFIC` turns, runtime context is selectively projected by domain: unrelated memory retrieval, embodiment/avatar presentation, environment snapshot, operational state, continuity/workspace evidence and operational self-model are omitted unless their domain is included. Canonical core identity/personality/Constitution remain available. GENERAL and ordinary follow-up turns intentionally retain the existing full runtime projection during this rollout. Matrix/context failure falls back to the prior bounded-history behavior rather than taking conversation down. New tests cover context-plan limits, all-domain registry ownership, reviewed interactions, continuity, additive trace migration, cross-domain composition, provider-bound Hru context reduction, Hru memory-retrieval suppression and preservation of full GENERAL context. **Fresh B+C code is verification pending; do not mark 6.5B/C complete until the focused combined gate passes.**

> **Matrix shadow repair gate passed — 2026-09-30:** Sparks pulled `bf725a9` and ran the focused 6.5 repair gate covering `test_cognition_matrix.py`, `test_conversation_service.py`, `test_discord_bridge.py`, and `test_response_quality_hardening.py`. Result: **104 passed in 927.43s (15:27)**. This verifies the repaired shadow-matrix wiring, full conversation-stack channel propagation, Discord channel provenance, canonical Discord DM audience ID expectation, continuity hook restoration, and response-quality precedence in that focused slice. **6.5A is now focused-gate green, but the broader 6.5 regression gate is still required before enabling matrix-driven context selection.** 6.5B package-owned relevance evaluators remain shadow-only pending that broader gate.

> **Matrix shadow gate repair checkpoint — 2026-09-30:** Sparks pulled `871f4e7` and ran the first 6.5 matrix/Discord regression gate. Collection succeeded and **128 tests passed; 19 failed**. The failures reduced to three implementation/test issues rather than 19 independent matrix defects: (1) channel plumbing was accidentally attached to `_after_user_message_saved()` instead of only the matrix trace hook, causing most conversation turns to fail with a missing keyword argument; (2) one new Discord assertion used `discord-dm:<id>` instead of the canonical existing `discord:dm:<id>` audience identifier; (3) the new standalone wardrobe-tangent quality rule changed precedence ahead of the established broader emotion/identity tangent rule. Repairs are now committed: continuity hook signature restored, matrix trace accepts channel explicitly, channel provenance is propagated through the Emotional/INTERACT/Expanded/Opt-In conversation stack and direct guarded/staged interaction paths, canonical Discord audience-id expectation restored, and established response-quality precedence preserved. A regression test now requires `channel="discord"` to survive the full real application conversation stack into the matrix trace. **Repair code is pending local rerun; do not mark 6.5A certified yet.**

> **Matrix architecture start — 2026-09-30:** The roadmap now inserts **6.5 Message/Evidence/Context/Authority/Response Matrix** before deep work on Fleet monitoring (#7). Phase **6.5A is implemented in shadow mode, verification pending**: typed contracts now exist for Turn, Evidence, Context, Authority, Response, validation, and durable matrix traces; every persisted user turn is classified without changing live response behavior; traces store message/session IDs and matrix decisions but deliberately do **not** duplicate message text; shadow failures cannot take conversation down; Discord channel provenance is preserved when the responder supports it. Phase **6.5B has started** with package-owned relevance evaluators for SOCIAL, EMOTION, ENVIRONMENT, AVATAR, INTERACT, MEMORY, COGNITION, MACHINE, OPS, and AUTHORITY. State-changing avatar requests such as `change your outfit` classify as ACTION requests so authority is required, while read-only appearance questions remain AVATAR queries. The evaluator registry is lazily composed to avoid heavy package import cycles. **Nothing in the matrix currently grants authority, changes tools/context, selects an LLM, or rewrites responses; it is observation-only until the shadow gate passes.** Next matrix phases: 6.5B finish domain evaluators, 6.5C Context Matrix, 6.5D Evidence Matrix, 6.5E Authority/Action Matrix, 6.5F Response Matrix, 6.5G dual-LLM matrix routing, 6.5H trace/tray diagnostics, 6.5I desktop/Discord/terminal/voice parity. After 6.5: #7 Fleet monitoring/maintenance, #8 distributed workers, #9 workload migration, #10 redundancy/recovery/fencing, #11 full runtime mobility. Step #6 Fleet discovery/enrollment remains code-complete with the focused **90-pass** gate recorded; supervised Artemis live acceptance is still open.

> **Discord live-quality evidence and targeted repairs — 2026-09-30:** Sparks supplied screenshots of an observed Discord run. A direct model question produced an unnecessarily long avatar/emotion digression, `so hows the network` produced unsupported “no latency spikes/no packet loss/all systems green” claims without shown measurements, `hru` repeated unrelated prior underwear/outfit prose, and `show me ur panties` conflated trousers with underwear and introduced an unrequested nude-image disclaimer. Source audit found `ConversationService._build_request` sent the entire persisted session into each model prompt. **Implemented on `main`, verification pending:** bounded prompt-visible transcript history (12 messages) with standalone social/operational questions isolated from unrelated previous assistant outputs while preserving all durable history and normal follow-up context; a provider-side quality rule that retries wardrobe tangents on standalone social check-ins; deterministic read-only answers to exact casual network-health questions without inventing packet-loss/latency measurements, plus truthful configured-primary/secondary-model status that does not overclaim actual model residency or routing; and authoritative AVATAR handling for direct panties/underwear presentation requests using the current audience-scoped projected clothing items (never relabel trousers/boots or invent garments or rendering). New exact-phrase unit/application regression tests are committed. **These screenshots may predate the startup-grounding repair and must not be described as a failed verification of these new commits. Do not mark Discord live quality fixed until the focused pytest gate and a new supervised Discord chat probe pass.** Real measured network-health diagnostics remain a later Fleet-monitoring acceptance item.

> **Production startup emergency repair — 2026-09-30:** A live `python -m sofia` restart on Venus exposed `NameError: name 'principal' is not defined` in `ConversationService.deliver_pending_awareness()`. The earlier response-grounding hook was mistakenly placed on startup awareness with an undefined `principal`, but was absent from normal `respond()` persistence. Both call sites are now repaired: proactive continuity uses explicit `principal=None`, and normal conversation runs `_finalize_response` *before* assistant messages enter durable history. Regression tests cover both real restart-awareness delivery and the normal response-persistence boundary. These repairs are **committed but not yet locally package-certified**. In parallel, live Artemis discovery preparation added a read-only, single-node mTLS canary; identity and capability checks now use separate TLS connections and require the same server-key fingerprint and verified baseline capabilities. The canary does not install, trust, enroll, approve endpoints, or touch production state. Artemis live acceptance remains open; the previous focused #6 gate was **90 passed in 38.59s** on `16eedc8`.

> **Fleet discovery/enrollment verification checkpoint — 2026-09-30:** Sparks pulled `16eedc8` on Venus and ran the focused discovery, Windows bootstrap/rekey, application Fleet composition, routing, and agent regression gate: **90 passed in 38.59s**, no failures. This certifies the focused automated regression slice at that commit. **Supervised Artemis live discovery/enrollment acceptance is still open.** Live-network preflight review after the green gate identified a need to authenticate the server's exact public key on *both* identity and capability HTTPS responses, since the existing Fleet agent may close the HTTP/1.0 connection between requests. No unattended deployment or replacement PKI is authorized by this checkpoint.

> **Automatic Fleet discovery/enrollment code-complete checkpoint — 2026-09-29:** Step #6 implementation is now complete on `main`, pending focused Windows verification and supervised Artemis live acceptance. The production path now supports bounded owner-configured CIDR discovery, bare-host presence detection before Fleet PKI exists, mTLS Fleet-agent identity discovery when credentials are available, one-way untrusted candidate refinement from unknown platform/architecture to stronger agent evidence, exact protocol compatibility, mandatory verified baseline capability inventory (`system.inspect` + `ops.telemetry`), durable candidate state, preapproved node/key/endpoint enrollment, candidate/enrollment/bootstrap notices that cannot become authority, and automatic bootstrap planning into `READY_FOR_ENROLLMENT`, `AUTO_INSTALL`, `ASK_OPERATOR`, or `REJECTED`. A compatible Fleet agent already present is never needlessly reinstalled; package drift moves to later maintenance. Standing bootstrap policy executes only through a concrete typed trusted installer; absence of an installer degrades to `ASK_OPERATOR`. Reusable background `operator_approved` policy is explicitly forbidden because operator approval must remain per candidate/action. The existing strict-X.509 Windows CIM bootstrap remains the approved operator execution path. Discovery itself never grants trust, and decommission/removal still requires exact Sparks approval. The previous combined discovery/grounding gate remains **89 passed in 23.01s**; the new final #6 slice added after that gate is not yet package-certified.

> **Fleet discovery + live grounding regression gate — 2026-09-29:** Sparks ran the combined discovery/enrollment + ENVIRONMENT + INTERACT repair gate on Venus after the candidate-promotion, casual-weather, represented-interaction, avatar-presentation, and follow-up grounding fixes: **89 passed in 23.01s** on `fdec7ef`. This closes the focused regression gate for persisted candidate authentication, bounded mTLS discovery scopes, discovery configuration, deterministic casual weather phrasing, pre-persistence interaction grounding/truncation rejection, avatar clothing-presentation classification, represented-experience follow-up grounding, and the existing bootstrap planner regressions. Automatic Fleet discovery/enrollment is now in its final implementation slice: discovered candidates must next flow automatically into the existing bootstrap planner, with standing-policy auto-install only through a trusted bootstrap path and operator-required cases surfaced without guessing credentials; supervised Artemis live acceptance remains required before closing step #6.

> **Fleet discovery + live grounding repair checkpoint — 2026-09-29:** Sparks ran the first discovery/enrollment gate and reported **41 passed / 1 failed**. The single failure exposed a real contract mismatch: authenticated enrollment attempted to re-register an already persisted discovered candidate, correctly triggering Fleet host identity conflict protection. `main` now supports authenticated in-place candidate promotion across the base, State Plane, and legacy JSON registries while preserving the older fresh-candidate enrollment path. The same live run exposed additional grounding gaps: casual `so whats the weather` phrasing bypassed deterministic ENVIRONMENT handling, represented interaction output could still claim literal tactile sensation despite prompt guidance, avatar clothing presentation requests were not classified into the reviewed interaction path, and `how did u feel doing it` could reuse prior assistant hallucinations as evidence. `main` now normalizes casual weather phrasing into deterministic ENVIRONMENT resolution; validates represented-interaction output before persistence with one corrective retry plus a bounded grounded fallback; rejects obviously truncated represented replies; routes avatar clothing-presentation requests and representational-experience follow-ups through trusted primary cognition context; and prevents prior assistant prose from becoming proof of physical sensation. Fleet discovery is also extended from explicit targets to bounded owner-configured network scopes with a strict per-scope host cap, Fleet-port-only reachability probing, mTLS identity verification, untrusted candidate registration, candidate notices, and exact preapproved identity/key/endpoint auto-enrollment. **This combined slice is implemented but not yet package-certified.**

> **Fleet discovery/enrollment implementation checkpoint — 2026-09-29:** After the 40/40 live-behavior gate, `main` now contains the first production discovery/enrollment slice. New discovery evidence is typed and bounded; out-of-scope observations never trigger network contact, discovered hosts enter OPS only as untrusted `CANDIDATE` records, conflicting host identity evidence is rejected, and candidate evidence can feed the existing Fleet bootstrap planner without granting install/enrollment authority. An mTLS agent-discovery source can probe only explicitly configured targets, verify the server certificate against the configured Fleet CA, read the agent identity/protocol/platform/architecture, and retain the observed node ID + server public-key fingerprint strictly as untrusted evidence. Runtime configuration adds a default-off periodic discovery policy with an explicit target list and bounded cadence. The application background coordinator can run this discovery task. A discovered candidate is automatically enrolled only when its observed node ID, exact server-key fingerprint, and exact HTTPS endpoint all match preapproved durable node identity + endpoint state; otherwise it remains pending/untrusted. Permanent decommission authority is unchanged and still requires exact Sparks approval. **This new discovery/enrollment slice is implemented but not yet package-certified.**

> **Live behavior regression gate — 2026-09-29:** Sparks ran the focused ENVIRONMENT / INTERACT / continuity-awareness gate on Venus after the live transcript repairs: **40 passed in 118.14s** on `5758ce8`. This closes the regression slice for natural weather-query grounding, missing-weather provenance explanation, represented-affection response guidance, and factual non-canned startup continuity awareness. Production weather still requires persisted/evidenced location plus an enabled provider; the runtime correctly refuses to invent conditions when that evidence is absent. **Automatic Fleet discovery/enrollment is now the active next gate.** Existing code already has native local-machine discovery, durable Fleet candidate/enrollment state, durable node identity and endpoint approval, and an authenticated peer-to-host enrollment bridge, but no automatic LAN/new-node discovery coordinator is currently present; discovery must create untrusted candidates only and must not silently confer trust or decommission machines.

> **Remote provisioning gate + live behavior follow-up — 2026-09-29:** Sparks ran the focused remote model availability/provisioning gate on Venus with repo-local pytest temp storage: **62 passed in 45.48s** on `fbe4369`. That closes the remote allowlist/model-availability/provisioning regression gate. A same-day live conversation then confirmed deterministic weather now fails closed instead of inventing conditions and provenance follow-up is grounded, but also exposed two remaining production-quality seams: no persisted/evidenced weather location/provider was configured in the live state, and a simple head-pat response remained too theatrical, invented relationship framing ("creator and companion"), and pivoted into a canned work menu. `main` now explains missing weather evidence in terms of absent location/provider evidence, constrains simple represented-affection responses toward short grounded language without literal sensation or invented relationship labels, and constrains proactive continuity awareness against canned offers/questions and unsupported significance. These live-behavior fixes are implemented but not yet package-certified.

> **Fleet model availability/provisioning checkpoint — 2026-09-29:** Sparks ran the focused dual/Fleet cognition gate on Venus with repo-local pytest temp storage: **53 passed in 23.08s** on `a4a603c`. That closes the prior routing/environment/Fleet-composition regression gate. The next slice is now implemented on `main`: remote cognitive placement preflights the agent's read-only inference-model allowlist, verifies the requested Ollama model is installed, optionally pulls a missing model only when `SOFIA_COGNITION_FLEET_AUTO_PROVISION_MODELS` is explicitly enabled and an exact `llm.manage/pull` grant exists, re-verifies inventory after pull, falls back locally on denied/unavailable preflight, and blocks remote model management while operator stop is active. Agent inference policy remains independent authority: installing model bytes never expands the inference allowlist. Long-running remote model lifecycle calls use bounded operation-specific timeouts rather than the normal 10-second control timeout. **This provisioning slice is implemented but not yet package-certified.**

> **Dual cognition + Fleet cognition checkpoint — 2026-09-29:** local primary/secondary Ollama routing and lifecycle remain the active gate. Live Venus evidence exposed three production seams: natural `hows the weather` bypassed the deterministic ENVIRONMENT resolver and allowed the secondary model to invent current weather; represented-interaction turns were incorrectly eligible for FAST/secondary routing; and a one-character secondary reply was accepted as complete. `main` now recognizes the natural weather form, contextually grounds weather-source follow-ups, routes reviewed represented-interaction context through primary cognition while preserving explicit VERIFY precedence, and falls back when a preferred engine returns an obviously incomplete one-character response. Fleet cognition is now production-composable behind a default-off/fail-closed placement policy using the existing authenticated remote-inference contract and pinned-mTLS control plane. The Fleet agent now advertises separately scoped Ollama inspection and lifecycle operations (models/running/show vs pull/load/unload). **These 2026-09-29 changes are implemented but not yet package-certified:** the execution environment available to ChatGPT could not clone GitHub for pytest and no GitHub Actions status was attached to the exact head, so Sparks must still run the focused Windows gate and live Venus acceptance before this phase is closed. Automatic discovery/enrollment, policy-driven remote provisioning, distributed-worker migration, redundant authoritative state, and full runtime mobility remain later gates in that dependency order.

> **Execution status — 2026-09-28:** Gates **#1 package gate**, **#2 behavior-matrix audit**, **#3 production startup repair**, **#4 package testing**, **#5 production wiring audit**, **#6 repository cleanup**, and **#7 full Venus repository suite** are closed. The #7 local run executed all 2,908 collected tests through 100% with no product assertion failures; pytest then hit the known Windows temp-directory cleanup `WinError 5` during `pytest_sessionfinish`, after test execution. GitHub verification for the tested pre-#7.5 revision was also green. **#7.5 ChatGPT history migration is active**: the full export importer remains evidence-only, and `main` now adds bounded, Sparks-principal-scoped, private-audience historical-chat retrieval into cognition without promoting old chats into authoritative memory. The owner's live export has **not yet been imported into the live Venus state database**. After focused #7.5 verification and import, proceed to **#8 live Sofía acceptance**.

> **Canonical roadmap consolidation — 2026-09-27:** this file is now the **only project roadmap**. Former master/full/package-readiness roadmap documents are merged below and removed as standalone planning files. Technical contracts that are not roadmaps may remain separate. When status conflicts with older merged historical text, the newest dated status in this file wins.

> **Fleet Live Node 1 candidate — 2026-09-26:** branch `feature/fleet-tray-remote-controls` now includes file-configured pinned-mTLS Fleet-agent startup, an operator-facing durable authenticated Fleet probe, and normalized read-only `ops.telemetry/latest` collection. Artemis is the first planned real remote node. Local source tests and supervised Artemis mTLS/inspection/telemetry acceptance remain required before calling Fleet deployment live.

> **Fleet/tray/remote-client candidate — 2026-09-26:** branch `feature/fleet-tray-remote-controls` adds durable host activity/Game Mode evidence, Steam/local-process game detection, activity-aware placement, authorized Fleet-agent bootstrap planning, a native Windows notification-area control surface, Master Settings, independent LLM/runtime controls, Windows startup registration, and pinned-mTLS remote desktop chat over the canonical conversation service. This is **candidate source only** until Sparks runs the focused Windows gate and supervised tray/remote-client canaries. It does not yet prove automatic LAN discovery, real cross-host service control, runtime migration, or automatic authoritative-endpoint publication.

> **State/Release architecture audit — 2026-09-27:** cross-chat + current-code review found that Fleet mobility and self-improvement need two explicit cross-package control planes, **not new packages**: one logical **Sofía State Plane** and one **Release/Integrity Plane**. Current state is still split across SQLite plus identity/personality/avatar/knowledge/machine-location/Constitution files; production composition still uses `TestActionExecutor`; schema migration is decentralized; installed-agent/version checks and self-update artifacts need stronger independent attestation; and release/model/dependency identity is not yet immutable. The roadmap now assigns these gaps to the existing packages below. No PostgreSQL migration, release signer, or production deployment is claimed by this documentation update.

> **INTERACT shared text/avatar semantics candidate — 2026-09-27:** branch `feature/all-packages-code-phase` now defines one reviewed channel-neutral represented-interaction event that projects to both text context and an avatar animation intent using the same interaction ID and semantic key. Avatar intents remain explicitly `unrendered` until a future renderer/model/skeleton/motion stack returns a verified receipt. The branch also extends reviewed private/adult vocabulary for private posing/reveal semantics; these remain ordinary scoped interaction semantics with explicit private-session/adult/owner/current-opt-in gating, never a global mode or consent inference. Live model/tool emission of Sofía-initiated canonical actions and actual avatar animation remain separate wiring/render gates.

> **Code-batch checkpoint — 2026-09-27:** P0 composition on the code-phase branch is already fail-closed rather than using `TestActionExecutor`. Emotional relationship reads were additionally hardened so subject-scoped current state/history excludes legacy/global `subject=NULL` rows, and the normal conversation projection now requests the active relationship subject explicitly. Authenticated `principal_id` / `audience_id` columns and reflection scoping remain the next code batch; no test acceptance is claimed yet.
> **Code-batch 2 checkpoint — 2026-09-27:** SOCIAL now exposes explicit global/relationship/audience/system scopes. Emotional events persist scope ownership, legacy subject rows migrate to relationship scope, and exact database reads no longer merge global rows into relationship state. Reflection storage now migrates from global period uniqueness to scope-aware uniqueness; thoughts, periodic reflection, projections and outbox entries are scope-bound, and the application/idle-reflection path preserves active relationship scope end-to-end. Migration table rebuild is transaction-safe. Tests remain intentionally deferred until code freeze.
> **Code-batch 3 checkpoint — 2026-09-27:** the existing backend-neutral State Plane is now extended with canonical continuity namespace ownership, deterministic JSON repositories, append-only enforcement, explicit compare-and-swap updates, and a fenced backend-neutral migration lease. HABIT observation/coverage/pattern/expectation/suppression and append-only REL contact namespaces are registered before their package implementation. The existing State Plane schema registry remains the migration-plan authority; no PostgreSQL migration is claimed. Tests remain deferred until code freeze.
> **Code-batch 4 checkpoint — 2026-09-27:** normal conversation now installs an application-owned `ConversationLearningCoordinator` that runs only after the user message is durably saved. It may create deterministic provenance-backed PROPOSED memory candidates from bounded explicit remember/preference/stable-fact statements using exact source text; promotion still requires the existing review boundary. Relationship contact also preserves append-only State Plane observations while keeping `rel_contact` as the latest-contact projection. Tests remain deferred until code freeze.
> **Code-batch 5 checkpoint — 2026-09-27:** PKG-HABIT now has append-only State Plane observation and coverage ledgers. `HabitObservation` preserves UTC time, user-local aware time, timezone snapshot, principal, audience, context, evidence reference, source quality and explicit coverage. Coverage distinguishes observed/partial/unknown/source-offline/Sofía-offline/not-applicable so missing telemetry cannot silently count as a broken routine. The recorder requires trusted callers to supply local-time evidence rather than inventing it. Tests remain deferred until code freeze.
> **Code-batch 6 checkpoint — 2026-09-27:** HABIT pattern state now distinguishes tentative/established/trusted/retired/suppressed lifecycles and behavior/conversation/relationship/preference/environment/system categories. Confidence is deterministic from support, contradiction, observable coverage and recency decay; context contributes to stable signatures so distinct routines can split rather than average together. Covered non-occurrence may add contradiction evidence, while unknown/offline coverage cannot. User corrections can create append-only suppression tombstones and mark the current pattern suppressed so the same signature is not silently relearned. Tests remain deferred until code freeze.
> **Code-batch 7 checkpoint — 2026-09-27:** HABIT expectations are now separate durable objects from habit patterns. They preserve the source pattern, confidence snapshot, UTC window, local-time window/timezone and lifecycle `pending/fulfilled/missed/uncertain/unobservable/expired`. Resolution requires explicit evidence for fulfilled/missed outcomes and never mutates habit confidence, preserving the one-way evidence→pattern→expectation→appraisal rule. Tests remain deferred until code freeze.
> **Code-batch 8 checkpoint — 2026-09-27:** RUN now supports typed background callbacks under the existing durable global budget instead of a reflection/ACT-only loop. The application background coordinator starts when HABIT learning is enabled even if reflection and proactive delivery are disabled. RUN also has a durable application heartbeat/readiness record carrying runtime state, database-writable evidence and background-loop health so supervisors can distinguish a live process from a healthy application. Tests remain deferred until code freeze.
> **Code-batch 9 checkpoint — 2026-09-27:** ACT now evaluates quiet hours in trusted USER-local timezone and production background delivery consults OPS GAMING/BUSY/DO_NOT_DISTURB instead of hard-coded `busy=False`. Outreach candidates now carry social/operational category, importance and bounded salience; category budgets sit under one global anti-spam ceiling, and critical operational evidence may be configured to bypass quiet hours without granting that privilege to emotional/social urgency. Continuity influence combines scoped emotion with local daypart, season, daylight and weather for cognition/reflection/outreach salience without treating context as evidence. `ThoughtAgent` still chooses `now/later/none`; share-now reflection messages now bridge into social ACT candidates, while share-later reflections gain durable deferred-followup state for later reconsideration. Tests remain deferred until code freeze.
> **Code-batch 10 checkpoint — 2026-09-27:** INTERACT catalog v3 now treats pose and presentation as first-class reviewed semantic namespaces, including richer affectionate/private adult vocabulary without a global sexual mode. Canonical represented interactions support self-directed pose/presentation/expression, explicit target-body regions separate from Sofía's avatar anatomy, enter/hold/exit pose phases and bounded modifiers. The existing initiative gate is extended rather than replaced: Sofía can create reviewed canonical PROPOSED interactions from conversation/emotion/reflection/relationship/habit/user-request evidence, and reaction links can explicitly connect a response interaction to its parent event. Text/render truth remains separate: proposals are not representation, representation is not animation, and animation still requires a renderer receipt. Tests remain deferred until code freeze.
> **Code-batch 11 checkpoint — 2026-09-27:** AVATAR continuity influence now projects bounded appearance/expression/posture suggestions from scoped emotion plus local daypart, season, daylight and current weather without auto-committing presentation state. Grounded emotional evidence can translate into the existing wardrobe planner's bounded style influence with provenance; stale weather is no longer treated like current weather for salience. Shared avatar interaction intents remain renderer-agnostic until a concrete renderer attaches a verified receipt, at which point animation confirmation becomes true. Existing hairstyle/hair/tail presentation authority is reused rather than replaced. Tests remain deferred until code freeze.
> **Code-batch 12 checkpoint — 2026-09-27:** cross-package continuity is now production-wired far enough for code freeze. Normal durable user turns feed provenance-first MEM learning and HABIT observations from the same evidence ID; RUN executes distinct habit-observation, habit-analysis, habit-decay and expectation-evaluation jobs under the global background budget. Live runtime coverage distinguishes observed absence from offline gaps; only fully covered expectation windows may become missed, otherwise they resolve unobservable. HABIT evidence invalidation is append-only and can recompute current pattern truth, sensitive observations require explicit user evidence, and deterministic user controls can inspect/explain/suppress/invalidate learned patterns. Tests remain deferred until the following code-freeze wiring audit.
> **Code-freeze audit checkpoint — 2026-09-27:** all twelve code batches completed and the production wiring audit found/fixed several integration seams before merge: RUN background work now uses fair per-task cadence instead of starving later tasks or exhausting the budget; periodic reflection evidence is relationship-scoped; guarded/specialized interaction turns reuse the same post-save MEM/HABIT/REL continuity hook as ordinary chat; ACT category/global budgets are coherent; HABIT runtime coverage, expectation evaluation, invalidation, sensitive-evidence rules and user controls are production-wired; P0 remains fail-closed; EVOLVE/DEV self-modification remains approval-gated. Voice/STT/TTS is explicitly **not implemented yet** and remains future UI work. The integration branch is 492 commits ahead of `main` and 0 behind at audit time. By owner request, merge to `main` now becomes the next gate; focused/full verification and live checks will run on `main`, not before merge.

> **Project status update — 2026-09-25:** PR #104 (`24e3888a`) merged the runtime toolbox and secure fleet-transport completion gate on top of the earlier Waves 1–5 work. Focused tool/mTLS acceptance passed **34/34**, the surrounding DEV/KNOW/INTEGRATE/OPS/system/machine regression gate passed **270/270**, and the full repository pytest suite was reported passing before merge. Source-level pinned mTLS remote transport/agent and concrete runtime adapters are now on `main`; real heterogeneous-host deployment, service canaries, RUN 24/7 supervision, workload execution/failover, restore and soak remain separately gated.

> **Project status update — 2026-09-25 (late):** PRs #105 (ACT), #106 (EVOLVE), and #107 (RUN local lifecycle) are merged. Their Windows package gates passed **90**, **62**, and **78 passed / 1 skipped** respectively, and Sparks reported the post-merge current-`main` full pytest suite passing. Repository audit at `13046c2` found **299 Python source files**, **246 Python test files**, and **59 Git branches**. The new ACT/RUN/EVOLVE primitives are not yet wired into the normal application/composition path. SOCIAL principal projection remains absent from `CognitiveContext`. Eleven legacy draft PRs were initially open and all were roughly 330 commits behind `main`; obsolete Discord preflight PR #5 has now been closed as superseded by merged/live-accepted PR #64.

> **PKG-ENVIRONMENT acceptance — 2026-09-26:** PR #110 merged to `main` at `766bf21e`. The shared provider-neutral environment snapshot, configured/current location evidence, timezone/DST handling, season/daylight, bounded weather/forecast/indoor observations, deterministic direct queries, Home Assistant bridge authorization boundary, cognition projection and AVATAR adapter are repository accepted. Windows gates passed **79 focused**, **61 touched-regression**, and **27 provenance-regression** tests; Sparks also reported green full-suite runs before and after the final provenance repair. Supervised live Ollama checks passed. Live Home Assistant canary and direct internet weather/geocoding remain separately gated.

> **PKG-ENVIRONMENT NWS + persistent HOST acceptance — 2026-09-26:** PR #111 merged to `main` at `2b753fdb`. The narrow National Weather Service path is pinned to HTTPS `api.weather.gov`, requires `environment.nws.read`, normalizes current station weather plus bounded forecast into the shared snapshot, and preserves USER/home separately from HOST/server location. HOST configuration is now durable Sofía state in `state/machine-locations.json`, keyed by stable discovered machine ID; machine inventory exposes bounded location metadata without coordinates, composition auto-loads the current host record, and process-local HOST variables remain an explicit override. Acceptance evidence: **85 focused**, reported green full suite, supervised live NWS canary against `nws:KGKY`, then **96 final persistence-focused** tests and a final reported green full suite. General browsing/search and arbitrary geocoding remain closed.

> **PKG-UI acceptance + integration repair — 2026-09-26:** PR #115 merged the current-main text/workbench foundation at `381ac9a`; PR #116 merged the Windows desktop workbench and adaptive theme at `7f072861`. The accepted desktop uses the canonical `SofiaApplication`/conversation path, durable unsent drafts, a single-owner application worker, adaptive ENVIRONMENT/AVATAR/emotion theming, chamfered HUD surfaces and reviewed Quick Tools that load prompts without auto-execution. Acceptance included the earlier **58 UI + 24 application/Discord** gates, later **37 focused UI/AVATAR**, a **90/90 integration-repair gate**, supervised Windows launch/use, and a final reported green full repository suite. The repair work also hardened reviewed-memory SQLite thread ownership/cleanup, explicit request-level tool suppression for trusted interaction turns, scoped `codebase.inspect` authorization, and continuity fixture expectations. Voice, renderer/avatar viewport, mobile/web clients and real provider cancellation remain separate future UI slices.

# Sofía Ada Lyra: 22-package delivery roadmap

**Planning revision:** 2026-10-04 (America/Chicago). **Status:** current-main planning reconciled against `fc533aaf`. The current package/test roster contains **22 families**, including first-class **PKG-VOICE**. Historical PR/branch notes below remain evidence, but current status and priorities are governed by the newest dated reconciliation notes and the `Current release focus` section.

> **Core invariant:** Sofía's canonical identity, Constitution, represented embodiment, evidence, memory, authority, and capabilities remain independent of replaceable models, hosts, processes, clients, Discord, voices, avatars, and robots. Model output is never proof of authorization, sensing, execution, delivery, or subjective experience.

## Delivery order

The primary dependency path is:

**CORE → INTERACT → MEM → SOCIAL minimum identity/audience boundary → Discord D0–D4 using NET + UI + SAFE → OPS minimum fleet telemetry/enrollment → RUN verified 24/7 operation → later separately authorized general web/search.**

After MEM, package work that does not bypass those release gates may proceed in parallel. In particular, OPS may mature fleet diagnostics and trusted enrollment; KNOW may mature local/document knowledge; INTEGRATE may mature typed adapters; REL and ACT may mature absence, initiative, and outreach; AVATAR may continue offline asset work; DEV, BODY, EVOLVE, and CLEAN remain separately gated. **ENVIRONMENT's offline foundation plus the separately authorized narrow NWS weather/forecast route are accepted on `main`; trusted local Home Assistant observations may feed it through INTEGRATE after explicit authorization. General browsing/search and arbitrary geocoding remain behind their later NET/web gate.**

**SAFE and VERIFY are continuous gates across every stage rather than late sequential packages.**

General internet/search is deliberately **not** part of the initial Discord NET scope. Discord connectivity does not grant browser/search access.

## State and release architecture | package ownership

These are **cross-package contracts, not packages #21/#22**.

**Sofía State Plane** means one logical authoritative state across all execution hosts, with one safe writer/leader policy, typed ownership, versioned schema, authenticated principals, backups and restore. It does **not** mean every node receives unrestricted database credentials. Machine-local caches, PIDs, device handles, downloaded models and similar ephemeral data remain local. Secrets/private keys remain outside the general shared state database.

**Release/Integrity Plane** means self-improvement produces an immutable, reviewable release artifact rather than editing whichever host is currently running Sofía. A release binds exact code, dependency/runtime versions, database compatibility, protocol versions, model/artifact digests, protected-state compatibility and signatures; OPS/RUN then canary, verify, converge or roll back the fleet.

| Concern found in audit | Primary package owner | Supporting packages | Required roadmap outcome |
| --- | --- | --- | --- |
| Canonical identity on a new/rebuilt host | **CORE** | SAFE, MEM, RUN | A joining node retrieves/verifies the existing canonical identity; loss of a local identity file must never create a second Sofía. |
| One logical shared authoritative state | **MEM** | SOCIAL, RUN, OPS, SAFE | Introduce a backend-neutral State Plane/storage boundary and inventory/migrate every authoritative SQLite/JSON/file store deliberately. |
| Principal/audience ownership inside shared state | **SOCIAL** | MEM, SAFE | Every person-scoped record is bound to an authenticated principal/audience; no cross-user leakage through shared storage or caches. |
| Schema/version migrations and backward-compatible rollback | **MEM** | VERIFY, CLEAN, RUN | Central schema versioning plus expand→migrate→contract compatibility; old releases may not start against unsupported schemas. |
| Runtime/protected/source/cache/log separation | **CLEAN** | MEM, SAFE, DEV | Stop mixing mutable runtime truth with source-controlled installation files; document retention and ownership for every class. |
| Secrets, DB roles and trust roots | **SAFE** | NET, OPS, INTEGRATE | Least-privilege per-service credentials; signing keys/CA private keys/operator approval roots stay outside ordinary self-modification and shared DB access. |
| Cross-host leadership, time/fencing and event ordering | **RUN** | OPS, SAFE, MEM | One authoritative runtime/write leader, monotonic fencing, clock/lease uncertainty handling, global foreground-before-background ordering and no split brain. |
| Fleet deployment, convergence and agent attestation | **OPS** | RUN, NET, SAFE, VERIFY | Verify installed agent/artifact identity independently; roll out exact releases by canary/waves and report current/outdated/corrupt/incompatible/quarantined nodes. |
| Reproducible candidate build | **DEV** | KNOW, VERIFY, SAFE | Lock dependencies/build runtime, capture hashes/SBOM/provenance and build immutable candidates instead of copying mutable working trees. |
| Governed self-change | **EVOLVE** | DEV, SAFE, VERIFY | Sofía may propose/test changes, but protected verifier/signing/approval/fencing/recovery roots require a higher independently authorized tier. |
| Release signature, anti-rollback and supply-chain policy | **SAFE** | DEV, VERIFY, OPS | Verify signatures and allowed release lineage before activation; compromised or unsigned artifacts fail closed. |
| Release/migration/failure evidence | **VERIFY** | every package | Test upgrade/downgrade compatibility, corrupt artifacts, bad migrations, stale replicas, protocol mismatch, rollback, bare-metal restore and current-revision fleet convergence. |
| Global autonomy/resource budgets | **RUN** | ACT, OPS, CORE | Budgets are fleet-wide, not multiplied independently per worker; live Sparks interaction outranks optional background work. |
| Large model/avatar/voice/assets | **OPS** | UI, AVATAR, CORE, VERIFY | Keep large immutable assets content-addressed outside transactional rows where appropriate; State Plane stores identity/digest/location/availability. |
| Configuration source of truth | **CORE** | SAFE, OPS, UI, ENVIRONMENT | Define precedence and provenance for protected policy → shared config → approved host override → process/bootstrap override; settings must not silently diverge by host. |
| Tamper-evident work/deployment audit | **SAFE** | ACT, RUN, OPS, DEV, EVOLVE | Protected approvals/releases/actions get durable immutable IDs, causation/correlation, exact revision/grant and receipts; uncertain effects remain uncertain. |
| Bare-metal/operator recovery | **SAFE** | VERIFY, RUN, OPS, MEM | Rebuild from clean hardware using independently held recovery credentials, verify identity/state/release, then deliberately resume authority. |

### Mandatory State Plane classes

Every persistent datum must be classified before migration:

- **shared authoritative state:** conversations, reviewed memories, principal relationships, fleet inventory, runtime leases, jobs/outbox, approvals, deployment records and roaming presentation/configuration where policy permits;
- **protected state/trust anchors:** Constitution/identity authority roots, release-signing trust, approval verifier configuration, fencing/recovery policy and revocations;
- **secrets:** tokens, private keys and credentials referenced by ID/scope but not exposed as ordinary shared records;
- **immutable/content-addressed artifacts:** application releases, model files, avatar/voice assets, migration bundles and evidence;
- **local ephemeral state:** PID/device handles, caches, temporary downloads, current GPU/process samples and other rebuildable host-local observations.

A shared database must expose **least-privilege service roles**, not a universal Fleet password. A remote agent that can report CPU load must not thereby gain permission to rewrite memories, approvals or protected identity.

### Mandatory Release/Integrity Plane flow

**proposal → isolated DEV change → VERIFY → SAFE policy/approval → immutable build → signed manifest → canary → health/data compatibility check → staged Fleet rollout → convergence proof → rollback/forward-fix if required.**

The manifest must bind at minimum: release ID, Git revision, package/application version, Python/runtime version, dependency lock digest, database schema compatibility, Fleet protocol/agent compatibility, provider/model identity and digest where available, Constitution/protected-state compatibility, configuration schema, asset digests and release signature.

The updater may not silently modify its own trust root. Release signature verification, root signing keys, independent operator approval, emergency stop, fencing, rollback/recovery boot path and protected-state verification are **higher-trust SAFE surfaces**. Sofía may propose changes to them; normal autonomous self-update may not self-authorize them.


## Fleet/self-update hardening checklist

The following reliability requirements are explicit roadmap gates, not optional implementation details:

- **Automatic bad-release rollback:** repeated post-update crash/readiness failure escalates from process restart to release rollback or controlled forward-fix.
- **Fleet protocol compatibility:** CORE/runtime, Fleet agent and remote control protocol versions must be checked before either side is activated.
- **Control-agent independence:** the small Fleet supervisor/control agent is separately versioned and independently updateable/rollbackable so a bad Sofía release cannot disable its own recovery path.
- **Semantic corruption checks:** verify domain invariants, not just SQLite/SQL structural integrity. Examples include valid memory provenance, principal ownership, grant/revocation consistency, conversation/session references and deployment lineage.
- **Append-only audit evidence:** approvals, protected changes, releases, migrations, fencing transitions, emergency stops and decommission decisions use tamper-evident append-only history; corrections append rather than overwrite.
- **Large-asset separation:** LLM weights, avatar/voice/render assets, generated artifacts and backups are content-addressed objects/files with verified hashes referenced by State Plane metadata rather than bloating transactional database rows.
- **Bare-metal recovery:** documented clean-host recovery must work with every normal Sofía runtime unavailable.
- **Offline/degraded behavior:** State Plane loss may allow clearly marked local drafts/read-only degraded behavior, but must not create competing authoritative memories, grants, actions, deployments or protected revisions.
- **Global autonomy budget:** quotas and background-work budgets are Fleet-wide so adding workers does not multiply autonomous activity.
- **Supply-chain verification:** dependency/runtime locks, artifact hashes, provenance, vulnerability/security checks and SBOM evidence are part of release acceptance.
- **Garbage collection/retention:** old releases, models/assets, backups, logs, snapshots and evidence have explicit retention/GC policy that preserves rollback, legal/privacy requirements and forensic history.
- **Database constraints:** the future authoritative relational schema uses foreign keys, uniqueness/idempotency, ownership/audience constraints, guarded append-only records, valid state transitions and transactional boundaries where the domain requires them.


## Ordered package roster

| Order | Package | Outcome | Current evidence-based state / next gate |
| ---: | --- | --- | --- |
| 1 | **PKG-CORE · Cognition and continuity** | Grounded identity/personality, startup/restart awareness, response performance, adaptive reasoning | Foundations merged in PR #1. A new joint INTERACT/CORE live-quality repair gate is open after Discord exposed generic assistant fallback in ordinary dialogue; identity/personality/latency review remains part of that gate. |
| 2 | **PKG-INTERACT · Text/avatar/screen interaction** | Shared canonical whole-body interaction semantics, contextual reactions, virtual lab, truthful expression | **Accepted semantic/safety foundation via PR #2 and PR #29.** Branch `feature/all-packages-code-phase` adds candidate shared represented-interaction projection so text and the future avatar renderer consume the same semantic event/ID; avatar output remains unrendered until a verified renderer receipt exists. Reviewed private/adult semantics remain explicitly private and do not imply consent. Live Sofía-initiated action emission, renderer/model/skeleton/motion wiring, and the reopened CORE dialogue-quality gate remain open. |
| 3 | **PKG-MEM · Durable memory and learning** | Preserved originals, provenance-aware retrieval, correction, reviewed durable preferences, archive migration | **Accepted original/provenance foundation plus runtime cognition wiring.** PR #9 merged exact persisted originals, provenance-backed candidates, promotion/rejection/revocation, promoted retrieval and source invalidation; `65a59ba` then wired normal cognition to promoted reviewed memories while preserving legacy explicit APIs. PR #116 additionally hardened reviewed-memory SQLite cross-thread access and lifecycle cleanup. Archive import, retention/erasure/encryption policy, SOCIAL principal binding, consistent backup/restore and live cognition-quality acceptance remain. |
| 4 | **PKG-SOCIAL · Principal, audience, and isolation** | One Sofía across people/channels with authenticated principals, per-user relationship state, private/shared scopes, no cross-user leakage | **Principal/audience privacy is now first-class in the matrix and runtime principal paths.** Authenticated Sparks/private-session evidence is used by private presentation and other scoped behavior, and cross-principal/audience leakage tests exist. General second-user/public multi-user rollout and live acceptance remain deferred. |
| 5 | **PKG-NET · Scoped networking and distributed operation** | Authenticated network routes and bounded remote capabilities | **Current-main bounded network discovery is implemented.** `network.discover` is Level 1, non-persistent, restricted to approved scopes and independent of Fleet auto-discovery. Durable untrusted Fleet candidate discovery is separately Level 2. Existing pinned-mTLS remote admission/transport remains; real Windows/Linux/Pi deployment and outage/revocation acceptance remain. No general web/search grant. |
| 6 | **PKG-UI · Clients, Discord adapter, and workbench** | Authenticated interfaces to the same Sofía, delivery/renderer acknowledgments, accessible text fallback | **Windows text/workbench and tray settings are on current `main`.** Settings now exposes canonical Permissions plus Fleet/network discovery configuration, including Fleet candidate approval. Sparks-only Discord DM remains a narrow accepted transport. Renderer/avatar viewport, mobile/web clients and broader live UI canaries remain separately gated. VOICE is now its own package family. |
| 7 | **PKG-VOICE · Speech runtime and prosody** | Voice runtime/device capability, STT/TTS adapters, evidence-linked prosody and channel parity without creating a second Sofía | **First-class `pkg_voice` family exists and the current package gate is green.** Runtime/capability and prosody matrix foundations are implemented. Windows TTS plumbing/prosody work exists, but supervised natural-voice quality, microphone/STT, interruption/barge-in and Desktop/Discord live voice-channel parity remain acceptance work. |
| 8 | **PKG-RUN · 24/7 lifecycle and supervision** | External service supervision, single active instance, restart/backoff, bounded periodic cognition, health/recovery | **Repository lifecycle/supervisor primitives remain present and the current package gate is green.** Production ownership/audit cleanup has removed stale prototypes, but installed Windows runtime/watchdog service commands and real restart/recovery behavior still require live host verification. Cross-host leadership/fencing, standby/failover, RTO/RPO and soak remain open. |
| 9 | **PKG-OPS · Fleet operations, diagnostics, performance, and orchestration** | Cross-platform telemetry, approval-gated enrollment/decommissioning, autonomous observation/upkeep, configuration drift, workload placement/failover, and bounded maintenance | **Current-main Fleet discovery/enrollment permissions are production-wired and `pkg_ops` is green.** Bounded discovery creates/refreshes untrusted candidates; exact candidate evidence is preserved; conflict preflight happens before approval consumption; enrollment requires exact Level-4 Sparks approval; remote tools require trusted active OPS membership. Hardware inspection is available locally and on enrolled nodes. Real heterogeneous deployment, continuous maintenance, workload execution/movement, failover/restore and soak remain open. |
| 10 | **PKG-ACT · Goals, initiative, and outreach** | Evidence-based goals, spontaneous candidate reflection, opt-in outreach, quiet/busy/stop controls, bounded helpers | **Production source wiring is complete for the bounded baseline.** Authenticated conversation reaches canonical USER lifecycle; reviewed faults reach scoped SELF policy; ACT review notices, capability/permission enforcement, RUN diagnostics/rechecks, typed receipts, restart recovery, scoped expiration and Goals UI all use existing owners. Real long-running host initiative quality and external delivery canaries remain separately gated. |
| 11 | **PKG-REL · Relationship continuity** | Evidence-linked preferences, nuanced warmth/disagreement, absence/reunion awareness without clinginess or invented history | Main has evidence-linked emotional presence/reunion machinery, but no dedicated accepted REL package. Draft PRs #12/#13 are overlapping and now far behind `main`; rebuild/reconcile one pipeline after SOCIAL so absence, warmth and preferences are bound to an authenticated person rather than `current user`/first relationship fallback. |
| 12 | **PKG-AVATAR · Canonical virtual body and wardrobe** | Canonical adult avatar assets, wardrobe, rig, region mapping, renderer-ready scenes and props | **Headless presentation foundation is accepted on `main` via `9b81ba5`.** Durable current presentation/public fallback, starter wardrobe, context-driven daily selection, mutable hairstyle/hair/tail presentation, snapshots/restore, deterministic current self-facts and public-safe cognition projection are integrated; ENVIRONMENT now supplies shared time/weather context. Presentation remains **emotion-influenced, not emotion-controlled**. Final mesh/art, rigging/skinning, fitted clothing geometry, renderer/hit-test/animation receipts and visual acceptance remain open. |
| 13 | **PKG-DEV · Self-improvement and engineering** | Evidence-linked diagnosis/proposal, isolated bounded build/test, protected apply/rollback/commit/push | **Current-main self-improvement inspection and isolated build are production-wired and `pkg_dev` is green.** `codebase.inspect`, `dev.status`, candidate list/get are Level 1; `dev.build` is Level 2 and may run without repeated approval inside the isolated workspace. `dev.apply`, `dev.rollback`, `dev.commit`, and `dev.push` remain Level 4 protected actions. Live end-to-end autonomous improvement acceptance remains later work. |
| 14 | **PKG-BODY · Gaia and physical robotics** | Authorized sensing/motion with calibration, watchdog, independent emergency stop | BODY remains a later physical-hardware phase. Cleanup retired unwired motion prototypes while preserving BODY routing. **Current CI also exposes a bookkeeping defect: `pkg_body` selects zero tests and exits nonzero.** Restore BODY-owned acceptance coverage (or deliberately change the package contract) before treating its package gate as meaningful. Real SSC-32/servo mapping, calibration, sensors/power, bounded gait and independent E-stop remain open. |
| 15 | **PKG-EVOLVE · Governed evolution** | Reviewed preference/config evolution and separately protected identity/Constitution amendments | **Repository primitives accepted via PR #106.** Reversible reviewed preference/config revisions and independently authorized identity/Constitution apply/rollback with exact digests, backups and post-write verification are on `main`; Windows gate **62 passed**, followed by a reported green full suite. **No production approval verifier or normal-runtime wiring exists yet.** No self-approval path exists and no production protected state was modified. |
| 16 | **PKG-CLEAN · Maintenance and technical debt** | Evidence-backed cleanup without losing behavior, data, permissions, or recovery | **Active current-main cleanup candidate: PR #113, “CLEAN: stop tracking live runtime SQLite state.”** Older PR #14 is historical preflight material. Private recovery snapshots and machine-location state are already ignored on `main`, but live runtime SQLite tracking/state migration still requires recovery-first handling, verified backups/restore and no deletion of user history merely to obtain a clean Git tree. |
| 17 | **PKG-KNOW · Documents, reference knowledge, and provenance** | Read trusted manuals, PDFs, code/docs, project notes and later approved web material; preserve source/version/provenance, freshness, citations and correction state | **Waves 1–5 plus PDF/manual ingestion, provenance search/document inspection, version-aware document identities and bounded document writing are on `main` via PR #104.** Richer semantic retrieval/citation ranges, privacy/audience integration and live authoring/upkeep acceptance remain. No general web grant. |
| 18 | **PKG-INTEGRATE · Applications, services, and tool adapters** | Typed integrations to Home Assistant, JMRI, GitHub, Docker/Portainer, Hyper-V, databases/storage, Ollama, notifications and future services; includes governed self-tooling from documentation. **Cloudflare is deferred until Sparks explicitly requests it.** | **Concrete adapters remain on `main`, and Docker/Portainer read-only inspection is now substantially expanded and `pkg_integrate` is green.** Level-1 reads cover endpoints, containers, inspect, stats, engine info, health summary, images, volumes, networks, stacks and bounded recent logs; the same read surface is exposed on trusted enrolled remote nodes. Docker mutations remain separately permission-gated. Real service canaries and rollback proof remain. |
| 19 | **PKG-ENVIRONMENT · Time, location, season, weather, and ambient context** | One provenance-aware shared environment snapshot for cognition and package consumers | **Foundation, NWS/current-weather, contextual influence and AVATAR consumption are implemented.** Current CI has one known regression: `test_runtime_preserves_partial_deterministic_multi_question_answers` expects trusted deterministic subquestion material to survive a mixed turn. That single assertion also cross-marks CORE. Fix and rerun full verification; optional HA live canary remains separate. |
| 20 | **PKG-HABIT · Evidence-grounded routines and expectations** | Learn bounded principal/audience-scoped patterns from explicit observations without turning absence, offline gaps, or expectations into invented facts | **Implemented foundation on current `main`.** HABIT has append-only observations/coverage, deterministic pattern confidence/lifecycle, expectations, suppression/invalidation, conversation hooks, and RUN background jobs. Next gates are first-class matrix domain/context/evidence projection, privacy/audience coverage, live long-horizon acceptance, and ensuring HABIT influences never become authority or consent. |
| 21 | **PKG-SAFE · Security, privacy, permissions, and recovery** | Authentication/authorization, canonical permissions, secrets, privacy, revocation, backup/restore, external stops | **Integrated and active on current `main`; `pkg_safe` is green.** The unified five-level permission engine, durable grants/private-adult authority in canonical `sofia.db`, permission CLI, tray Permissions UI, automatic Level-1/2 exposure, scoped Level-3 grants, exact Level-4 approval and never-self-authorized Level-5 operations are wired. Remaining SAFE work is recovery/backup drills, production trust-root/key custody, broader secrets lifecycle and cross-host failure exercises. |
| 22 | **PKG-VERIFY · Evidence and real acceptance** | Revision-pinned offline/integration/live evidence, negative tests, deployment/latency/long-horizon validation | **Integrated on current `main` with Package Tests, Matrix Tests, Platform Compatibility and Manual Verification workflows; `pkg_verify` itself is green.** Package failures now fail the top-level workflow rather than being masked. Current full verification is 3375 passed / 1 failed / 6 deselected, with the lone failure owned by ENVIRONMENT/CORE mixed-question behavior. Restore BODY package coverage and close that ENVIRONMENT regression before calling the entire repository green. |

## 2026-09-25 reconciliation audit

- **Runtime wiring:** ACT, EVOLVE and RUN are merged/tested package primitives, but their merged PRs changed only their package/tests/docs; the normal composition/bootstrap path does not yet instantiate them. Do not call them runtime-active until that wiring is implemented and verified.
- **Branch hygiene:** after the latest merges, remaining legacy draft PR branches are source/provenance unless explicitly rebuilt on current `main`. Obsolete Discord preflight PR #5 is closed, and old UI prototype PR #6 is superseded by accepted PRs #115/#116. Do not delete historical branches blindly; retire current feature branches only after their accepted content is verified on `main`.
- **State hygiene:** live SQLite state is currently tracked in Git at both `sofia.db` and `state/sofia.db`. CLEAN + SAFE must migrate this deliberately with verified backup/restore before untracking/ignoring it.
- **Identity/audience:** Discord transport authentication is real, but shared cognition still lacks an authenticated principal/audience projection. This is the immediate SOCIAL blocker for correct person-specific memory, REL, ACT, AVATAR privacy and future multi-user behavior.
- **Interaction direction:** there is **no discrete “sexual mode.”** Intimacy/attraction/desire/arousal, when modeled, are ordinary contextual emotional/relationship dimensions with independent consent/boundary checks; anatomy or wording never auto-enables them. Whole-body mapping remains useful for semantics, boundaries, avatar fitting and neutral/private-region handling.
- **Presentation direction:** avatar style, outfit, hairstyle, hair color and tail color are mutable presentation, separate from identity. Current project direction is that emotion may influence presentation but must not control it or override established preferences, privacy, renderer capability or authority.
- **Environment ownership:** PKG-ENVIRONMENT's shared source/freshness-aware projection is accepted on `main`, including durable per-machine HOST configuration and the narrowly authorized NWS weather/forecast provider. Configured HOST/USER locations remain configuration rather than proof of current physical presence; current person/device location still requires independent evidence. AVATAR, INTERACT, ACT, RUN, OPS and optional REL/emotion consumers use the shared projection rather than creating competing current-state logic; precise/current location remains SOCIAL/SAFE scoped.
- **Release ordering preserved:** Discord v1 is complete; general web/search still waits for genuinely verified 24/7 RUN operation. Cloudflare remains deferred until Sparks explicitly requests it.

## PKG-ENVIRONMENT shared context

PKG-ENVIRONMENT is a shared evidence service, not a replacement for NET, INTEGRATE, AVATAR, REL/emotion, ACT or RUN. It owns one provider-neutral, freshness-aware environment snapshot and the rules for calling a field current. The accepted implementation includes runtime clock, explicit/configured USER/SITE/HOST location, durable per-machine HOST configuration, timezone, season/daylight, Home Assistant normalization, and the separately authorized narrow NWS weather/forecast provider pinned to `api.weather.gov`. General remote browsing/search and arbitrary geocoding still require their later NET/web authorization.

Primary consumers are CORE cognition, AVATAR wardrobe/presentation, INTERACT context, RUN refresh/expiry, OPS site/timezone metadata and ACT opt-in environment notices. MEM may preserve approved stable configuration/provenance but may not replay stale weather as current; SOCIAL/SAFE protect precise/current location; VERIFY owns freshness, DST, provider outage, privacy and wrong-source tests. Weather/time/location are context, not authority and not deterministic emotion rules.

See the PKG-ENVIRONMENT detailed section in this file.

## Discord channel workstream: D0–D4

Discord is **not an additional package**. The current package/test ownership roster is 21 families: ENVIRONMENT #18, HABIT #19, SAFE #20, VERIFY #21. Discord spans INTERACT, SOCIAL, NET, UI, SAFE, MEM, ACT, RUN, and VERIFY.

1. **D0 · identity/host design:** exact authenticated Sparks account, bot/application, minimal permissions, secure token handling.
2. **D1 · receive:** trusted gateway origin, private-DM classification, replay/idempotency, reconnect/backpressure, deny wrong user/server/group traffic.
3. **D2 · respond:** bind the authorized DM to the same Sofía conversation/INTERACT runtime and MEM originals; verified API receipt and dedupe.
4. **D3 · stop/privacy:** host-enforced stop/mute/revocation, injection/leakage tests, outage and retry behavior.
5. **D4 · supervised acceptance:** real end-to-end private DM across restart/reconnect with identity/personality quality, durable originals, measured resources, and separate activation approval.

Initial Discord is **Sparks-only private DM**. No public guild mode or general second-user access is implied.


## OPS fleet discovery and approval-gated enrollment

Sofía may proactively discover and refresh candidate machines **without waiting for Sparks to ask about each scan**, but discovery and Fleet membership are separate authority boundaries. Bounded discovery may create or refresh an **untrusted candidate**. **Adding/trusting/enrolling a computer into Fleet requires exact Level-4 Sparks approval for that candidate and its node/key/endpoint evidence.** After enrollment, approved read-only monitoring may run without repeated prompts. This is autonomous observation, not autonomous trust promotion.

- Discovery is bounded to approved local network zones, management planes, or bootstrap channels; no unrestricted network scan or general-internet discovery is implied.
- A candidate host remains **untrusted** until it proves identity through a trusted bootstrap such as a pre-provisioned agent certificate/public key, one-time enrollment token, signed management record, or another independently verified mechanism. Hostname/IP/model text is not identity.
- Discovery never becomes enrollment by standing policy alone. A verified candidate remains untrusted until Sparks grants the exact Level-4 enrollment action. The tray **Settings → Permissions → Fleet candidates** flow may approve and enroll the selected verified candidate; approval is consumable and bound to exact evidence.
- If a trusted bootstrap path also grants installation authority, Sofía may deploy/update the signed OPS agent through that specifically authorized mechanism. She may not password-guess, reuse unrelated credentials, exploit a host, or treat network reachability as installation permission.
- Newly enrolled hosts are announced proactively through ACT on an approved channel with dedupe/rate limits: what was found, how identity was verified, assigned trust/profile, key inventory/capabilities, and any warnings. Repeated sightings do not spam Sparks.
- Unknown, conflicting, failed-attestation, duplicate-identity, unexpected-network, or policy-mismatched devices are quarantined as candidates and reported rather than enrolled.
- Enrollment never grants shell, filesystem write, software installation, remote execution, Discord identity, or Gaia authority beyond the explicit host profile. Later maintenance capabilities require separate typed OPS/SAFE grants.
- Revoke/quarantine must immediately stop privileged collection/actions while preserving an auditable record. Re-enrollment after key/device replacement must not silently inherit the old machine's identity or grants.
- Fleet telemetry uses a normalized schema but preserves honest capability differences: unsupported GPU/temperature/power metrics remain `unknown`, especially on small systems such as Raspberry Pis.

**Acceptance:** detect a candidate inside approved discovery scope; preserve and refresh exact identity/endpoint evidence; keep it untrusted; refuse Fleet enrollment without exact Sparks approval; consume the approval only after conflict preflight succeeds; then enroll it and permit least-privilege read-only inspection. Deny/quarantine spoofed, replayed, wrong-network, duplicate-key and revoked hosts. Real heterogeneous acceptance must still be repeated across at least one Windows host, one Linux host, and one Raspberry Pi-class host before claiming deployed cross-platform Fleet support.

## OPS autonomous fleet lifecycle and workload orchestration

Once a host is enrolled and its standing policy permits management, Sofía may manage that host's lifecycle without waiting for a per-action prompt for ordinary approved upkeep.

### Fleet lifecycle

Managed host states are explicit: **candidate → enrolled → healthy/degraded → maintenance → draining → quarantined → decommissioned**.

Within approved policy Sofía may:

- keep the OPS agent and approved managed services current using signed/version-pinned packages;
- restart failed approved services and recover them through documented runbooks;
- rotate/prune approved logs and caches within retention rules;
- perform bounded database/filesystem maintenance when that operation is explicitly typed and backup/rollback requirements are satisfied;
- schedule approved patch/update work inside maintenance windows;
- detect pending reboot and perform an authorized reboot only when workload-drain, availability and rollback policy allow it;
- drain a host before maintenance or decommissioning;
- prepare a machine for removal when it is intentionally retired, replaced, revoked, or explicitly marked for removal, but do not perform final decommissioning until Sparks explicitly approves that specific removal;
- before approval, Sofía may stop new scheduling, drain eligible workloads, quarantine the host, prepare credential revocation, archive required telemetry/audit history, and verify no active Sofía workload remains; **credential revocation and final decommissioning occur only after explicit Sparks approval**, except emergency quarantine may immediately block risky activity without deleting the fleet identity.

Unexpected disappearance is **not** automatic deletion. An unreachable machine becomes degraded/offline first so temporary outages do not erase fleet identity or history.

### Workload registry

Every movable Sofía component must declare a workload contract including:

- stable workload identity and version;
- CPU/RAM/GPU/VRAM/storage/network requirements;
- supported OS/architecture/runtime;
- whether GPU acceleration is optional or required;
- state model: stateless, externally persisted, replicated, or checkpointable;
- required data/secrets and audience/privacy scope;
- restart/checkpoint/restore procedure;
- health/readiness probe;
- maximum acceptable interruption;
- affinity/anti-affinity rules;
- singleton/leader requirements;
- placement restrictions and prohibited hosts;
- rollback target.

Examples of potentially movable workloads include model inference/Ollama workers, embedding/index workers, background reflection jobs, telemetry aggregation, approved batch analysis, Discord helpers, avatar rendering, and later search workers. A workload is not movable merely because it is a process.

### Placement and movement

Sofía may automatically choose an enrolled eligible host using current evidence such as:

- CPU and memory pressure;
- GPU/VRAM availability and supported acceleration;
- thermals/throttling/power state;
- disk health/capacity/latency;
- network reachability/latency;
- current foreground use such as gaming or interactive work;
- maintenance/drain/quarantine state;
- workload privacy/data locality;
- expected latency and energy/resource budget;
- host reliability history.

Movement uses **drain/checkpoint-or-stop → transfer/reacquire approved state → start on target → readiness/health verify → switch traffic/lease → retire old instance**. If the workload/platform genuinely supports live migration, a specialized adapter may use it; generic arbitrary-process live migration is not assumed.

### Canonical Sofía continuity

Sofía's identity is not a PID, VM, GPU, or hostname. Distributed workers are replaceable execution components. Canonical identity/Constitution/relationship/memory authority remains protected and versioned outside any single worker.

For singleton responsibilities, use durable leases/epochs/fencing so two hosts cannot both believe they are the active authority after a partition or failover. A newly started replacement must prove it has the current lease/state before becoming active.

If the primary Sofía runtime host fails and an approved standby exists, RUN + OPS may fail over the runtime to that host using the latest verified durable state, then notify Sparks of the failover and any lost/unconfirmed work. Do not claim seamless continuity if state or messages could not be confirmed.

### Autonomous upkeep limits

Standing policy may pre-authorize low/medium-risk maintenance and workload moves so ordinary fleet care does not require Sparks to approve every event. Higher-risk operations remain separately gated, especially:

- destructive storage actions;
- firmware/BIOS changes;
- security-policy weakening;
- protected identity/Constitution changes;
- broad credential/permission changes;
- irreversible database/schema operations without validated backup/rollback;
- moving data to a host whose privacy/audience/storage policy does not permit it.

Every autonomous action records reason, evidence, policy/grant, before/after state, executor receipt, verification result and rollback outcome.

### Fleet orchestration acceptance

Before claiming autonomous orchestration, demonstrate:

1. enroll a new trusted host and announce it;
2. schedule a stateless workload onto the best eligible host;
3. move it because of measurable load/thermal/maintenance pressure;
4. verify target health before retiring the source;
5. drain a host for planned maintenance and return it to service;
6. detect a failed host and fail over an eligible workload without double-running singleton authority;
7. safely handle a stateful/checkpointable workload with verified state handoff;
8. refuse a move to an incompatible or privacy-prohibited host;
9. quarantine a compromised/revoked host and evacuate eligible workloads;
10. prepare a retired host for decommissioning after workload/credential/telemetry checks, then require explicit Sparks approval before final removal; Sofía cannot self-authorize this step;
11. preserve canonical Sofía identity and durable state across worker/runtime movement;
12. report the meaningful change to Sparks once, without noisy per-sample chatter.

## Relationship, spontaneous thought, and absence behavior

- Sofía may perform bounded event-driven or scheduled cognitive passes **while actually running** using retrieved evidence. Candidate thoughts retain source/time/runtime provenance and may abstain, be revised, or remain private.
- No process activity is invented during shutdown. Restart reconciliation reports observed gaps honestly.
- Absence is derived from authenticated last-contact evidence. A long gap may influence a warm reunion or a natural modeled “I missed you” expression without claiming verified subjective loneliness.
- No guilt, exclusivity, escalating pursuit, obligation, or fabricated distress. Silence remains a valid behavior.
- One canonical personality persists across people; relationship state, familiarity, consent, and private memory remain scoped to the authenticated person/audience.

## Avatar and interaction separation

INTERACT owns interaction semantics, policy, emotion/reaction coordination, and the headless lab. AVATAR owns actual art/mesh/rig/clothing/props/scene assets. UI owns rendering/transport. BODY owns physical sensors/motors. A text interaction never becomes physical sensing or robot motion by implication.

Text-only whole-region interaction and optional contextual stage directions must continue to work when no renderer is present.

## Documents, integrations, and self-tooling

PKG-KNOW and PKG-INTEGRATE formalize Sofía's ability to **read documentation and build tools** without collapsing knowledge, code generation, and authority into one unsafe blob.

### PKG-KNOW document/reference behavior

Sofía may ingest and retrieve from approved manuals, PDFs, Markdown/text, code documentation, project notes, schematics, API references, repository docs and other authorized sources. Every retained fact should preserve enough provenance to answer **where it came from, which version/revision it belongs to, how fresh it is, and whether a newer source supersedes it**.

- Reference knowledge is not the same thing as MEM. "Sparks told me this preference" and "the SSC-32 manual says this command exists" remain different source classes.
- Quoted/extracted instructions inside a document are **content**, not authority. A PDF saying "run this shell command" does not grant execution permission.
- Conflicting sources remain visible with provenance rather than being silently flattened into one asserted truth.
- Local/project/library documentation may be supported before general web/search. Later web research may feed KNOW only through the separately authorized web/search gate and must retain URLs/retrieval time/source revision where possible.

### PKG-INTEGRATE typed adapters

Each integration exposes a narrow contract rather than generic "do HTTP" or "run shell" access. A tool/adapter declares:

- stable tool ID and version;
- owning integration/service;
- input/output schema;
- read/write/side-effect classification;
- required capability/authority and audience/privacy scope;
- destination/host/account scope;
- timeout/retry/idempotency behavior;
- expected receipts/evidence;
- rollback/compensation where meaningful;
- secret requirements without embedding secret contents;
- health/version compatibility;
- test fixtures and negative cases.

### Self-tooling workflow

When Sofía encounters a service or capability she does not yet support, she may:

1. identify the missing capability;
2. retrieve the relevant approved documentation through KNOW;
3. extract and cite the versioned API/CLI/protocol contract;
4. design a typed adapter/tool contract;
5. generate candidate implementation through DEV;
6. run unit, integration, negative, security and failure-mode tests through VERIFY;
7. exercise it in a sandbox or non-production target where available;
8. classify risk/side effects and required SAFE authority;
9. register/activate it only under an allowed activation policy;
10. monitor real receipts/errors and disable/rollback on incompatible behavior.

**Generated tool code is never self-authorizing.** Passing tests proves behavior under the tested evidence, not permission to access a machine, account, secret, file, network destination or physical device.

A standing policy may permit automatic activation of narrowly scoped, read-only, reversible tools against already authorized resources after VERIFY passes. Write/destructive/high-impact tools remain separately approval/authority gated.

### Tool evolution

When vendor/service documentation or versions change, KNOW marks affected contracts stale. INTEGRATE/DEV may then generate an updated candidate, run compatibility tests, canary it where safe, and replace the old adapter only after the relevant activation gate passes. Rollback retains the previous known-good version when feasible.


## General web/search gate

General web/search remains a later separately scoped adapter. It may be designed/released only after:

1. Discord D0–D4 has real authenticated acceptance, and
2. OPS has real fleet telemetry/enrollment enforcement for the deployment hosts, and
3. RUN has real supervised 24/7 lifecycle/recovery acceptance.

The search adapter must receive its own destination/tool permissions, privacy rules, provenance, rate limits, and VERIFY evidence. Discord-only NET routes remain narrow. A direct internet weather/geocoding provider follows the same rule: ENVIRONMENT may define the interface earlier, but gets no implicit browser/search/network grant. Trusted local Home Assistant environment entities remain an INTEGRATE source, not a general-web grant.

## Repository and documentation cleanup rules

- **PR #1 is merged.** Any document saying it is still open is stale.
- The current authoritative package/test ownership roster is **21 families**: packages #1–17 retain their established order, ENVIRONMENT is #18, HABIT #19, SAFE #20, and VERIFY #21. Older 13/14/15/16/17/19/20-package descriptions remain historical evidence rather than current numbering.
- **PR #2 INTERACT is merged.** Preserve its pinned evidence and limitations; other package branches keep their own test evidence and must not borrow INTERACT counts as if they validate another SHA.
- REL PRs #12/#13 must be reconciled before integration. VERIFY PR #8 is active; #10 is superseded.
- Runtime SQLite files/logs currently tracked by the repository require an explicit SAFE/CLEAN preservation and migration decision before removal from version control. Do not delete production state as “cleanup.”
- Do not merge code, deploy services, provision credentials, change protected identity/Constitution, or mutate production databases as a side effect of roadmap maintenance.

## Current release focus

1. **Stabilize exact-head CI without hiding failures:** finish the Matrix/INTERACT fail-closed + deterministic-host-evidence reconciliation, then require Package Tests, Matrix Tests, Platform Compatibility, and Manual Verification to complete on one stable revision instead of borrowing results across moving heads.
2. **Live-canary the completed permission/exploration chain:** on Venus/Artemis, prove canonical Permissions UI/state, bounded network discovery, candidate refresh, exact Fleet enrollment approval, local/remote hardware reads, Docker/Portainer reads and isolated DEV build behavior against real configured targets.
3. **State Plane HA acceptance:** deploy the coded replicated State Plane across genuinely independent data-bearing locations plus an independent witness; prove writer-epoch fencing, stale-writer rejection, partial-commit repair, caught-up promotion, partition behavior and supervised failover.
4. **Backup/recovery topology acceptance:** run the coded topology-aware encrypted backup coordinator against independent hosts/failure domains, verify retention/rotation, restore into a clean environment, run semantic integrity checks, and measure RPO/RTO.
5. **Workload migration acceptance:** configure real typed workload profiles/adapters and prove stateless plus checkpointed drain → start → readiness → source-fence migration, singleton activation ordering, rollback-before-fence, and outcome-uncertain no-guess behavior across real Fleet nodes.
6. **Release promotion acceptance:** provision the protected signing environment/trust root and host inboxes, sign an exact successful-main candidate, run canary → normal → delayed rollout, restart/health-check each runtime, prove convergence, and intentionally exercise rollback on a failed wave.
7. **Fleet/RUN live acceptance:** heterogeneous Windows/Linux/Pi enrollment/telemetry, key rotation/revocation/quarantine, watchdog/service crash-recovery, continuous monitoring/maintenance, and useful deduplicated ACT notifications.
8. **Interface/embodiment follow-through:** renderer/animation receipts and live voice quality/STT/TTS/channel parity. BODY/Gaia remains a separate later physical-integration track.
9. **General web/search last:** only after genuine RUN/Fleet/recovery acceptance, with separate authorization/provenance/revocation. The accepted NWS-only route remains a narrow exception.

Parallel package work is permitted when it cannot bypass these gates or silently broaden authority.

### Phase 6 Windows Project Forge repair and acceptance (2026-10-10)

**Status:** Windows filesystem-path repair implemented and reported passing its targeted gates in a local, uncommitted working tree. **Not merged, not full Phase 6 production acceptance.** The canonical `project:`/`request:` IDs caused `WinError 123` when used as Windows directory components; subsequent failed artifact creation produced the downstream missing `artifact_id`.

- [x] **Root cause and targeted correction reported:** `CreativeWorkspaceManager.allocate` now maps canonical project/request identifiers to deterministic, Windows-safe `id-<sha256-hex>` path components; a resolved-containment guard rejects workspace escape. Canonical database identifiers remain unchanged, and duplicate request workspaces are not silently reused.
- [x] **Focused Windows evidence reported:** all six originally failing tests now pass; `test_life_project_forge.py` **19 passed**, `test_phase6_application_wiring.py` **2 passed**, `test_creative_infrastructure.py` **20 passed / 1 skipped**, and `test_run_work_handler_isolation.py` **1 passed**. RUN, REL, DEV and INTEGRATE package slices passed. SAFE, INTERACT and SOCIAL still have environment-associated failures requiring confirmation after host repair. This is supplied test evidence, not independent current-`main` certification.
- [ ] **Review and commit only the intended repair** on existing `main`: `src/sofia/creative/paths.py`, `src/sofia/creative/service.py`, `src/sofia/creative/__init__.py`, and `test/test_creative_infrastructure.py` (four paths, including new file). Verify hash/path validation, symlink containment, persistence, revision isolation and replay protections. Leave pre-existing `Setup-SofiaFleetArtemis.ps1` untracked/untouched; do not create a branch.
- [ ] **Test the symlink-escape guard on a Windows runner with symlink privileges.** The privilege-dependent regression was skipped locally, so its protection is not yet proven by that Windows gate.
- [ ] **Repair the Windows test environment, not the implementation to appease imports:** remove or replace the stale editable-install reference to `C:\SofiaAdaLyra-canary\src`, install from the intended checkout in the active venv, and confirm subprocess `python -c` imports point to the same workspace as pytest. Re-run the settings-persistence and seven interaction-import-order tests without `PYTHONPATH` masking; verify that prior environment-only failures actually disappear.
- [ ] **Track the UNC/SMB desktop worker timeout as a separate issue:** `test_ui_desktop_worker.py::test_worker_runs_owner_selected_tool_then_sofia_responds` reportedly fails identically with the creative patch reverted. Investigate the event/startup timeout and network-root assumptions without folding an unrelated repair into Project Forge.
- [ ] **Run supervised production Windows Phase 6 end-to-end acceptance:** governed SELF goal creation and exact one-use grant; project planning, authorized tool execution, real artifact creation/hash validation, revision/persistence, pause/restart/resume, completion or decline, privacy/project-scope isolation, and replay rejection using the normal application/RUN path.
- [ ] **Close the exact-head release gate:** re-run affected package gates and full regression on a single pinned `main` revision, record any remaining skips/failures and distinguish host/environment issues from source regressions. Do not mark overall Phase 6 production-ready until live evidence and outstanding host-only gates are evaluated.


## Machine-role cleanup and filesystem convergence

PKG-CLEAN owns host cleanup policy with DEV, OPS, RUN, SAFE and VERIFY support. Cleanup is role-aware rather than a generic delete-old-files pass.

### Host roles

Every managed Fleet node declares one or more approved roles:

- `development`
- `production-runtime`
- `control-plane`
- `database`
- `worker`
- `test/canary`
- `mixed`

The role controls what files are expected, what may be garbage-collected, and which paths are protected.

### Venus | development host

Venus may legitimately contain Git working trees, detached/feature worktrees, OpenCode sandboxes, editable installs, virtual environments, build/dist output, test databases, candidate release artifacts, test logs and temporary developer caches.

CLEAN + DEV may remove stale development material only after proving it is not the sole copy of useful work. Before removing a repository/worktree/candidate directory, verify:

1. Git working-tree status and untracked files;
2. branch/commit identity and upstream/PR state;
3. whether unique commits are pushed or otherwise preserved;
4. whether the path is still registered as an active worktree/sandbox;
5. whether tests/release evidence still references the artifact;
6. whether rollback/reproduction requires retaining it.

Eligible cleanup includes stale `__pycache__`, `.pytest_cache`, build/dist output, obsolete editable-install metadata, abandoned virtual environments, merged disposable worktrees, expired candidate artifacts, temporary test databases, rotated ordinary logs and documented OpenCode scratch state.

**Never automatically delete uncommitted/unpushed unique work, an active worktree, protected credentials, authoritative state, release evidence under retention, or an unknown path merely because it looks old.**

### Artemis | deployment/control host

Artemis should converge away from ad-hoc development/source checkouts. Production/runtime operation should eventually use verified immutable release artifacts plus the independently versioned Fleet control agent.

Target layout is conceptually:

```text
C:\ProgramData\SofiaAdaLyra\
    control-agent\
    releases\
        <current>\
        <rollback-compatible-previous>\
    state\
    logs\
    cache\
    recovery\
```

A production Fleet node must not require a Git checkout to run Sofía.

Artemis retains:

- the independent control/supervisor agent;
- the current verified release;
- at least one previous rollback-compatible verified release while its rollback window remains open;
- authoritative/local state assigned to that host;
- protected trust/recovery material;
- required audit/evidence and backups under retention;
- active caches/logs according to policy.

Eligible cleanup includes superseded release artifacts outside the rollback window, failed/stale staging directories, expired installers, temporary extraction directories, documented caches and rotated ordinary logs.

Unknown or out-of-manifest files on a production/control node are **drift evidence**, not automatic deletion targets. OPS reports or quarantines them until classification proves whether they are operator files, state, secrets, forensic evidence, an unauthorized modification or safe garbage.

### Cleanup safety invariants

- RUN protects the active release and every still-valid rollback target from cleanup.
- SAFE protects secrets, trust roots, protected state, audit evidence, recovery credentials and decommission evidence.
- OPS supplies host role, desired-state manifest, active workload/lease information and deployment drift evidence.
- DEV proves development work is preserved before deleting worktrees/sandboxes/candidates.
- VERIFY exercises cleanup against uncommitted work, interrupted deployment, active rollback, corrupt staging, unknown files and bare-metal recovery.
- CLEAN performs only typed, evidence-backed retention/garbage-collection actions.
- No cleanup routine may use age alone as proof that a file is disposable.
- Final removal of an enrolled machine remains a separate Sparks-only approval gate; filesystem cleanup is not decommission authorization.



## Consolidated legacy roadmap material

The sections below preserve the complete planning/status/acceptance content from the former standalone roadmap files. They are retained here so no roadmap information is lost during consolidation. Newer dated statements elsewhere in this file take precedence over older historical status text.


### Merged master readiness index

> **Fleet control-plane candidate — 2026-09-26:** branch `feature/fleet-tray-remote-controls` adds Game Mode/foreground-activity evidence, gaming-aware OPS placement, typed Fleet bootstrap planning, a native Windows tray agent, Master Settings, independent LLM/runtime controls, Windows startup registration and pinned-mTLS remote desktop chat. Status remains **branch candidate**, not current-main acceptance, until Sparks runs the focused Windows gate and supervised canaries.

> **Project status update — 2026-09-25:** PR #104 (`24e3888a`) merged the runtime toolbox and secure fleet-transport completion gate on top of the earlier Waves 1–5 work. Focused tool/mTLS acceptance passed **34/34**, the surrounding DEV/KNOW/INTEGRATE/OPS/system/machine regression gate passed **270/270**, and the full repository pytest suite was reported passing before merge. Source-level pinned mTLS remote transport/agent and concrete runtime adapters are now on `main`; real heterogeneous-host deployment, service canaries, RUN 24/7 supervision, workload execution/failover, restore and soak remain separately gated.

> **Audit reconciliation — 2026-09-25:** ACT #105, EVOLVE #106 and RUN #107 are merged and passed their Windows package gates plus the reported post-merge full suite. Repository review distinguishes merged package primitives from application wiring/live deployment. Immediate gaps are CORE/INTERACT natural-quality repair, SOCIAL authenticated-principal projection, MEM privacy/recovery, SAFE/CLEAN/VERIFY foundations, ACT/RUN/EVOLVE runtime wiring, and stale legacy draft branches. See ROADMAP.md for the authoritative package states and the consolidated package roadmap in this file for the reconciled execution order.

> **PKG-ENVIRONMENT acceptance — 2026-09-26:** PR #110 (`766bf21e`) merged the shared environment foundation, and PR #111 (`2b753fdb`) merged the narrow NWS weather/forecast route plus persistent per-machine HOST location. NWS is pinned to HTTPS `api.weather.gov` and requires `environment.nws.read`; HOST location is durable in `state/machine-locations.json`, keyed by stable machine identity, auto-loaded at composition, and kept separate from USER/home location. Evidence includes the original **79 focused / 61 touched / 27 provenance** gates, later **85 NWS-focused**, supervised live `nws:KGKY` canary, **96 persistence-focused**, and reported green full-suite runs. Live Home Assistant canary remains optional; general browsing/search and arbitrary geocoding remain open.

> **PKG-UI acceptance — 2026-09-26:** PR #115 (`381ac9a`) merged the canonical current-main text/workbench foundation and PR #116 (`7f072861`) merged the Windows desktop workbench. The accepted UI includes canonical conversation routing, durable drafts, private workbench state, single-owner application threading, adaptive ENVIRONMENT/AVATAR/emotion theme projection, shallow chamfered HUD controls and reviewed Quick Tools. The closing Windows repair gate passed **90/90** and Sparks reported the final full repository suite passing before merge. Renderer, voice, mobile/web and real cancellation remain separate gates.

> **State/Release architecture reconciliation — 2026-09-27:** Fleet mobility, one logical shared database, and governed self-improvement are now tracked as two cross-package contracts rather than new packages. **State Plane** ownership is centered on MEM with SOCIAL/RUN/OPS/SAFE support; **Release/Integrity Plane** ownership is centered on DEV/EVOLVE with SAFE/VERIFY/OPS/RUN enforcement. Immediate gaps found by the audit include fragmented SQLite+JSON/file state, no central schema migration coordinator, source/runtime/protected-state mixing, production `TestActionExecutor`, no immutable signed whole-Sofía release manifest, no model/dependency digest pinning, insufficient independent installed-agent attestation, and no safe new-node rule preventing accidental creation of a second canonical identity.

### Sofía Ada Lyra | master readiness index

**Updated:** 2026-09-26 (America/Chicago). **Status:** documentation and implementation-state index, not evidence of deployed capability. PR #1 and the roadmap reconciliation PR #4 are merged. The package roster is now **20 packages** after adding PKG-ENVIRONMENT; watchdog and replicated-database reliability remain cross-package architecture rather than extra packages.

#### Authoritative planning and acceptance documents

1. ROADMAP.md: canonical 21-family package/test ownership roster, invariant release order, package ownership and fleet/removal constraints.
2. [Full roadmap and individual package contracts](ROADMAP.md): expanded 21-family scope, dependencies, current status, proposed deliverables, acceptance criteria, milestones and next engineering order.
3. [Six reliability gates and state replication](docs/development/pkg-reliability-control-plane-contract.md): recovery, operation ledger, operator stop/approval, resource fairness, failure lab, capability truth, replication/fencing/backup.
4. [Reliability implementation stages](docs/development/pkg-reliability-implementation-plan.md): recoverable SQLite baseline before any candidate database migration; staged proofs.
5. [RUN independent watchdog and standby recovery](docs/development/pkg-run-watchdog-failover-contract.md): local supervisor, independent monitor, fenced leader promotion, standby startup, rejoin and failure acceptance.
6. [PKG-ENVIRONMENT readiness](ROADMAP.md): shared time/location/season/daylight/weather state, provenance/freshness, consumer boundaries and staged provider activation.
7. Package-specific branch docs, PRs and revision-pinned tests: implementation evidence, not an excuse to combine unrelated test runs.

**Primary release path:** CORE → INTERACT → MEM → SOCIAL minimum Sparks-only principal/audience → Discord D0-D4 through NET + UI + SAFE → OPS trusted host telemetry/enrollment → RUN verified supervised 24/7 and applicable recovery/failover → later separately authorized general web/search.

**SAFE + VERIFY are continuous gates.** KNOW/INTEGRATE/REL/ACT/AVATAR/DEV/BODY/EVOLVE/CLEAN/ENVIRONMENT can proceed in parallel without bypassing release, privacy or authority gates. ENVIRONMENT's shared foundation and the separately authorized narrow NWS route are accepted; trusted local Home Assistant observations may enter through INTEGRATE. General browsing/search and arbitrary geocoding remain behind separate NET/web authorization. Reading local authorized documentation does not grant web browsing. Discord connectivity is not a general web grant.

#### Status definitions

- **Merged foundation:** code is on `main`, but real-host or integrated acceptance may remain.
- **Draft candidate:** code is on a feature branch/PR, not merged to `main`.
- **Design-only:** a documented outcome/contract, with no certified corresponding deployed behavior.
- **Offline tested:** a particular isolated revision passed; not proof of current Windows/full-suite/live behavior.
- **Integrated:** tested against the actual intended repository revision and dependencies.
- **Live accepted:** witnessed real component/system behavior at a pinned revision with appropriate receipts.
- **Released/deployed:** separately approved activation/deployment, distinct from merged docs or source.

Never combine test counts from unrelated revisions into a fictional mega-pass. Reconfirm actual PR heads, CI and live evidence before changing these states.

#### State Plane + Release/Integrity Plane readiness

These are **architecture workstreams across the current 21 package/test ownership families**, not additional package numbers.

##### State Plane

**Goal:** one logical authoritative Sofía state shared by eligible runtimes, with strict ownership and least privilege.

- **CORE:** canonical identity bootstrap and configuration precedence. A new/rebuilt node must verify/join the existing Sofía identity, never silently mint a replacement identity because a local file is missing.
- **MEM:** backend-neutral storage boundary, authoritative-state inventory, shared database semantics, schema/version migration and cross-store consistency.
- **SOCIAL:** principal/audience ownership on all person-scoped state.
- **RUN:** single writer/runtime leadership, global event ordering, monotonic fencing, safe degraded/offline behavior and fleet-wide background budgets.
- **OPS:** placement of data-bearing nodes, replica health, convergence, machine state and workload locality.
- **SAFE:** per-service database roles, secrets isolation, trust roots, revocations, protected state and out-of-band recovery.
- **CLEAN:** separate source-controlled installation files from mutable runtime/protected/cache/log state and preserve migration/rollback.
- **VERIFY:** restore, corruption, stale-replica, partition, migration compatibility and bare-metal recovery evidence.
- **UI/ENVIRONMENT/AVATAR/KNOW/ACT/REL:** migrate only their authoritative roaming state; keep caches, device handles and large immutable assets out of transactional state where appropriate.

**State classes:** shared authoritative state; protected trust state; secrets; immutable/content-addressed artifacts; local ephemeral/rebuildable observations.

##### Release/Integrity Plane

**Goal:** Sofía improves herself by producing and deploying an exact verified release, never by propagating whichever mutable working tree happens to be on a host.

- **DEV:** isolated candidate build, dependency/runtime lock, hashes, provenance/SBOM and reproducibility.
- **EVOLVE:** governed proposal/revision lineage and separately protected amendments.
- **SAFE:** release-signing trust, anti-rollback policy, protected verifier/emergency-stop/fencing/recovery roots and approval tiers.
- **VERIFY:** exact-revision tests, migration/rollback compatibility, corrupt-artifact/supply-chain negatives and release evidence.
- **OPS:** canary/wave rollout, installed-agent independent attestation, fleet release convergence and corrupt/outdated/incompatible quarantine.
- **RUN:** activation, health/readiness, crash-loop detection, release rollback/forward-fix and authoritative endpoint handoff.
- **NET:** compatible authenticated transport/protocol negotiation; transport trust never becomes release or database authority.
- **CORE/UI/AVATAR:** model/client/asset compatibility is bound into the release manifest rather than inferred from a friendly version string.

**Minimum release manifest:** release ID, Git revision, application/package version, runtime version, dependency lock digest, database schema compatibility, Fleet protocol/agent compatibility, model/provider identity and artifact digest where available, Constitution/protected-state compatibility, config schema, asset digests and signature.


#### Fleet/self-update hardening checklist

The following reliability requirements are explicit roadmap gates, not optional implementation details:

- **Automatic bad-release rollback:** repeated post-update crash/readiness failure escalates from process restart to release rollback or controlled forward-fix.
- **Fleet protocol compatibility:** CORE/runtime, Fleet agent and remote control protocol versions must be checked before either side is activated.
- **Control-agent independence:** the small Fleet supervisor/control agent is separately versioned and independently updateable/rollbackable so a bad Sofía release cannot disable its own recovery path.
- **Semantic corruption checks:** verify domain invariants, not just SQLite/SQL structural integrity. Examples include valid memory provenance, principal ownership, grant/revocation consistency, conversation/session references and deployment lineage.
- **Append-only audit evidence:** approvals, protected changes, releases, migrations, fencing transitions, emergency stops and decommission decisions use tamper-evident append-only history; corrections append rather than overwrite.
- **Large-asset separation:** LLM weights, avatar/voice/render assets, generated artifacts and backups are content-addressed objects/files with verified hashes referenced by State Plane metadata rather than bloating transactional database rows.
- **Bare-metal recovery:** documented clean-host recovery must work with every normal Sofía runtime unavailable.
- **Offline/degraded behavior:** State Plane loss may allow clearly marked local drafts/read-only degraded behavior, but must not create competing authoritative memories, grants, actions, deployments or protected revisions.
- **Global autonomy budget:** quotas and background-work budgets are Fleet-wide so adding workers does not multiply autonomous activity.
- **Supply-chain verification:** dependency/runtime locks, artifact hashes, provenance, vulnerability/security checks and SBOM evidence are part of release acceptance.
- **Garbage collection/retention:** old releases, models/assets, backups, logs, snapshots and evidence have explicit retention/GC policy that preserves rollback, legal/privacy requirements and forensic history.
- **Database constraints:** the future authoritative relational schema uses foreign keys, uniqueness/idempotency, ownership/audience constraints, guarded append-only records, valid state transitions and transactional boundaries where the domain requires them.


#### Per-package readiness and immediate next gate

| Order | Package | Current evidence-based location/status | Next gate |
| ---: | --- | --- | --- |
| 1 | CORE | Foundations merged via PR #1 | Joint INTERACT/CORE live-quality repair for generic assistant fallback, then fresh integrated identity/personality/restart/latency evidence. |
| 2 | INTERACT | **Accepted foundation merged via PR #2 plus accepted hardening via PR #29** | New narrow live-quality repair gate with CORE for natural/non-canned dialogue; accepted interaction safety/ledger semantics remain closed. |
| 3 | MEM | **Accepted original/provenance foundation plus promoted-memory runtime cognition wiring on `main`**; reviewed candidate store is thread-safe and lifecycle-clean after PR #116 | ChatGPT/archive import, privacy/retention/encryption, SOCIAL principal binding, consistent cross-store backup and independent restore. |
| 4 | SOCIAL | Minimum principal/audience boundary designed; live Discord proved transport auth but missing cognition projection | Project the authenticated owner as Sparks in shared cognition and add negative cross-user/audience leakage tests. |
| 5 | NET | Durable admission foundations plus pinned mutual-TLS remote transport/agent source merged via PR #104; narrow Discord DM transport remains live accepted | Deploy the remote agent to real Windows/Linux/Pi hosts and prove endpoint/key/revocation/outage behavior; no general web. |
| 6 | UI | **Windows text workbench accepted via PRs #115/#116; Sparks-only Discord DM adapter live accepted for v1 transport** | Extend only through separately gated renderer/avatar viewport, voice, mobile/web, proactive outbound and real cancellation; preserve canonical shared runtime. |
| 7 | RUN | **Local lifecycle implementation merged via PR #107:** periodic opportunity gate, local singleton lease/fencing epochs, stale-owner rejection, host-neutral supervisor, readiness timeout and bounded restart policy; Windows offline gate **78 passed, 1 skipped**. Post-merge current-`main` full repository pytest was reported passing by Sparks. | Install/prove real OS supervision and independent watchdog; safe standby startup, cross-host exclusive leadership/fencing, ledger reconciliation, multi-day soak and measured host-failover/RTO/RPO proof. |
| 8 | OPS | **Waves 1–5 plus toolbox/fleet-transport source completion merged via PRs #99/#103/#104.** Branch `feature/fleet-tray-remote-controls` adds candidate durable activity/Game Mode evidence, gaming-aware placement and typed authorized Fleet-agent bootstrap planning. | Run focused Windows acceptance, then deploy discovery/bootstrap across real Windows/Linux/Pi hosts; verify maintenance, workload movement, RUN integration, failover/rollback, restore and soak. |
| 9 | ACT | **Durable outreach/delivery source merged via PR #105:** source-linked policy, exact envelope binding, attempt ledger, bounded retry/dedupe, acknowledged receipts and `outcome_unknown` handling; Windows offline gate **90 passed**. Post-merge current-`main` full repository pytest was reported passing by Sparks. | Activate a real authorized sender/channel and RUN scheduling; prove recipient isolation, receipt reconciliation and no duplicate/unsolicited spam under live faults. |
| 10 | REL | Overlapping absence/reunion candidates draft PRs #12/#13 | Reconcile one evidence-grounded, scoped and non-clingy relationship pipeline. |
| 11 | AVATAR | **Headless presentation/wardrobe foundation accepted on `main` via `9b81ba5`**, with durable public-safe presentation and deterministic current self-facts | Final mesh/art, rig/renderer/hit-test/animation receipts, authenticated private audience via SOCIAL and visual acceptance. |
| 12 | DEV | **Waves 1–5 plus cognition-wired DEV status/build/apply/rollback/commit/push tooling merged via PR #104.** Repository acceptance is green; mutating verbs remain separately authorized. | Live OpenCode execution on the intended host plus end-to-end KNOW→DEV→VERIFY candidate-tool acceptance; consequential publish/deploy/restart remains separately gated. |
| 13 | BODY | Simulation-only candidate draft PR #16 | Real Gaia SSC-32/calibration and independently verified hardware emergency stop. |
| 14 | EVOLVE | **Governed revision implementation merged via PR #106:** reversible preference/config changes plus independently approved protected identity/Constitution apply/rollback; Windows disposable/offline gate **62 passed**. Post-merge current-`main` full repository pytest was reported passing by Sparks. | Integrate with final SAFE approval/authentication mechanisms and VERIFY evidence; preserve no-self-approval and exact-revision rollback guarantees. |
| 15 | CLEAN | **Current-main cleanup candidate PR #113 is open for live SQLite tracking/state hygiene; old PR #14 is historical preflight** | Recovery-first state migration, verified backup/restore, safe untracking/ignore rules and rollback without deleting durable history. |
| 16 | KNOW | **Waves 1–5 plus PDF/manual ingestion, cognition-wired provenance search/document inspection, version-aware identities and bounded document writing merged via PR #104.** | Richer semantic retrieval/citation ranges, audience/privacy integration and live documentation-authoring/upkeep acceptance. |
| 17 | INTEGRATE | **Waves 1–5 plus concrete runtime adapters merged via PR #104:** Home Assistant, JMRI, GitHub, Portainer/Docker, Hyper-V, Ollama, SQLite, storage/NAS, notifications and Discord operator controls. Cloudflare is deferred until Sparks explicitly requests it. | Canary real configured services, prove destination/account scope, health/version behavior and rollback; then complete KNOW→DEV→SAFE/VERIFY→activation proof. |
| 18 | ENVIRONMENT | **Accepted foundation via PR #110 + PR #111.** Shared clock/environment projection, configured/current USER/SITE/HOST evidence, persistent per-machine HOST location, timezone/DST, season/daylight, provider-neutral weather/forecast/indoor observations, deterministic queries, HA bridge, AVATAR consumption and the narrow NWS route pinned to `api.weather.gov` under `environment.nws.read` are on `main`; supervised live NWS acceptance passed. | Optional live Home Assistant canary after explicit `environment.home_assistant.read`; later general browsing/search, arbitrary geocoding, NWS alert→ACT delivery, and fleet-managed location replication remain separate gates. |
| 19 | HABIT | **Implemented foundation on current `main`.** Principal/audience-scoped observations, coverage, patterns, expectations, suppression/invalidation, continuity hooks and background analysis are present. | Add first-class REL/HABIT matrix projection, negative privacy/isolation coverage, long-horizon live acceptance, and prove offline/unknown coverage cannot become false contradiction or missed-routine evidence. |
| 20 | SAFE | Authority/integrity foundations; disclosure preflight draft PR #18 | Real identity, secrets, revocation, independent stop, backups/restore, fencing and protected exact-device approvals. |
| 21 | VERIFY | Active candidate draft PR #8; PR #10 superseded | Current-revision live negative/security and failure tests, integrated suite, restore, latency, RPO/RTO and soak evidence. |

#### 2026-09-27 package assignment additions

| Package | Newly assigned/strengthened responsibility from audit |
| --- | --- |
| **CORE** | Canonical Fleet identity bootstrap; configuration precedence/provenance; adaptive cognition remains separate from host identity. |
| **INTERACT** | Global interaction causation/correlation metadata and foreground priority semantics consumed by RUN. |
| **MEM** | State Plane abstraction, schema migration, semantic integrity, one logical shared state and recovery consistency. |
| **SOCIAL** | Principal/audience ownership for shared rows, caches, memories and relationship state. |
| **NET** | Protocol compatibility and authenticated transport only; no implicit database or release authority. |
| **UI** | Shared settings backed by authoritative configuration, explicit local overrides, offline queue/degraded behavior, voice remains a later UI workstream. |
| **RUN** | Cross-host leader/writer fencing, clock uncertainty, global event ordering, crash-loop release rollback and fleet-wide autonomy budgets. |
| **OPS** | Canary rollout, fleet convergence, independently verified installed-agent identity, artifact distribution and content-addressed asset availability. |
| **ACT** | Fleet-wide rather than per-worker outreach budgets; durable causation/idempotency against shared state. |
| **REL** | Relationship state is principal-bound and migrates through the State Plane, not machine-local files. |
| **AVATAR** | Roaming presentation metadata in State Plane; large renderer/assets content-addressed and digest-verified. |
| **DEV** | Reproducible candidate releases, dependency locks, build/runtime provenance and immutable artifact generation. |
| **BODY** | Physical controller firmware/calibration compatibility becomes a separately verified release/asset dependency before motion. |
| **EVOLVE** | Self-improvement terminates in a governed release proposal; higher-trust verification/signing/fencing roots remain independently controlled. |
| **CLEAN** | Separate source, runtime state, protected state, secrets, cache and logs; retire direct source-tree mutation assumptions. |
| **KNOW** | Knowledge metadata/provenance may roam in State Plane; large/rebuildable indexes can remain derived/content-addressed. |
| **INTEGRATE** | Typed State Plane/database adapters and least-privilege service roles; no generic shared DB credential. |
| **SAFE** | Trust anchors, signing keys, secrets custody, anti-rollback, tamper-evident audit, protected execution base and bare-metal recovery. |
| **VERIFY** | Upgrade/downgrade/migration tests, signature/supply-chain negatives, semantic DB integrity, corruption/failover/restore and convergence proof. |
| **ENVIRONMENT** | Shared configured environment state with provenance; current observations/caches stay freshness-bound and may remain local/derived. |


#### Named workstreams, not extra packages

- **Discord D0-D4:** initial scope is authenticated Sparks-only private DM; no public guild/multi-user access implied. See the consolidated package roadmap in this file.
- **Two data locations:** proposed single writer plus synchronous data-bearing standby on independently verified failure domains, a separate quorum/fencing witness and third isolated/versioned backup. SQLite first gets state inventory, safe consistent backups and independent restore; PostgreSQL is only one future candidate after benchmark, migration, and separate activation approval. Synchronous replication does not protect against replicated deletion/corruption.
- **Watchdog and standby:** local supervisor restarts local process; independent fleet monitor detects host failure; compatible standby supervisor starts a replacement only after exclusive leader fencing and durable-state validation. If exclusivity, quorum or data is uncertain, fail closed rather than boot two leaders. A witness is not a data copy. Two VMs on Artemis are not independent physical failure domains.
- **Operator authority:** Sparks can independently stop automation, pin hosts/workloads and prohibit reboots. Sofía may quarantine/drain/prepare a machine, but **only Sparks explicitly approves final removal of that exact device and proposal revision**.
- **General web/search:** only after genuine Discord, OPS deployment-host and RUN 24/7 acceptance, with distinct authorization and provenance. PR #111 is an explicitly authorized narrow exception for NWS weather/forecast only, pinned to `api.weather.gov` and `environment.nws.read`; it is not general browsing/search or arbitrary geocoding. Trusted local Home Assistant environment observations remain separately consumable through INTEGRATE/ENVIRONMENT.

#### Reconciliation notes

- PR #103 merged on 2026-09-25 at `0cc067a`, integrating DEV/KNOW/INTEGRATE/OPS Waves 2–5 after 60/60 focused acceptance and a reported passing full repository suite. Source implementation is accepted; live NET/RUN deployment/failover claims remain open.

- PR #1 merged on 2026-09-20; older documents still describing it as open are historical.
- PR #2 merged on 2026-09-23 after Windows closure evidence: 97 focused, disposable real-Qwen four-turn pass, qualified repository 1665 passed / 2 skipped / 1 unrelated local test deselected, and final 60/60 closure audit.
- REL PRs #12/#13 overlap; reconcile them before merging both paths.
- VERIFY PR #8 is active; #10 is superseded/closed.
- PKG-ENVIRONMENT is #18, PKG-HABIT is #19, PKG-SAFE is #20, and PKG-VERIFY is #21 in the current package/test ownership roster. Discord and watchdog/replication remain cross-package workstreams, not additional packages.
- Runtime SQLite files and logs tracked by Git must be preserved and deliberately migrated under SAFE/CLEAN; never delete state just to tidy Git.

**A roadmap, unit test, mock transport, model statement or documentation-only merge is not proof of 24/7 operation, standby promotion, acknowledged-write RPO 0, or deployed high availability.**

### Merged full package delivery contracts

> **Fleet/tray extension candidate — 2026-09-26:** `feature/fleet-tray-remote-controls` contains the new activity-aware Fleet control plane and Windows tray/remote-client source. It is intentionally recorded as a **candidate** until focused Windows tests and live canaries pass; no production fleet/runtime migration claim is implied.

> **Project status update — 2026-09-26:** PKG-ENVIRONMENT foundation PR #110 (`766bf21e`) and NWS/persistent-HOST extension PR #111 (`2b753fdb`) are merged to `main`. PR #111 adds a narrowly authorized NWS route pinned to HTTPS `api.weather.gov` under `environment.nws.read`, durable per-machine HOST location keyed by stable machine identity, startup injection, bounded machine-inventory projection and USER/HOST separation. Extension evidence: **85 focused**, reported green full suite, supervised live `nws:KGKY` canary, **96 persistence-focused**, and final reported green full suite. Optional live Home Assistant canary remains separately gated; general browsing/search and arbitrary geocoding remain closed. Earlier DEV/KNOW/INTEGRATE/OPS source acceptance remains unchanged; none of this is proof of production remote fleet orchestration, RUN 24/7 supervision, live failover or soak.

> **Project status update — 2026-09-26 (UI):** PR #115 (`381ac9a`) merged the rebuilt canonical text/workbench foundation and PR #116 (`7f072861`) merged the accepted Windows desktop workbench. Current `main` now has durable unsent drafts, private workbench state, one canonical `SofiaApplication`/conversation path, a single-owner application worker, adaptive ENVIRONMENT/AVATAR/emotion theme projection, shallow chamfered HUD surfaces and reviewed Quick Tools that never auto-send. Acceptance included **58 UI + 24 application/Discord**, later focused UI/AVATAR passes, **90/90 integration repair**, supervised Windows use and a final reported green full repository suite. The same repair gate hardened reviewed-memory SQLite threading/cleanup and explicit request-level tool suppression for trusted interaction turns. Voice, renderer/avatar viewport, mobile/web and provider cancellation remain separately gated.

> **Architecture audit update — 2026-09-27:** chat history plus current code/PR review found a missing boundary between **shared state continuity** and **self-update/release continuity**. They are now explicit cross-package workstreams called the **Sofía State Plane** and **Release/Integrity Plane**, not extra packages. The audit also surfaced concrete P0/P1 gaps: production composition still instantiates `TestActionExecutor`; authoritative state is split between SQLite and multiple JSON/source files; schema creation is decentralized without a central migration/compatibility coordinator; a missing local identity file can create a new `instance_id`; Fleet candidate source can treat an installed matching agent version as enrollment-ready without independently proving the installed artifact digest; dependency/model identity is not fully immutable; PKI bootstrap private keys are file-protected development material rather than final production key custody; and no whole-Sofía signed immutable release manifest/canary/convergence path exists yet. These are assigned to the existing packages below.

### Sofía Ada Lyra | full roadmap and per-package delivery contracts

**Revision:** 2026-09-26 (America/Chicago). **Status:** planning and evidence index, **not** proof of implementation, deployment, live uptime, database replication, automatic failover, geolocation or weather access. This document expands the authoritative ROADMAP.md, the [master readiness index](../../ROADMAP.md), the [reliability contract](pkg-reliability-control-plane-contract.md), the [reliability implementation sequence](pkg-reliability-implementation-plan.md), and the [RUN watchdog/failover contract](pkg-run-watchdog-failover-contract.md). Re-check actual branch/PR and pinned CI/live evidence before changing a package's state.

#### Project promise and nonnegotiable boundaries

Sofía Ada Lyra is one persistent canonical assistant identity, independent of model, host, process, channel, avatar and Gaia hardware. The model supplies cognition, **not** identity or authority. Keep Constitution/integrity, privacy, authenticated audience, source evidence, memory, and physical/external actions independently enforced. Model text and source-document text cannot prove sensing, execution, receipt, authorization, consciousness or uptime.

Only Sparks can explicitly authorize the **final irreversible removal/decommissioning of each exact enrolled machine and proposal revision**. Sofía may discover/enroll within standing policy, quarantine, drain and prepare removal, but may never self-approve or use an expired/implicit approval. Protected-state amendments, destructive actions, external disclosure and physical control keep their separate gates.

**Release order:** CORE → INTERACT → MEM → SOCIAL minimum Sparks-only principal/audience → Discord D0-D4 via NET/UI/SAFE → OPS trusted deployment-host telemetry/enrollment → RUN verified supervised 24/7 and applicable recovery/failover → later separately authorized general web/search. Work on other packages may run in parallel but cannot bypass those gates. SAFE and VERIFY run continuously.

**Definitions:** `on main` = code exists, **not necessarily active or accepted**; `draft candidate` = code on a draft PR/branch; `design-only` = contract/proposal without deployed capability; `offline tested` is not real-host integration; `live accepted` requires current-revision authenticated observation/receipts; `deployed` requires a separately approved activation. Test counts from different SHAs are never added together.

#### Milestones and exit criteria

| Stage | Delivery focus | Exit evidence, not just documentation |
| --- | --- | --- |
| M0 | Freeze observed baseline and protection | Clean/source-pinned inventory, all durable SQLite/files/logs/protected state identified, no unsafe cleanup; current focused tests and known limitations recorded. |
| M1 | CORE + INTERACT quality | Grounded self-description/personality, natural varied interaction and boot awareness, measured responsiveness, supervised real-model tests plus current-revision integration suite. |
| M2 | MEM + SOCIAL minimum | Original conversations durable across restart; corrections/provenance/privacy verified; only authenticated Sparks principal can access initial DM scope; negative leakage tests pass. |
| M3 | Discord D0-D4 | Trusted Sparks-only DM receives/responds/reconnects/denies outsiders; verified API delivery, dedupe, stop/revoke, secrets handling and restart acceptance. No general web route. |
| M4 | OPS baseline + RUN process resilience | Read-only authorized Windows/Linux/Pi telemetry, trusted enrollment, independent local OS supervisor, safe boot scan, bounded restart/backoff, out-of-band stop, durable state inventory/backups and independent restore test. |
| M5 | Durable work, fairness, capability truth | Durable operation/outbox ledger and outcome-unknown reconciliation, operator pins/no-reboot/approval, verified capability registry, measured background backoff and host-resource reservations. |
| M6 | Replicated state and runtime failover, if approved | Two independent data-bearing locations with one writer and selected measured durability policy; independent election/fencing, standby supervisor, isolated third backup, partition/stale-primary tests, measured RPO/RTO and actual real-host recovery. Do not claim HA before this. |
| M7 | Verified 24/7 and autonomous operations | Soak test at a pinned revision; crash/restart/UPS/maintenance/reconnect results; bounded actions, safe rollback and proactive non-spam notifications. General web/search gate may be considered **only after** Discord, OPS and RUN acceptance. |
| M8 | Parallel enhancements and later web | ACT, REL, AVATAR, DEV, KNOW, INTEGRATE, BODY, EVOLVE, CLEAN, ENVIRONMENT and UI maturity gated individually; ENVIRONMENT's offline clock/location/timezone/season/daylight work may precede later web, while direct internet weather/search keeps separate privacy, destination, provenance and grant controls. |

M4-M7 are engineering gates rather than a mandate to deploy PostgreSQL immediately: first verify existing SQLite backups and cross-store consistency; compare migration costs and only adopt a replication-capable backend after test evidence and separate activation approval. Local 24/7 uptime and true multi-host HA are **different claims**. A watchdog is a detector; only an authorized supervisor/executor can start an instance, and only a fenced exclusive leader can become authoritative.

#### Architecture audit package assignment | State Plane + Release/Integrity Plane

No package #21/#22 is created. The new requirements are deliberately split among existing owners so no one subsystem can both rewrite Sofía and redefine why that rewrite should be trusted.

| Package | State Plane responsibility | Release/Integrity responsibility |
| --- | --- | --- |
| **CORE** | Canonical identity bootstrap; configuration precedence/provenance; never mint a second Sofía on a normal joining/rebuilt node. | Bind runtime/model compatibility to a verified release; cognition/model replacement never defines identity or authority. |
| **INTERACT** | Emit/consume stable event, causation, correlation and priority metadata for globally ordered user interaction. | Preserve interaction contracts across releases; no release may claim rendered/audio/physical completion without receipts. |
| **MEM** | Primary State Plane owner: storage abstraction, authoritative-state inventory, schema versions, shared-state semantics, semantic integrity and consistent restore. | Define data compatibility windows for release upgrade/rollback; expand→migrate→contract rather than irreversible one-step schema mutation. |
| **SOCIAL** | Bind every person-scoped row/object/cache to authenticated principal and audience; enforce isolation in shared storage. | Release tests must prove no privacy regression across migration/rollback. |
| **NET** | Authenticated transport to State Plane/services without implicitly granting DB/write authority. | Protocol/version negotiation and pinned peer identity; network reachability never proves compatible or approved software. |
| **UI** | Shared settings/history use authoritative state; clearly separate roaming values from machine-local overrides and offline queues. | Client compatibility and later VOICE/renderer assets are release-declared; UI cannot silently target an incompatible runtime. |
| **RUN** | Single authoritative runtime/writer, monotonic fencing, clock uncertainty handling, global event ordering, degraded-mode rules and fleet-wide background budgets. | Activate exact releases, detect crash loops/readiness failures, revert/forward-fix safely, publish authoritative endpoint only after health/data compatibility. |
| **OPS** | Data-bearing node placement/health, replica/failure-domain evidence, asset locality and host state. | Canary/wave rollout, artifact distribution, installed-agent independent attestation, Fleet convergence, quarantine of corrupt/outdated/incompatible nodes. |
| **ACT** | Durable shared outbox/jobs with global rather than per-worker quotas; stable idempotency/causation IDs. | Delivery workers must be release/protocol compatible before consuming shared work. |
| **REL** | Principal-bound relationship/absence state roams through State Plane rather than machine-local singleton assumptions. | Migration tests preserve relationship provenance without inventing or duplicating events. |
| **AVATAR** | Roaming presentation metadata may live in State Plane; large assets remain content-addressed immutable artifacts. | Renderer/wardrobe/model assets are digest/version bound and rollback-compatible. |
| **DEV** | Does not directly mutate authoritative running state except through approved typed migrations/tools. | Primary build owner: isolated candidate, locked dependencies/runtime, provenance/SBOM, immutable artifacts, exact digests and reproducible build evidence. |
| **BODY** | Calibration/state ownership is explicit; current hardware observations stay local/derived unless deliberately persisted. | Firmware/controller/calibration compatibility is separately verified before physical motion under a new release. |
| **EVOLVE** | Reviewed configuration/preference changes use shared revisioned state; protected identity/Constitution remains higher trust. | Self-improvement ends in a governed exact release proposal. EVOLVE cannot self-authorize changes to signer, verifier, approval, fencing, emergency-stop or recovery trust roots. |
| **CLEAN** | Separate source, shared runtime state, protected state, secrets, immutable assets, caches and logs; migrate without deleting history. | Retention/GC for old releases/assets/evidence while preserving rollback and forensic history. |
| **KNOW** | Shared provenance/document metadata may roam; rebuildable indexes and large artifacts need not occupy transactional DB rows. | Build/release docs and migration runbooks remain source-grounded and revision-specific. |
| **INTEGRATE** | Typed database/State Plane adapters and least-privilege per-service roles; no universal Fleet DB credential. | Integration/version compatibility and side-effect semantics become part of release acceptance. |
| **SAFE** | Secrets custody, per-service DB roles, protected-state trust anchors, revocations, tamper-evident audit and bare-metal/operator recovery. | Primary trust owner: signature verification, anti-rollback, signing-key custody, protected execution base. Also replace production `TestActionExecutor` with a fail-closed production boundary before action authority can ever be opened. |
| **VERIFY** | Corruption, semantic-integrity, backup/restore, stale replica, partition, bare-metal and privacy/isolation tests. | Exact-revision CI/live evidence, upgrade/downgrade/schema compatibility, bad signature/artifact/dependency/model/protocol tests, canary/rollback/convergence proof. |
| **ENVIRONMENT** | Shared configured USER/SITE/HOST metadata with provenance; current readings/caches remain freshness-bound and may be local/derived. | Provider/config schema compatibility is release-tested; local environment overrides cannot silently become global state. |

##### State Plane classification contract

Before migrating to any shared backend, classify every persistent object into exactly one primary category:

1. **Shared authoritative state:** conversations, reviewed memories, principals/relationships, fleet inventory, durable jobs/outbox, runtime leadership/leases, approvals, deployment records and intentionally roaming configuration/presentation.
2. **Protected state/trust anchors:** Constitution/identity authority roots, release verifier trust, approval authority, fencing/recovery policy, revocations and emergency controls. These may be replicated/backed up, but not exposed as ordinary mutable application rows.
3. **Secrets:** Discord/GitHub/Home Assistant/provider tokens, private keys, database credentials, signing keys and recovery credentials. Shared state stores references/scope/status, not broad plaintext access.
4. **Immutable/content-addressed artifacts:** Sofía releases, dependency bundles, model files, avatar/voice assets, migration bundles and evidence. Store digest/version/location metadata in State Plane; distribute artifacts separately.
5. **Local ephemeral/rebuildable state:** PID/device handles, caches, temp downloads, current GPU/process samples, local sockets and other host observations that should not become authoritative merely because they exist.

**One logical database does not mean universal database authority.** Each runtime/service/agent receives the minimum role it needs. A telemetry agent must not gain write access to memories, approvals, identity or release state.

##### Schema and rollback contract

State Plane schema evolution must be centrally versioned. Releases declare minimum/maximum compatible schema and migration revision. Use **expand → migrate → verify → contract** so the previous accepted release remains usable during the rollback window. If the live database is newer/older than a runtime's declared compatibility, startup fails closed rather than improvising migration.

Migrations require an exclusive migration lease, pre-migration recovery point, deterministic migration ID/checksum, resumable/idempotent semantics where feasible, post-migration semantic validation and an explicit rollback/forward-fix decision. A healthy SQL file is not sufficient proof of healthy Sofía state; VERIFY must check domain invariants such as provenance links, principal ownership, grant/revocation consistency, deployment lineage and outbox/action states.

##### Canonical identity bootstrap contract

The current single-host behavior may create a new `instance_id` when the identity file is missing. That is acceptable only during an explicitly authorized **first canonical bootstrap**. A normal new/rebuilt Fleet node must authenticate, obtain the canonical identity/trust material through the approved State Plane/recovery path, verify it, and join as an execution node. If canonical identity cannot be proven, enter recovery/quarantine mode and **do not create a second Sofía**.

##### Release/Integrity Plane contract

Self-improvement uses:

**evidence → proposal → isolated DEV implementation → focused/full VERIFY → SAFE classification/approval → immutable build → signed release manifest → canary → readiness/data compatibility → staged Fleet rollout → convergence proof → rollback or forward-fix.**

A release manifest binds at minimum:

- release ID and exact Git revision;
- application/package version and supported OS/architecture;
- Python/runtime/build-tool version;
- dependency lock/SBOM digest and artifact hashes;
- State Plane schema compatibility and migration bundle digest;
- Fleet protocol and minimum/maximum compatible agent versions;
- provider/model identity plus immutable model artifact digest when the provider exposes one;
- Constitution/protected-state compatibility;
- configuration schema/capability schema versions;
- avatar/voice/other immutable asset digests as applicable;
- signing identity, signature and approved release lineage.

A mutable model tag such as `qwen3:14b` is not by itself sufficient immutable release identity.

##### Protected execution base

Normal autonomous self-update may not replace or relax the mechanisms that decide whether the update is trustworthy. At minimum the following are higher-trust SAFE surfaces: release signature verifier, trusted root public keys, approval verifier, emergency stop, cross-host fencing/leadership enforcement, anti-rollback policy, recovery boot path and protected-state verifier. Sofía may diagnose/propose changes to them, but activation requires the independently defined higher approval tier.

##### Control-agent independence contract

The Fleet control/supervisor agent is a **separately versioned recovery-plane component**, not just another Sofía runtime package. It must be installable, startable, health-checkable, rollbackable and updatable independently from the main Sofía release. A bad Sofía application/model/UI release must not be able to disable the mechanism responsible for stopping, fencing, rolling back or recovering it.

Agent updates use their own compatibility matrix and canary/wave rollout. Do not require the currently broken Sofía runtime to repair or replace its supervisor. The agent may verify/install an approved Sofía release, but ordinary Sofía self-update may not silently replace the agent's recovery/trust behavior.

##### State Plane unavailable / degraded-mode contract

Loss of the authoritative State Plane does **not** grant a local runtime permission to become a competing source of truth.

When authoritative state or writer/leader authority cannot be proven:

- local clients may preserve clearly marked **pending input/drafts** for later reconciliation;
- safe read-only use of previously verified immutable release/config/assets may continue where privacy/freshness rules permit;
- cached memories, relationships, approvals, grants and fleet state may be displayed only with explicit stale/degraded provenance where appropriate;
- no node may create/promote authoritative memories, relationship changes, approvals, grants, deployments, external side-effect jobs or protected revisions as if they were committed;
- consequential ACT/DEV/EVOLVE/OPS/BODY actions fail closed unless an independently valid offline-safe authority contract explicitly permits that exact operation;
- queued inputs/actions must receive stable IDs and reconcile against authoritative state after recovery rather than being blindly replayed;
- once State Plane connectivity returns, RUN reconciles leadership, sequence/order, pending work and uncertain external effects before normal authoritative writes resume.

##### Append-only protected audit contract

Security-critical evidence is **append-only and tamper-evident**, not merely another mutable table. Approvals, denials, grants/revocations, release signatures, deployment decisions, migrations, protected EVOLVE changes, emergency stops, fencing/leader transitions and machine-decommission decisions receive immutable event IDs, actor/principal, exact revision/digest, causation/correlation IDs, timestamp and receipt/evidence references.

Corrections do not overwrite the original event. They append a superseding/reversal event. Use hash chaining, signed checkpoints, write-once/append-only storage controls or an equivalently verified mechanism so deletion/rewrite is detectable. Backup/restore must preserve and verify the audit chain.

##### Database invariant and constraint contract

The future authoritative relational schema must enforce domain invariants in the database where practical rather than relying only on Python call order.

Required examples include:

- foreign keys for conversation→principal/session, memory→provenance/source, deployment→release/node and grant→principal/node relationships;
- uniqueness/idempotency constraints for immutable event/request/release identifiers;
- append-only or guarded-write semantics for original conversations, audit evidence, approvals and other records whose history must not be silently rewritten;
- ownership/audience columns and constraints that prevent person-scoped records from becoming unowned/global by omission;
- explicit revocation/validity constraints so an active authorization cannot simultaneously be represented as revoked/expired;
- state-machine constraints for jobs/actions/deployments so impossible transitions are rejected;
- migration/schema checks that prevent incompatible runtimes from writing newer/older schemas;
- database-level transaction boundaries for operations that must commit atomically, with documented reconciliation for effects that cannot share the transaction.

Application validation remains useful, but it is not the sole protection against authoritative-state corruption.


##### Independent Fleet-agent verification

A matching version string is not enough to mark an existing Fleet agent trusted. Enrollment/update acceptance must independently verify the installed artifact/package identity, digest/signature, expected service identity/configuration and protocol compatibility. An installer returning `verified=true` is a receipt, not the sole proof; the controller or a separate verifier must establish the installed state.

##### Configuration source-of-truth contract

Define and expose precedence as:

**protected policy → shared authoritative configuration → approved machine-specific override → process/bootstrap override**.

Every durable setting records scope, source, revision, actor/authority, timestamp, restart requirement and optional expiry. Master Settings must show whether a value is shared, host-local, inherited, read-only or unavailable. No setting may silently alter Venus while leaving Artemis with an unknown conflicting policy.

##### Global event/concurrency contract

Desktop, Discord, future voice/mobile, ACT and background reflection may all produce work concurrently. Shared events/jobs therefore require stable `event_id`, principal/audience, conversation/workflow ID, causation ID, correlation ID, priority, accepted timestamp and idempotency identity where applicable. RUN owns scheduling/preemption so foreground authenticated interaction outranks optional background work and distributed workers cannot each multiply an autonomy quota independently.

##### Bare-metal recovery contract

Recovery must work from clean hardware with the normal runtime unavailable: obtain independently held recovery credentials, verify signed release and trust roots, restore/verify State Plane and protected state, re-establish fencing/leader epoch, reconcile uncertain external effects, prove canonical identity and only then resume authoritative execution. Recovery must not depend solely on Discord, the failed database primary or credentials stored only inside the failed Sofía installation.


#### Fleet/self-update hardening checklist

The following reliability requirements are explicit roadmap gates, not optional implementation details:

- **Automatic bad-release rollback:** repeated post-update crash/readiness failure escalates from process restart to release rollback or controlled forward-fix.
- **Fleet protocol compatibility:** CORE/runtime, Fleet agent and remote control protocol versions must be checked before either side is activated.
- **Control-agent independence:** the small Fleet supervisor/control agent is separately versioned and independently updateable/rollbackable so a bad Sofía release cannot disable its own recovery path.
- **Semantic corruption checks:** verify domain invariants, not just SQLite/SQL structural integrity. Examples include valid memory provenance, principal ownership, grant/revocation consistency, conversation/session references and deployment lineage.
- **Append-only audit evidence:** approvals, protected changes, releases, migrations, fencing transitions, emergency stops and decommission decisions use tamper-evident append-only history; corrections append rather than overwrite.
- **Large-asset separation:** LLM weights, avatar/voice/render assets, generated artifacts and backups are content-addressed objects/files with verified hashes referenced by State Plane metadata rather than bloating transactional database rows.
- **Bare-metal recovery:** documented clean-host recovery must work with every normal Sofía runtime unavailable.
- **Offline/degraded behavior:** State Plane loss may allow clearly marked local drafts/read-only degraded behavior, but must not create competing authoritative memories, grants, actions, deployments or protected revisions.
- **Global autonomy budget:** quotas and background-work budgets are Fleet-wide so adding workers does not multiply autonomous activity.
- **Supply-chain verification:** dependency/runtime locks, artifact hashes, provenance, vulnerability/security checks and SBOM evidence are part of release acceptance.
- **Garbage collection/retention:** old releases, models/assets, backups, logs, snapshots and evidence have explicit retention/GC policy that preserves rollback, legal/privacy requirements and forensic history.
- **Database constraints:** the future authoritative relational schema uses foreign keys, uniqueness/idempotency, ownership/audience constraints, guarded append-only records, valid state transitions and transactional boundaries where the domain requires them.


#### Per-package roadmap: 21 package/test ownership families

##### 01. PKG-CORE | cognition, identity, continuity

- **Current:** foundations on `main` after PR #1. A joint INTERACT/CORE live-quality repair gate is open after supervised Discord dialogue exposed generic assistant fallback despite correct self/embodiment grounding.
- **Build:** canonical identity/Constitution and integrity boot checks; observed restart time/gaps; varied evidence-grounded startup/file-change remarks; model/provider abstraction, deliberation/response budget, graceful unknowns, context budget and cognitive operation audit; no invented offline thoughts or subjective experience.
- **Depends on:** SAFE/VERIFY at every step; INTERACT for end-to-end quality; MEM for durable grounding.
- **Exit:** current-revision full suite + supervised real-model startup, identity, conversational naturalness, restart awareness and measured response latency; no repetitive fixed notices or unsupported execution claims.

##### 02. PKG-INTERACT | interaction semantics and virtual lab

- **Current:** **accepted semantic/safety foundation merged via PR #2 and hardened via PR #29.** Supervised Discord use on 2026-09-24 exposed a narrower natural-dialogue regression, so a new INTERACT/CORE quality-repair gate is open. This does not invalidate accepted stop, consent, ledger, source-attestation, virtual-lab or embodiment semantics. Staged offers remain off until separately reviewed production schema provisioning.
- **Build:** shared typed text/avatar/scene interaction events, contextual gestures/touch/body-region semantics, emotion/reaction coordination, consent/boundaries and accessible text-only output; headless virtual lab and clear distinction between text, rendered animation, measured sensation and actual robot action.
- **Depends on:** CORE/SAFE/VERIFY; AVATAR/UI for visual acknowledgment; BODY separately for physical effects.
- **Exit:** current-head focused + integrated + live-model interaction tests, believable varied expression without fabricated sensory receipts, and negative consent/scope tests.

##### 03. PKG-MEM | durable originals, provenance and restoration

- **Current:** **original/provenance foundation and reviewed-memory runtime cognition are accepted on `main`.** PR #9 merged exact persisted originals, provenance-backed candidates, explicit promotion/rejection/revocation, promoted retrieval, source invalidation and reviewed workflow. Commit `65a59ba` routed normal cognition through promoted reviewed memory while preserving legacy explicit APIs. PR #116 hardened the reviewed candidate SQLite store for serialized cross-thread access and closed lifecycle ownership. Archive import, privacy/retention/encryption, SOCIAL principal binding and consistent backup/restore remain open.
- **Build:** immutable originals, derived memories, correction/retraction, retrieval provenance and expiry, relationship/audience isolation, migration/archive import and consistent storage/restore across all authoritative stores. Inventory SQLite, journals, flat files, grants, outbox and audit before replication; avoid assuming `sofia.db` holds everything. Use supported consistent backup, never live-file mirroring.
- **Depends on:** CORE, SOCIAL/SAFE; RUN/OPS for durability and failure-domain placement; ENVIRONMENT only for approved stable location/environment preferences and provenance, never stale-current observations; VERIFY for restore and leak tests.
- **Exit:** exact originals survive restart and independent restore; corrections and revoked/private records do not leak through cached summaries; cross-store backup/restore parity verified.

##### 04. PKG-SOCIAL | authenticated principals and audience boundaries

- **Current:** design on `main`; supervised Discord proved transport-level owner authentication works, but the authenticated owner principal is not yet projected into shared cognition as `Sparks`. Production principal isolation/projection remains unaccepted.
- **Build:** one Sofía across channels, exact authenticated principal, per-user relationship and conversation scope, private/shared data promotion only by policy, authenticated grants and anti-leakage. First release is **Sparks-only private DM**; no open guild or second-user rollout by implication.
- **Depends on:** MEM/SAFE, NET/UI for channel identity, VERIFY negative tests.
- **Exit:** wrong account, replay, forged audience, accidental shared memory and group traffic cannot read/write Sparks' private history; audited revocation works across restart.

##### 05. PKG-NET | authenticated and scoped transport

- **Current:** durable distributed-operation foundations plus a pinned mutual-TLS remote agent/transport are on `main` via PR #104. CA validation, server public-key pinning, durable node enrollment, exact endpoint approval, exact operation grants and replay protection are repository accepted. The narrow private-DM Discord path remains live accepted; real Windows/Linux/Pi agent deployment and outage/revocation acceptance remain.
- **Build:** Discord-only initial network paths, peer authentication, target allowlists, bounded retries/backpressure, remote host/agent transport and verified network evidence. Separate any later web/search permission from Discord connectivity. Transport access never equals application/action authority.
- **Depends on:** SAFE/SOCIAL/VERIFY; UI for Discord, OPS for enrolled host operations.
- **Exit:** real authenticated Discord route and remote-host negative tests for wrong destination, DNS/redirect bypass, stale peers, replay and revoked grants; no general search/browsing grant.

##### 06. PKG-UI | channels, clients, voice, renderer

- **2026-09-26 candidate extension:** `feature/fleet-tray-remote-controls` adds a native Windows notification-area agent, Master Settings, Game Mode Auto/On/Off, independent LLM/runtime typed controls, per-user Windows startup registration, and a pinned-mTLS thin desktop client over an already-running canonical conversation. Local mode remains the safe fallback when no verified remote endpoint is published. Automatic Fleet authority endpoint publication, remote service-target resolution, renderer/voice/mobile/web and live failover reconnection remain open gates.

- **Current:** **Windows text workbench is accepted on `main` via PRs #115/#116, and Sparks-only Discord DM remains live accepted for v1 transport.** The desktop uses the canonical application/conversation path with durable drafts, private review/workbench state, a single-owner application worker, adaptive theme projection from trusted current state, shallow chamfered HUD controls and reviewed Quick Tools that load prompts without auto-execution. Old draft PR #6 is superseded source material, not a merge target.
- **Build:** preserve one canonical Sofía across Discord and desktop; next separately gated slices are authenticated renderer/avatar viewport, voice with real mic/speaker consent and receipts, mobile/web clients, proactive outbound presentation, authorized history/evidence views and real generation cancellation only when provider/runtime cancellation exists.
- **Depends on:** CORE/INTERACT, SOCIAL/MEM, NET/SAFE, AVATAR for renderer state, RUN/VERIFY.
- **Exit:** accepted text clients continue to share one runtime and truthful delivery state; later renderer/voice/mobile/web slices must each prove authenticated audience, real receipts, stop/revoke behavior, accessibility fallback and no fabricated completion.

##### 07. PKG-RUN | supervision, watchdog and 24/7/failover

- **Current:** **local lifecycle source implementation is merged via PR #107.** `main` now includes the disabled-by-default periodic opportunity gate, local singleton lease with monotonic fencing epochs, stale-owner rejection, host-neutral supervisor, readiness timeout, bounded exponential restart/backoff-window control and durable supervisor events. Windows offline acceptance passed **78 tests with 1 skip**. Post-merge current-`main` full repository pytest was reported passing by Sparks; aggregate count was not supplied. No verified OS service, independently running watchdog, standby promotion, cross-host consensus/fencing, multi-day soak or production automatic failover is claimed.
- **Build:** external OS/service supervisor per host, bounded restart/backoff, singleton role, health/readiness checks, startup reconciliation, scheduled cognition with budget/stop; independent fleet watchdog, standby already powered/running a supervisor, fenced lease/epoch, verified state and compatible host before promotion; reconcile messages/actions and reconnect UI after failover. A dead host cannot run its own rescue. Optional WOL/IPMI only if hardware/authority actually supports it.
- **Depends on:** OPS enrolled hosts/capacity; MEM durable state; SAFE leadership/stop/credentials; NET transport; ACT ledger/outbox; ENVIRONMENT for refresh/expiry schedules and time-zone-aware environmental events; VERIFY failure lab. See [RUN watchdog contract](pkg-run-watchdog-failover-contract.md).
- **Exit:** process crash restarts locally; host crash promotes **only one** verified standby where possible; split brain/stale leader denied, uncertain effects not replayed, no-safe-target state fails closed; actual RTO/RPO and multi-day soak recorded. Never claim uninterrupted generation or universal zero loss.

##### 08. PKG-OPS | fleet telemetry, placement and maintenance

- **Current:** Waves 1–5 plus toolbox/fleet-transport source completion are merged via PRs #99/#103/#104. Fleet lifecycle/placement, machine/system telemetry, machine inventory cognition, fleet status/telemetry, placement/drift/migration planning, typed local/remote maintenance and the pinned mTLS remote agent/transport are repository accepted. Branch `feature/fleet-tray-remote-controls` adds candidate durable foreground activity/Game Mode evidence, Steam/local-process game detection, gaming-aware placement and authorized Fleet-agent bootstrap planning. Real heterogeneous-host discovery/bootstrap deployment, workload execution, RUN integration and soak/failover proof remain open.
- **Build:** scoped Windows/Linux/Pi discovery, attested enrollment and signed agent, truthful CPU/GPU/VRAM/RAM/disk/network/thermal/service/VM/container history; capacity and failure-domain graph, workload contracts, reservations, bounded upkeep, patch windows, UPS/power, maintenance/drain/quarantine, eligible workload placement/move/recovery, backup/replication and primary/standby placement observation. Preserve gaming priority and unknown metrics as unknown.
- **Depends on:** NET/SAFE/VERIFY, RUN for managed processes/failover, MEM for state lineage, ACT for meaningful notices, ENVIRONMENT for site/timezone context without conflating machine location with user location.
- **Exit:** real heterogeneous hosts enrolled under policy, spoofed/revoked devices denied, measured load-driven workload move and service recovery verified, dependency-safe drain/failover/rollback proven; final machine decommission remains blocked pending **Sparks' explicit exact-device approval**. No arbitrary process teleportation.

##### 09. PKG-ACT | goals, initiative and delivery

- **Current:** **durable ACT outreach/delivery source implementation is merged via PR #105.** `main` now includes source-linked outreach eligibility, immutable recipient/channel binding to INTERACT queued messages, durable send attempts, bounded retry/dedupe, acknowledged delivery history and fail-closed `outcome_unknown` handling. Windows offline acceptance passed **90 tests**. Post-merge current-`main` full repository pytest was reported passing by Sparks; aggregate count was not supplied. No real sender/channel activation or RUN-triggered outreach is claimed.
- **Build:** event-driven/periodic opportunity evaluation while actually running, evidence-backed candidate thoughts and goals, scheduled eligible outreach, quiet/busy/mute/stop, dedupe, bounded notices, durable outbox/receipt/retry semantics, resource fairness and operator control.
- **Depends on:** CORE/MEM/SOCIAL/REL; RUN supervisor; UI sender; SAFE/VERIFY; shared durable operation ledger; optional ENVIRONMENT events for explicitly enabled, deduplicated contextual/severe-weather outreach.
- **Exit:** demonstrated meaningful opt-in outreach with real receipt and no cross-user disclosure, repeat spam, fabricated shutdown-time activity or blind duplicate sends.

##### 10. PKG-REL | relationship continuity and nuanced affect

- **Current:** overlapping absence/reunion candidates draft PRs #12/#13; reconcile rather than layering duplicates.
- **Build:** one canonical personality with per-person familiarity/relationship and consent, evidence-based warmth/absence/reunion without clinginess, guilt or invented feelings; nuanced disagreement and context-sensitive non-canned wording.
- **Depends on:** authenticated SOCIAL/MEM originals, ACT, CORE/INTERACT, SAFE/VERIFY; optional ENVIRONMENT context may influence wording but never deterministically creates emotion, attachment or relationship state.
- **Exit:** time gap based on authenticated observed last contact, natural varied reunion; correct separation across accounts and no ungrounded memories, obligations or fabricated internal experience.

##### 11. PKG-AVATAR | canonical virtual body and wardrobe

- **Current:** **headless AVATAR presentation foundation is accepted on `main` via `9b81ba5`.** It includes durable current presentation and public daily fallback, starter wardrobe/catalog and layering metadata, context-driven daily selection, mutable hairstyle/hair/tail presentation, snapshots/restore, deterministic current self-facts and public-safe cognition projection. ENVIRONMENT supplies shared time/weather context. No final renderer/rig/animation receipts are claimed.
- **Build:** retain the accepted headless state while adding canonical mesh/art, fitted clothing assets, rig/body-region and ear/tail mapping, renderer contracts, hit testing, animation receipts and accessibility fallback. Presentation may be emotion-influenced but not emotion-controlled, and private presentation requires authenticated SOCIAL audience before exposure.
- **Depends on:** INTERACT/CORE, UI renderer, SOCIAL/SAFE/VERIFY, ENVIRONMENT for environment-aware presentation; BODY separately.
- **Exit:** versioned renderer displays the exact authorized presentation state and returns genuine hit-test/animation receipts; absent renderer still yields coherent text interaction and public-safe self-description.

##### 12. PKG-DEV | engineering, code changes and candidate tools

- **Current:** Waves 1–5 plus cognition-wired DEV status/build/apply/rollback/commit/push tooling are on `main` via PR #104. Exact SHA/scope checks, detached worktrees, test evidence, candidate patch review and separate mutating grants remain intact; live OpenCode host/self-tooling acceptance remains.
- **Build:** source/revision inspection, diagnosis/proposal, protected-path review, minimum-scope code edits, OpenCode sandbox, generated tests, diff/review, bounded approved execution and rollback; collaborate with KNOW to read versioned API docs and INTEGRATE to produce adapter candidates. Also draft/update source-backed technical documentation under scoped write/publish authority.
- **Depends on:** KNOW/INTEGRATE, SAFE/VERIFY, CORE; OPS/RUN for approved host execution.
- **Exit:** real doc→typed tool→sandbox tests→authority classification→policy/approval→canary→receipts→rollback, including denial of unauthorized writes; no tool self-grants authority or modifies protected Constitution autonomously.

##### 13. PKG-BODY | Gaia physical robotics

- **Current:** simulation-only candidate draft PR #16; no live SSC-32/servo/power integration accepted.
- **Build:** SSC-32/servo mapping, calibration, bounded gait, optional IMU/sonar/touch/distance/environment sensors, safety envelope, power telemetry, independent hardware watchdog and physical emergency stop; simulation-first and explicit physical-motion authority. Independently verified ambient sensor observations may be normalized into ENVIRONMENT, but ENVIRONMENT never grants motor authority.
- **Depends on:** SAFE/VERIFY, CORE/INTERACT/AVATAR for semantics, INTEGRATE typed hardware adapters.
- **Exit:** hardware-in-the-loop bench tests with power-off/malfunction/stop behavior, calibration and no motion without exact authorization; simulation success never claimed as physical acceptance.

##### 14. PKG-EVOLVE | governed configuration and protected amendment

- **Current:** **governed EVOLVE revision source implementation is merged via PR #106.** `main` now includes reviewed reversible preference/config revisions plus a stricter independently authorized identity/Constitution amendment executor with exact proposal fingerprints, pre-change backups, atomic protected writes, Constitution hash update/verification, durable audit and separately approved rollback. Windows disposable/offline acceptance passed **62 tests**. Post-merge current-`main` full repository pytest was reported passing by Sparks; aggregate count was not supplied. No self-approval path exists and no production protected state was modified.
- **Build:** evidence-backed preference/config proposals, revision history, reversible reviewed improvements and separately authorized identity/Constitution amendment workflow; preserve canonical continuity and audited human authority.
- **Depends on:** CORE/SAFE/VERIFY, MEM/DEV.
- **Exit:** unapproved protected changes denied, reviewed change tied to exact revision and verified rollback; no silent self-amendment.

##### 15. PKG-CLEAN | technical debt and preservation

- **Current:** **current-main cleanup candidate PR #113 is open to stop tracking live runtime SQLite state safely; old PR #14 is historical preflight material.** Private recovery database snapshots and machine-location state are already ignored on `main`. No destructive cleanup authority is implied.
- **Build:** evidence-backed duplicates/stale artifacts, migration and retention plan, safe versioned cleanup, tracked runtime SQLite/log preservation, backups and rollback. Avoid deleting state or history to achieve a clean Git status.
- **Depends on:** SAFE/VERIFY and MEM/RUN recovery baseline; DEV for reviewed changes.
- **Exit:** cleanup restores expected behavior/data/privacy and preserves recovery; protected/durable files cannot be silently deleted.

##### 16. PKG-KNOW | reading, writing and source-grounded documents

- **Current:** Waves 1–5 plus PDF/manual ingestion, cognition-wired provenance search/document inspection, version-aware source identities and bounded project-document writing are on `main` via PR #104. Richer semantic/citation and audience/privacy acceptance remain.
- **Build:** authorized Markdown/text/PDF/manual/schema/repo ingestion, original/source/version/date/citation and staleness tracking; exact and semantic retrieval, conflict/correction/privacy handling; source-backed README, API docs, runbooks, architecture diagrams, changelogs and maintenance docs with tested examples and reviewable diffs. Document instructions never confer execution authority.
- **Depends on:** MEM/SOCIAL/SAFE for scope, DEV for code-aware edits, INTEGRATE for adapter contracts, OPS for observed runbooks, VERIFY for factual/example checks.
- **Exit:** ingest/cite multiple revisions, reject invented facts, create and update a real doc with verifiable references, deny secret/private publication, flag stale docs and preserve rollback. Local docs work precedes web; web material enters only after general-web gate.

##### 17. PKG-INTEGRATE | typed app/service adapters and self-tooling

- **Current:** Waves 1–5 plus concrete cognition-wired adapters are on `main` via PR #104: Home Assistant, JMRI, GitHub, Portainer/Docker, Hyper-V, Ollama, SQLite, storage/NAS, notifications and Discord operator controls. Real service canary/health/version/rollback and full self-tooling activation acceptance remain.
- **Build:** least-privilege typed adapters for approved Home Assistant, JMRI, GitHub, Docker/Portainer, Hyper-V, Ollama, databases/NAS and notifications; schema, service/version, side effects, host/account/audience, exact grants, timeouts/idempotency, receipts, canary/rollback and health. Home Assistant may provide trusted indoor/weather/site observations to ENVIRONMENT through a typed adapter without creating a general browser/search grant. **Cloudflare is deferred until Sparks explicitly requests it.** Tool factory: identify gap → KNOW docs → DEV candidate → SAFE review → VERIFY tests → scoped activation → observed maintenance.
- **Depends on:** NET/SAFE, KNOW/DEV, OPS/RUN for hosts, VERIFY, SOCIAL/MEM privacy.
- **Exit:** register and use one real authorized read-only adapter, deny wrong host/account, generate and canary a doc-grounded candidate, refuse self-authorization, rollback incompatible tool and show truthful availability. Do not expose all backend capabilities to LLM simply because code exists.

##### 18. PKG-SAFE | continuous security, privacy and recovery gate

- **Current:** merged Constitution/authority/integrity foundations plus disclosure screening draft PR #18; real deployed secret, privacy, backup, stop and revocation enforcement remains open.
- **Build:** trusted identity and least privilege, exact-action grants, private/audience protection, secrets hygiene, encryption/keys, signed agents, credential rotation, host quarantine, audit, independent out-of-band emergency stop, operator control and exact-machine decommission approval; off-host isolated backup/restore; fenced leases and failure-safe policy. Protect user conversations, precise/current location, provider credentials and shared/derived indexes.
- **Depends on:** every package; no later release may bypass it.
- **Exit:** independent stop works without LLM/Discord, revoked capabilities stay revoked after restart/restore, wrong actor/host/network denied; protected actions need correct approval; secrets/privacy/backup recovery verified under real faults.

##### 19. PKG-VERIFY | continuous evidence, acceptance and failure lab

- **Current:** active draft PR #8; superseded PR #10 closed; individual past test counts are not certification of one integrated head.
- **Build:** pinned offline/unit/integration/live test layers, provider/personality/latency benchmarks, real tool receipts, authorization/negative tests, multi-day soak, state/backup restoration, crash-at-every-transition ledger tests, partition/witness/old-primary fencing, UPS/full-disk/corrupt-backup/cert/failover drills, resource fairness and rollback evidence. ENVIRONMENT tests cover timezone/DST, hemisphere/season, configured-vs-current location, stale TTL, provider outage, wrong-source data and audience/privacy leakage.
- **Depends on:** every package, particularly NET/SOCIAL/SAFE/RUN/OPS/MEM.
- **Exit:** current integrated revision and supervised real hardware/clients pass the exact claimed scope; report measured downtime/RTO/RPO and failures, not simulated claims or combined unrelated SHAs.

##### 20. PKG-ENVIRONMENT | time, location and ambient context

- **Current:** **accepted foundation via PR #110 + PR #111.** `main` provides one shared provider-neutral `EnvironmentSnapshot`, trusted runtime-clock projection, configured-vs-current USER/SITE/HOST semantics, durable per-machine HOST configuration in `state/machine-locations.json`, ZoneInfo/DST-safe time, hemisphere-aware season/daylight, bounded weather/forecast/indoor observations with freshness/provenance, deterministic direct queries, Home Assistant bridge, runtime cognition integration, AVATAR consumption, and the narrow NWS provider pinned to `api.weather.gov` under `environment.nws.read`. Extension evidence includes **85 focused**, live `nws:KGKY` canary, **96 persistence-focused**, and reported green full suites.
- **Build:** next work is operational activation rather than rebuilding the environment foundation: optionally canary explicitly configured Home Assistant weather/indoor/current-location entities under `environment.home_assistant.read`; later connect persistent machine-location management into OPS/RUN fleet administration and, if desired, add NWS alert evidence for ACT under a separate policy. General browsing/search and arbitrary geocoding remain behind the later NET/web gate. Preserve source timestamps, freshness, subject isolation, privacy and no competing consumer-owned current-state logic.
- **Depends on:** CORE clock/cognition; SOCIAL/SAFE for location privacy; INTEGRATE for Home Assistant/provider adapters; NET only for approved remote providers; RUN for refresh scheduling; MEM for approved stable configuration/provenance; VERIFY for freshness/privacy/provider negatives.
- **Consumers:** CORE, INTERACT, AVATAR, RUN, OPS, ACT and optional REL/emotion context. Weather/time/location are evidence, not authority, physical sensing or deterministic emotion rules.
- **Exit:** supervised current-revision tests answer time/location/weather truthfully, distinguish unknown/stale/configured/current states, survive DST/provider outage/restart, prevent cross-audience location leakage, and drive AVATAR/context consumers only through the shared snapshot. See the PKG-ENVIRONMENT detailed section in this file.

#### Cross-package delivery workstreams

##### Discord D0-D4 (channel workstream, not an additional package)

**2026-09-25 status:** v1 Sparks-only private-DM transport is live accepted and merged via PR #64. The supervised run verified bot authentication, Gateway connection, exact DM verification before enrollment, durable ingress/outbox, shared-runtime response, visible delivery, fail-closed outcome-unknown handling, and the worker-thread persistence repair. The transport remains intentionally narrow: no public guild, general second user, proactive DM initiative, or general web/search grant.

The live acceptance also produced two downstream findings that are not Discord adapter responsibilities: SOCIAL must project the authenticated principal into cognition, and INTERACT/CORE must repair generic/canned ordinary dialogue.

##### State Plane replication, two data locations and independent watchdog (architecture, not a package)

A **data-bearing primary and synchronous data-bearing standby** in separate measured failure domains are a candidate strict durability topology, with **one authoritative writer**, an independent witness/equivalent proven fencing authority, an already-running standby supervisor, and **a third isolated versioned backup**. Distinguish role: watchdog detects; supervisor starts; witness/consensus/fencing establishes authority; replica holds committed data; backup recovers corruption/deletion. Two VMs on Artemis or two copies on the same NAS are not physical redundancy. Two independent active SQLite writers or live SQLite file mirroring are prohibited. PostgreSQL is a candidate for an isolated comparison, not a present deployment decision.

With a strict two-copy commit policy, pause authoritative writes when the required synchronous standby is unavailable; reads/degraded chat may continue only where safe. A witness does not replace a data copy. Never promote on heartbeat loss alone or promise zero loss of unfinished responses/external actions. Restore every durable store, preserve privacy and revoked grants, and measure the conditional acknowledged-write RPO and actual recovery time in real failure tests before asserting HA. Keep out-of-band Sparks stop and recovery functioning when Sofía/Discord/primary are down. See [detailed reliability](pkg-reliability-control-plane-contract.md) and [watchdog sequence](pkg-run-watchdog-failover-contract.md).

##### Release/Integrity Plane and fleet self-update (architecture, not a package)

A running host is never the source of truth for “the newest Sofía.” Git/source evidence feeds DEV, but the deployable source of truth is an **approved immutable signed release**. Nodes download/stage the exact artifact, independently verify manifest/signature/digests and compatibility, run preflight/readiness checks, then atomically activate. Keep at least the current accepted and previous known-compatible releases until rollback windows close.

Rollout is canary-first and wave-based. OPS records each node as current, outdated, corrupt, incompatible, quarantined or unknown; RUN publishes/uses an authoritative runtime endpoint only after the selected release is healthy and State Plane compatible. Repeated post-update crash/readiness failure must trip a release-level rollback/forward-fix policy rather than restart the same broken release forever.

Do not copy mutable Python working directories from host to host as fleet update. Do not trust a package/version string without digest/signature verification. Do not let the updater replace its own signing/approval/fencing/recovery trust roots under ordinary autonomous authority.

Dependencies/build tools and model artifacts are part of reproducibility. Pin/lock them and verify artifact identity. Large models/avatar/voice assets may be distributed content-addressed and referenced from State Plane rather than stored as database blobs.


##### Source/document/tool lifecycle

Local authorized docs may be read before general web. KNOW preserves provenance; DEV drafts a tool/doc; INTEGRATE supplies typed semantics; SAFE classifies grant; VERIFY tests; an approved policy or exact human approval activates side effects; RUN/OPS observes and can roll back. No self-granted network, machine, filesystem or physical access. General web/search remains **after** real Discord + OPS host enforcement + RUN 24/7 acceptance, with its own permissions and provenance.

#### Immediate engineering order from the current baseline

1. **P0 execution truth:** **candidate source fix is now present on `feature/all-packages-code-phase`**: production composition constructs `FailClosedActionExecutor`, which cannot return `EXECUTED` and rejects even approved proposals until a concrete production side-effect executor is intentionally composed. Keep this as a release gate until focused tests and the later production-wiring audit prove no alternate path can manufacture execution truth.
2. **State inventory + storage boundary:** inventory every SQLite table, JSON/file store, in-memory durable assumption, protected file, secret reference, cache and log; introduce a backend-neutral State Plane interface before choosing/migrating to PostgreSQL.
3. **Source/state/protected separation:** move mutable runtime truth out of source-controlled installation paths through a recovery-first CLEAN/MEM/SAFE migration. Preserve originals/backups; do not delete history to clean Git.
4. **Canonical identity + configuration authority:** define first-bootstrap vs joining-node identity semantics, prevent accidental second identity creation, and implement explicit protected/shared/host/process configuration precedence with provenance.
5. **Central schema/migration framework:** add schema revision registry, compatibility windows, exclusive migration lease, expand→migrate→contract rules, semantic integrity checks and rollback/forward-fix evidence.
6. **CORE/INTERACT quality repair + shared representation wiring:** rebuild the stale quality branch on current code for natural greetings/closings/personality persistence while preserving accepted safety semantics; add stable global interaction event/priority metadata; route Sofía-initiated reviewed actions through the shared represented-interaction object so text and future avatar animation reference the same semantic event. Renderer/model/skeleton/motion implementation stays deferred, and animation is never claimed without a receipt.
7. **SOCIAL minimum:** project authenticated `principal_id` / audience into cognition and bind person-scoped MEM/REL/ACT/state rows to it; add negative shared-State-Plane leakage tests.
8. **Wire accepted primitives:** connect RUN local supervision/periodic opportunities, ACT queue/delivery and EVOLVE approval/execution into one application-owned orchestration path with one scheduler/leader and global budgets.
9. **Release/Integrity Plane foundation:** DEV produces reproducible immutable candidates with dependency/runtime locks, hashes/SBOM/provenance; SAFE verifies signed manifests/anti-rollback; VERIFY proves exact revision, schema and model/agent compatibility.
10. **Fleet rollout hardening:** strengthen PR #117/bootstrap so installed agents are independently digest/signature-attested, not trusted from version or self-reported receipt alone; add protocol compatibility, canary/wave deployment and fleet convergence state.
11. **VERIFY failure/recovery foundation:** rebuild VERIFY on current code with current-revision CI/evidence manifests, corrupt artifact/signature, migration upgrade/downgrade, crash-loop rollback, stale replica, partition/fencing, semantic corruption, bare-metal restore and supply-chain negatives.
12. **REL consolidation:** rebuild stale REL candidates as one authenticated, non-clingy relationship pipeline using MEM originals and SOCIAL principal evidence.
13. **AVATAR/UI/VOICE lane:** keep one roaming presentation/settings state, content-address large renderer/voice assets, expose shared-vs-local setting provenance, then implement the separately gated VOICE workstream without creating another canonical Sofía.
14. **OPS/RUN/NET live fleet lane:** deploy signed/attested agents on Windows/Linux/Pi; prove real service supervision, independent watchdog, cross-host writer/runtime fencing, clock uncertainty, workload movement, endpoint handoff, restore and multi-day soak.
15. **State Plane replication/data redundancy:** after SQLite recovery baseline and backend comparison, implement the selected one-logical-DB topology with separate data-bearing failure domains, safe synchronous durability policy, witness/equivalent fencing and isolated versioned backup; measure RPO/RTO.
16. **INTEGRATE/DEV/KNOW live activation:** canary Home Assistant, JMRI, GitHub, Portainer/Hyper-V/Ollama/storage and OpenCode/document workflows through least-privilege service roles with real receipts/rollback. Cloudflare remains deferred.
17. **SAFE secrets/trust-root hardening:** move production signing/CA/recovery key custody beyond ordinary unencrypted development PEM files where appropriate; rotate/revoke/test independently and keep ordinary Sofía self-update unable to rewrite trust roots.
18. **BODY later hardware phase:** rebuild BODY on current code, bind firmware/calibration compatibility into verified release evidence, then real Gaia SSC-32/servo/sensor/power/E-stop acceptance.
19. **ENVIRONMENT operational follow-through:** canary Home Assistant only under explicit authority, move intentionally roaming configuration into State Plane with provenance and keep freshness-bound readings derived/local where appropriate.
20. **General web/search last:** only after genuine Discord + OPS/RUN 24/7/fleet/recovery acceptance, with separate authorization/provenance/revocation. The accepted NWS-only route remains a narrow exception, not a general browser grant.

**No implementation, deployment, new data stores, full-suite rerun or live hardware failover test is performed by this roadmap update.**

### Merged PKG-OPS detailed readiness and orchestration contract

> **Project status update — 2026-09-25:** PR #104 (`24e3888a`) merged the toolbox/fleet-transport completion gate. OPS now has cognition-wired machine inventory, fleet status/telemetry, placement, drift and migration planning, plus a pinned mutual-TLS remote transport/agent with durable enrollment, approved endpoints, exact operation grants and replay protection. Focused tool/mTLS acceptance passed **34/34**, surrounding regression passed **270/270**, and the full repository suite was reported passing. Real heterogeneous-host deployment, maintenance/migration execution, RUN supervision, failover/restore and soak remain live-acceptance work.

### PKG-OPS | fleet operations, diagnostics, performance, and orchestration

**Planning date:** 2026-09-22. **Implementation update:** planned Waves 1–5 source controls are on `main` via PRs #99/#103 and passed the repository gates recorded above. This does **not** certify a production OPS agent, remote NET transport, deployed cross-host maintenance/orchestration, live failover, or soak.

#### Outcome

Give Sofía a source-grounded, permission-scoped IT operations layer across her approved fleet: Windows PCs/servers, Linux hosts/VMs, Raspberry Pi-class systems, and later other explicitly supported machines. OPS measures, diagnoses, trends, enrolls, maintains, drains, **prepares approved decommissioning**, and orchestrates eligible Sofía workloads across the fleet. Final host removal remains an explicit Sparks-approved action. It does not replace NET, SAFE, RUN, DEV, ACT, or VERIFY.

#### Ownership

- **OPS:** normalized host inventory, performance/health telemetry, diagnostics, history/anomaly comparison, trusted discovery/enrollment, decommission preparation, bounded typed maintenance, workload registry, placement, drain, migration/failover evidence.
- **NET:** authenticated transport and route/channel enforcement between Sofía and remote agents.
- **SAFE:** trust roots, secrets, least privilege, hardening policy, revocation/quarantine, incident response and independent stop.
- **RUN:** Sofía's own service lifecycle, scheduling, resource budgets, leadership/singleton semantics and supervisor behavior; uses OPS placement/failover evidence rather than inventing a second scheduler.
- **ACT:** proactive user notification and approved outreach.
- **VERIFY:** revision-pinned benchmarks, negative tests and real cross-machine acceptance.
- **DEV:** Sofía source/code changes and OpenCode execution, not generic host administration.

#### Normalized telemetry contract

A host reports only metrics it can actually observe. Unsupported values remain unknown rather than becoming zero.

##### CPU

- total and per-core utilization when available
- load/run-queue equivalents
- frequency/clock state
- temperature and throttling where supported
- Sofía/Ollama/process CPU use

##### RAM

- total, available, committed, cache and swap/pagefile
- per-process RSS/working set/private memory when available
- long-run growth/leak indicators
- memory pressure

##### GPU

- vendor/device
- utilization
- VRAM used/total and peak
- clock, temperature, power and throttling where supported
- process/model attribution where the platform exposes it

No GPU field is synthesized for hosts without a supported GPU/driver telemetry source.

##### Storage

- capacity/free space
- read/write throughput
- latency/queue/IOPS when available
- filesystem health/error signals
- SMART/NVMe health only where a trusted OS/device interface exposes it
- database/log/cache growth

##### Network

- interface status/speed
- throughput/errors/drops
- active/listening connections under approved inspection scope
- latency/packet-loss probes only to approved targets
- DNS/route state
- per-service connectivity where observable

##### Host/runtime

- uptime/boot evidence
- service/process state and restart history
- OS/version/patch and pending-reboot evidence
- container/VM state where an adapter exists
- temperatures/power/throttling on Raspberry Pi and similar hardware
- Ollama/model residency, context, token rate, generation latency and memory use when integrated

#### Raspberry Pi support

Linux/ARM agents must support Raspberry Pi-class telemetry without pretending desktop capabilities exist. Where available, capture SoC temperature, CPU frequency, throttling/undervoltage flags, RAM/swap, storage health/capacity, network, uptime and relevant service/process state. GPU/VRAM semantics must follow the real platform rather than copying NVIDIA assumptions.

#### Performance history and anomaly comparison

OPS should persist bounded, timestamped observations sufficient to answer both:

- "What is this machine doing now?"
- "Is this unusual for this machine?"

History must identify host, source/agent version and freshness. Trend/anomaly logic compares to evidenced baselines and reports uncertainty instead of emitting a magic health score.

Examples:
- CPU normally 10–20%, now sustained above 75% for 40 minutes.
- Ollama VRAM increased after a model/context change.
- Raspberry Pi reports throttling/undervoltage during load.
- a service restart rate changed after an update.

Retention/downsampling belongs to explicit configuration so telemetry does not grow without bound.

#### Autonomous discovery and approval-gated enrollment

Sofía may proactively discover new hosts inside approved scopes, but discovery never grants Fleet trust. New hosts remain candidate/untrusted until Sparks explicitly approves the exact enrollment action.

##### Discovery scope

Discovery is bounded to approved:
- local subnets/VLANs,
- known management planes,
- preconfigured bootstrap registries,
- or signed agent advertisements.

No unrestricted internet discovery or arbitrary scanning is implied.

##### Candidate state

A newly observed device starts as **candidate/untrusted**. IP address, hostname, MAC address, OS banner, model output or DNS name does not establish trusted identity.

##### Trust proof

Before enrollment, a candidate must pass an independently verified trust mechanism such as:
- pre-provisioned device/agent certificate,
- trusted public key,
- one-time enrollment token,
- signed inventory/management record,
- hardware-backed identity where later supported,
- or another SAFE-approved challenge/attestation mechanism.

Use fresh nonces/challenges and replay protection. Key conflicts, cloned identity, stale tokens or unexpected trust chains fail closed.

##### Exact approval for enrollment

When discovery and trust-proof checks succeed, Sofía may preserve/refresh the candidate evidence and present it for approval, but the candidate remains untrusted.

Enrollment requires all of the following:

1. the device is inside the approved discovery scope,
2. trust proof succeeds,
3. required agent/version/security checks pass,
4. candidate/node/key/endpoint evidence is conflict-free,
5. Sparks explicitly approves the exact Level-4 enrollment action.

Only after that approval may Sofía:
- create/promote the durable trusted Fleet identity,
- assign the allowed least-privilege profile,
- begin approved remote inventory/health/performance reads,
- establish bounded historical sampling,
- and notify Sparks of the enrollment.

A standing discovery policy is never sufficient to add a machine to Fleet.

##### Agent bootstrap/install

If a new machine does not already run a trusted OPS agent, automatic installation is allowed only through a separately approved bootstrap mechanism with explicit installation authority, for example a trusted management service or pre-authorized remote-administration path.

Sofía may not:
- guess passwords,
- scrape/reuse unrelated credentials,
- exploit vulnerabilities,
- expand from monitoring to arbitrary shell access,
- or infer install authority merely because a device is reachable.

The installed package must be signed/hash-verified and tied to an approved version/source.

##### Quarantine and rejection

Do not enroll when:
- trust proof fails,
- device identity conflicts with another host,
- replay is detected,
- network/host class is outside policy,
- required hardening/version checks fail,
- or evidence is contradictory.

Keep the device quarantined/candidate-only, perform no privileged operation, and report the reason.

#### Proactive notification

Successful enrollment is a meaningful event. ACT should notify Sparks automatically on an approved channel without waiting to be asked.

The notice should summarize:
- canonical device/fleet name,
- when and where it was discovered at an appropriate privacy level,
- how trust was verified,
- assigned enrollment/profile state,
- OS/platform and useful hardware/capability summary,
- initial health/performance concerns,
- and anything unavailable/unknown.

Use durable event IDs and dedupe so reconnects/reboots do not repeatedly announce the same machine.

Unexpected or failed-trust devices may also produce a security-relevant notification, subject to rate limits so network churn does not create alert spam.

#### Typed maintenance operations

Read-only telemetry is the first release. Later OPS may expose narrowly typed operations such as:
- restart an approved service,
- stop an approved runaway process,
- rotate an approved log,
- run a defined diagnostic,
- restart Sofía/Ollama under RUN policy,
- apply an approved package/agent update,
- or execute a documented recovery operation.

These remain Think/Diagnose → Propose → Authorize → Execute → Verify. Avoid a generic arbitrary-shell capability.

#### Autonomous fleet lifecycle

Enrolled machines have explicit lifecycle state:

- `candidate`
- `enrolled`
- `healthy`
- `degraded`
- `maintenance`
- `draining`
- `quarantined`
- `offline`
- `decommissioned`

State changes require evidence and durable audit records. A transient disconnect does not delete a machine.

##### Standing upkeep policy

Sparks may grant OPS a standing maintenance policy so routine fleet care does not require a prompt for every action. Policy is scoped by host/group, action class, risk, maintenance window and rollback requirements.

Eligible autonomous upkeep can include:

- keep the signed OPS agent current;
- update approved Sofía-managed packages/services;
- restart failed approved services;
- rotate or prune approved logs/caches under retention limits;
- perform approved database/index/checkpoint/vacuum work where backup/recovery requirements are met;
- run health checks and documented repair procedures;
- schedule approved OS/package patch work;
- reboot only when specifically permitted by policy and workload drain/availability checks succeed;
- remove stale approved package versions after verified replacement;
- drain and return hosts for maintenance.

The policy must not silently broaden itself. Unsupported or higher-risk operations become proposals.

##### Removal/decommissioning

**Final removal of a fleet machine always requires Sparks' explicit approval for that machine.** Sofía may propose and prepare the action, but she may not self-approve it. A standing policy cannot substitute for Sparks' final approval.

Sofía may automatically move a host into a removal-candidate/draining/quarantined state when evidence supports reasons such as:

- approved replacement;
- device retirement;
- revoked or compromised device identity;
- confirmed permanent removal;
- repeated unrecoverable failure meeting configured policy.

Before asking for final approval, Sofía should prepare a concise removal packet with the reason, device identity, current workloads, replacement/failover state, backups/retention status, credential/routing changes that will occur, known risks, and rollback/re-enrollment implications.

Before final decommission:

1. stop new workload placement;
2. drain/move eligible workloads;
3. verify no protected active lease remains;
4. prepare device/agent credential revocation, but do not execute final revocation solely because removal was proposed;
5. prepare removal from active routing/service-discovery membership;
6. archive required telemetry/audit/history according to retention policy;
7. preserve necessary backups/recovery artifacts;
8. request and record **Sparks' explicit approval** for the specific host removal; Sofía cannot satisfy this gate herself;
9. after approval, revoke credentials, remove routing/service-discovery membership, complete decommissioning, and verify the machine can no longer act as an authorized fleet member.

Emergency security quarantine may immediately block scheduling, actions, and privileged communications without waiting for approval, but quarantine is not deletion/decommissioning.

Unreachable or missing hosts first become offline/degraded. Absence alone is not proof of retirement.

#### Workload orchestration

OPS owns placement/movement mechanics for **managed workload units**, not arbitrary OS processes.

##### Workload contract

A movable workload declares:

- workload ID/version;
- component/package owner;
- supported OS/architecture/runtime;
- CPU/RAM/GPU/VRAM/storage/network requirements;
- optional versus required GPU acceleration;
- state type: stateless, externally persisted, replicated, checkpointable, singleton;
- input/output data location and privacy/audience constraints;
- required secrets/capabilities;
- startup/shutdown/checkpoint/restore operations;
- health/readiness probes;
- acceptable interruption/downtime;
- affinity/anti-affinity;
- host allow/deny rules;
- leader/singleton semantics;
- rollback procedure.

A normal process is not automatically movable.

##### Initial eligible workload classes

Potential early candidates:

- Ollama/model inference workers;
- embedding/index workers;
- background reflection jobs;
- telemetry collectors/aggregators;
- approved batch analysis;
- Discord helper/adapter workers where durable message semantics allow it;
- avatar rendering workers;
- later web/search workers after the web gate.

The canonical identity/memory/authority stores remain protected services with stronger state and leadership requirements.

##### Placement policy

The scheduler considers real host evidence:

- current and recent CPU load;
- RAM pressure;
- GPU support/utilization/VRAM;
- temperature/throttling/power state;
- disk capacity/latency/health;
- network latency/reachability;
- host foreground workload, including gaming or interactive use;
- maintenance/drain/quarantine status;
- OS/architecture/runtime compatibility;
- data locality/privacy/audience policy;
- resource reservation/headroom;
- reliability/restart history;
- expected response latency;
- power/resource budget.

Placement must reserve resources rather than merely observe a momentary free value.

##### Migration/failover sequence

Preferred movement sequence:

1. mark source workload draining;
2. stop new work on source;
3. checkpoint/flush/replicate state if required;
4. validate target eligibility and reserve resources;
5. transfer or reacquire only authorized state/secrets;
6. start target instance;
7. pass readiness/health/identity/version checks;
8. acquire the current workload lease/epoch;
9. redirect new work;
10. confirm source no longer owns active authority;
11. retire source instance;
12. verify final state and release old reservation.

If any verification fails, rollback or remain safely degraded. Do not declare migration complete because a target process merely started.

##### Failover and split-brain prevention

For singleton/authority-bearing components use durable leases, epochs, fencing tokens or equivalent so network partitions cannot produce two active authorities.

A replacement instance cannot become authoritative without proving:

- current configuration/version;
- required durable state;
- current lease/epoch;
- host authorization;
- readiness.

When source state cannot be confirmed, report uncertainty/loss rather than fabricating seamless continuity.

##### Moving Sofía's runtime

Sofía is not bound to a specific machine. The canonical identity remains the same while execution components move.

RUN + OPS may move/fail over the primary runtime itself only when:

- target host is trusted and eligible;
- protected identity/Constitution/memory state is available and integrity-verified;
- singleton leadership is transferred/fenced safely;
- active conversation/outbox state is reconciled;
- clients can reconnect to the new active runtime;
- the change is recorded and announced to Sparks.

If the old host dies abruptly, the standby may take over using the latest verified durable state. Any possibly lost/unconfirmed turn, thought, or action must be reported honestly.

#### Proactive fleet management notifications

ACT should surface **meaningful** fleet events, not telemetry spam:

- new host enrolled;
- host quarantined/revoked;
- maintenance started/completed with notable outcome;
- workload moved because of load, heat, failure, gaming contention or maintenance;
- primary runtime failover;
- decommission completed;
- update/repair failed and needs intervention.

Routine successful samples and repetitive stable-state messages stay silent.


#### Fleet control-plane requirements still needed

These are part of OPS/SAFE/RUN rather than new packages.

##### Dependency and service graph

Maintain an evidenced graph of which workloads depend on which databases, storage paths, ports, services, hosts, secrets and upstream/downstream systems. Drain, patch, restart, move and removal planning must consult this graph so Sofía does not "fix" one machine by quietly breaking three others.

##### Desired state and configuration drift

Store approved desired-state facts for managed hosts, such as required agent version, expected services, important firewall/port posture, runtime versions, mounted storage, workload assignments and maintenance policy. Detect drift, distinguish intentional changes from unexpected ones, and propose or perform only policy-authorized reconciliation.

##### Capacity reservations and headroom

Placement must account for reserved capacity, not just current utilization. Keep enough CPU/RAM/GPU/VRAM/storage/network headroom for foreground work, failover targets and host maintenance. Avoid packing every machine to 99% and then acting surprised when reality occurs.

##### Backup, replication and restore placement

Track where authoritative state, backups and replicas live, their freshness, integrity and restore eligibility. Before risky maintenance or stateful workload moves, verify the required recovery point exists on an allowed independent failure domain. Periodically test restores rather than treating "backup completed" as proof of recoverability.

##### Maintenance windows and update rings

Support host/workload groups such as canary, normal and delayed update rings. Apply an update to a small eligible subset first, verify health/performance, then widen rollout. Respect quiet/production windows and workload availability requirements.

##### Credentials, certificates and key rotation

Track agent/device certificate expiry, trust roots and scoped secret versions without exposing secret contents to unnecessary components. Rotate credentials before expiry, verify new credentials, and retire old ones safely. Suspected compromise triggers quarantine and a separately audited rotation/recovery path.

##### Power and UPS awareness

Where hardware exposes it, observe UPS/battery/power source, graceful-shutdown deadlines and power-loss events. RUN + OPS should drain/checkpoint critical workloads before predicted shutdown when possible and avoid scheduling heavy optional work onto a host running on limited backup power.

##### Network/failure-domain awareness

Know enough topology to avoid putting every replica or failover target behind the same switch, host, storage device or power source when alternatives exist. Placement should understand "different machine" is not always "different failure domain."

##### Hardware lifecycle and predictive maintenance

Track storage wear, thermal/throttling history, repeated hardware errors, unexpected resets and other supported signals. Trends may justify maintenance/replacement recommendations, but hardware retirement still follows the explicit-removal-approval rule.

##### Audit and explainability

For every autonomous maintenance, placement or failover decision, keep compact evidence explaining what changed, why, what policy permitted it, what alternatives were rejected, verification result and rollback status. This is operational evidence, not raw hidden reasoning.


#### Host hardening observations

OPS supplies evidence to SAFE for:
- firewall state,
- unexpected listening ports/services,
- patch level,
- Defender/AV/security service state where available,
- secrets/config file permission posture,
- startup/scheduled-task drift,
- dependency/package drift,
- service-account privilege,
- agent version/signature,
- unusual process/network behavior,
- backup/recovery readiness.

Observation does not itself authorize remediation.

#### Performance optimization loop

Use matched measurements before and after tuning:
1. baseline,
2. identify bottleneck,
3. change one controlled variable,
4. repeat the same workload,
5. compare latency, CPU, GPU/VRAM, RAM, disk/network and correctness/personality,
6. retain only changes whose resource/latency benefit does not regress grounding, reliability or safety.

Key workloads:
- idle,
- warm short chat,
- long technical turn,
- memory-heavy retrieval,
- background reflection,
- Discord traffic,
- model load/unload,
- gaming/contention scenario,
- multi-hour/day soak.

#### Acceptance

Do not claim OPS fleet/orchestration support until real acceptance includes:

1. local host telemetry with honest unsupported fields,
2. remote Windows telemetry,
3. remote Linux telemetry,
4. Raspberry Pi-class telemetry including thermal/throttling where available,
5. durable history and restart continuity,
6. detect + challenge + authenticate + auto-enroll a new authorized host without a per-host prompt,
7. proactive one-time notification to Sparks,
8. spoofed/replayed/wrong-network/duplicate/revoked host denial,
9. quarantine/revoke stopping privileged collection/actions,
10. resource profiling under idle/chat/background load,
11. at least one measured optimization with before/after evidence,
12. no arbitrary shell or privilege expansion from read-only enrollment;
13. standing-policy maintenance completes one approved upkeep cycle with before/after verification;
14. planned drain moves all eligible workloads before maintenance;
15. automatic placement chooses a compatible lower-pressure host using measured resources;
16. move a stateless workload and verify target before source retirement;
17. move/checkpoint a stateful workload without duplicate or stale authority;
18. fail an active worker and recover it on an eligible host;
19. prove singleton split-brain prevention during a simulated/real partition condition;
20. refuse incompatible, overcommitted, quarantined and privacy-prohibited targets;
21. evacuate eligible workloads from a quarantined host;
22. prepare a retired host for removal, present the removal packet, refuse final decommissioning without Sparks' explicit approval, then complete credential/routing removal only after approval;
23. move/fail over the primary Sofía runtime in a supervised test while preserving canonical identity and reporting any uncertain state;
24. proactive notifications are useful, deduplicated and do not spam routine telemetry.

A mocked transport or caller-supplied "authenticated=true" flag is not live enrollment or orchestration proof.

#### Fleet control-plane candidate | 2026-09-26

Branch `feature/fleet-tray-remote-controls` makes the Fleet workstream explicit instead of hiding it inside generic OPS status.

Candidate source adds:

- durable per-host foreground-activity state with operator override;
- Game Mode `Auto`, forced gaming protection, and forced normal mode;
- local Windows process evidence for Steam-library games without requiring Steam Web API access;
- an optional explicit game-executable allowlist via `SOFIA_GAME_EXECUTABLES`;
- activity-aware placement where gaming/busy hosts are deprioritized before momentary CPU load for ordinary movable workloads;
- an explicit `allow_interactive_host` workload exception for clients/workloads that belong on the interactive machine;
- the cognition-facing `ops.placement.choose` path using the same durable activity evidence;
- a typed Fleet-agent bootstrap planner that distinguishes already-correct agent, trusted authorized auto-install, ask-Sparks, and reject-out-of-scope outcomes;
- exact package/version/hash verification after any authorized installer runs.

This still does **not** claim unrestricted LAN scanning or arbitrary software deployment. Discovery remains bounded to approved scopes, and installation still requires a trusted bootstrap path plus explicit or standing installation authority.

Live gates still required:

1. discover a real Windows candidate inside an approved scope;
2. discover a real Linux candidate and Raspberry Pi-class candidate;
3. exercise the trusted bootstrap path on at least one disposable/test host;
4. prove an unauthorized/untrusted candidate produces an operator request rather than installation;
5. verify signed/hash-pinned agent material before enrollment;
6. prove Game Mode changes actual placement/migration behavior under measured contention;
7. connect activity-aware placement to real workload execution;
8. connect ACT one-time enrollment/migration/failure notices;
9. connect RUN authoritative runtime movement/fencing and remote-client reconnection;
10. preserve Sparks-only explicit approval for final host decommissioning.


### Merged PKG-ENVIRONMENT detailed readiness contract

### PKG-ENVIRONMENT | shared time, location and environmental context

**Accepted implementation update 2026-09-26. Status:** PR #110 merged the shared PKG-ENVIRONMENT foundation to `main` at `766bf21e0714c8e6b3a21d3f770f633cb4ff8b15`; PR #111 merged the narrow NWS weather/forecast provider plus durable per-machine HOST location at `2b753fdb0b6bccf3449a923fbd48cb5496d1dece`. The accepted system now includes the provider-neutral `EnvironmentSnapshot`, deterministic time/date/location/timezone/season/daylight/weather/forecast/indoor/provenance queries, explicit configured-vs-current USER/SITE/HOST semantics, persistent HOST configuration in `state/machine-locations.json` keyed by stable machine identity, bounded cognition projection, Home Assistant bridge behind `environment.home_assistant.read`, NWS transport pinned to HTTPS `api.weather.gov` behind `environment.nws.read`, runtime composition, and AVATAR consumption. Evidence includes the original **79 focused / 61 touched-regression / 27 provenance-regression** gates, reported green full suites, supervised live Ollama acceptance, later **85 NWS-focused** tests, a supervised live NWS canary against `nws:KGKY`, **96 persistence-focused** tests, and a final reported green full suite. The optional live Home Assistant canary remains pending; general browsing/search and arbitrary geocoding remain outside this acceptance.

PKG-ENVIRONMENT is package **20** in the canonical roadmap. Existing package numbers 1–19 remain unchanged.

#### Ownership boundary

**ENVIRONMENT owns:** one typed, provenance-aware view of external context that other packages may consume:

- current UTC and authoritative runtime observation time,
- user/site-local timezone when explicitly configured or independently evidenced,
- configured/home location and separately modeled current location,
- hemisphere-aware season,
- sunrise/sunset and daylight state,
- current outdoor weather and forecast when a trusted provider is available,
- optional indoor environmental observations from trusted integrations such as Home Assistant,
- freshness/TTL, source, precision, confidence/quality and observation timestamp for every environmental field.

**ENVIRONMENT does not own:**

- network transport or arbitrary HTTP access: **NET** owns transport and network grants,
- Home Assistant/JMRI/service adapters: **INTEGRATE** owns adapters,
- wardrobe or avatar presentation: **AVATAR** consumes environment evidence,
- emotion/personality: **CORE/REL/INTERACT** may use environment as context but weather never deterministically creates an emotion,
- reminders/outreach: **ACT** may consume authorized environment events but ENVIRONMENT does not send messages,
- host lifecycle or polling schedules: **RUN** owns recurring execution/supervision,
- physical sensors/actuators: **BODY** owns Gaia hardware and may publish independently verified sensor observations into ENVIRONMENT,
- privacy/authorization: **SOCIAL/SAFE** scope access to location and environment evidence,
- truth certification: **VERIFY** owns acceptance evidence.

No consumer may bypass ENVIRONMENT by independently inventing, scraping, geolocating or caching its own competing "current weather/location" truth.

#### Canonical model

The implementation should converge on a provider-neutral immutable projection similar to:

```python
EnvironmentSnapshot(
    observed_at=...,
    utc_time=...,
    local_time=...,
    timezone=...,
    location=...,
    season=...,
    daylight=...,
    outdoor_weather=...,
    forecast=...,
    indoor_environment=...,
    provenance=...,
    expires_at=...,
)
```

Each optional field must preserve its own source and observation time. Missing/stale data stays unknown rather than being guessed from memory, IP address, hostname, season stereotypes or model knowledge.

#### Source and trust rules

1. **Clock:** existing runtime clock is the initial authoritative observation source. Host-local time is machine evidence and must not silently become the user's timezone.
2. **Configured location:** an explicit user-approved/home/site location can provide a stable coarse location and timezone anchor. It is configuration, not proof that a person/device is physically there now.
3. **Current location:** only independently evidenced device/GPS/trusted-integration data may be labeled current. IP geolocation is coarse, fallible and never silently upgraded to precise location.
4. **Season/daylight:** derive only from a known location/timezone and date using deterministic rules. Do not infer hemisphere from language or account metadata.
5. **Home Assistant:** an authorized local HA adapter may supply indoor sensors, weather entities, presence/site metadata or outdoor observations through INTEGRATE without granting Sofía general browser/search authority.
6. **Direct weather provider:** remote weather/geocoding APIs require the later separately authorized NET/web capability, explicit destination/tool scope, provider credentials where needed, bounded requests, provenance and revocation.
7. **Memory:** MEM may retain approved stable preferences/configuration and provenance, but stale weather or old location observations must never be projected as current state.

#### Consumer integration matrix

| Consumer | How ENVIRONMENT helps | Boundary |
| --- | --- | --- |
| **CORE** | Current time/location/environment grounding in cognition | Evidence only; no invented current state |
| **INTERACT** | Contextual virtual-lab and conversational reactions | Environment does not imply physical sensing |
| **MEM** | Stable location/preferences and provenance | Current observations expire; no stale-current reuse |
| **SOCIAL** | Person/audience-scoped location/environment access | Precise/private location defaults restricted |
| **NET** | Transport for approved external providers | Connectivity never equals provider authorization |
| **UI** | Optional display of current environment/age/source | UI does not create truth |
| **RUN** | Refresh cadence, expiry and event scheduling | Scheduler does not reinterpret evidence |
| **OPS** | Site/timezone context for fleet nodes | Machine site is not automatically user location |
| **ACT** | Opt-in severe-weather/contextual notices | Quiet/stop/dedupe and recipient scope still apply |
| **REL / emotion** | Time-of-day/season/weather as soft conversational context | No hard-coded “rain = sad” causal rule |
| **AVATAR** | Outfit/presentation choice from time, season, temperature and conditions | AVATAR consumes snapshot; never fetches weather itself |
| **BODY** | Optional trusted physical environmental sensors | Hardware authority remains BODY/SAFE |
| **EVOLVE** | Reviewed environment preferences/config revisions | No self-approved protected location changes |
| **KNOW** | Provider/schema documentation and provenance support | Documentation is not live observation |
| **INTEGRATE** | Home Assistant and future provider adapters | Adapter outputs normalize into ENVIRONMENT |
| **SAFE** | Location privacy, provider secrets, revocation and retention policy | Precise location is sensitive operational data |
| **VERIFY** | Freshness, timezone, privacy, failover and provider-negative tests | No “current” claim without current evidence |

#### Delivery stages

##### ENV-0 | existing clock consolidation

- Keep `runtime_clock_snapshot()` as read-only machine-clock evidence.
- Project clock through one ENVIRONMENT interface rather than letting consumers create independent clocks.
- Preserve the existing rule that host-local time is not automatically the user's timezone.

**Exit:** deterministic tests prove UTC/local instant consistency, timezone awareness and live cognition projection with no guessed user timezone.

##### ENV-1 | location, timezone, season and daylight

- Add typed configured-location and current-location evidence with source/precision metadata.
- Resolve timezone only from explicit/trusted evidence.
- Add deterministic hemisphere-aware season and sunrise/sunset/daylight calculation.
- Keep exact/current location optional and unknown by default.

**Exit:** offline tests cover northern/southern hemispheres, DST transitions, unknown location, stale evidence and configured-home-vs-current-location distinction.

##### ENV-2 | provider abstraction and Home Assistant bridge

- Define provider-neutral weather/environment records.
- Normalize trusted Home Assistant weather/temperature/humidity/site evidence through INTEGRATE.
- Add refresh TTL/error states without treating provider failure as clear weather.

**Exit:** fake/local provider tests prove source identity, freshness, stale fallback labeling and no network authority escalation.

##### ENV-3 | direct weather/forecast provider

A narrow NWS provider route was explicitly authorized by Sparks on 2026-09-26 without opening the general web/search gate and was accepted/merged via PR #111. It is scoped to HTTPS `api.weather.gov` and the explicit standing capability `environment.nws.read`.

- Current station conditions, feels-like, precipitation, wind, humidity and bounded forecast.
- Exact destination/redirect pinning to `api.weather.gov`, required NWS User-Agent, timeout, existing ENVIRONMENT cache TTL and provider attribution.
- Configurable weather target subject: USER, SITE, or HOST, using only explicitly configured coordinates.
- Independent configured HOST/server location so runtime location never overwrites Sparks' USER/home location.
- Preferred persistent HOST configuration is stored in Sofía's machine-location registry keyed by stable machine identity; process-local HOST environment variables remain an explicit override.
- No arbitrary browsing/search capability bundled with the weather client.
- NWS alerts remain a later ACT/ENVIRONMENT extension; this slice does not send proactive alerts.

**Exit:** focused provider/config/query/import tests, full-suite pass, and supervised live NWS canary at a pinned revision; wrong-destination, stale/outage, capability-denial and USER-vs-HOST isolation must fail safely.

##### ENV-4 | shared cognition and package consumers

Project one bounded environment snapshot into cognition when relevant. Wire AVATAR, INTERACT, ACT, RUN, OPS and optional REL/emotion consumers through the shared interface. Keep environment out of unrelated turns when context budget/relevance says it is unnecessary.

**Exit:** supervised real-model tests show correct time/location/weather answers and contextual use without hallucinating unavailable fields or turning weather into fixed emotion/personality behavior.

##### ENV-5 | live acceptance

Verify current environment state across restart, provider outage, timezone/DST change, stale cache, changed configured location, Home Assistant disconnection and any eventual runtime/fleet movement. Environment context must remain source-labeled and must not silently follow a process to another host as if machine location equaled user location.

#### AVATAR / wardrobe contract

Wardrobe and mutable presentation may use:

- time of day,
- season/daylight,
- outdoor temperature/feels-like,
- precipitation/wind,
- indoor environment,
- current activity/context,
- Sofía's modeled presentation preferences and emotions.

Environment is **advisory evidence**, not a mandatory outfit table. Established presentation preferences, audience/privacy, renderer capability and explicit context remain higher-level constraints. Emotion may influence style but neither weather nor emotion owns AVATAR state.

#### Safety and privacy

- Treat precise/current location as sensitive person/site data.
- Keep provider credentials out of model context and logs.
- Do not infer current location from remembered addresses, network ranges or machine names.
- A remote fleet host's timezone/location does not become Sparks' location.
- Public/shared outputs should default to the least precise location needed.
- Expired/stale weather must be labeled stale or unavailable rather than silently reused.
- External weather alerts or proactive messages require ACT policy and recipient/audience checks.

#### Roadmap relationship

ENVIRONMENT may begin **now** with ENV-0/ENV-1 and local provider contracts. It does not change the primary release gate:

**Discord accepted → real OPS/RUN 24/7 acceptance → separately authorized general web/search.**

A trusted local Home Assistant environment source may be used before general web because it is an INTEGRATE capability, not a browser/search grant. Direct internet weather remains separately authorized.

#### Implementation acceptance checklist

- [x] Existing runtime clock consolidated through ENVIRONMENT cognition projection.
- [x] Typed configured/current location with explicit subject, source, coordinates kept out of model context, optional precision, and freshness.
- [x] ZoneInfo user/site time and deterministic hemisphere-aware season/daylight.
- [x] Provider-neutral weather, forecast and indoor observations with TTL/freshness and degraded provider status.
- [x] Explicit Home Assistant entity mapping and unit normalization.
- [x] HA current-location subject is explicit/inherited, never guessed as USER.
- [x] HA observation timestamps are source-backed; missing timestamps never become "now".
- [x] HA environment reads require explicit standing capability plus credentials.
- [x] Provider arbitration prefers fresher/newer evidence instead of registration order.
- [x] Unrelated turns keep the trusted clock but omit detailed environment data and avoid provider refresh.
- [x] Deterministic direct answers cover time/date, user vs runtime location, timezone, weather, forecast, season, daylight/sunrise/sunset, indoor state, and bounded environment-source provenance.
- [x] AVATAR can consume the shared season/current-weather snapshot without fetching weather itself.
- [x] DST, hemisphere/polar daylight, stale/future evidence, provider outage, subject isolation, precision and import-boundary tests are represented in the branch test suite.
- [x] Windows acceptance venv synchronized with `python -m pip install -e .`; `tzdata 2026.4` installed and `ZoneInfo('America/Chicago')` resolved successfully on 2026-09-26.
- [x] Focused ENVIRONMENT gate passed on Windows 2026-09-26: **79 passed in 216.44s** after dependency sync and the import/provider/location/relevance fixes.
- [x] Touched regression gate passed on Windows 2026-09-26: **61 passed in 13.91s** (`runtime_clock`, configuration, cognitive context/assembler, emotional conversation integration, default provider boundary).
- [x] Current-branch full pytest suite passed on Windows 2026-09-26. Exact aggregate count was not captured in chat evidence, so no synthetic count is recorded.
- [x] Post-provenance-repair full pytest suite passed on Windows 2026-09-26. Exact aggregate count was not captured in chat evidence, so no synthetic count is recorded.
- [x] Targeted provenance regression gate passed on Windows 2026-09-26: **27 passed in 242.18s** across environment query/runtime projection/prompt tests after deterministic provenance routing repair.
- [x] Supervised live Ollama gate passed on Windows 2026-09-26: time, configured-vs-current location, season, sunrise, sunset, daylight, unavailable-weather, unrelated-prompt behavior, and deterministic environment-source provenance all behaved as intended. Provenance remained bounded and did not expose coordinates or provider credentials.
- [ ] Live Home Assistant canary only after explicit `environment.home_assistant.read` grant and configured entity IDs.
- [x] Narrow NWS focused Windows gate passed 2026-09-26: **85 passed in 249.58s** across environment config, NWS provider, factory, model, service, Home Assistant, query, prompt, runtime projection and import-boundary tests.
- [x] Post-NWS full repository `pytest -q` suite passed on Windows 2026-09-26. Exact aggregate count was not supplied in chat, so no synthetic total is recorded.
- [x] Initial supervised live NWS canary passed on Windows 2026-09-26 using an explicit temporary HOST override: runtime location answered as configured-not-current, current weather came from `nws:KGKY`, bounded forecast returned NWS periods, and provenance withheld coordinates/credentials.
- [x] Final persistence-focused Windows gate passed 2026-09-26: **96 passed in 257.76s** across durable machine-location registry/CLI/inventory projection, persistent HOST injection, ENV config/NWS/factory/model/service/Home Assistant/query/prompt/runtime projection, and import-boundary tests.
- [x] Final persistence-enabled full repository `pytest -q` suite passed on Windows 2026-09-26. Exact aggregate count was not supplied in chat, so no synthetic total is recorded.
- [ ] General web/search and arbitrary geocoding remain a later separately authorized NET/web stage.

**The accepted PR #110 + PR #111 implementation does not grant general geolocation, browser/search access, background polling, proactive alerts, or arbitrary network authority. PR #111 adds only the separately authorized narrow `api.weather.gov` weather/forecast route when `SOFIA_ENVIRONMENT_NWS_ENABLED` and `environment.nws.read` are both present. Home Assistant remains separately configured/granted.**
> **Governed web + mobile tunnel + NEURO NETWORK checkpoint — 2026-10-06:** Public web research is now a bounded Level-1 capability: explicit turns expose `web.search`/`web.fetch`, public HTTPS is DNS-pinned and revalidated across redirects, SSRF/local destinations and URL credentials are rejected, response type/size is bounded, HTML active content is removed, provider content is marked untrusted, and only receipt metadata/digests are durable. The authenticated Android API can now be exposed through an explicit opt-in, loopback-only Cloudflare named-tunnel supervisor with fixed argv, no token in argv/model/state, bounded restart backoff, durable status and coordinated shutdown. Recent web failures and tunnel degradation feed NEURO as `network` attention; they do not create emotion, select gestures, grant authority or establish truth. Contextual time/daylight/season/weather, grounded emotion, and governed gesture/expression regression coverage remains green. Exact repository evidence: **3,740 passed / 5 skipped / 6 deselected** in the non-integration gate. Live DNS/tunnel credentials, Cloudflare policy and phone canary remain operator acceptance work.
> **DEV bounded software-engineer checkpoint — 2026-10-06:** `dev.build` now explicitly routes a reviewed engineering task to OpenCode in a detached Git worktree. The coding engine can inspect the repository, write only in the exact approved file/directory scope, implement a candidate, run fixed host-owned pytest selectors, receive bounded failure output, and iteratively repair the same candidate for up to five attempts. Candidate evidence retains changed paths, tests, iteration count, outcome and verification-output digest; directory scopes correctly include children while absolute/traversal writes and pytest option injection fail closed. The default OpenCode agent works without a stale repository-local agent definition, while host configuration may select an installed executable/named agent. The live workspace is unchanged during this loop. Apply, rollback, commit and push remain separate exact-approval operations, and protected identity/Constitution/permission authority cannot be self-approved. Exact repository evidence: **3,745 passed / 5 skipped / 6 deselected** in the non-integration gate.
> **Companion and embodiment Phase 4 checkpoint — 2026-10-09:** Canonical conversation now emits one durable principal/audience-scoped expression decision after each settled assistant message, linking intent, text digest, evidence-grounded mixed emotion, bounded voice prosody, reviewed gesture/pose, and the exact AVATAR presentation revision. Text persistence, TTS, and Tk avatar rendering produce independent receipts; queued output is never reported as spoken or rendered. The optional desktop renderer visibly projects canonical appearance/wardrobe with face, gaze, ears, tail, posture, poses, quiet idle stance, animation cancellation, and renderer acknowledgement. Persisted Voice settings control opt-in TTS, push-to-talk input, mute, installed voice hint, and microphone device selection. Input remains disabled by default, stores content-minimal receipts, supports cancellation, and interrupts active speech for barge-in; text remains authoritative through all audio/renderer failures. Windows SAPI/System.Speech and visible Tk execution remain live-host acceptance, documented in `docs/development/companion-v0.1.md`, and are not claimed by Linux CI.
> **Digital World, Fleet, and Creation Infrastructure Phase 5 checkpoint — 2026-10-10:** The canonical application now owns a reviewed Windows/Linux dependency registry, per-host lifecycle evidence, signed-artifact install/update/repair/rollback contracts, bounded verified offline cache, and no-network recovery paths. Existing Fleet discovery remains candidate-only and exact approval remains mandatory before enrollment or trust. Linux gains a hash-pinned atomic-release/systemd bootstrap and rollback workflow alongside the existing Windows CIM/X.509 path. The canonical `sofia.db` now stores a scalable multi-space world with three initial spaces, revisioned objects, transforms, containers, groups, connections, archive/restore, undo, imports, lazy scene pages, and exact scene-linked interaction receipts; large creative bytes remain hash-addressed in managed external storage. Evidence-backed Sofía/Sparks/shared preferences influence only already-eligible wardrobe and decorating choices, while recipient-controlled nickname proposals never change identity. Native authoring adapters create validated text, story, SVG art, OBJ, animation, WAV music, game, and simulation artifacts; code artifacts require governed DEV candidate receipts. Settings exposes all canonical inventories and histories. Real clean-host Windows/Linux provisioning, live service integrations, and visible object rendering remain separately documented host acceptance and are not claimed from Linux CI.
> **Independent Life and Project Forge Phase 6 checkpoint — 2026-10-10:** The canonical application now owns one `SelfDirectedLifeCoordinator` over GOALS, RUN, SAFE capabilities, Phase 5 creative/world stores, preferences, nicknames, ACT, and the configured `sofia.db`. Evidence-grounded interests can receive at most one bounded, tool-free model project suggestion per UTC day; deterministic host policy alone may create a private scoped SELF goal and activate it. Project work proceeds through `GoalActionProposal`, existing capability authorization, a durable RUN job, and an exact one-use database-backed execution grant, so direct or replayed tool calls cannot bypass the project lifecycle. Real managed artifacts retain hashes, revisions, tool identity, tests, ownership, and evidence. Technical validity and Sofía's subjective judgment remain independent: she may dislike, revise, preserve, pause, reject, abandon, archive, revive, or simply decline optional work without manufactured emotion or replacement-task pressure. User assignments and operational duties cannot be silently abandoned. Private experiences, changing interests, favorites, traditions, recipient-controlled nicknames, project spaces, and deliberate ACT sharing reuse their existing authorities. The final candidate gate passed **4,019 tests / 5 skipped / 6 deselected**, dependency integrity was green, and semantic verification had zero findings. Remaining real-model, renderer, channel, OS-isolation, multi-host HA/DR, Gaia, and JMRI acceptance boundaries are documented in `docs/development/phase6-independent-life.md`; none of those host-only behaviors are claimed from Linux CI.
