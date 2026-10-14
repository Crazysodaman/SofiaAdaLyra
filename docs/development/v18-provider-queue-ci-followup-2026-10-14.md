# V18 malformed Ollama response and honest deferred-work queue

Date: 2026-10-14. Batch supports CA-1207 (provider contract) and V18
CA/ML/GA dependency queue verification. No host operations or acceptance promotion.

## Observed failure evidence

[Debian release run 38650361705](https://github.com/Crazysodaman/SofiaAdaLyra/actions/runs/38650361705)
at `955afc23becfe4819e0471967e06651a69932800` reported
**5660 passed, 3 failed, 5 skipped and 6 deselected**. The failures were:

1. `test_ollama_malformed_response_boundary.py`: Ollama
   `SimpleNamespace(message=None)` was accepted as empty assistant output.
2. `test_v18_dependency_queue.py`: a test assumed a real Gate 3 proof
   existed; the authoritative ledger had zero. It was a test-fixture
   assumption, not an absent worker feature.
3. `test_v18_gate4_batch50.py`: stale snapshot equality rejected valid
   additive source evidence, addressed by the previous batch.

## Corrective code

- Production `OllamaProvider._response_from_ollama()` rejects an absent
  or structurally incomplete `message` before quality retries or
  response persistence. Valid tool-call-only messages with `content=None`
  and a real message object continue through existing tool authority.
- Added malformed message-without-content regression to the existing
  provider payload matrix, preserving the no-tool and invalid-argument
  protections.
- The work-queue test now calculates the real recorded Gate 3 count
  without inventing evidence, then injects a local synthetic Gate 3
  progress row and proves it is deferred from selection until final CI.
  No canonical ledger records or code paths are changed.

## Audit and remaining verification

Provider errors cannot authorize tool execution or mask a missing message
as a good response. No external model is contacted by regression fixtures;
no database, consent, host/credential policy, or canonical writer changes
occurred. Queue mutation is confined to a deep-copied test object.
Production performance is unchanged apart from two constant-time checks.
No acceptance is claimed until exact-commit targeted regressions and
installed-wheel checks are inspected. Live Ollama, model response shapes,
release candidate, Windows and Artemis acceptance remain independent.
