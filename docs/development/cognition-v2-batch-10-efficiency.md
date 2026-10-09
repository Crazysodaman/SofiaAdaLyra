# Cognition v2 Batch 10 efficiency evidence

Measured on the same deterministic CI-host scenarios as the Batch 1 baseline.
These measurements cover application/Matrix/NEURO/context/persistence overhead;
they do not pretend to be live Ollama or GPU evidence.

| Measure | Batch 1 | Batch 10 observed |
|---|---:|---:|
| Startup wall time | 441.129 ms | 493.596 ms |
| Casual turn wall time | 38.979 ms | 43.155 ms |
| Technical turn wall time | 33.768 ms | 43.893 ms |
| Fleet-status turn wall time | 35.373 ms | 47.799 ms |
| Multi-turn follow-up wall time | 51.016 ms | 46.682 ms |
| Idle 250 ms process CPU | 0.070 ms | 0.068 ms |
| Peak RSS | 72,855,552 bytes | 73,465,856 bytes |
| SQLite API operations | unavailable | 109 queries / 4 writes |
| Runtime HotState | unavailable | 3 hits / 1 miss |

The additional startup and most turn cost is an accounted tradeoff across the
completed v2 production pipeline: durable Turn Kernel/focus/evidence/goal
coordination, NEURO refresh, KNOW indexing, and the first WAL setup now execute
in this same path. Batch 10 itself removes repeated WAL negotiation, bounds
repair history, caches immutable operational projection, and makes the
remaining database work measurable. The follow-up scenario improved in this
single matched observation, while idle CPU remained essentially unchanged.
Single observations are not stable percentiles and no improvement percentage
is claimed.

Model-side allocation is now bounded before inference: FAST 2,048,
STANDARD 4,096, DEEP/OPEN 8,192, and VERIFY 16,384 context-token targets,
always capped by operator configuration. Prompt/generated token counts,
inference/load duration, GPU/VRAM, residency, and real dual-model overlap were
not available from the deterministic test provider. The production Ollama
adapter records those values when the provider supplies them; missing sensors
remain `unknown`.
