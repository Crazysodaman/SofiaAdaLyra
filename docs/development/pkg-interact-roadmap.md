> **Closure update — 2026-09-23:** PKG-INTERACT was accepted by Sparks and merged to `main` via PR #2 (merge commit `d6658d0`). Final verified Windows evidence: **97 focused tests**, a four-turn disposable real-application/Qwen probe, **1665 passed / 2 skipped / 1 deselected** in the qualified repository run (the deselected case was Sparks's unrelated local Ollama expectation mismatch), and a final **60/60 closure audit** including both SQLite writer orders, source attestation, revocation, restart-persistent interaction state, stop behavior, authentication and tool authority. Staged offers remain off by default; production interaction-policy schema provisioning is a separate reviewed migration. The active dependency gate is now **PKG-MEM**.

# PKG-INTERACT: completed implementation and acceptance record

**Closed:** 2026-09-23 (America/Chicago). **Merged:** [PR #2](https://github.com/Crazysodaman/SofiaAdaLyra/pull/2) into `main` at merge commit `d6658d0`. This is the detailed tracker for the 13-package [project roadmap](../../ROADMAP.md); the initial fuller version remains available in Git history. The [complete embodiment/agency contract](pkg-interact-complete-embodiment-and-agency-contract.md) is a *target*, not a statement that every feature is running. **New:** [Discord DM channel contract and D0–D4 delivery milestones](pkg-interact-discord-channel-contract.md).

## Revision-specific evidence

| Revision | Actual reported result | Scope / limitations |
| --- | --- | --- |
| `7175835` / `84695a6` / `eb73357` / `02a5a25` | Earlier focused reports: 59 / 44 / 20 / 116 passes | Distinct revisions and slices; not current combined acceptance. |
| `a8fb5c8` | 3 import-order and 143 coordinated checks passed | Subsequent real-model CLI review **failed**. |
| `52a5d44` | 11 Windows stop/repetition regressions passed in 2.24 s | Targeted, not full suite or live quality. |
| `0a5769a` | 28 Windows standalone registry/temporal/expression/initiative tests passed in 3.38 s | Standalone foundations, not live I8–I16 acceptance. |
| `f3cf992` | 112 passed before first hypothetical-prompt assertion failed | Fixed at `412dc32`. |
| `412dc32` | 28 focused passed in 3.44 s; **264 coordinated interaction/application passed in 87.92 s** on Windows | Supervised CLI subsequently **FAILED conversational quality** despite correct stop/resume and compound nonexecution text. |
| `682fb79` | Focused test run stopped at 5 passed, 1 failed; coordinated stopped at same newly introduced A/B-probe error | Probe wrongly demanded accepted status for ambiguous `*pats your ear*`. This is not evidence that the personality repair worked. |
| **`23fe17d`** | **26 focused passed in 6.59 s; 274 coordinated interaction/application passed in 93.68 s** on Sparks's Windows PowerShell after successful fast-forward | Ambiguity-preserving A/B probe repair and live-quality *candidate* pass current focused gates. **Ollama A/B, fresh supervised CLI, full `pytest -q`, and merge acceptance remain unreported.** |

Test counts from different revisions are **not additive**. Later documentation-only commits do not constitute fresh behavioral test evidence. Preserve the modified local `state/sofia.db`, user's modified `test/test_ollama_generation_contract.py`, and the untracked timestamped pre-interaction SQLite backup; never reset or stash them blindly. Tests use isolated temporary DBs.

## I1–I16 milestone tracker

| Slice | Deliverable | Evidence-based state / next gate |
| --- | --- | --- |
| **I1** | Shared headless human/fox semantics and source/actor distinctions | Candidate; current coordinated regression green at `23fe17d`; real-model review still open. |
| **I2** | Synthetic virtual hit-test fixture, clearly distinct from authenticated renderer | Candidate; prove fixtures cannot forge sensing or mutate production. |
| **I3** | Persistent virtual-lab software world | Candidate; independent transitions and restart review outstanding. |
| **I4** | Read-only virtual-world observation | Candidate; no invented tool action or offline activity. |
| **I5** | Saved-message-linked gesture evidence, replay, contextual regions | Candidate; recognition is never consent, sensation or animation. |
| **I6** | Durable per-session exact stop/resume, blocked contact | Candidate and targeted tests; live text stops worked at `412dc32`; **cross-client/global enforcement not built**. |
| **I7** | Conservative single-action parser, hypotheticals, compounds, contextual dialogue | Regression green; **live personality/variety/grounding failed**. Unspecified `ear` is ambiguous, not a license to guess. |
| **I8** | Versioned anatomy, laterality, colloquial aliases | Expanded registry and partial live grammar wired; need full alias/laterality coverage and migration compatibility. |
| **I9** | Gestures vs social actions, actor/target, offer vs description, phases, atomic compound semantics | Partial reviewed single-action grammar and live CLI projection; never claim offered hugs as completed. |
| **I10** | Source-checked, append-only preference/boundary revisions and enforceable reconstruction | Partial journal + live pre-model checks; atomic ledger enforcement, authentication, restart/replay and DB-copy migration outstanding. |
| **I11** | Natural, context-dependent and non-repetitive dialogue | **FAILED supervised CLI at `412dc32`**; no automatically assigned emotions from pats in current repair candidate; Ollama A/B and fresh live review required. |
| **I12** | Same semantics across text, virtual lab and future authenticated avatar | Headless foundation only; real adapter and renderer acknowledgments absent. |
| **I13** | Independent laughter/crying/facial/ear/tail/silent expression lifecycle | Registry and expression planner; no actual audio or avatar output/acknowledgment. |
| **I14** | Mixed emotional context, changing positive/negative/uncertain preferences | Extended modeled labels and explicit storage; automatic evidence-backed promotion and reliable live reactions incomplete. |
| **I15** | Sofía-originated offers, bounded own goals, running-only worker and optional delivery | Proposal gate + queue-only goals/outbox; no autonomous outreach, presence or send transport. **Discord D0–D4** is a planned delivery channel, not an installed feature. |
| **I16** | Cross-client stop, source authentication, privacy/retention, recovery and end-to-end verification | Partially implemented controls; Discord DM enrollment/revocation and real delivery tests are additional acceptance obligations. |

**Dependencies:** finish current I11 live-quality diagnosis/acceptance before broadening to Discord or launching a worker. Stabilize shared identity, evidence and stop across I8–I12; expression/active emotion need evidence-safe projections; initiative and delivery require ACT and SAFE authorization; all migrations and failure recovery require VERIFY. The independent packages remain separately reviewable.

## Discord: private DMs without a second Sofía

[Full design, security boundaries and D0–D4 acceptance](pkg-interact-discord-channel-contract.md). Discord is **roadmap-only**. Start with *reply-only, enrolled-account private DMs* routed to the **same runtime and conversation/memory/authorization system** as CLI. Never deploy a second independently minded Sofía or interpret a Discord account name as authentication. Protect bot credentials in a secret store/environment rather than Git; reject non-enrolled users and server-wide monitoring by default.

- **D0:** Explicit bot/account/destination enrollment, secret handling and host selection; no bot activation as a side effect of docs/tests.
- **D1:** Two-way private DM adapter with idempotent incoming events, shared source-linked conversation and verified send outcomes; CLI still works when Discord is disconnected.
- **D2:** Cross-client stop/revocation, privacy and retention, restart/reconnect handling and strict message/tool authorization. An inbound DM cannot grant filesystem, avatar or robotics authority.
- **D3:** Separately opted-in Sofía-initiated DMs through ACT's running-only goal/outbox worker: consent by destination and type, quiet hours, caps, cancellation, expiry, retries and actual delivery receipts. Queue != sent != read. No inferred user presence from silence or fabricated work while offline.
- **D4:** Fake-gateway negative tests and supervised enrolled-account real DM checks, Discord outage/rate-limit/duplicate/unauthorized-user scenarios, isolated DB migration/recovery, privacy and deployment approval.

INTERACT owns conversation/gesture semantics; ACT owns goal selection and sender scheduling; UI owns Discord adapter; SAFE owns enrollment, scoped permission and cross-client revocation; MEM/REL own context continuity; VERIFY owns fault and real-DM acceptance. Choose an always-on Eos/Artemis deployment host only after reviewing actual resources and networking. Use an official bot, not a personal-account self-bot. This plan does **not** install an app, request a Discord token, start a worker, authorize proactive messages or merge code.

## Next Windows PowerShell gate

**Completed on `23fe17d`:** focused 26-pass and coordinated 274-pass results, confirmed after fast-forward. Do not repeat simply to accumulate test counts. With Sofía's CLI closed, first inspect branch, HEAD and the local edits, and pull the documentation-only roadmap commit as a fast-forward without discarding them:

```powershell
git branch --show-current
git status --short
git pull --ff-only origin feature/pkg-interact-shared-engine
if ($LASTEXITCODE -ne 0) { throw "Pull failed; keep local changes." }
git log -1 --oneline
```

**Next behavioral experiment, with Ollama available:**

```powershell
python -m sofia.interaction.ab_probe
```

This A/B uses synthetic inputs and the same configured Ollama model for short-profile versus *static* assembled-context prompts. It does not access the production SQLite DB, reproduce historical dialogue or prove the live context was assembled correctly. Compare ear ambiguity, offered hug, hypothetical grounding and direct Windows-service troubleshooting. Share both variants' actual responses. If the probe reveals a defect, repair the specific layer and rerun the focused/coordinated tests at the new SHA.

**Then supervised fresh `python -m sofia`:** separate ear/hand pats, offered and described hug, exact stop, blocked head pat and hug, exact resume, new head pat, tail/chest hypothetical, one compound gesture, technical Windows service diagnosis. Review natural voice and concise nonrepetition as well as ledger-truthful safety. If necessary, inspect effective personality/context/provider with a redacted *read-only* diagnostic. Do not infer ledger completion from text alone.

**Closure:** live acceptance and the bounded migration/security review were completed for the package scope, followed by explicit Sparks merge approval. PR #2 is merged. The unrelated local Ollama test expectation mismatch was not committed, and production interaction-policy schema provisioning remains a separate future migration. Independent package PRs remain separate.

## Invariants and supporting documents

Classification is neither consent, character enjoyment, subjective sensation, external action nor rendered animation; no canonical body region is inherently welcomed or banned. Explicit stop and boundaries outrank modeled emotions. Repetition/time do not grant permission or imply a preference. Saved originals and source IDs are retained; privacy-sensitive context requires scope and retention controls. A model's prose never proves tool execution or delivery. Running-only optional work cannot imply activity during shutdown. An absent avatar or Discord bot must not prevent ordinary CLI text conversation.

Supporting documents: [live CLI failures](pkg-interact-live-cli-review.md), [repair candidate](pkg-interact-live-quality-repair.md), [ear A/B regression](pkg-interact-ab-probe-ear-regression.md), [I8–I16 implementation limits](pkg-interact-i8-i16-integration-checkpoint.md), [I5–I7 acceptance](pkg-interact-i5-i7-acceptance.md), [component evidence](pkg-interact-i8-i10-code-status.md), [I8–I12 contract](pkg-interact-i8-i12-expansion-contract.md), [complete embodiment/agency contract](pkg-interact-complete-embodiment-and-agency-contract.md), [initiative/idle contract](pkg-interact-initiative-and-idle-contract.md), [Discord D0–D4 contract](pkg-interact-discord-channel-contract.md).
