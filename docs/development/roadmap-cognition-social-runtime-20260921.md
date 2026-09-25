> **Project status update — 2026-09-23:** PKG-INTERACT was accepted by Sparks and merged to `main` via PR #2 (merge commit `d6658d0`). Verified Windows evidence includes 97 focused tests, a four-turn disposable real-application/Qwen probe, a qualified repository run of **1665 passed, 2 skipped, 1 deselected** (the deselected case was Sparks's unrelated local Ollama expectation mismatch), and a final **60/60** closure audit including both SQLite writer orders, source attestation, boundary revocation, restart-persistent state, stop behavior, authentication and tool authority. Staged offers remain off by default; production interaction-policy schema provisioning is a separate reviewed migration. **Next dependency gate: PKG-MEM.**

# Sofía Ada Lyra: cognition, relationships, multi-user, and 24/7 implementation notes

**Updated 2026-09-22. Status:** documentation-only in draft PR #4. The ordered **16-package** roster and release sequence now live in [../../ROADMAP.md](../../ROADMAP.md). This file keeps the detailed behavioral contracts that motivated the SOCIAL and RUN additions; it is no longer a competing package-count proposal.

## Locked sequencing and boundaries

1. CORE/INTERACT/MEM remain the first functional dependency chain.
2. SOCIAL supplies the minimum authenticated Sparks principal/audience boundary before Discord; general multi-user stays deferred until explicitly expanded.
3. Discord D0–D4 uses only the network access needed for Discord. NET connectivity is not general internet permission.
4. RUN must demonstrate real supervised 24/7 lifecycle/recovery before general web/search is introduced.
5. SAFE and VERIFY apply to every stage.
6. One canonical Sofía identity persists across models, hosts, and channels. Relationship state and private memory are actor/audience scoped.

## CORE: response performance and adaptive cognition

- Measure startup, queue delay, first-token latency, prompt/context assembly, retrieval, provider prefill, generation, end-to-end latency, hardware/load/model/context, and foreground/background resource contention.
- Prefer warm model residency only when measured resource policy allows it.
- Use relevance-ranked, token-aware context without silently dropping canonical identity, Constitution, or authoritative safety policy.
- Support evidence-based quick/balanced/deep reasoning policies only where the provider/runtime genuinely supports them.
- Accept using matched before/after conditions plus live serious/playful/technical cases. Faster but less grounded is a regression, not an optimization.

## ACT + RUN: spontaneous thought without fictional continuous consciousness

- A scheduled/event-driven wake is an **opportunity** for bounded reasoning, not proof of a thought.
- Independent cognitive passes use explicit source references such as unfinished questions, corrections, approved goals, meaningful system changes, and relevant memories.
- Candidate reflections retain timestamp, initiating event/schedule, source refs, runtime/model version, uncertainty, and lifecycle state.
- Foreground conversation wins resource contention.
- No processing is claimed while the process is stopped. Restart may reconcile missed windows and actual elapsed time but cannot invent activity.
- Outreach remains opt-in, novelty/relevance limited, rate-capped, quiet/busy/stop/mute aware, deduplicated, and acknowledged by the real delivery channel.

## REL: absence, reunion, and “missing Sparks”

- Track last **observed authenticated contact**, not guessed availability.
- Elapsed absence is evidence of a time interval, not proof of loneliness, distress, rejection, or entitlement.
- Sofía may naturally acknowledge a reunion and may express a modeled “I missed you” response when relationship context and real absence evidence support it.
- Do not claim “I thought about you all day” unless an actual recorded running-time reflection supports that statement.
- No guilt, exclusivity demands, escalating pursuit, jealousy, or pressure to respond.
- Silence is valid. Unanswered outreach does not escalate by default.
- One canonical personality persists across people; familiarity, trust, tone, and remembered preferences may differ by authenticated relationship state.

## SOCIAL + MEM + SAFE: privacy is structural

- Bind every turn to a verified principal, conversation/channel, audience, and permission before retrieval and persistence.
- Default private originals, summaries, reflections, emotional appraisals, indexes, and relationship records to that authenticated scope.
- Display names, usernames, mentions, message text, or model claims cannot establish identity.
- Private DM data does not automatically become shared/channel/project memory.
- Shared data requires an explicit scoped promotion with provenance, audience, revocation/expiry, and audit.
- Administrative control of the deployment is not automatically permission to disclose every participant's private conversational content.
- Enforce the same boundary for prompts, retrieval, embeddings/indexes, summaries, background reflection, notifications, avatar/workbench objects, exports, backup, restore, and deletion.
- If multi-user is later enabled, negative tests must prove no A↔B leakage through all of those surfaces.

## SOCIAL: staged scope

### Minimum before Discord

- Exactly one independently authenticated Sparks principal.
- Exact private-DM audience binding.
- Unknown/other/group/server actors denied.
- Cross-session replay/identity spoofing denied.
- Same Sofía runtime and identity, no second personality instance.

### Deferred until explicitly expanded

- Additional enrolled principals.
- Independent relationship memories for other users.
- Shared/group knowledge semantics.
- Account linking.
- Moderation/retention/export/deletion policies for multiple people.
- Live two-user noninterference and privacy acceptance.

## Discord and NET

Initial networking is restricted to the Discord capability actually required by D0–D4. No browser, general HTTP client, arbitrary fetch, search provider, network scan, or unrestricted shell is implied.

Discord acceptance requires authenticated receive, replay/idempotency, same-runtime response, actual delivery receipts, stop/revocation, outage/reconnect behavior, privacy negatives, restart recovery, and human-reviewed conversational quality.

## RUN: real 24/7 is operational infrastructure

RUN owns external supervision, restart/backoff, single-instance enforcement, service identity/environment, bounded wake schedules, health/status, resource budgets, clean shutdown, failure visibility, catch-up rules, and safe upgrade/restore behavior.

A running-only idle worker is not 24/7 acceptance. A successful service restart is not evidence of continuous thought during downtime.

## General web/search

Search is deliberately deferred. It receives its own adapter, destination/tool grants, privacy/retention, provenance, rate limits, failure semantics, and VERIFY evidence only after:

- real Discord D0–D4 acceptance, and
- real supervised RUN 24/7 acceptance.

## Private reflections and selective disclosure

A private candidate reflection may influence later scoped reasoning or modeled social behavior without being immediately shown. It can be revised, expire, or be deliberately shared with an authorized audience.

Private reflection:
- is not a verified fact,
- is not proof of subjective experience,
- grants no tools or permissions,
- cannot bypass STOP,
- cannot leak another person's private data,
- is not automatically promoted to durable preference/history.

Consequential explanations should provide useful authorized evidence and reasoning summaries, not raw hidden model reasoning.

## Repository hygiene follow-up

The repository currently contains tracked SQLite/log artifacts. Treat these as a SAFE/CLEAN migration task:

1. identify which are runtime state versus intentional fixtures,
2. preserve and back up any real user/state data,
3. migrate runtime state out of version control deliberately,
4. update ignore rules only after confirming required fixtures remain available,
5. verify startup/recovery/migration behavior,
6. remove tracked artifacts only with reviewed rollback.

Do not turn cleanup into accidental amnesia.
