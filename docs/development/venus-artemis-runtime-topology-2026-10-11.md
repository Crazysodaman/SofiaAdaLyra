# Sofía canonical runtime and GPU inference topology

**Owner decision:** 2026-10-11. **Deployment status: design approved in principle; no state move, host change, model installation, enrollment or live verification performed.**

## Two-stage location decision

| Concern | Now | Operator-approved future |
| --- | --- | --- |
| Canonical Sofía runtime and sole active `sofia.db` writer | Venus | **Dedicated Hyper-V VM named `Sofia` on Artemis** |
| Durable memory, GOALS, LIFE, SAFE, ACT and production state | Venus | VM `Sofia`, on a guest-local persistent filesystem with exactly one fenced writer |
| GPU-dependent primary/secondary inference | Venus's existing NVIDIA GPU | Venus as a separately enrolled, approved Fleet inference worker |
| Desktop UI | Venus | Venus as authenticated client to Artemis; it must not open a competing state DB |
| Protected credentials, identity and state-home pointer | Current Venus canonical home | Verified operator-controlled migration; never copy secrets into broad SMB shares |
| CPU-only noncognitive tasks | Existing authority/policy | VM `Sofia` can run them; never imply it has access to a physical GPU |
| Fallback if Venus inference is offline | Existing explicit model policy | Report provider/remote cognition unavailable; retain conversation/state and permitted deterministic work, **no automatic model fallback or unreviewed local CPU inference** |

The runtime and the language-model inference engine are separate. Artemis does **not** need a GPU for the canonical runtime/database. Venus's RTX-class GPU can serve approved models over the existing Fleet remote inference transport; **do not expose an unauthenticated Ollama API/11434 to the LAN or Internet**. The existing `ConfiguredRemoteInferenceClient` and `DurableRemoteInferenceControl` require enrolled identity, pinned mutual TLS, a fresh advertised `llm.inference` capability and exact grant. Model-management rights stay separately scoped; `auto_provision_models=false` is the safe migration default.

## Dedicated production VM versus experiment VM

- **`Sofia` is the reserved canonical runtime VM name on Artemis.** This VM is a single protected production authority, not a scratch guest. It must have its own guest identity, OS-managed credential store, local state disk, service account and authenticated application endpoint. Hyper-V host is a separate privilege boundary; the guest must not inherit unrestricted host admin power.
- **The existing/proposed testing VM remains separate.** The earlier workshop concept calls that lab **Hephaestus**; retain that as a proposed role/name only until its actual enrolled VM ID is checked. It can host builds, disposable experiments and synthetic tests, never a second writer of production `sofia.db`.
- Workshop guests use isolated networking by default and have no direct production state disks, raw `sofia.db`, protected runtime keys, writer-epoch keys, host Hyper-V admin identity or production backup decryption secrets. A synthetic or sanitized test fixture does not convey canonical authority.
- `src/sofia/ops/workshop_policy.py` now rejects a lab experiment naming its guest `Sofia` (case-insensitive), in addition to existing budget, image hash, operator approval and isolated-network constraints. It is an **admission check**, not permission to create a VM or to start/stall a real host.
- The existing production `HyperVAdapter` is reused by **local** `hyperv.vm.start/stop` and **remote** Fleet `vm.manage.start/stop`. It now refuses to start or stop VM `Sofia` (case-insensitive), including forced stop, through these general-purpose tool paths. Read-only discovery remains available. An independently authenticated, privileged hypervisor maintenance/cutover broker is needed for canonical VM lifecycle operations; model-facing Level-3 approval alone does not grant that role.
- These VM roles can coexist on Artemis, but their scheduling, resource limits, security policy, operator approvals and state access must remain separately enforced. A test VM outage cannot automatically promote itself to production or cause a missing primary to be resurrected.

## Source-backed components reused, not reimplemented

- Runtime composition: `src/sofia/composition/root.py` and `engines.py`.
- Actual remote cognition: `src/sofia/cognition/fleet_engine.py` and `src/sofia/distributed/inference_client.py`.
- Fleet placement policy: `FleetCognitionConfiguration` and `WorkloadContract`; approval must use the **observed Fleet host ID for Venus**, not merely a display name, and `gpu_required=true`, `local_fallback=false`, `auto_provision_models=false`, `allowed_host_ids=(<verified Venus host ID>,)`.
- The source fix on `main` makes `create_model_lifecycle` skip local Ollama management on the explicit remote-only canonical host while retaining lifecycle management where the same host is an eligible local inference provider.
- Staged relocation: `src/sofia/ops/state_mobility.py`, `state_relocation.py` and `state_promotion.py`; this is staging and operator handoff, **not a completed privileged fencing/promotion broker**.
- Signed location bootstrap: `src/sofia/config/state_home_pointer.py`. Its HMAC and epoch checks are not independently sufficient to fence a disconnected old writer.
- Encrypted state snapshot/restore: `src/sofia/ops/backup.py`, including canonical `sofia.db`, identity and other protected assets; do not simply copy open SQLite files/WAL over SMB.

## Staged migration requirements

1. **Preflight only:** inspect exact Venus/Artemis machine and Fleet IDs and select the separately provisioned Hyper-V VM **`Sofia`** on Artemis. Check guest OS, persistent disk location, guest identity, virtual networking, permissions, throughput, resources, mobile/desktop client routing, model availability and encrypted independent backup capacity. The destination SQLite must be on an approved **host-local filesystem**, not a live SMB share.
2. **Trust and capacity:** enroll Venus as an authenticated remote inference worker before moving the writer; preserve exact allowed primary and secondary models; verify pinned certificates, capability adverts, host identity and no unapproved download. The Artemis process must not need a GPU just to boot or read state.
3. **Operator-approved offline handoff only:** stop the active Venus writer; fence all old clients/writers; take/verify an encrypted consistent snapshot and full asset manifest; stage/verify Artemis restore; independently protect keys and witness writer epoch. Never promote a copy while Venus may still write.
4. **Privileged broker validation:** check exact intended destination writer host, old source host and witness, external epoch floor, approval nonce, health/schema/identity and optional rollback. Existing `state_promotion.py` explicitly does **not** implement this last host-privileged broker.
5. **One-time activation:** make the signed, guest-host-bound pointer active **inside VM `Sofia` on Artemis** and start **one** canonical service. Venus becomes UI and GPU inference only; its old `sofia.db` is an archive, **never another live writer**. Desktop, Discord and future Android clients rebind through authenticated application APIs.
6. **Degraded-state tests:** Venus GPU worker unavailable => deterministic cognitive unavailable response, not a silent provider substitution; Artemis offline => Venus UI cannot silently resurrect the old state; reconnect => single-writer reconciliation and operator-reviewed restoration.
7. **Only after acceptance:** compare actual response latency, provider traffic, CPU/RAM, outage behavior, backups, recovery times and double-writer prevention. Run full unit/integration/Windows/Fleet tests in the user's deferred campaign, not as part of this coding handoff.

## Unresolved owner inputs

- **Guest operating system for VM `Sofia`:** not yet specified; this determines the service launcher, protected key storage, guest firewall and local persistent state root. The hypervisor is Artemis Windows, not the future guest's automatically assumed OS.
- **Standby objectives:** desired maximum acceptable data loss and downtime (RPO/RTO); do not invent numbers.
- **Authenticated operator identity and independent fencing witness:** the current literal actor label is not human authentication, and stage-only helpers cannot be misrepresented as live failover.
- **Exact source and destination Fleet host IDs / addresses:** must be discovered and approved, not guessed or put into code as hardcoded network addresses.

No live host changes or permission grants are authorized by this document.
