# Sofía canonical runtime and GPU inference topology

**Owner decision:** 2026-10-11. **Guest OS confirmed: Debian 13 Stable (Trixie), minimal headless install, dedicated VM `Sofia` on Artemis.** **Deployment status:** design/source only; no OS installation, state move, host change, model installation, enrollment or live verification performed.

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

## Operator-reported provisioning status (2026-10-11)

- **REPORTED BY OWNER:** The Hyper-V VM named `Sofia` has been created on Artemis. **Debian is not installed in that VM.** This statement is operator-supplied, not independently observed VM identity, disk, firmware, network or guest operating-system proof.
- **NOT YET VERIFIED:** Actual VM GUID, Generation 2 firmware, CPU/RAM, attached VHDX/storage filesystem, selected virtual switch, ISO integrity, guest hostname/OS, Fleet enrollment, mTLS connection, protected credentials, running application, trusted backup or any state migration.
- **CURRENT WRITER:** Venus still owns the active canonical runtime and `sofia.db`; an empty VM on Artemis has **no production writer authority**. Installing Debian by itself will not change this. The separate research/test VM remains isolated.
- **READ-ONLY PRODUCTION INSPECTION:** `HyperVAdapter.sofia_guest_inventory()` is callable through the existing Level-1 `hyperv.sofia.inspect` local integration or the new Level-1 `remote.vm.sofia.inspect` tool, which routes exact `vm.inspect / sofia_preflight` over the existing pinned-mTLS Fleet transport. It observes exact VM `Sofia` host metadata and reports blockers for missing disks/unknown networking while always leaving guest OS readiness, writer activity and activation **unverified/unauthorized**. This method does not start VMs, attach ISOs, install Debian, grant credentials or switch state ownership. Its availability does not mean a live inspection has been performed.
- **NEXT HUMAN-SUPERVISED INSTALL MILESTONE:** After reviewing guest hardware/network and Debian 13 install-media authenticity, the owner or independently approved host operator installs Debian 13 minimal headless. Only then can guest OS identity, non-root service setup and signed pointer preflight be tested against that guest. Production DB restore and sole-writer activation are a later, separately approved operation.

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

## Headless Linux runtime service (source committed; not deployed)

**Debian 13 Stable (Trixie) is the approved target OS**, rather than a still-open Debian/Arch comparison. Its current point updates should be applied using reviewed Debian Stable security/update repositories; the application compatibility gate deliberately pins the Debian **major version 13**, not an individual point-release image. The production guest uses the existing `src/sofia/run/systemd_runtime.py` to launch the actual application rather than installing a Windows service or reusing `sofia-fleet-agent.service` (a **separate Fleet agent**).

The launcher verifies `/etc/os-release` identifies Debian 13 (`ID=debian`, `VERSION_ID=13`, codename Trixie) both at systemd `ExecStartPre` and immediately before composing the runtime. An unexpected distro, Debian major upgrade, missing release metadata, or wrong identity is a **fail-closed** startup until independently reviewed. The launcher starts the actual canonical `SofiaApplication` and calls its shutdown path on SIGTERM/SIGINT. It requires an existing, externally signed state-home pointer and explicitly refuses any systemd environment-file override of `SOFIA_RUNTIME_MODE=production` or `SOFIA_IDENTITY_BOOTSTRAP_MODE=require_existing`. It must not create a new `sofia.db` or independently promote a copied database. The pointer only authenticates location/epoch and **does not itself fence Venus**.

For operator review only, once a Linux guest and persistent paths are chosen:

```shell
/opt/sofia/.venv/bin/python -m sofia.run.systemd_runtime render-unit \
  --python /opt/sofia/.venv/bin/python \
  --state-root /var/lib/sofia-ada-lyra \
  --environment-file /etc/sofia/production.env \
  --user sofia
```

This prints a unit and **does not install, enable or start it**. The real state root and Python path must match the operator-approved guest. The environment file is independently protected by the OS administrator, not world-readable and **outside** the state home; it supplies signed pointer path, externally protected HMAC key location, verified guest writer-host ID, independent writer epoch floor, and approved mTLS Fleet inference settings. Do not put API keys in the command line or in this document. The rendering source refuses unsafe path/service-user values and disallows root.

The rendered unit now uses **`Type=notify` with `NotifyAccess=main`**. Sofía sends systemd `READY=1` only after the real `SofiaApplication.start()` returns, and `STOPPING=1` during clean shutdown. A missing or unusable systemd notify socket prevents a premature ready signal; an application startup failure never publishes `READY=1`. The unit keeps `Restart=on-failure`, `WantedBy=multi-user.target`, a non-root `sofia` account, `ProtectSystem=strict`, `ProtectHome=true`, `NoNewPrivileges=true`, limited `ReadWritePaths` and normal journald output. **`active` now means the runtime reported application-start completion**, not proof that remote inference, UI, Fleet trust, periodic jobs or backup/recovery work correctly. The operator must verify those receipts on the actual guest.

**No live service may be enabled on VM `Sofia` while Venus is still an active writer.** Migration must first establish the privileged broker, restore/verify the full state, fence the Venus writer and independently advance the epoch before the external signer activates the new pointer. Inference remains pinned to the approved Venus GPU worker; no fallback to an unapproved local model.

## Approved Debian guest prerequisites (design only)

- **Guest OS:** current supported Debian 13 (Trixie) amd64 minimal/server installation, **without a desktop environment**. Validate the ISO's publisher checksum/signature and Hyper-V Generation 2 Secure Boot compatibility before provisioning. Use the selected operator-reviewed machine/storage sizing and private/controlled virtual networking. Do not treat a workshop VM as the canonical guest.
- **Python:** run Sofía from a dedicated virtual environment using a supported interpreter (the project requires Python 3.12+). Keep installation/dependency artifacts pinned and supply-chain verified; do not assume unreviewed OS packages or download a model as a shortcut.
- **Service identity:** dedicated unprivileged `sofia` user/group, systemd and journald, guest-local `/var/lib/sofia-ada-lyra` state home only after verified restore, and root-protected `/etc/sofia/production.env` with the signed pointer/key locations and witnessed epoch. Exact locations remain subject to deployment review.
- **Connectivity:** independently enrolled and pinned-mTLS remote Venus inference; approved management path, firewall scope, time/DNS reliability and backup reachability. Exposing Ollama directly is prohibited.
- **Startup refusal:** systemd's `verify-guest` step must accept only Debian 13, and the application separately checks it again before loading canonical state. An unapproved OS upgrade intentionally stops startup until source compatibility and single-writer cutover are reviewed.
- **No duplicate writer:** a prepared Debian guest may exist for testing with *synthetic* fixtures, but neither a systemd runtime start nor a restored production database may be activated there while Venus is the active owner. An external privileged broker must fence Venus and authorize the promotion.

## Staged migration requirements

1. **Preflight only:** inspect exact Venus/Artemis machine and Fleet IDs and select the separately provisioned Hyper-V VM **`Sofia`** on Artemis. Check guest OS, persistent disk location, guest identity, virtual networking, permissions, throughput, resources, mobile/desktop client routing, model availability and encrypted independent backup capacity. The destination SQLite must be on an approved **host-local filesystem**, not a live SMB share.
2. **Trust and capacity:** enroll Venus as an authenticated remote inference worker before moving the writer; preserve exact allowed primary and secondary models; verify pinned certificates, capability adverts, host identity and no unapproved download. The Artemis process must not need a GPU just to boot or read state.
3. **Operator-approved offline handoff only:** stop the active Venus writer; fence all old clients/writers; take/verify an encrypted consistent snapshot and full asset manifest; stage/verify Artemis restore; independently protect keys and witness writer epoch. Never promote a copy while Venus may still write.
4. **Privileged broker validation:** check exact intended destination writer host, old source host and witness, external epoch floor, approval nonce, health/schema/identity and optional rollback. Existing `state_promotion.py` explicitly does **not** implement this last host-privileged broker.
5. **One-time activation:** make the signed, guest-host-bound pointer active **inside VM `Sofia` on Artemis** and start **one** canonical service. Venus becomes UI and GPU inference only; its old `sofia.db` is an archive, **never another live writer**. Desktop, Discord and future Android clients rebind through authenticated application APIs.
6. **Degraded-state tests:** Venus GPU worker unavailable => deterministic cognitive unavailable response, not a silent provider substitution; Artemis offline => Venus UI cannot silently resurrect the old state; reconnect => single-writer reconciliation and operator-reviewed restoration.
7. **Only after acceptance:** compare actual response latency, provider traffic, CPU/RAM, outage behavior, backups, recovery times and double-writer prevention. Run full unit/integration/Windows/Fleet tests in the user's deferred campaign, not as part of this coding handoff.

## Unresolved owner inputs

- **Guest operating system for VM `Sofia`: CONFIRMED Debian 13 Stable (Trixie), headless.** The hypervisor remains Artemis Windows. This decision authorizes source targeting, **not** VM installation or promotion; the specific ISO checksum, host resources and actual service-enrollment action remain separately reviewed.
- **Standby objectives:** desired maximum acceptable data loss and downtime (RPO/RTO); do not invent numbers.
- **Authenticated operator identity and independent fencing witness:** the current literal actor label is not human authentication, and stage-only helpers cannot be misrepresented as live failover.
- **Exact source and destination Fleet host IDs / addresses:** must be discovered and approved, not guessed or put into code as hardcoded network addresses.

No live host changes or permission grants are authorized by this document.
