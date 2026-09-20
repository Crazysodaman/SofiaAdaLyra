# Batch G3 and Engineering 22C checkpoint

**Status: implementation delivered for local verification; full batches remain open.**

## G3: actual provider-path evidence

`test/test_personality_provider_path.py` assembles a supplied personality and
uses a recording `LLMProvider` with the actual `LLMCognitiveEngine`. It checks
that the system message and original user message reach the provider intact.
A second case deliberately returns a generic response: it documents that
prompt delivery does **not** establish personality fidelity. Real-model
behavior needs separate, bounded live testing; do not call G complete on the
strength of mocked-provider results.

## 22C: peer knowledge

`sofia.distributed.knowledge.PeerKnowledge` is an in-memory registry of
observations for **already enrolled** nodes. It keeps the most recent immutable
observation and rejects unknown nodes, older evidence, and conflicting records
with identical timestamps. A caller-supplied timezone-aware `now` and
explicit positive `max_age` yield CURRENT, STALE, UNOBSERVED, or CLOCK_SKEW.
Stale, future, and absent observations expose UNKNOWN effective reachability;
original evidence remains inspectable. An observed failed connection does
not prove the machine is offline. Neither enrollment nor observation grants
network access, identity proof, or authorization.

This slice does not yet persist observations, inspect the LAN, discover peers,
verify remote credentials, or execute operations. Those remain later gates.

## Suggested local verification

```powershell
pytest -q test/test_personality.py test/test_personality_embodiment_contract.py test/test_personality_pipeline.py test/test_personality_expression_boundary.py test/test_personality_provider_path.py test/test_distributed_node_contract.py test/test_distributed_identity.py test/test_distributed_peer_knowledge.py
git diff --check
git status --short
```

Run the broader `pytest -q -m "not integration"` at the combined checkpoint;
record actual results and distinguish skipped/deselected live tests. Review
and explicitly stage only intended files, not state databases, logs, or
one-time installer scripts.
