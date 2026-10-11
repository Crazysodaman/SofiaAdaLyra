# Sofía's evidence-grounded homelab digital twin

## Why this is the first useful fidelity

Current production scope is **`dependency_graph_v1`**. It reads known, **trusted** canonical OPS Fleet hosts and only owner-declared dependencies from `sofia.db`. It never scans the LAN or derives dependency edges from a shared switch or IP prefix.

The alternatives remain explicit and unavailable:

| Fidelity | Useful question | Current boundary |
|---|---|---|
| Reviewed dependency graph | Which *declared* hosts might be affected by a hypothetical DNS, disk or service fault? | Implemented, strictly synthetic |
| Disposable Docker replicas | Does a service recover from a simulated container crash? | Not installed or proven isolated; requires pinned images, verified worker, separate approval |
| Full VM replicas | Does a guest OS recover from a simulated boot/disk failure? | Not available until the actual OS-less Hephaestus VM has a verified guest, snapshot and isolated runner |

A result from the dependency graph is **never** evidence of packet reachability, container health, actual host failure or guest OS behavior.

## Production routes

**Tray Settings → Fleet → Homelab Digital Twin** can inspect trusted OPS host IDs, review explicitly declared links (dependent → prerequisite), and model a failure scenario. The system keeps those links in the canonical `ops_twin_reviewed_dependency` table, only after a deliberate owner UI decision.

The existing cognitive OPS capability layer exposes:

- `ops.digital_twin.inspect`: read sources, uncertainties, fidelity options, Gaia/JMRI physical-action limits
- `ops.digital_twin.simulate`: bound synthetic failure propagation to a verified existing Fleet host and one predefined scenario

Both are SAFE Level 1 and have **no host mutation, network scan, Fleet enrollment, database schema authority or physical robot/railroad action**.

## Scenarios and explicit assumptions

Predefined synthetic scenarios are DNS outage, Fleet agent unreachable, disk pressure, SQLite locking, container crash, stale clock, bad weather sensor and conflicting node identity.

For each scenario, **only matching reviewed edge types** propagate hypothetical impact. E.g., a DNS outage may propagate along `dns` edges, but not automatically through a `service` or `storage` edge. Unknown edges stay unknown; no inference of unrestricted homelab connectivity occurs.

An observation without telemetry or with telemetry older than 30 minutes is reported stale/missing. If the source is out of bounds, a hypothesis cannot be independently falsified, repeated attempts fail without learning, or compute would displace responsiveness, the experiment receives **`ABANDON_RESEARCH`**. Otherwise it remains **`REVIEW_SYNTHETIC_ONLY`**. Neither permits real work.

## Reproducibility and evidence

Each synthetic experiment writes an immutable-by-API, bounded `ops_twin_experiment_capsule` record in canonical `sofia.db`, with:

- Source Fleet snapshot SHA-256, host timestamps, exact reviewed dependency receipts
- Exact scenario and target host, deterministic algorithm version and seed
- Bounded evaluator, modeled affected hosts, stale/unknown telemetry and abandonment reason
- Output SHA-256, checked when read, and an explicit **`NOT EXECUTED`** real-world action field

Simulation does not create arbitrary proof artifacts or verified acceptance receipts.

## Gaia 2.0 and JMRI boundaries

For **Gaia**, virtual 3-DOF geometry, nominal gait and support polygons can be explored in research; actual servo deadband, mixed 180°/continuous rotation calibration, power, current draw and SSC-32 latency remain unmeasured until independent sensors/calibration. *Simulation output may not send physical servo pulses.*

For **JMRI**, a fictional route or roster study is not the same as verified occupancy, switch position, track power or actual loco control. Read-only roster/occupancy needs an approved, authenticated observation source; track power, turnouts and movement have separate authority requirements.

## Operational limits

The dependency graph is bounded to 64 trusted hosts and 128 reviewed edges. Capsule history is bounded to 32. Unknown identity, stale observation, malformed inputs, oversized graphs, unsupported scenarios, cross-namespace requests and invalid signatures/receipts are rejected or explicitly labeled unknown.

No Hephaestus OS installation, Docker clone, VM clone, Gaia actuator command, JMRI command, tests or live host action were performed when this code was authored.
