# Batch G5–G8 and Engineering 22E–22H: combined implementation package

**Status:** Code prepared as one installable package. Offline checks are necessary but not sufficient. Do **not** mark full G or 22 operationally complete until the live gates below are observed and recorded.

## Personality (G5–G8)

- G5: `sofia.personality.evaluation` accepts explicitly constructed **full** `CognitiveContext` scenarios including canonical identity, constitution, embodiment, personality and other fields as appropriate. The caller supplies the engine; this code never silently creates a provider, runs a model, saves prompts or writes personal data.
- G6: `sofia.personality.review` stores reviewer-attributed qualitative criteria and rationales next to raw observations. No automated personality "score" and no silent rewrite of a generic answer.
- G7: A supervised Ollama gate is still required: choose a small explicit scenario set and model/context configuration, record complete raw responses and elapsed time in a **private local** location, review generic self-introductions, canonical identity usage, invented actions, repetitive gestures and uncertainty. The G4 harness is a bare-personality probe; G5's full-context harness is a separate, stronger test surface. Neither is a replacement for `SofiaRuntime.respond` integration.
- G8: deterministic regression tests verify context preservation, limits, error capture and human review bookkeeping. These tests **cannot** prove the live model will consistently express personality. Avoid an unbounded ten-generation default regression.

## Distributed system (22E–22H)

- 22E: immutable, timestamped advertised capabilities and strict freshness/identity checks. Advertising does not convey permission.
- 22F: explicit node + capability + operation + grant-ID + expiry permission, deny by default and revocation. Human approval must happen *outside* the grant data model.
- 22G: `DistributedGateway` requires an injected `RemoteTransport` and rechecks authorization and transport authentication for each invocation. It refuses arbitrary command/script/secret parameters, bounds scalars to 4096 JSON bytes, checks same-node fresh inventory, prevents local repeated request IDs, does not retry uncertain execution, and exposes remote-reported outcomes as claims.
- 22H: fake-transport contract/integration tests cover denial, identity mismatch, stale/wrong inventory, duplicate requests, reported failures, and uncertain transport errors. This is **not** an actual authenticated remote-agent implementation.

**Security limit:** No concrete network transport, verified mTLS/SSH handshake, credential provisioning, durable replay ledger, persistent approvals, persistent audit, crash recovery, installed remote agent, remote capability handler, or real multi-machine test is provided by this package. `RemoteTransport.authenticate` is an **abstract contract**, not cryptographic proof; never plug in a transport that merely returns `True` without verifying possession of the enrolled key and endpoint identity. The gateway and in-memory audit are development scaffolding, **not production-safe remote execution**. Do not expose a network endpoint or enable consequential remote actions until these controls are implemented and independently tested.

## Verification gates

1. Installer `--check` must refuse unknown repo root, collisions and missing committed predecessors without changes.
2. Run `python -m pytest -q test/test_personality_evaluation.py test/test_distributed_capabilities.py test/test_distributed_authorization.py test/test_distributed_operations.py`.
3. Run `python -m pytest -q -m "not integration"`, then inspect `git diff --check`, `git status --short`, exact staged diff and file set. On Windows, do not rely on shell wildcard expansion for pytest filenames.
4. Separately run and record an explicitly opted-in **real** Ollama/full-runtime personality test and a **real** authenticated multi-machine test once infrastructure is available. Report each as passed, failed, or not run. No fake result can satisfy these gates.
5. Only after human review, checkpoint intended source, test and documentation paths. Installer scripts, database and diagnostic logs stay out of the commit.
