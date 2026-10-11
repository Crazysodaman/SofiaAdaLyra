# V18 owner decision: Venus now, Artemis after verified migration

**Decision recorded 2026-10-11. This is a target architecture, not an authorized live cutover.**

## Current production

Venus owns Sofía's sole writable `sofia.db`, the canonical runtime,
scheduling/goal/memory authorities, primary GPU inference, and the desktop UI.
Artemis does **not** become a second active writer because code was committed
or a configuration file was created.

## Approved future architecture

- **Artemis** becomes the only canonical runtime, writer, goals/memory owner,
  scheduler, service and recovery-control host.
- **Venus** supplies RTX 3080 Ti Ollama inference through the existing
  enrolled Fleet endpoint and pinned-mTLS authenticated remote inference.
  Venus may keep its desktop UI and owner-approved local tools.
- No shared writable SQLite filesystem, split brain or concurrent state
  writers. Read-only clients use host-owned authenticated APIs.
- Loss of the Venus inference worker is **not** permission to create a
  synthetic cognitive reply, swap to a different model or run Artemis-local
  LLM inference. Artemis-owned state, status, scheduling and independently
  authorized non-LLM work can continue.
- A separate **operator-approved, source-fenced and verified** migration,
  complete protected-state backup/restore, writer epoch handoff, failback and
  host recovery gate is mandatory before Artemis becomes the actual writer.
  Neither an LLM nor a model-provided payload can approve that cutover.

## Dormant production configuration gate

The normal Venus runtime remains unchanged when no split-role environment
variables are provided. After a *separate* human-approved cutover, an operator
may supply these variables on the **actual Artemis runtime**:

```text
SOFIA_SPLIT_INFERENCE_ROLE=artemis_runtime
SOFIA_SPLIT_RUNTIME_HOST_ID=<verified exact Artemis Fleet machine ID>
SOFIA_SPLIT_GPU_HOST_ID=<verified exact Venus Fleet host ID>

SOFIA_REMOTE_CA=<approved fleet CA file path>
SOFIA_REMOTE_CLIENT_CERT=<approved Artemis client certificate path>
SOFIA_REMOTE_CLIENT_KEY=<approved Artemis private-key path>
```

Those identifiers must match actual enrolled Fleet host IDs. Do not assume
that the display names "Artemis" and "Venus" are the exact Fleet identifiers.
Use the existing `SofiaConfiguration.fleet_cognition` values:

```text
enabled=True
local_fallback=False
auto_provision_models=False
gpu_required=True
allowed_host_ids=(<exact Venus host ID>,)
```

An enabled two-model router must also have `fallback_enabled=False`;
both configured providers must use the explicitly selected Ollama models.
The existing worker-side inference policy and exact grants still control
which models and operations the Venus agent accepts.

The production engine composition enforces these constraints and requires
the concrete `ConfiguredRemoteInferenceClient` type, provided through the
existing pinned-mTLS factory. Both the lifecycle and cognitive engine
factories fail closed on an inconsistent Artemis role. If Venus is offline,
`FleetPlacedCognitiveEngine` returns `CognitiveEngineError` without local
fallback. No replacement model is inferred, pulled or launched automatically.

This gate is **not** a writer election, not a replacement for a verified
state-home pointer and not permission to modify hosts. The explicit writer
fence remains a separate recovery-control obligation.

## Staged migration identity evidence

`RelocationAuthorization` distinguishes
`source_writer_host_id` (Venus, current owner) from
`writer_host_id` (Artemis, the proposed next owner). The existing
`stage_verified_state_home` passes **Venus** as the source of its encrypted
backup and verifies that the authenticated backup manifest reports the same
source. The pending writer pointer still names **Artemis** and the approved
next epoch. Any mismatch aborts staging before restoration. A trusted host
controller must still independently verify the exact physical source,
exclusive writer fence, operator consent and destination, as before.

This is evidence correctness, not permission to stage production data,
promote a pointer, restart Venus or activate Artemis.

## Verification deferred

Tests are written for missing/bad role and host IDs, unauthorized workers,
missing pinned-mTLS transport, local or alternate-model fallback,
automatic provisioning and missing GPU requirements. User requested all test
execution and physical device acceptance at the end of development.

Status: **coded as a dormant future-role safety gate. Not enabled or
deployed on Artemis or Venus.**
