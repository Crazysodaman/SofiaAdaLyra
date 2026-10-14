# V18 next 50: operator experiences and canonical hosting (CA-4701–5408)

Design reviewed 2026-10-13. Existing software may implement a subset; no host run, owner enrollment, live transfer, or complete task acceptance is asserted.

## CA-4701 | User-facing memory correction
A memory card requires fact/classification, exact original source and principal/audience, first-seen and last independently confirmed time, confidence origin, corrections, used-by decision IDs and retention/erase state. Controls are *inspect*, *propose correction*, *request private-only*, *forget* and *show affected decisions*. Every edit must pass the same SAFE and MEM durable boundary as existing canonical stores, never only hide a UI row. On forget, old retrieval, embeddings, cached prompt and reminders must stop using revoked material; separately retained originals require explicit policy. Missing: complete UX plus end-to-end erasure/replay receipt on actual hosts.

## CA-4702 | Portable device handoff
Authenticated device pairing (separate credentials) may expose only an audience-allowed thread. Before `continue here`, display source device, target device, principal, audience, transport, pending drafts and last-read. Handoff changes delivery routing, *not* ownership/permissions or message ancestry. Local-only mode cannot leak history to other channels. Revoke while a message is queued, reconnect offline, duplicate acknowledgment and channel switch are mandatory negative cases. Missing: supervised live mobile + desktop handoff.

## CA-4703 | Isolated research notebooks
Hephaestus notebooks must pin hypothesis, image/OS, source asset license, exact sandbox identity, resource/authority budget, planned procedure, criterion, observed measurements, independent checker, failed controls, restart/teardown receipt and disposition (confirmed/refuted/inconclusive). Use existing LIFE and DEV store owners; a markdown notebook is an explanatory projection, never authority. Scrub private raw data before export. Missing: guest provisioned and fenced operational experiment.

## CA-4704 | Model placement experiment
Freeze equal workloads and compare fast model, deep model and authenticated remote model by independent task success and p50/p95, estimated tokens, GPU load/unload cost, VRAM footprint, CPU/RAM and concurrent gaming impact. While gaming on Venus, never initiate keyboard/mouse automation and release discretionary GPU inference; after independently observed >=30 minutes idle, optional models may be loaded under budget/permission controls. No silent provider fallback and no third-party/other-machine inference without approved discovery. Missing: real gamer-active/idle mixed-host results.

## CA-4705 | Homelab digital-twin scope
Read-only observations from Artemis/Eos/Hestia are tagged observed_at, hostname, source capability, freshness, identity and scope; simulated topology changes are typed `simulation`, never `actual`. Compare predictions with independently observed metrics before recommending action. Do not write VM/switch/router state from model inference. Missing: trustworthy signed per-host observation and approved isolated simulation replay.

## CA-4706 | Research and supply-chain provenance
Pin dependency/version/digest/license, maintainer-source URL and retrieval date, vulnerability/security patch evidence and next audit date. For papers/datasets: immutable citation, license, user-consent scope and contamination/replication method. For software experiments: admission proof, artifact SHA, independent reviewer, stop conditions and deletion fate. Any upstream claim not checked against source is marked `unverified`. Missing: continuous signed manifests and bounded scheduled review on both Windows and Debian.

## CA-5401 | Approved present topology
Option A: Sofía services on current Windows/Linux. Venus remains one canonical `sofia.db` writer, while Artemis hosts Fleet/VM infrastructure. Future guest named Sofia runs Debian 13 for runtime, memory and scheduling *only after* protected cutover; Venus remains GPU inference source over authenticated network. No split-brain, no autonomous DB migration. This is a record of owner's approved architecture, not live-state proof.

## CA-5402 | Cross-platform service shape
Common authenticated contracts: `timeline.list/append`, `memory.search/review`, `asset.preview`, `tool.propose/execute`, `grant.inspect`, `job.status/receipt`, `runtime.health`. Each includes schema version, canonical principal and audience, capability name, effect class, expiration, idempotency key, state revision and independent receipts. Use typed Windows/Linux drivers beneath the contract. No alternate SQLite writer embedded in client.

## CA-5403 | Deferred appliance packaging
Option B is an **appliance packaging** for the same identity and processes, not a cloned personality/second Sofía. Must reuse constitution identity, authenticated device registry, journals and canonical primary DB after writer fencing. Preserve revert to Venus as an explicit signed recovery action; never run two primaries.

## CA-5404 | Appliance entry criteria
All required before B promotion: exact SHA pinned CI and wheel/provenance; true boot/shutdown; durable LIFE create/evaluate/revise; cross-device history and privacy; independent 2-snapshot backup and restore; mTLS Fleet; STOP + protected RESUME; CPU/RAM/VRAM budgets; supervised 7-day mixed workload soak; measured RPO/RTO, safe recovery and independent owner approval. Any unavailable evidence = not ready.

## CA-5405 | Artemis host versus dedicated hardware
Compare failure domains: power/UPS, one hypervisor outage, storage durability/SSD writes, RAM reservations, inference GPU availability, heat/noise, encrypted disk recovery, mTLS topology, snapshot scope, network outage and total cost. Quantify workload and recovery on real devices. A VM does not magically survive Artemis being powered off; separate dedicated hardware remains an option when measured availability warrants it.

## CA-5406 | Verified boot/release/rollback
Pinned Debian base and signed release artifacts; independent deploy controller on Artemis Windows host; staged verified candidate, fenced canonical writer, health check, persistent state identity, two-slot application rollback and protected key recovery. Roll back code without rolling back erasure/privacy and without replaying uncertain external actions. A failed state promotion must preserve exactly one writer, append-only proof and operator STOP.

## CA-5407 | Duplicate overhead control
Record per-host model residency, polling workers, CPU/VRAM, RAM, SQLite writes and duplicate jobs under A and A+B paired measurements. The new guest should not load a second permanent LLM, create an independent SAFE authority or mirror unsynchronized writers. Use sleep/unload for optional inference; prefer remote GPU via authenticated connection under gaming priority. No made-up overhead savings before benchmark.

## CA-5408 | Custom-kernel proposal deferred
A true new OS kernel is explicitly outside the active scope. Reconsider only after a reproducible capability gap impossible through stable Linux/Windows driver, hypervisor and isolated-worker APIs, backed by threat model, maintenance/driver matrix, resource cost and independently approved design. **No link between implementing an OS kernel and consciousness or improved intelligence is assumed.**

### Acceptance record
These 14 entries are design decisions with measured acceptance requirements. The operating-layer topology has *not* been migrated, no remote privileged access was used, and no extra trusted credentials or processes were created.
