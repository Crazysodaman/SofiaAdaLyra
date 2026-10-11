# Workstream 2, Phase 06 • Original episode and preference source audit, batch 2

**2026-10-11 • main only • source audited, tests deferred**

Six original CA tasks were previously `unassessed`. Source tracing below proves a **partial existing production owner**, not full feature completion, and avoids inventing a second episodic database.

| CA | Exact production source | Evidence-grounded reuse | Still missing |
| --- | --- | --- | --- |
| CA-302 | `life/coordinator.py:project_causal_trace` | Requires original evidence refs before marking project event/run/evaluation/experience records `source_state='observed'`; otherwise labels `unknown` and suppresses unsupported summary | Separate `inferred`, `hypothesis`, `fictional`, plan-versus-execution classification for non-project episodes and generated claims |
| CA-303 | `life/model.py:ExperienceRecord`, `life/store.py:project_experiences, current_interest`, `life/coordinator.py:project_causal_trace` | Existing `project_id`, evidence refs, audience, goal and interest relationships are real canonical LIFE joins, not copied prose | Scope-safe relationship/person/topic/correction graph beyond LIFE projects |
| CA-304 | `life/store.py:project_experiences`, `life/coordinator.py:project_causal_trace, voluntary_project_updates` | Bounded project-history reads and optional evidence-backed owner-only project updates already exist | Ordinary conversation and non-project autobiographical retrieval are not wired as a validated, bounded, per-turn memory source |
| CA-305 | `life/store.py:record_interest_learning, revise_interest, current_interest, active_interests` | Existing source-experience consumption plus optimistic revision checking creates durable, audience-scoped preference updates without duplicated owner tables | User-reported likes/dislikes, conflict resolution with reviewed MEM corrections, decay and current-versus-historical preference evaluation across channels |
| CA-307 | `life/store.py:life_experience,life_interest_revision,life_interest_learning`, `life/model.py:ExperienceRecord` | Original `experience_id`, optional `project_id`, `evidence_refs`, interest revision records, timestamps and audience are stable durable owners | Dedicated typed episode↔relationship/topic/revision links, explicit correction supersession and efficient semantic index |
| CA-310 | `life/store.py:revise_interest,current_interest,active_interests,project_experiences` | Revision numbers and recorded-at timestamps preserve later updates rather than rewriting the first historical preference; project experiences are bounded and ordered by occurred-at | General cross-session bitemporal semantic recall, explicit governed forgetting and decay, cross-audience ACL proof on all new retrieval surfaces |

## Entry point and authority notes

The actual LIFE-owned `SelfDirectedLifeCoordinator.project_causal_trace` selects a previously authorized project, fetches its canonical goal, RUN receipts, project events, artifact evaluations and LIFE experiences, and validates original evidence references before building a read-only projection. A project trace is not a semantic memory promotion decision, an independently approved observation about every topic, or a grant to publish the trace on Discord/phone.

`LifeStore.record_interest_learning` writes source-learning consumption and a new interest revision in one canonical SQLite `BEGIN IMMEDIATE` transaction; it declines duplicate processing of the same experience ID. That protects against some repeated self-confirmation, but does **not** establish complete external review, cross-channel identity mapping or preference-decay policy.

## Remaining gates

- Complete CA-301/302/303/304/307 with a source-verified **non-project** episode and query bridge based on the existing LIFE owner, before sending context to any model.
- Add original-user correction and deletion propagation into derived LIFE interest/experience views, not just model-written project reflections.
- Keep project experiences original, scoped and no broader than the caller's authenticated audience; do not automatically mirror private LIFE stories into other channels.
- Run the deferred audience-leak, contradiction, time, restart, index, and performance acceptance suites only after all coding is ready.

**Classification:** six newly assessed `partial_wiring`; **zero accepted**, no claims of test success, live migration or functioning multi-decade retrieval.
