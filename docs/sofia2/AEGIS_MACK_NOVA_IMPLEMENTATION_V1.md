# Aegis Mack / Nova Inference, Management and Lifecycle V1

**Status date:** 2026-11-17  
**Workstream:** Aegis E/F — inference routing, management, lifecycle integration,
documentation and disposable acceptance  
**Branch:** `aegis/mc-inference-lifecycle`  
**Baseline:** `main` at `cc225f6f`  
**Evidence class:** local source and simulated-fixture tests only. No real
Ollama process, model download, installed Core package, host deployment, voice
asset or avatar renderer was used.

## Implemented source modules

- `sofia.core.multicore.inference`
  - Exact per-Core binding over `sofia.platform.inference`:
    `(core UUID, Platform, generation, conversation)`.
  - Independent per-Core prompt/context assembly with generation fencing.
  - Explicit per-Core model selection from an authorized exact-model map.
  - One shared backend with fair per-model queues, global bounded dispatch,
    cancellation, deadlines, failure and uncertain-outcome evidence.
  - Text-only requests; explicit provider/model/digest provenance on results.
  - Restart journal for registrations, bindings, context snapshots, results,
    failures and unfinished work.
- `sofia.core.multicore.management`
  - Read/registration/display adapter over actual definition, installation and
    runtime evidence.
  - Expected owner-facing identities: Sofía, Mack and Nova.
  - `installed` and `active` are reported only from explicit evidence;
    unverified, stale or generation-mismatched evidence becomes `unknown`.
  - Owner-visible participation, notification and STOP control seams.
  - A Core-free Platform is a valid healthy snapshot.
- `sofia.core.multicore.acceptance`
  - Disposable definition and asset fixture under a caller-owned temporary
    directory.
  - Path: definition -> registration -> authorized activation ->
    identity/constitution/memory load -> channel routing -> injected text
    inference -> persistence -> simulated restart/recovery.
  - Missing voice or avatar metadata never blocks the text path.

## Security boundaries

- Platform/Fleet admission is still authoritative; this layer does not enroll
  hosts, reserve GPU resources or grant execution authority.
- SAFE/STOP gates deny submission, dispatch and owner controls when active.
- No cloud fallback, CPU/model substitution or implicit download is attempted.
  A backend that returns a different model is rejected rather than relabelled.
- Conversation context is keyed by exact Core, Platform and generation. A
  stale generation cannot read, append, submit or cancel against a newer one.
- Management never converts a definition, registration or process claim into
  installed/active evidence without the matching explicit runtime record.
- Acceptance stages fail closed on missing definitions/assets, identity
  mismatch, foreign memory ownership, denied authorization or operator STOP.

## Verification performed

Focused local suite:

```text
test/test_core_multicore_inference.py
test/test_core_multicore_management.py
test/test_core_multicore_acceptance.py
23 passed
```

Related shared-inference regressions:

```text
test/test_platform_shared_inference_identity.py
test/test_platform_shared_inference_scheduler.py
test/test_platform_shared_inference_capacity_gaming.py
39 passed
```

## Limitations and deferred gates

- No real Ollama provider, model installation, GPU residency, power or gaming
  impact measurement was performed.
- No real Core package was installed, signed by a production key, launched as a
  process or allowed to own durable protected state.
- The restart journal is in-memory for these fixtures; a production durable
  journal must be supplied by the owning Platform state authority.
- Management sees only definitions returned by its configured source. It does
  not scan arbitrary hosts for unknown Core identities.
- Voice assets, prosody and avatar/embodiment rendering are deferred. Text
  inference is intentionally independent of their presence.
- Installation, activation on a real host, service recovery after reboot,
  rollback, multi-host scheduling and owner-approved commissioning remain
  installation gates and are not claimed complete by this document.
