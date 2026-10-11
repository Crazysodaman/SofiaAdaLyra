# Sofía canonical runtime and GPU inference topology

**Owner decision:** 2026-10-11. **Deployment status: design approved in principle; no state move, host change, model installation, enrollment or live verification performed.**

## Two-stage location decision

| Concern | Now | Operator-approved future |
| --- | --- | --- |
| Canonical Sofía runtime and sole active `sofia.db` writer | Venus | Artemis (specific Windows host vs Artemis VM to be selected) |
| Durable memory, GOALS, LIFE, SAFE, ACT and production state | Venus | Artemis, on one host-local filesystem with exactly one fenced writer |
| GPU-dependent primary/secondary inference | Venus's existing NVIDIA GPU | Venus as a separately enrolled, approved Fleet inference worker |
| Desktop UI | Venus | Venus as authenticated client to Artemis; it must not open a competing state DB |
| Protected credentials, identity and state-home pointer | Current Venus canonical home | Verified operator-controlled migration; never copy secrets into broad SMB shares |
| CPU-only noncognitive tasks | Existing authority/policy | Artemis can run them; never imply it can run the absent GPU model |
| Fallback if Venus inference is offline | Existing explicit model policy | Report provider/remote cognition unavailable; retain conversation/state and permitted deterministic work, **no automatic model fallback or unreviewed local CPU inference** |

The runtime and the language-model inference engine are separate. Artemis does **not** need a GPU for the canonical runtime/database. Venus's RTX-class GPU can serve approved models over the existing Fleet remote inference transport; **do not expose an unauthenticated Ollama API/11434 to the LAN or Internet**. The existing `ConfiguredRemoteInferenceClient` and `DurableRemoteInferenceControl` require enrolled identity, pinned mutual TLS, a fresh advertised `llm.inference` capability and exact grant. Model-management rights stay separately scoped; `auto_provision_models=false` is the safe migration default.

## Source-backed components reused, not reimplemented

- Runtime composition: `src/sofia/composition/root.py` and `engines.py`.
- Actual remote cognition: `src/sofia/cognition/fleet_engine.py` and `src/sofia/distributed/inference_client.py`.
- Fleet placement policy: `FleetCognitionConfiguration` and `WorkloadContract`; approval must use the **observed Fleet host ID for Venus**, not merely a display name, and `gpu_required=true`, `local_fallback=false`, `auto_provision_models=false`, `allowed_host_ids=(<verified Venus host ID>,)`.
- The source fix on `main` makes `create_model_lifecycle` skip local Ollama management on the explicit remote-only canonical host while retaining lifecycle management where the same host is an eligible local inference provider.
- Staged relocation: `src/sofia/ops/state_mobility.py`, `state_relocation.py` and `state_promotion.py`; this is staging and operator handoff, **not a completed privileged fencing/promotion broker**.
- Signed location bootstrap: `src/sofia/config/state_home_pointer.py`. Its HMAC and epoch checks are not independently sufficient to fence a disconnected old writer.
- Encrypted state snapshot/restore: `src/sofia/ops/backup.py`, including canonical `sofia.db`, identity and other protected assets; do not simply copy open SQLite files/WAL over SMB.

## Staged migration requirements

1. **Preflight only:** inspect exact Venus/Artemis machine and Fleet IDs, choose Artemis Windows host or a VM, check disk location, permissions, network link, throughput, resources, mobile/desktop client routing, model availability, and encrypted independent backup capacity. The destination SQLite must be on an approved **host-local filesystem**, not a live SMB share.
2. **Trust and capacity:** enroll Venus as an authenticated remote inference worker before moving the writer; preserve exact allowed primary and secondary models; verify pinned certificates, capability adverts, host identity and no unapproved download. The Artemis process must not need a GPU just to boot or read state.
3. **Operator-approved offline handoff only:** stop the active Venus writer; fence all old clients/writers; take/verify an encrypted consistent snapshot and full asset manifest; stage/verify Artemis restore; independently protect keys and witness writer epoch. Never promote a copy while Venus may still write.
4. **Privileged broker validation:** check exact intended destination writer host, old source host and witness, external epoch floor, approval nonce, health/schema/identity and optional rollback. Existing `state_promotion.py` explicitly does **not** implement this last host-privileged broker.
5. **One-time activation:** make the signed, host-bound pointer active on Artemis and start **one** canonical service. Venus becomes UI and GPU inference only; its old `sofia.db` is an archive, **never another live writer**. Desktop, Discord and future Android clients rebind through authenticated application APIs.
6. **Degraded-state tests:** Venus GPU worker unavailable => deterministic cognitive unavailable response, not a silent provider substitution; Artemis offline => Venus UI cannot silently resurrect the old state; reconnect => single-writer reconciliation and operator-reviewed restoration.
7. **Only after acceptance:** compare actual response latency, provider traffic, CPU/RAM, outage behavior, backups, recovery times and double-writer prevention. Run full unit/integration/Windows/Fleet tests in the user's deferred campaign, not as part of this coding handoff.

## Unresolved owner inputs

- **Artemis installation boundary:** Windows host service vs a dedicated VM on Artemis. The choice determines local state root, OS-bound secrets, service launcher, firewall and restore/fencing workflow.
- **Standby objectives:** desired maximum acceptable data loss and downtime (RPO/RTO); do not invent numbers.
- **Authenticated operator identity and independent fencing witness:** the current literal actor label is not human authentication, and stage-only helpers cannot be misrepresented as live failover.
- **Exact source and destination Fleet host IDs / addresses:** must be discovered and approved, not guessed or put into code as hardcoded network addresses.

No live host changes or permission grants are authorized by this document.
