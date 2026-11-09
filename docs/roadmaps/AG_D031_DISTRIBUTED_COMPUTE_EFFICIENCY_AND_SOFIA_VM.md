# AG-D031 | Sofía VM + cross-host compute efficiency (design TODO)

**Captured:** 2026-11-09  
**Status:** OWNER-DESIRED / CAPTURED / NOT SCHEDULED / NOT IMPLEMENTED OR BENCHMARKED.  
**Owner intent:** Sofía Core moves to a VM on Artemis; inference and other GPU-intensive workloads run on Venus and another independent computer through enrolled Aegis Platforms. Minimize wasted VRAM, host RAM, CPU time, GPU time and unnecessary power or model duplication. This document is a TODO, not authorization to move Sofía, deploy code, enroll nodes or run hardware tests.

## Intended topology

- **Artemis:** Windows virtualization host, runs the future Sofía VM, which holds the Core and its canonical state. The VM is not assumed to have GPU passthrough. Distinguish VM memory from parent-host memory and all other co-hosted VMs.
- **Venus:** Windows 11 desktop with i7-9700K, 32 GB system RAM and RTX 3080 Ti 12 GB VRAM; a shared interactive/gaming machine, not guaranteed spare GPU capacity. Aegis Platform acts as an independently enrolled compute node.
- **Third computer:** separate Aegis Platform compute node; exact CPU, GPU, RAM, VRAM, OS, model support and availability **not yet specified**. Do not invent hardware capability or assume a second GPU until measured.
- **Fleet coordination:** the VM/Core sends bounded requests to a Platform-authorized inference service on an approved enrolled compute host. Remote GPU VRAM cannot be pooled transparently with VM RAM or with a second GPU; multi-node execution is workload placement, not free unified memory. Keep Core identity, canonical memory and privileged operations out of untrusted inference/agent subprocesses.
- **AG-D028:** one primary Artifact Library/LAN Hub is planned on the Sofía VM with independently governed Core/Platform separation; approved model artifacts can be distributed via authenticated, content-verified Hub/peer workflows. Distribution must not imply auto-installation or auto-activation.
- **AG-D029:** optional Pi/Goose harness and native llama.cpp inference research remains a separate proposed provider implementation. Do not couple the VM migration to one mandatory agent or backend.

## Efficiency rules to design, not yet accepted or benchmarked

1. **One owner of compute scheduling:** Aegis Platform/Fleet remains sole budget, lease, identity, SAFE/STOP and admission authority; Ollama/llama.cpp/Pi/Goose remain bounded workers, never autonomous competing schedulers.
2. **Real resource admission:** place a model only after fresh per-host telemetry covers free RAM, free VRAM, GPU/CPU pressure, desktop/gaming activity, model digest and required context. Budget model weights **plus** KV cache, compute buffers, allocator overhead, runtime processes and a configurable safety margin. Do not use nominal GGUF file size alone as an exact VRAM requirement.
3. **VRAM residency:** count distinct physical model assets once even if reused across multiple logical roles; keep only the minimum needed model resident. Use cold/on-demand, warm/short TTL and bounded scheduled preload profiles. Reclaim unused models under desktop/game pressure, but never kill active sessions to optimize an idle metric.
4. **Avoid hidden duplication:** audit Ollama vs native worker model copies, duplicate agent inference servers, tokenizer/context caches, OS page-cache interpretation, same-host per-role replicas, unnecessarily pinned CPU memory and repeated model downloads.
5. **Compute arbitration:** assign foreground interactive work priority on Venus; selectively route inference to the other node only after genuine suitability checks; avoid extra CPU offload and cross-host transfers when net performance/power is worse. Limit model concurrency and prevent excessive parallel KV contexts.
6. **Core VM footprint:** run Core orchestration and canonical persistence independently of GPU workers; cap VM vCPU/RAM against Artemis' other VMs. Avoid busy-poll loops, duplicate scheduler workers, aggressive heartbeat frequencies, unnecessary background inference and heavy model weights inside the VM.
7. **Stable power and thermal operation:** distinguish truly idle resident model memory from idle GPU compute/power use. Use duty cycle and actual energy measurements; don't claim that nonzero VRAM means nonzero compute or that high utilization always indicates waste.
8. **Failure and safety:** network outage, host shutdown, missing telemetry, gaming pressure or STOP must produce truthful unavailable/deferred outcomes, a bounded failover only where owner-approved, and no unauthorized local CPU inference or cloud routing.

## Future acceptance and measurements (not performed)

- **Host matrix:** (A) Artemis VM/Core only; (B) Venus gaming/non-gaming; (C) third host measured independently; (D) concurrent Venus + third-host tasks; (E) host/Fleet disconnection and STOP. Require an explicitly approved test environment for each.
- **Per process and host:** idle/loaded CPU%, resident RAM (RSS), host free memory, per-GPU used/free VRAM, GPU utilization, power (W), temperature, swap/page faults, model load/unload and counts, per-role KV/context allocation, competing foreground latency, network traffic and model/artifact cache storage.
- **Per workload:** time-to-first-token, prefill/decode tokens/s, p50/p95 end-to-end latency, total energy per completed job, quality/correctness/tool-call outcomes, cold vs warm starts, model churn and rejected placement decisions.
- **Acceptance comparisons:** compare existing Ollama and tested native llama.cpp only with the same model bytes/quantization, context, prompts and machine when supported. Compare on-demand vs warm and single vs concurrent workloads. Report tradeoffs; do not assign an efficiency percentage from source review alone.
- **Open question:** third computer's actual specifications and desired gaming priority, VM RAM/vCPU allocation, concurrency and acceptable model wake latency need explicit owner inputs before locking resource budgets.

## Related design and release fences

- [AG-D028 Artifact Library](AG_D028_AEGIS_FEDERATED_ARTIFACT_LIBRARY.md)
- [AG-D029 inference and agent alternatives](AG_D029_AGENT_AND_INFERENCE_ALTERNATIVES_2026-11-09.md)
- [AG-D030 model landscape](AG_D030_AI_MODEL_LANDSCAPE_2026-11-09.md)
- Existing lifecycle foundation: `src/sofia/core/cognition/model_lifecycle.py`, `src/sofia/platform/config/model.py`, `src/sofia/platform/ops/placement.py`, `src/sofia/platform/ops/local_telemetry.py`.

**FENCE:** Do not amend Platform 1.0 issue #201, add a release gate, reassign an executor, modify runtime defaults, enroll Fleet hosts, execute a migration, benchmark real hardware or claim performance validation by merely adding this TODO. Owner scheduling/approval is a separate decision.
