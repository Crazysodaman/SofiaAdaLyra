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

## Batch 12 final control-path observation

The matched deterministic measurement at base revision `9a2a43e` observed
480.393 ms startup; 44.012 ms casual, 44.386 ms technical, 43.630 ms Fleet,
and 49.825 ms follow-up turns; 0.062 ms process CPU during a 250 ms idle window;
73,310,208 bytes peak RSS; 109 SQLite queries, 4 writes, 1 cache hit, 1 miss,
and zero model calls. The temporary database contained 8 messages, 4 completed
traces, and occupied 118,784 bytes. This is a single Linux CI control-path
observation, not a percentile or live-Ollama claim. GPU load, VRAM, tokenizer
counts, model residency, and real Primary/Secondary inference remained
unavailable and therefore unknown.

## Phase 1 correctness observation

The matched deterministic measurement after multi-request correctness work
observed 479.127 ms startup; 41.804 ms casual, 40.386 ms technical, 41.110 ms
Fleet, and 45.072 ms follow-up turns; 0.059 ms process CPU during a 250 ms idle
window; 74,158,080 bytes peak RSS; 109 SQLite queries, 4 writes, 1 cache hit,
1 miss, and zero model calls. Against the single Batch 12 observation this run
was lower in every recorded latency sample, while peak RSS was 847,872 bytes
higher. These are individual CI-host observations, not stable percentiles or
proof of a performance improvement. Live tokens, GPU/VRAM, model residency,
and Primary/Secondary latency remain unmeasured here.
