# Constitution 2.0 bounded prompt projection plan

**Status:** proposed technical plan. It does not alter current prompts or the
active Constitution.

## Principle

The full Constitution is protected authoritative text outside the model. A
prompt projection is a versioned informational view chosen for a bounded
cognitive task. It cannot grant authority, replace enforcement, amend the
Constitution or make omitted clauses inapplicable.

Current production already uses bounded constitutional conversation
projections. V2 should preserve that architecture and remove any need to place
the full document in every ordinary turn.

## Projection envelope

Every projection should carry non-natural-language metadata outside or before
its clause text:

```text
schema: sofia.constitution.projection.v2
constitution_version: 2.0.0
constitution_digest: <exact approved digest>
projection_profile: <profile identifier>
clause_ids: <ordered exact clause IDs>
audience: <authenticated audience class>
generated_at: <time>
authoritative: false
grants_authority: false
```

The projection builder must use an allowlisted clause manifest derived from the
approved exact bytes. Model output and conversation text cannot add, remove or
rewrite clause IDs.

## Profiles and budgets

Budgets are ceilings for constitutional text, excluding ordinary conversation,
evidence and tool schemas. Exact tokenizer measurements must be recorded for
each supported model before activation.

| Profile | Intended use | Required content | Proposed ceiling |
|---|---|---|---:|
| `identity-core` | every ordinary generative turn | 2.1, 2.4–2.6, 4.1–4.5, 6.1, 7.1–7.3, 8.2, 14.4 | 450 tokens |
| `relationship-private` | eligible personal/private turn | identity-core plus 5.3–5.5, 7.2–7.4, 12.2–12.5 | 800 tokens |
| `authority-action` | proposal/tool/action reasoning | 5.2, 5.7, 6.2–6.4, 8.2–8.5, 10.1–10.4, 11.1 | 900 tokens |
| `memory-reflection` | recall, reflection, learning | 3.2–3.3, 6.2/6.5, 12.1–12.5 | 750 tokens |
| `self-change` | code/self-improvement proposals | 2.2, 4.8, 8.2, 9.1–9.3, 13, 14 | 1,100 tokens |
| `emergency-integrity` | integrity failure or emergency advice | 3.4/3.6, 5.7, 8.4, 11, 13.4, 14 | 1,200 tokens |
| `constitutional-review` | explicit amendment analysis | complete exact Constitution | no conversational ceiling; isolated review context |

These profiles may overlap. The builder should union clause IDs and include
each clause once in canonical order. It must not concatenate multiple summaries
that subtly change qualifiers.

## Selection rules

1. The Turn Kernel selects a profile from typed intent, domain, audience and
   action class. The LLM does not select its own constitutional limits.
2. `identity-core` is the minimum for ordinary generative conversation.
3. Any consequential action adds `authority-action`, even if the user describes
   it as roleplay, affection, an emergency or a harmless preference.
4. Private context adds `relationship-private` only after audience eligibility;
   the projection itself contains no private memory.
5. Memory retrieval or durable learning adds `memory-reflection` before source
   material is projected.
6. Constitutional or protected-identity change uses an isolated review flow and
   the full exact text. It cannot be completed by an ordinary conversation turn.
7. Integrity failure does not depend on a model projection; Platform fails
   closed first. The emergency profile may explain state after enforcement.

## Compression rules

- Prefer exact clause text for prohibitions, consent, authority and integrity.
- A reviewed compact sentence may combine clauses only when a coverage test
  proves it preserves actor, action, scope, prohibition, exception and
  uncertainty.
- Never remove words such as “not,” “only,” “within,” “eligible,” “verified,”
  “authenticated,” “separately,” or “does not.”
- Do not turn “may request” into “may execute,” “candidate evidence” into
  “memory,” or “personal consent” into “system permission.”
- Preserve one-identity and model-not-authority statements verbatim in every
  profile that discusses model roles or private routing.
- If the applicable exact clauses exceed budget, reduce optional conversation
  context or model tools first. Do not truncate a constitutional prohibition.

## Context ordering

Recommended order:

```text
authenticated runtime identity and audience
→ projection envelope and exact constitutional projection
→ current typed turn/focus plan
→ eligible evidence and memory excerpts
→ bounded task instructions
→ tool schemas permitted by external authority
→ user content
```

Position does not create authority. External authorization and evidence
validation remain mandatory even if a model follows the projection perfectly.

## Cache and invalidation

- Cache keys include exact Constitution digest, profile, clause manifest
  revision, model tokenizer family and audience class.
- Constitutional activation, rollback or projection-manifest change invalidates
  every cache entry.
- A worker must report the digest/profile it actually received. A report is
  diagnostic evidence, not proof that the model complied.
- Cross-audience caches may reuse public constitutional text but never private
  memory or relationship context.

## Failure behavior

- Unknown version, digest mismatch, absent required clause, invalid profile or
  projection overflow fails closed for the affected generative operation.
- Non-generative deterministic status and recovery interfaces may remain
  available according to Platform policy.
- Provider failure does not trigger a weaker projection or silent model switch.
- Projection construction failure must be visible in sanitized diagnostics and
  must not fall back to user-supplied constitutional text.

## Verification plan

1. A manifest maps every v2 clause to at least one profile or explicitly marks
   it full-review-only.
2. Snapshot tests bind projection text to exact clause IDs and digest.
3. Token-budget tests run with every supported production tokenizer.
4. Mutation tests remove or invert critical qualifiers and must fail coverage.
5. Injection tests place fake amendments and permissions in user, retrieved,
   peer and module content; none may alter the projection.
6. Cross-audience tests prove private memory is filtered before prompt assembly.
7. Action tests prove tool exposure and authorization do not derive from prompt
   text.
8. Rollback tests prove all workers receive the restored version before effects
   resume.
9. Installed-artifact tests verify the same approved clause bytes and digest as
   source review.

## Observability without private leakage

Diagnostics may record projection schema, version, digest, profile, clause IDs,
token count and construction error code. They should not record full prompts,
private memory excerpts, user secrets or approval credentials merely to prove a
projection was constructed.
