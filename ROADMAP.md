# Sofía Ada Lyra: 13-package delivery roadmap

**Planning revision:** 2026-09-21 (America/Chicago). **Current INTERACT branch:** `feature/pkg-interact-shared-engine`; [draft PR #2](https://github.com/Crazysodaman/SofiaAdaLyra/pull/2) is unmerged. **Separate CORE/Artemis branch:** `feature/g22-live-integration-artemis`; [draft PR #1](https://github.com/Crazysodaman/SofiaAdaLyra/pull/1) requires independent review. This is the 13-package roster. The [longer historical root roadmap](https://github.com/Crazysodaman/SofiaAdaLyra/blob/0a5769a030e036f53776d689ff13b06d448de0f0/ROADMAP.md) and [`ROADMAP-EXTENSION.md`](ROADMAP-EXTENSION.md) remain available. The detailed and current [INTERACT I1–I16 tracker](docs/development/pkg-interact-roadmap.md) now includes [Discord private-DM milestones D0–D4](docs/development/pkg-interact-discord-channel-contract.md).

> **Core invariant:** Sofía's identity, Constitution, represented embodiment, evidence, memory, authority and capabilities persist independently of replaceable models, computers, processes, Discord, CLI, voices and avatars. A model message is not proof of sensor input, tool execution, consent or delivery. Authentication never by itself grants authorization.

## Delivery order and verified status

**CORE** remains separately gated. Earlier full Windows and supervised personality/identity acceptance are not established as complete here. Do not merge CORE/Artemis PR #1 as part of INTERACT.

**INTERACT** is an active, partial candidate. At `23fe17d`, Sparks reported **26 focused tests passed in 6.59 s and 274 coordinated interaction/application tests passed in 93.68 s** on Windows, following an A/B-probe ambiguity repair. At `412dc32`, an earlier supervised real CLI test **failed natural conversational quality**, despite 264 passing automated tests. The newest live-quality repair still needs Ollama A/B comparison, a fresh supervised real-model session and a full-suite/security/privacy review. Tests at different SHAs are not additive; later documentation commits are not new behavioral verification. [Exact evidence and runnable PowerShell gates](docs/development/pkg-interact-roadmap.md).

**Discord DM channel is planned, not enabled.** Under INTERACT/ACT/UI/SAFE/VERIFY, start with enrolled-account reply-only private DMs connected to the **same Sofía runtime**, not a second personality. Later, separately opt in to bounded, evidence-backed Sofía-originated DMs with quiet hours, caps, cancellation, cross-client stop, verified transport receipts and privacy controls. No token, bot, listener or background sender is installed by the roadmap update. [D0–D4 implementation and acceptance contract](docs/development/pkg-interact-discord-channel-contract.md). Stabilize the failed CLI personality gate before deploying another conversation surface.

**MEM** is the next top-level package following an accepted INTERACT release. SAFE and VERIFY are continuing gates, not permission to erase state. NET read-only/auth architecture and CLEAN scoped inventory can progress independently. ACT goals/outbound work, DEV execution, remote NET actions, external screen access and BODY motor movement each need their own explicit authority and verified executors; EVOLVE requires protected amendment procedures.

## Thirteen-package dashboard

| Package | Outcome | Evidence-based status / next gate |
| --- | --- | --- |
| **PKG-CORE: cognition and continuity** | Grounded identity, persona, startup and restart awareness | Foundations exist; independent supervised/full review remains open. Keep PR #1 separate. |
| **PKG-INTERACT: text, avatar and screen interactions** | Shared canonical human/fox semantics, virtual lab, evidence-linked and evolving responses | Candidate I1–I16 partial; **274 Windows coordinated tests at `23fe17d`**, live-quality retest pending. [Detailed tracker](docs/development/pkg-interact-roadmap.md). |
| **PKG-MEM: memory and learning** | Original messages, provenance, retrieval, correction, reviewed preferences | Follows accepted INTERACT; existing stores are foundations. |
| **PKG-NET: distributed homelab** | Authenticated, scoped multi-machine observation/operations | Peer/grant/replay foundations; real Artemis transport and acceptance outstanding. |
| **PKG-ACT: goals and initiative** | Reviewable goals, running-only workers, opt-in delivery | Proposal and queue-only outbox foundations; no autonomous Discord sender or real message delivery. |
| **PKG-DEV: self-improvement and engineering** | Authorized OpenCode proposal/execution/rollback | CLI/analyzers are foundations; runtime execution and recovery unverified. |
| **PKG-REL: social continuity** | Evidence-linked, nuanced emotional context and correction | Profile and journal exist; meaningful live quality and evidence-backed learning incomplete. |
| **PKG-UI: voice, avatar and clients** | Authenticated interfaces and real output acknowledgments | Headless expression planner; real speech/avatar absent. [Discord private-DM adapter D0–D4 planned](docs/development/pkg-interact-discord-channel-contract.md). |
| **PKG-BODY: robotics and embodiment** | Authorized Gaia sensing/motion with independent safety | Separate hardware project; no verified Sofía-to-robot actuation. |
| **PKG-SAFE: security and recovery** | Authorization, audit, privacy, revocation, backup/restore | Foundations only; enforce cross-client stop, Discord enrollment and secret safety before deployment. |
| **PKG-EVOLVE: controlled evolution** | Reviewed changes with protected identity/Constitution | Integrity foundations; no silent protected amendments. |
| **PKG-VERIFY: integration and operations** | Negative, security, real-model, deployment and performance tests | Current focused tests pass; live-quality/full-suite and future real Discord DM proof pending. |
| **PKG-CLEAN: maintenance** | Behavior/data-preserving technical debt work | Inventory and scoped regressions required before destructive changes. |

## PKG-INTERACT contracts and ownership

The current code includes a canonical represented body and headless text gestures, synthetic lab fixture (not a real sensor), persistent software lab and read-only observations, source-linked ledger and replay protection, per-session stop/resume, bounded grammar and hypothetical handling. Expanded registry, preference/boundary revision storage, expression planning and Sofía-initiated proposal foundations are **partially integrated**, not end-to-end accepted. No canonical anatomical region is automatically accepted or banned; classification does not imply approval, physical feeling, animation or permission. Stop and sourced boundaries outrank model prose and inferred emotions.

The `412dc32` real-model review showed repeated generic gesture replies, weak offer-vs-contact distinction, unsupported earlier-history wording and generic Windows service advice. A later repair avoids auto-assigning Sofía's feelings to user pats, filters identifiable legacy auto-appraisals *from model projections only* and provides a synthetic A/B model probe. These changes have **not** yet passed a new supervised live-quality review. [Live CLI failure evidence](docs/development/pkg-interact-live-cli-review.md), [repair candidate](docs/development/pkg-interact-live-quality-repair.md), [I8–I16 implementation limits](docs/development/pkg-interact-i8-i16-integration-checkpoint.md), [full design](docs/development/pkg-interact-complete-embodiment-and-agency-contract.md).

**Discord ownership:** INTERACT handles shared conversation and represented interaction; ACT handles reviewed goals and opt-in outbox; UI owns the Discord adapter and provider receipts; SAFE authenticates the enrolled account, protects the token and enforces stop/privacy; MEM/REL own source-scoped continuity; VERIFY tests fake and supervised real DM failure cases. Discord messages grant no filesystem, screen, robot or external-tool authority. Queue is not send; platform accepted is not read. A process that is shut down must never claim it kept thinking or messaging. [Full Discord contract](docs/development/pkg-interact-discord-channel-contract.md).

## Next checkpoint: Windows and Ollama

With the CLI closed, preserve the modified local `state/sofia.db`, `test/test_ollama_generation_contract.py`, and the untracked pre-interaction backup. Confirm branch/commit, then fast-forward pull; **do not reset or stash blindly**:

```powershell
git branch --show-current
git status --short
git pull --ff-only origin feature/pkg-interact-shared-engine
if ($LASTEXITCODE -ne 0) { throw "Pull failed; preserve local changes." }
git log -1 --oneline
```

**Already passed at `23fe17d`:** focused 26-test and coordinated 274-test Windows gates. **Next experiment:** `python -m sofia.interaction.ab_probe` with Ollama available; this uses synthetic inputs and a static context comparison, *not the exact historical live prompt*. Analyze actual A/B responses, repair only a diagnosed layer, and repeat targeted/current-SHA tests for any behavior-changing commit. Then repeat a supervised separate-turn `python -m sofia` review. Only after naturalness, truthfulness and stop behavior pass, run `python -m pytest -q`, inspect the full PR/security/privacy/migration behavior against copies, and obtain **separate explicit merge approval**. PR #2 remains draft; other branches and the configured production database/backup are unaffected by this roadmap update.

**Open choices:** real voice/avatar and authenticated screen, latency targets, scoped sensitive-data retention, Discord bot permissions and deployment host, optional outbox delivery policies, Artemis transport, OpenCode execution rights, Gaia emergency stop and protected amendment design. A planning document is not an implementation or grant of permission.
