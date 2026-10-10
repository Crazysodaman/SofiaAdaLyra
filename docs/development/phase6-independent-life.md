# Phase 6: independent life and Project Forge

## Production ownership

`SelfDirectedLifeCoordinator` is the application-owned coordinator for optional
personal activity. It extends, rather than replaces, the canonical GOALS, RUN,
capability, creative, world, preference, nickname, ACT, and State Plane
components. All durable metadata is stored in the configured `sofia.db`; large
artifact bytes remain in Phase 5 managed asset storage.

The production flow is:

```text
recorded interest / real experience
  -> one bounded model suggestion (at most once per UTC day)
  -> deterministic feasibility and evidence policy
  -> IDEA -> PROPOSED -> canonical scoped SELF goal -> ACTIVE
  -> GoalActionProposal -> capability authorization -> durable RUN job
  -> one-use Project Forge execution grant
  -> real managed artifact + hash + operation evidence
  -> grounded technical and subjective critique
  -> revise, complete, pause, reject, abandon, archive, or revive
```

The model suggests a structured idea only. It receives no tools in that call and
cannot persist a project, grant permission, mint a RUN receipt, or authorize an
artifact. The host validates evidence, interest strength, confidence, creative
adapter availability, scope, resource pressure, and lifecycle transitions.

## Right to fail, change course, or do nothing

The lifecycle distinguishes technical `FAILED`, voluntary `ABANDONED`,
`REJECTED`, `PAUSED`, `COMPLETED`, `ARCHIVED`, and `SUPERSEDED`. Completion is
optional. Rejected personal activity establishes a quiet window instead of
immediately generating replacement work. Busy/gaming/DND state, resource
pressure, an explicit quiet choice, an exhausted budget, or the absence of a
grounded interest all produce inactivity without manufacturing distress.

Technical outcome and personal judgment are independent. A hash-verified,
objectively valid artifact may still be disliked, revised, or preserved because
an unsuccessful result is interesting. These records do not write emotional
state. Conversely, emotion cannot authorize work or force enthusiasm.

Optional personal projects may be abandoned by Sofía. User assignments and
operational duties cannot be silently rejected or abandoned by the Sofia actor;
they retain their existing handoff and cancellation requirements.

## Durable records

The `life_*` tables retain:

- revisioned projects, status events, goals, milestones, and decisions;
- associated artifacts, virtual spaces, and RUN jobs;
- artifact technical results and separate personal judgments;
- evidence-linked private/shared experiences and traditions;
- revisioned interests, including retirement and changed confidence;
- activity selections, explicit quiet choices, resource use, and bounded idea
  attempts;
- one-use artifact execution authorizations.

Project and interest updates use transactional compare-and-swap behavior. RUN
work interrupted by process restart becomes `outcome_unknown`/uncertain rather
than completed. Experience records describe only observed runtime events; no
offline interval is converted into invented activity.

## Authority and privacy invariants

- project != goal authority;
- goal != permission, execution, evidence, consent, or receipt;
- model output != canonical project state;
- attention/emotion/preference != permission;
- artifact existence != successful project completion;
- avatar scene state != evidence that work ran;
- private experience remains scoped to its exact audience;
- creative capability execution requires both existing SAFE authorization and
  an exact, unused durable Project Forge grant;
- direct or replayed model/tool calls cannot reuse that grant;
- code artifacts remain behind the existing DEV/OpenCode candidate and approval
  boundary.

## Resource and scheduling policy

Personal work runs only after the application's foreground-idle gate. The
coordinator respects gaming, busy, and do-not-disturb state, NEURO resource
pressure, per-project concurrency, CPU admission cost, daily wall-time, storage,
memory/GPU declarations, bounded queues, and cancellation/deadline handling.
The current native adapters are small local deterministic jobs and record actual
wall/CPU proxy and byte use. Host-level CPU/GPU/memory enforcement remains the
responsibility of the existing RUN/worker isolation and platform layer; a budget
record is not represented as an OS resource-control receipt.

The background lifecycle does not continuously invoke an LLM. With no eligible
grounded interest, an existing live project, busy state, resource pressure, or a
quiet choice, ideation is skipped deterministically. A suggestion attempt is
durably limited to one per UTC day.

## World, preferences, and social behavior

An active project can own a private or shared Phase 5 world space. Only an
artifact already linked to that exact project can be placed there. Preferences
and favorites are evidence-backed revisions in the existing registry. Nickname
proposals use the existing recipient-controlled nickname lifecycle, so rejection
prevents adoption and canonical identities never change.

Sharing is deliberate rather than automatic. When Sofía chooses to share, the
application submits the grounded event through the existing Presence/ACT policy.
Quiet hours, recipient authorization, transport availability, quotas, dedupe,
and delivery receipts remain authoritative.

## Batch status

| Batch | Repository status | Honest boundary |
| --- | --- | --- |
| 6A Life coordinator | Implemented and production-composed | Live host scheduling still needs soak acceptance |
| 6B Project Forge core | Implemented | Real-model originality/quality remains host acceptance |
| 6C Creative production | Native text/story/SVG/OBJ/animation/WAV/game/simulation adapters verified in tests | External art/music/3D suites are not claimed |
| 6D Critique/right to fail | Implemented and release-blocking tests present | Aesthetic quality is subjective, not a verification claim |
| 6E World/experience | Implemented over Phase 5 stores | Visible renderer acknowledgement remains host acceptance |
| 6F Social development | Preferences, interests, traditions, nickname proposal/rejection, and explicit ACT sharing implemented | Real channel delivery needs configured host transport |
| 6G Distributed autonomy | Existing Fleet placement, migration, fencing, release rollback, dependencies, Gaia and JMRI boundaries retained | Real multi-host migration, HA/DR, Gaia/JMRI and worker isolation are not accepted by Linux CI |
| 6H Production acceptance | Automated repository gates cover local production composition and boundaries | Windows/Linux/Fleet/renderer/channel canaries remain listed below |

## Required live-host acceptance

The following must not be inferred from source or unit tests:

1. supervised real-model ideation quality and idle-cost soak;
2. visible project artifact placement through the desktop renderer;
3. real Discord/mobile/Desktop ACT share delivery and recipient acknowledgement;
4. clean Windows and Linux restart/recovery with the production service account;
5. OS-enforced worker CPU/GPU/memory limits and restricted OpenCode identity;
6. approved multi-node workload placement/migration, single-writer fencing,
   partition recovery, database restore, and disaster-recovery drills;
7. real Gaia safety/reflex hardware and JMRI integration canaries.

Until those receipts exist they remain host-unverified. Their absence does not
turn optional personal activity into mandatory work and does not weaken any
existing SAFE, ACT, Fleet, BODY, or DEV boundary.

## Automated acceptance evidence

On 2026-10-10 the final uncommitted candidate tree passed the complete candidate
gate: **4,019 passed, 5 skipped, 6 deselected**; dependency integrity passed and
semantic verification accepted with zero findings. The focused Phase 6
production/path boundary set passed **22/22**. Revision-bound release evidence is
recorded separately after commit; these results do not substitute for the
live-host acceptance list above.
