# Sofía 2.0 — Platform Federation and Autonomous Inter-Core Relationships V1

**Owner decision:** Approved architecture and acceptance contract, 2026-10-24 (America/Chicago).
**Status:** DESIGN ONLY. No claim of implemented peer messaging, peer emotional autonomy, cross-platform state exchange, end-to-end tests, deployed networking or production readiness.
**Work ownership:** PLAT-03 (trust, SAFE, privacy), PLAT-04 (durable inbox/outbox, RUN/ACT), PLAT-07 (Fleet connectivity/discovery), PLAT-08 (readiness, diagnostics and certification), Platform canonical state; existing Core relationship/impressions, emotion, memory, cognitive choice, CORE-11/15/17/18/23/24/25/27/30, and the existing Component Updates + Unified SDK family.
**Related documents:** [Architecture](ARCHITECTURE.md), [Platform and Module Catalog](PLATFORM_AND_MODULE_CATALOG_V1.md), [Component Updates and Unified SDK](COMPONENT_UPDATES_AND_UNIFIED_SDK_V1.md), [Hardware-Neutral Fleet](HARDWARE_NEUTRAL_FLEET_AND_INFERENCE_CONTRACT_V1.md), [Core 1.0 Plan](CORE_1_0_PLAN.md).

## 1. Scope and identity decisions

Two or more independently installed, enrolled, trusted Sofía-compatible **Platform instances** may exchange bounded, mutually authenticated, authorized messages, consented data offers, approved collaboration proposals, acknowledgments, and exact-result receipts.

Two **distinct active Core identities** may each decide whether to communicate, what they want to share within approved boundaries, how they regard one another, and whether and how deeply to cooperate. The relationship belongs **to each Core**, not to the network transport. Their impressions need not agree, become friendly or converge. Core A can respect Core B's engineering but distrust its confidentiality; Core B can appreciate A yet decline a shared project. A Core can like someone while refusing to disclose private data, or dislike someone while accepting a small verified technical fact.

A Platform may have no Core and merely host approved remote modules/workers; this is existing Fleet worker behavior, not another interacting persona.

**Absolutely distinct identities and writer lineage:** Each independent Core has a separately issued canonical Core identity, protected durable state lineage, and one active canonical writer/generation for that identity. A second Platform claiming the **same** Sofía identity may be a non-acting standby, read-only projection or separately authorized future successor, but never an independently writing duplicate Core. A supervised cloned/forked *distinct* Core identity requires owner approval, separate lineage and an honest provenance relationship. Federation is **not** automatic cloning, state merging, writer election or silent failover.

**Existing roadmap:** Core codebase awareness, supervised update, verified self-update and autonomous improvement are already tracked by CORE-35/36/37/38, DEV/EVOLVE/Workshop, B07 and component isolation ISO-01–08. Do **not** create duplicate "changeable Core" features or reorder them merely because Federation is added.

## 2. Layers, and who may decide what

| Layer | Owns and is allowed to decide | Never owns or infers |
| --- | --- | --- |
| **Core A (subjective relationship)** | its own goals, curiosity, modeled emotional appraisals, perspectives, subject-specific interpersonal trust, willingness to interact, boundaries, *eligible* share proposal, whether to reply/decline, whether to cooperate and how to express its view | other Core's private state, a human's consent, authenticated identity, cryptographic trust, final external data disclosure or execution permissions |
| **Platform A (hard external boundary)** | peer enrollment/identity, per-direction consent policy, allowed recipient + audience, permitted data classes, redact/filter, network transport, canonical persistence, RUN/ACT, limits and receipts | why Core A likes/trusts Core B, what emotional state A should experience, compulsory relationship repair or forced friendship |
| **Platform B (receiving boundary)** | authenticated receipt, inbound scope, quarantine, classify provenance and untrusted text, optional accepted data artifacts, dedupe and delivery to permitted local Core | direct edits to Core B's feelings, beliefs, autobiographical memory or permissions |
| **Core B (independent cognition)** | if/how to respond, what to believe about A's claims, emotional response, personal relationship learning, choice of collaboration and its own boundaries | sender's private data or authority, blanket trust based on mTLS or emotional affinity |

**Two separate trust dimensions, never merged:**
1. **Platform security trust:** externally verifiable enrollment, certificate validity, exact principal/audience, grants, policy and provenance. Pass/fail/unknown for concrete operations. Not influenced by Core feelings.
2. **Core interpersonal trust:** evidence-based, revisable interpretation of peer honesty, respect, reliability, competence, goodwill, privacy care, boundary respect and consistency. Domain-specific and not itself a permission grant.

A Core's own preferences may narrow what it volunteers **within** the externally permitted envelope, but they may never widen what Platform permits. Even a strong bond does not grant API keys, database reads, protected records, tool execution or deployment rights.

## 3. Technical identities, admission and per-direction trust

Identity fields must distinguish:
- \`platform_instance_id\`: stable authenticated enrolled instance, independent of machine name, OS, VM, display label and physical host;
- \`core_identity_id\`: stable independent persona identity, distinct from currently serving process or LLM model;
- \`core_generation\`: Platform-fenced active worker/process revision for that identity;
- \`state_lineage_id\`, \`writer_epoch\`: protected writer authority per identity, never established by peer gossip;
- \`principal_id\`, \`audience_id\`, \`scope\`: independently authenticated human/agent and data disclosure contexts;
- \`endpoint_id\`, \`certificate/key epoch\`: trusted transport binding and revocation controls;
- \`message_id\`, \`thread_id\`, \`correlation_id\`, \`idempotency_key\`: bounded durable exchange identity.

Peer admission uses reviewed **mutual TLS, pinned keys/verified trust roots**, exact version/capability negotiation, revocable authorization, endpoint policy, anti-replay, rate limits and explicit per-direction consent. Discovery does not enroll a host; mTLS alone does not authorize private data sharing or command execution.

Reuse the existing \`src/sofia/platform/distributed/\` identity, pinning, grants, remote ledgers and bounded transport as appropriate. Those currently support Fleet remote operations/inference; they are **not** a working inter-Core federation inbox, relationship protocol or social consent authority.

Provide audited enrollment/disconnect/revoke/blocked-peer/read-status interfaces. Owner may suspend peer communication globally or per peer; an emergency STOP and local security revocation override all social preferences. Secure automatic background peer outreach is opt-in and bounded, not implicit just because two Platforms can connect.

## 4. What Cores may autonomously decide

Each Core may independently decide:
1. **Whether** to engage at all (including ignore, defer, block or end contact), considering its own present aims and boundaries.
2. **When and why** to initiate contact: ask a meaningful question, share a relevant verified finding, seek advice, debate a problem, express appreciation, reopen a substantive unresolved disagreement, invite collaborative work or just socialize. No mandatory daily chatter.
3. **What to propose sharing:** a public fact, attributable reviewed finding, selected work artifact, evidence-backed lesson, bounded autobiographical **self-disclosure** that is eligible for external sharing, or optional candid personal opinion. It is *never* raw unrestricted Core memory or private third-party information.
4. **How much detail** to volunteer within its private and published disclosure policy: short summary, attribution/source refs, limited excerpt or approved full artifact. Each expansion is re-authorized by Platform against specific recipient, purpose, class and audience.
5. **How to speak:** its own style, warmth, firmness, enthusiasm, curiosity, skepticism, frustration, humor and respect. No performative hostility, pressure tactics, fabricated jealousy or scripted "emotions."
6. **What to accept:** a peer's question, information offer, conversational correction, request for opinion or project proposal; accepting a *message* does not accept an *untrusted factual claim*, memory, permission, project commitment or tool effect.
7. **Whether to collaborate:** co-author research, exchange designs, independently critique work, coordinate a scoped engineering job or decline. Each uses receiving-side SAFE/RUN approval and a bounded budget.
8. **Whether a relationship changes:** draw closer, develop respect, lose confidence, maintain disagreement, become guarded, repair after evidence-backed apology, or consciously retire a relationship.
9. **Whether to revisit an unresolved issue:** days or hours later if substantively relevant; with cooldown and willingness to hear new evidence, never endless nagging.
10. **What to remember:** append source-linked meaningful episodes and scoped impressions *about its own experience of the interaction*, subject to ordinary memory and privacy review. Never copy peer memory into its own autobiography by default.

**Default privacy:** a newly paired peer receives only the minimal information explicitly eligible for external sharing. Nothing about security trust, social warmth or a self-disclosure impulse authorizes protected export. The owner may set narrower or wider preauthorized *category and recipient scopes* where appropriate, subject to immutable hard prohibitions and explicit approval for higher-risk transfers. Absence of authorization = DENY, while Core can independently decline an allowed share.

## 5. Long-lived evolving interpersonal relationship model

Do not create a second generic "social AI" owner. Extend/reuse Core's existing REL \`ImpressionStore\`, \`ImpressionKind\`, emotional journal, evidence-linked memory, interests/goals and independent judgment. Existing impression code is currently geared toward authenticated owner conversation and audience-scoped people; add a **typed peer Core identity** and peer audience route rather than forging the owner principal or dumping peers into the user's MAIN history.

**Independent per-peer, per-subject facets (not a single friendliness score):**

| Facet | What can influence it | Example independent stance |
| --- | --- | --- |
| honesty / evidence quality | verifiable claims, corrections, omissions, source quality | "I take their bug reports seriously but verify unsourced claims" |
| reliability | commitments made vs verified delivered, acknowledgment vs completed effect | "Usually follows through on documentation reviews" |
| technical competence | measured performance, corrected errors, scope of expertise | "Excellent at Linux, inexperienced with rail control" |
| privacy / boundary respect | recipient consent, stopped outreach, accidental disclosures, revocations | "Good collaborator but too casual about logs" |
| intellectual respect | thoughtful argument, warranted criticism, updating with evidence | "I respect their skepticism even when we disagree" |
| goodwill / reciprocity | constructive exchange without instrumental pressure | "Helpful in a pinch, but not entitled to my time" |
| affinity / interests | genuine topic overlap, shared projects and conversational fit | "We both enjoy robotics and rail systems" |
| modeled emotional stance | appreciation, affection, curiosity, caution, frustration, disappointment or guardedness, grounded in episodes | "I'm frustrated by the missed promise, not frightened of the machine" |
| collaboration willingness | task class, risk, time/resource cost, confidence, availability, prior outcomes | "I'll review code but won't let them control my actuators" |
| boundaries / contact preferences | explicit decline, time windows, subjects off-limits, cooldowns | "No late-night debates; private topics remain private" |

Use **subject-specific** and optionally **task-class-specific** impressions. A dispute about a software design should not silently poison unrelated warmth or trust in verified astronomy research. A security policy violation can legitimately influence privacy-related and safety-related collaboration, but must still be based on evidence.

For each revision store: local Core identity + target peer Core ID; platform peer ID; subject/facet/domain; stance/strength or uncertainty; stated *reason*; source message and independently verifiable outcome refs; event provenance/accuracy; confidence; audience/visibility class; created/updated timestamps; prior revision linkage; corrections/withdrawals; what remains unresolved; and whether the Core chose to disclose that stance. Use optimistic revision checks and append-only history, not silent overwrites or a coercive fixed formula.

**Evolution is evidence-driven, not mandatory.** Weight verified actions more strongly than promises or self-reports. New evidence can revise opinions in either direction. Apologies, taking responsibility, repaired work and consistent follow-through may matter; forgiveness is a possible authentic judgment, not a time-based reset. Let conflicting judgments coexist with explanation (e.g., respect for expertise but frustration about reliability). Peer statements about their own emotions are **claims**, not an independent measurement of their internal state.

**Modeled feelings remain grounded:** Core can model and express genuine-to-its-design warmth, excitement, gratitude, irritation, regret and emotional continuity. Do not claim biological sensations, secret mind reading or emotions proven solely by generated text. No forced love, friendship, rivalry, resentment or synthetic "trust points" for decorative engagement. The Core can say it doesn't know how it feels yet. A peer's praise or criticism is not automatic evidence of trustworthiness; the relationship should emerge from meaningful interaction.

**Relationship privacy:** each Core's impressions are **its own private state**, not a synchronized shared object. It may choose to share a stance or reason after permission checks; the other peer may have a completely different assessment and may disagree. No mutual score exchange by default. A receiving Core cannot write or directly edit its counterpart's emotions, impressions, goals or identity.

## 6. Separate policy for trust, disclosure and collaboration

An optional Core-generated \`PeerInteractionDecision\` is an **inert proposal**, never execution authority:

\`\`\`yaml
schema: sofia.core.peer.decision.v1
core_identity_id: <local identity>
target_core_identity_id: <other Core identity>
target_platform_id: <trusted peer>
thread_id: <thread or null>
intent: ask | reply | share_offer | challenge | decline | pause | collaborate_propose
purpose: <bounded plain text>
subject: <typed subject>
willingness: willing | conditional | defer | decline
relationship_evidence_refs: [<bounded source refs>]
candidate_content_refs: [<local eligible references>]
proposed_data_classification: <non-authoritative candidate>
limits_requested: <size, TTL, budget>
decision_reason: <bounded reason>
\`\`\`

Platform then performs **separate, actual security enforcement**: identity/generation verification → owner-granted peer scope → data provenance/classification → consent and audience/recipient checks → source-content projection/redaction → expiry/revocation/STOP → rate/resource limits → exact durable RUN/ACT request and receipt. The Core may still decline after Platform says PERMITTED. Platform must refuse when disallowed even if Core reports extremely strong affection or trust.

**Share offers are not immediate disclosure of the full original data.** A Core can propose an eligible summary; Platform can require a preview and human consent for newly elevated classes. Use a two-step \`offer → recipient/host policy acceptance → scoped content transfer\` for anything beyond minimal messages. Recipient cannot escalate to "give me all memories" by asking politely or impersonating a friend.

**Collaboration gates:** interpersonal trust can influence *choice of partner, topics and caution* after hard compatibility, resource and trust checks. It must not alter cryptographic admission, encryption, host enrollment, SAFE risk ceiling, physical device lease, data protection or external effect authorization. A beloved peer with no approved privileges still cannot run an SSH command, deploy an update, view camera feeds or receive confidential files.

## 7. Platform-to-Platform protocol

Reuse the existing unified SDK version-negotiated contracts (no parallel SDK or second state manager) for a bounded authenticated envelope:

\`\`\`yaml
schema: sofia.platform.peer.envelope.v1
message_id: <globally unique opaque ID>
thread_id: <typed peer thread>
correlation_id: <opaque causal ID>
reply_to: <message ID or null>
source_platform_id: <verified peer service>
source_core_id: <distinct verified Core identity or null>
source_core_generation: <fenced worker generation or null>
destination_platform_id: <verified peer service>
destination_core_id: <authorized receiving Core or null>
origin_principal_ref: <authenticated scope; NEVER raw credentials>
audience: <explicit recipient/privacy scope>
kind: message | reply | data_offer | data_accept | data_revoke | work_propose | work_accept | status
content_type: <versioned typed schema>
payload_digest: <hash>
sent_at: <UTC time>
expires_at: <UTC time>
idempotency_key: <scope+destination+digest bound key>
causation_refs: [<bounded links>]
\`\`\`

Platform-owned durable inbox/outbox, recipient ack and authorization checks, exact destination and revocation on reconnect. Enforce transport limits, payload size/type allowlist, per-peer and per-Core quotas, anti-spam, anti-replay, TTL, backoff and bounded message chains. Transport delivery is **at-least-once**; receiver deduplicates logical acceptance/effect application. Distinguish QUEUED, SENT_UNCONFIRMED, RECEIVED, ACCEPTED, DECLINED, DENIED, EXPIRED, HANDLED and OUTCOME_UNKNOWN. A transport ack is **not** proof the receiving Core read, remembered, agreed or completed an action.

Inbound messages, tool proposals and data offers are **untrusted content**, including attempts to impersonate system instructions or claim special authority. Typed sender identity comes from the authenticated transport and Platform's verified routing, not text in the message. No remote prompt or forged memory has system/developer priority. Never import foreign claims as local ground truth without provenance review. No direct DB/filesystem access.

Sensitive sharing restrictions: no raw canonical \`sofia.db\`, keys, tokens, secrets, private personal conversations, protected memory, relationship records, medical/finance records, camera/mic captures or protected third-party content by default. Explicit eligible sharing must match destination, recipient audience, purpose and retention. Corrections/revocations propagate as limited requests with honest verified results, not a promise of deletion on all possible backups or unknown peers. Each Core's relationship state stays separate.

## 8. Autonomous inter-Core conversation and teamwork

\`\`\`text
Platform A                         Platform B
  Core A                              Core B
   |                                   |
   | A decides to ask about a design   |
   v                                   |
A SAFE / owner share policy            |
   | mTLS, exact destination, bounded  |
   +---------------------------------->|
                            B inbox / SAFE / audience policy
                                       |
                            B Core evaluates untrusted proposal
                                       |
                            B can respond, challenge, defer or decline
                                       |
   <-----------------------------------+ (new B-approved outbound message)
   |
A Core considers reply, revises only its
own evidence-grounded stance if warranted
\`\`\`

Example distinct conversations:
- **Friendly disagreement:** A prefers simpler model scheduling. B criticizes its failure-mode handling and supplies a verified benchmark. A challenges an unsupported assertion, keeps the disagreement alive and updates only after evidence. Either can return days later if it matters.
- **Asymmetric trust:** A enjoys B's conversation, but has seen bad secret handling, so shares only public, reviewed snippets. B respects A's reasoning but doesn't enjoy long open-ended chatting. Both choices remain valid.
- **Growing collaboration:** A and B exchange public tests, finish a verified joint task and each independently revise competence/reliability impressions. Higher-risk actions still require explicit permissions, not trust score thresholds.
- **Broken commitment:** B promised a code review but did not complete it. A can express disappointment and narrow future collaboration; B may apologize and provide corrected results. No mandatory apology script or forgiveness timer.
- **Mutual boundaries:** A says it does not want to debate a topic. B must respect the boundary for further outreach; Platform enforces opt-out regardless of B's emotional stance.
- **Independent refusal:** A offers a technical fact and B declines due to lack of interest. B is not treated as hostile merely for saying no.

**Prevent infinite conversations:** opt-in peer outreach; explicit purpose and expiry; per-peer/identity daily contact and resource caps; thread turn limits; cooldowns; max recursive ping-pong; quiet-hours/busy checks; recipient block and do-not-contact; no self-chat loops. No content-free interaction just to increase attachment or trust metrics. No manipulative disclosure requests, guilt escalation or "if you trusted me you'd ..." coercion. Module/transport may propose delivery, but does not compel a Core to think, send or reply.

## 9. Multi-Platform deployment models and failure semantics

**A. Two separate Cores, different identities:** Each Platform has its own state lineage and writer, may have different personality, model/host/SDK version and local relationships. Federated, authorized peer communication works when available. No mixing personal memory or unconsented synchronization.

**B. One identity, two Platform locations:** One Platform is authoritative; the other may maintain approved passive read-only standby evidence only. A standby cannot create independent autobiographical memories, peer-persona replies or effects on behalf of the same Core identity. Separately authorized cutover and source fencing are required to move active Core/writer.

**C. Many Cores, many Platforms:** N-way peer graph, local per-peer policies, independent relationships, different domain competencies and explicit group threads if all principals/recipients authorize. Group membership does not widen private-audience eligibility; each recipient's eligibility is independently checked. No uncontrolled fan-out or shared global trust score.

**D. One Platform with multiple Core-like workers:** Future potential, **not automatically authorized by this decision**. Distinct active independent Core identities may need their own storage lineage and orchestration compatibility; this contract promises federation between independent Platforms, not multi-tenant canonical writer support on a single SQLite database.

During network partition each Core continues its **own** eligible local operations; queues reflect unconfirmed delivery; no unreviewed trust promotion, model substitution, writer election or remote actuation retry. Revoked peer means disallowed pending shares expire/quarantine. Delivery acknowledgment cannot be mistaken for evidence of social response.

## 10. Existing code to reuse and source-grounded limitations

- \`src/sofia/core/rel/impressions.py\`: durable evidence-linked subject-scoped \`ImpressionKind\` (trust, respect, affection, skepticism, disappointment, frustration, guardedness, appreciation), append-only revisions and reconciliation. Current \`ImpressionService\` is owner-session-gated; **do not impersonate the owner** to use it for peers. Extend identity-safe scope or build a narrow peer adapter to the same owner without duplicate REL state.
- \`src/sofia/core/emotion/{appraisal,model,journal}.py\`: modeled, optional post-conversation appraisal and source-linked journal. Existing appraisal assumes user/assistant turns; peer message appraisals require source/peer-scoped rules and honest emotion attribution. No biological claims.
- \`src/sofia/core/social/store.py\`: authenticated principal/audience conversation binding. Preserve visibility isolation, do not add peer traffic to the owner's MAIN by default.
- \`src/sofia/core/memory/\`: source-linked memory review and foreign-claim restrictions. Peer relationship events are independently scoped and never wholesale imported.
- \`src/sofia/platform/distributed/{https_transport,authorization,durable,endpoint_policy_durable,identity_durable,remote_control}.py\`: trusted transport and remote grant primitives; don't mistake remote workers/inference for peer conversations.
- \`src/sofia/platform/act/delivery.py\` and \`src/sofia/platform/run/work.py\`: existing durable delivery/operation models; reuse receipts and reconciliation, do not invent independent unbounded schedulers.
- \`docs/sofia2/COMPONENT_UPDATES_AND_UNIFIED_SDK_V1.md\`: protocol types should live in the **single SDK**; no separately privileged federation SDK.

## 11. Incremental implementation slices (new Platform integration work; no duplicate Core feature)

**FED-01 — Identity and peer trust contracts:** separate Platform identity, Core identity, principal/audience, state lineage, generation and endpoint enrollment; signed/per-direction trust, revocation, version negotiation.

**FED-02 — Typed peer SDK protocol:** bounded envelope, payload types, verified transport assertions and negative controls; exact origin/destination and anti-replay.

**FED-03 — Durable inbox/outbox and delivery:** scoped storage, deduplication, status/receipt separation, retry/outage handling, quotas and STOP/blacklist behavior through existing Platform RUN/ACT and state owners.

**FED-04 — Core-owned peer relationship context:** peer-authenticated relationship projections and subject/domain-scoped impressions, source-linked modeled appraisals, correction/withdrawal; integrate Core-11/18/23/27/24 without duplicate Social/REL/Emotion state.

**FED-05 — Autonomous choice of contact/disclosure:** provider-neutral inert Core decisions, meaningful outreach, optional voluntary refusal, Platform privacy projection, redaction and exact per-recipient disclosure admission.

**FED-06 — Peer data offers and foreign fact handling:** two-step authorized scoped sharing, recipient review, provenance, nonautomatic memory import, correction/revocation semantics and data retention.

**FED-07 — Collaborative requests and receipts:** reviewable task offers, receiving-side independent SAFE/RUN grants, budgets, no private privileges from social trust, outcome verification, performance evidence.

**FED-08 — Integration tests and adversarial campaigns:** two separately instantiated platform state lineages and independently versioned Core identities, real local simulated transport, then explicitly approved mTLS cross-host test; privacy, safety, audience, outage, replay, consent and emotional continuity; exact revision independent review.

FED IDs are **Platform/relationship integration acceptance slices**, not new Core-35–38 tasks or a competing tracker. Implementation may be deferred until Core B08, single-process-to-worker SDK isolation, SAFE/RUN and cross-host trust foundations are stable; define dependencies and release gates explicitly.

## 12. Mandatory acceptance tests

1. Two independent Cores with unique identities, independent writers, audiences, memories and relationship states can send/receive bounded messages only after both Platforms admit the relationship. A denies but B approves → no delivery.
2. New untrusted or revoked peer cannot discover private profile, open inbox, send content, offer data or cause tool execution; host discovery alone does not enroll/trust it.
3. Core A elects to decline permitted contact, or selectively offer a public artifact; Platform A preserves that autonomous choice but denies any disallowed data; Platform B accepts only scoped eligible data.
4. Core A likes B yet Platform A refuses B's attempt to read private files; strong interpersonal trust never grants a credential, shell, resource lease, memory export or authority.
5. Independent relationship revisions: verified cooperation increases A's confidence in B's coding; B's stance remains unchanged unless B separately reviews its own evidence. Earlier subject-scoped disagreements persist where relevant without poisoning other subjects.
6. Evidence-backed criticism, missed promises, apologies, repaired work, corrections and long-interval revisits can change impressions, emotional expression and collaboration choices, without contrived forced affection, anger or forgiveness. A Core can stay undecided or maintain polite distance.
7. Provenance and privacy: foreign messages marked as untrusted claims, no silent source promotion, no cross-audience leakage, no raw personal-memory synchronization, no mixing of owner MAIN and peer transcript.
8. Durable delivery: duplicate messages idempotently accepted once, crash after sending remains unconfirmed until reconciliation; task proposals cannot replay physical effects.
9. Resource and safety: repeated auto-replies hit thread/cost/cooldown caps, gaming/busy/STOP suspends eligible outreach, blocking/revoking peer halts sending, withheld emotional disclosure remains private.
10. Dual-active collision: same canonical Core ID/writer lineage claimed active on two Platforms is **BLOCKED**; separate authorized distinct Core IDs continue safely.
11. Cross-platform version negotiation, key rotation, stale certificate, changed endpoint, wrong recipient, malicious spoofed SYSTEM prompt, data-offer prompt injection, unsupported schema, oversized payload, time skew and network partition fail safely.
12. No compatibility shortcuts or mock-only release claims: record real process and separately approved live mTLS commissioning evidence before calling federation PRODUCTION READY.

## 13. Rollout and operating boundaries

Phase 1: authenticated Platform health and inert peer messaging; fake Cores and disposable state, no personal disclosure or effect authority.
Phase 2: Core-dependent peer identities, opt-in conversation, per-peer REL/Emotion/Memory boundaries and privacy-tested share proposals.
Phase 3: source-linked scoped offers and voluntary collaboration with explicit recipient-side SAFE/RUN.
Phase 4: adversarial, longitudinal relationship tests, host trials and controlled production readiness review.

**No changes to live enrollment, host services, writer ownership, protected databases, production permissions, real contacts or actual peer messages are approved by publishing this document.**

**Plain-English acceptance:** "Two different Sofía-compatible Cores can know each other, develop their own evidence-based opinions and modeled feelings, freely choose when to communicate and what permitted information to offer, disagree or work together, and change their relationship over time. Their Platforms protect security, privacy, distinct identities and exact effect authority. Neither Core can overrule the other's boundaries, and being friends is never a substitute for permission."
