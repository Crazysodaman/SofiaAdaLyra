# Cognition v2 Batch 2 production audit

Branch: `main`

Canonical database: `sofia.db`

## Production path

1. `ConversationService.respond()` authenticates the caller and durably saves
   the exact user message.
2. The application-owned `ProductionTurnKernel` receives the saved message ID,
   session, channel, principal, and audience.
3. The resolver advances structured focus and the SQLite store commits it with
   a compare-and-swap revision in the matching audience partition.
4. The kernel invokes existing Matrix planning and then NEURO attention. These
   are transitional delegates, not competing coordinators.
5. The focus projection joins the provider request as discourse context only.
   It explicitly grants no factual evidence, reachability, or authority.
6. After the assistant response is persisted, typed evidence may settle a
   relevant information request. Only an execution receipt settles pending
   action state.

The same path is used by authenticated owner-direct UI tool turns. Application
restart reloads focus from the canonical database when the session resumes.

## Files

| File | Decision | Production responsibility |
|---|---|---|
| `cognition/v2/contracts.py` | EXPAND | Typed references, topics, unresolved requests, pending actions, and coordinated turns. |
| `cognition/v2/focus.py` | ADD | Audience-partitioned durable focus with compare-and-swap revisions. |
| `cognition/v2/references.py` | ADD | Structured alias, typo, pronoun, ellipsis, correction, and subject-switch resolution. |
| `cognition/v2/kernel.py` | ADD | Authoritative focus advance plus Matrix-then-NEURO turn sequencing and typed settlement. |
| `application/bootstrap.py` | MODIFY | Compose the one shared kernel and project Fleet identities as non-factual candidates. |
| `application/conversation_service.py` | MODIFY | Route normal and owner-direct turns through the kernel and project focus to cognition. |
| `application/conversation_matrix.py` | MODIFY | Prevent focused remote subjects from falling through to local hardware inspection. |

## Safety and privacy findings

- Focus is keyed by both session and audience; one audience cannot inherit
  another audience's primary subject.
- A reference is discourse state, not proof that a named host exists or is
  reachable.
- Local hardware inspection is removed when a resolved subject is non-local;
  this prevents an Artemis pronoun follow-up from reporting Venus data.
- Questions such as “Do you see …?” do not become pending executions. The
  elliptical command “Do it” does.
- Arbitrary assistant prose cannot settle work. Capability/environment/memory
  evidence can settle information requests; execution receipts settle actions.
- Focus carries no permission, consent, execution, or receipt authority.

## Observed verification

- Focused V2 gate: 14 passed.
- Conversation, Matrix, NEURO integration, application lifecycle, and
  continuity regression slice: 233 passed.
- Non-integration CORE/SOCIAL/OPS package gate, including permitted localhost
  socket tests: 2,764 passed, 4 skipped, 1,082 deselected.
- Live Ollama integration remains unobserved because no Ollama service is
  available in this cloud environment; it is not reported as passing.
- Exact required Artemis chain retains one subject through all six turns.
- Restart, audience isolation, stale revision, typo, correction, multi-topic,
  pending-action, and production composition tests passed.

Batch 3 replaces Matrix v1 behind the Turn Kernel boundary and introduces the
validated cognitive scheduler. Until then Matrix v1 remains a deliberate
transitional delegate; it is not a fallback or second turn owner.
