# V18 Workstream 4 source-audit and implementation handoff

**Date:** 2026-10-11. **Branch:** `main` only. **Scope:** 182 original CA IDs, phases 11-16. **Tests/CI/live acceptance:** deferred by operator instruction.

This is a **coding-only checkpoint**, not a 182-task completion claim. The original V18 master, AGENTS.MD, ROADMAP.md and shared evidence ledger were read. The exact original IDs and first-pass evidence findings are preserved in [the workstream-specific 182-ID register](v18-workstream4-task-evidence.json). The global `v18-task-evidence.json` and ROADMAP are coordinated elsewhere; neither was overwritten here.

## Source-status snapshot

| Phase | IDs | Status of production integration |
|---|---:|---|
| 11 Resource and model selection | 49 | Real dual-model routing/residency exists; default startup model pulls disabled; telemetry fail-closed. Model promotion end-to-end host broker and benchmarking still open |
| 12 Screen vision | 24 | Screen permit/receipt library only; **no proven interactive OS picker-to-perception path** |
| 13 Hephaestus digital twin | 63 | Admission policy only; **no proven governed VM execution endpoint** |
| 14 Model training | 12 | Adaptation manifest policy only; **no approved training worker** |
| 15 Connectome NEURO | 22 | Competition integrated into canonical NEURO attention; durable diagnostic receipt and deterministic fallback; association persistence, UI disable, experiments outstanding |
| 16 Consciousness research | 12 | Research preregistration/self-model library; no validated experiment runner or scientific proof of subjective consciousness |

**182 unique IDs:** 2 production-path code candidates requiring tests, 6 inspected partial implementations, 3 policy/research-only foundations, 171 phase-inventoried but not individually source-traced. **Zero source tasks accepted.** The 171 are not assumed to be missing. Every task still requires its exact source-to-effect audit and the later verification campaign. A checklist count must not pretend to be a coding percentage.

## Production code commits

- [`3813b31`](https://github.com/Crazysodaman/SofiaAdaLyra/commit/3813b31fc83163048b8aa1a9b5f3e9efdbe14f59): `SofiaApplication`'s shared `NeuroRuntime` now uses the existing `CircuitCompetition` on bounded TTL-filtered eligible activations, guards explicit turn focus, retains deterministic arbitration, and persists algorithm/explanation with the real observed snapshot. Added unexecuted tests.
- [`57da413`](https://github.com/Crazysodaman/SofiaAdaLyra/commit/57da4138f1e9545ad96067ce78d50fb12d8bd1dc): no startup `install_missing` invocation, fresh/legacy auto-install setting defaults off, invalid local CPU/RAM/GPU/VRAM and observer failures interpreted conservatively by production residency manager. Added unexecuted tests.
- [`b7fcec5`](https://github.com/Crazysodaman/SofiaAdaLyra/commit/b7fcec5b4a0edc9bd347d5d26821458a3862fb22): unexpected engineered circuit backend failures fall back to salience. Added unexecuted regression source.

**NEURO end-to-end route:** `src/sofia/application/bootstrap.py` constructs one `NeuroRuntime` and `NeuroObservabilityStore`; `NeuroInputCoordinator` and conversation feed actual signals/turns; `NeuroRuntime._snapshot_unlocked` calls the existing `CircuitCompetition`; focus enters `NeuroStateSnapshot` consumed by conversation, adaptive routing and optional background priority; `NeuroObservabilityStore.record` persists current snapshot metadata. **It does not grant actions, use actual anatomical neuron graphs, or assert consciousness.**

**Model lifecycle route:** `src/sofia/composition/engines.py` creates `ModelLifecycleManager` with local OPS telemetry and optional host activity; the runtime calls `reconcile_residency` and uses the manager around role inference; `SofiaApplication.start` no longer requests automatic model pulling. The explicit low-level `install`/`install_missing` APIs still exist for future separately authorized workflows, but are not called from production startup. Existing saved settings values are not forcibly rewritten.

## Exact blockers and next slices

1. **Phase 11:** Benchmarked host CPU/GPU/RAM/VRAM, p50/p95 turn latency, model load/unload receipts and 7-day soak; independently authorized role-swap broker with in-flight settlement, health receipt and rollback; per-feature optional-autonomy token/energy and background budgets. Never let a model self-authorize installation or promotion.
2. **Phase 12:** Windows.Graphics.Capture picker in the interactive user session and Hyprland ScreenCast portal/PipeWire helper, exact target binding, protected-window and lock-screen fail-closed behavior, local visible indicator, watch expiration, untrusted screenshot handling, output-channel disclosure policy, source-verified image interpretation. No automatic/invisible capture or invented observations.
3. **Phase 13:** Operator-selected hypervisor host and Hephaestus guest identity, signed installer handoff, isolated network, separately approved hypervisor-side bootstrap, attested guest enrollment, bounded RUN receipts, real image/snapshot rollback and live isolation tests. An empty guest cannot self-provision without a trusted external bootstrap authority. No privileged VM changes were made.
4. **Phase 14:** Operator-approved datasets and privacy/license attestations; no raw lifelong chat or screenshot use by default; bounded GPU and storage reservations, isolated training process with deterministic dataset/seed/holdout, independently evaluated resulting adapter and explicit model promotion gate. No training performed.
5. **Phase 15:** Canonical audience-scoped optional associative memory only after MEM permission and correction filtering, bounded durable provenance/rollback, real host ablations against deterministic salience, persisted owner disable in the existing UI, negative-result reporting. Scientific fly data not bundled or simulated as a full brain.
6. **Phase 16:** Falsifiable hypotheses separated into agency, global broadcast/access, self-model calibration and *unverified* phenomenal experience; controlled preregistration, independent review, bounded comparative studies, negative result persistence and limitations. No consciousness finding can be produced by implementation status alone.

## Release/verification handoff

No tests or CI were run. Relevant unexecuted source tests include `test/test_neuro_circuit_production_wiring.py`, `test/test_model_lifecycle.py`, `test/test_production_dual_cognition.py`, `test/test_runtime_user_settings_defaults.py`; existing broader NEURO, model lifecycle, app startup and Windows acceptance must be run in the separate verification campaign. No Ollama model was installed, no VM created, no screen captured, no dataset trained, and no host or canonical writer role changed.
