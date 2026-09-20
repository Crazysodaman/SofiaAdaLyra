# Batch G and Engineering 22A: initial implementation slices

**Status:** implementation proposed / local verification pending. This file is
not evidence that either complete batch is finished.

## Batch G: personality architecture

Source inspection found that the versioned-in-repository personality JSON is
loaded through `PersonalityStore` and `SofiaRuntime.start`, then passed to
`CognitiveContext` and included as name, traits, communication style, and
embodiment guidance by `CognitiveContextAssembler`. The stored profile is much
richer than the current four-field `PersonalityProfile`, so baseline projection
and live expressiveness must not be confused.

**G1 baseline:** `test/test_personality_pipeline.py` verifies that the actual
persisted profile reaches provider-neutral assembly once, unchanged, and that
user text is kept in a separate role. It does not prove resistance to prompt
injection or that Ollama will follow the style.

**G2 implementation (not yet started):** inspect actual failures from test-engine
and Ollama captures; only then refine a deterministic, versioned personality
expression boundary without duplicating canonical identity or fabricating
physical acts. Preserve variability and context sensitivity rather than canned
responses. Keep source facts outside the LLM.

**G3 evaluation (not yet started):** test stable personality source, restarts,
truth priority, authorized actions, uncertain knowledge, natural style, and
representational embodiment using an offline fixture and separately documented
real-model probes. No exact wording or response-format guarantee from tests of
prompt construction alone.

## Engineering Batch 22: distributed / multi-machine Sofía

**22A contracts:** `sofia.distributed.model` introduces a provisioned stable UUID,
a display name, optional endpoint hints, and time-stamped reachability evidence.
It deliberately does not open sockets, discover hosts, authenticate, authorize,
or execute code. `UNREACHABLE` means a recorded failure of an observation, not
proof of an offline device. Non-UNKNOWN conclusions require explicit evidence;
observations require timezone-aware timestamps and preserve node identity when
an address changes.

**22B–22H (not yet started):** node identity provisioning and verification;
peer knowledge and provenance; multi-signal reachability with expected-state
registry; per-node capability discovery; authenticated and separately authorized
remote execution; structured results, audit, recovery, and end-to-end tests.
Review existing `sofia.external` authentication/knowledge/capability and
`sofia.system` capability models before adding adapters. No remote operations
are authorized by the presence of a node record.

## Local verification

Run after installing the new files from the repository root:

```powershell
pytest -q test/test_personality_pipeline.py test/test_distributed_node_contract.py
pytest -q -m "not integration"
git diff --check
git status --short
```

Do not run the ten-generation Ollama probe for this offline contract slice.
Do not commit `state/sofia.db`, diagnostic logs, or one-time patch scripts.
Approve and review the intended source/test/docs files before any Git checkpoint.

## G2 and 22B continuation (2026-09-20)

**G2:** `sofia.personality.expression` defines a deterministic guidance section
placed beside the persisted profile in the assembled *system* message. The
original name, traits, communication style, and embodiment guidance remain
untouched, and user messages remain separate. This section distinguishes style
from factual authority and forbids invented operations or canned embodiment
reactions. It is **not** a reliable output validator or proof of live Ollama
personality fidelity; context budgeting and real-model probes remain open.

**22B:** `sofia.distributed.identity` supports immutable, operator-recorded
node ID/public-key SHA-256 pins and an in-memory append-only registry. It
rejects duplicate IDs/pins and implicit key rotation. Fingerprint comparison
is **not authentication**: an untrusted party can present arbitrary public-key
bytes. Actual proof-of-possession, trusted enrollment, persistence, key rotation,
network discovery, per-node authorization, and execution are still future gates.

**Focused verification:**

```powershell
pytest -q test/test_personality.py test/test_personality_embodiment_contract.py test/test_personality_pipeline.py test/test_personality_expression_boundary.py test/test_distributed_node_contract.py test/test_distributed_identity.py
```

Run `pytest -q -m "not integration"` before declaring either *full* batch
complete. No live inference or network activity is required for these slices.
Stage only reviewed intended source, tests, and documentation at checkpoint.
