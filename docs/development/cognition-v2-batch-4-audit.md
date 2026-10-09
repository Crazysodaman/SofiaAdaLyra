# Cognition v2 Batch 4 evidence and truth audit

Branch: `main`

Canonical database: `sofia.db`

## Finding

The pre-V2 evidence surface primarily projects identifiers such as
`capability:hardware.inspect` or `operational.measurement`. Those identifiers
can show that some capability returned successfully, but they do not encode the
subject or value. They are therefore insufficient to prove that a returned CPU
belongs to Artemis rather than Venus. Batch 4 does not reinterpret those
strings as typed facts.

## Files

| File | Decision | Production responsibility |
|---|---|---|
| `cognition/v2/contracts.py` | HARDEN | Validate finite JSON values while retaining separate epistemic/acquisition states. |
| `cognition/v2/evidence.py` | ADD | Append-only ledger, exact-key graph, durable correction cascade, and capability-result ingestion. |
| `cognition/v2/matrix.py` | KEEP | Produces the subject-scoped `EvidenceNeed` inputs consumed by the graph. |
| `application/bootstrap.py` | MODIFY | Compose one ledger, graph, and acquisition coordinator over canonical `sofia.db`. |
| `test_cognition_v2_evidence.py` | ADD | Subject, scope, freshness, trust, provenance, correction, dependency, receipt, restart, and production composition gates. |

## State model

Epistemic state and acquisition state remain independent:

| Dimension | Values |
|---|---|
| Epistemic | `OBSERVED`, `KNOWN`, `USER_REPORTED`, `INFERRED`, `HYPOTHESIS`, `UNKNOWN` |
| Acquisition/truth | `CURRENT`, `NOT_SAMPLED`, `UNAVAILABLE`, `STALE`, `FAILED`, `CONTRADICTED`, `REVOKED` |

An acquisition failure is therefore `UNKNOWN + FAILED`, not a false fact. A
hypothesis can be current as a recorded hypothesis but cannot satisfy an
operational fact need. Staleness is calculated from observation/expiry time and
the need's maximum age; elapsed time never changes the append-only atom.

## Safety results

- Exact subject/predicate/scope matching prevents Venus → Artemis substitution.
- Audience-private evidence and dependency edges cannot cross scopes.
- Future, stale, weak, failed, unavailable, hypothesis, contradicted, and
  revoked material cannot masquerade as a current operational observation.
- Observed/known atoms accept only reviewed host-source namespaces.
- Assistant/conversation prose is rejected as observed evidence.
- Execution predicates require an actual execution-receipt source.
- Correction target validation and the contradiction/revocation cascade occur
  in one SQLite transaction, preserving history and preventing partial truth
  mutation.
- Capability ingestion validates success/failure state, exact requested key,
  and exact capability source. Denial/unauthorized results remain authority
  outcomes rather than factual evidence.

## Transitional boundary

The ledger is production-composed and Matrix v2 emits its exact needs. Fleet
and Machine capability payload normalization and claim-driven answer generation
are deliberately Batch 5. Until then, existing domain response validators keep
their compatibility evidence projection; it is not promoted into this ledger
without subject/value provenance.

## Observed verification

- Focused V2 evidence/contract/Matrix/Turn Kernel gate: 38 passed.
- Combined application/conversation/Matrix regression slice: 253 passed.
- Non-integration CORE package gate: 2,219 passed, 4 skipped, 1,651
  deselected.
- Live Ollama execution is unavailable in this cloud environment and is not
  reported as passing.
