# Hephaestus: owner-created blank VM on Artemis (Hyper-V)

**Architecture decision, 2026-10-11:** The owner has already created the **Hephaestus** Hyper-V virtual machine on Artemis, with **no operating system installed**. Sofía must **not** create or adopt another VM. This is the production v1 path on `main`.

## Ownership

- Owner: Creates the named VM and confirms the reviewed OS VHDX is empty. Supplies an independently verified, **unattended**, offline Debian installation ISO. Sets any host-only agent scope and authorizes the exact operation.
- Artemis: The authenticated, pinned-mTLS Fleet agent can inspect the VM **before an OS exists**. A separately enabled, pinned host-side operation may attach only the approved ISO to the exact Hephaestus VM and start the installer.
- Sofía: Presents the typed handoff and independent SAFE approval. Saves source receipts to canonical `sofia.db` on Venus until explicit runtime/DB migration. It does not hold Artemis administrator credentials or invent guest observations.
- After installation: Guest identity and OS facts must be independently observed. **Fleet enrollment is separate** and requires the existing protected `fleet.enroll` approval and proof of possession.

## Exact owner-created handoff

1. The host must be Artemis' already enrolled **cryptographic Fleet node UUID**, not a name resolved from an LLM.
2. The VM must be **Hephaestus**, Hyper-V **Generation 2**, with an exact verified VM GUID. The separate canonical VM **Sofia** must never be the target.
3. Provisional VM bounds: **2–4 vCPU, 4–8 GiB RAM, 60–128 GiB VHDX**. VM must be **Off** when reviewed and before installation.
4. Exactly **one** existing VHDX at the owner-reviewed path. The owner confirms that disk is blank. Hyper-V metadata alone cannot prove disk emptiness. No other attached DVD ISO is accepted.
5. Exactly one vNIC on the dedicated **Private** switch `Sofia-Hephaestus-Private`. **Default Switch, Internal, NAT, external bridge and home LAN are not acceptable substitutes.** No VM network changes are part of the installer boot permission.
6. Windows/Hyper-V firmware boot order and Secure Boot configuration are observed before mutation. Only a reviewed Linux-compatible Gen2 mode is accepted.
7. The boot medium must be an explicitly reviewed **unattended Debian installer ISO** inside the host-admin offline image directory, with an independently pinned exact SHA-256 digest. A plain interactive Debian ISO is **not** a completed unattended installer.
8. The observed VM ID, disk, resource settings, network, firmware and media SHA-256 are rechecked before any approved mutation. Changes require **another owner review**.

## Artemis operator prerequisites (no automatic host changes)

On the **Artemis Fleet agent service account**, configure the following host-controlled environment only after reviewing exact paths and ACLs:

- `SOFIA_WORKSHOP_IMAGE_ROOT`: a dedicated local directory of approved offline ISO images, excluding UNC shares, NAS, users' home and host secrets. Read and hash only.
- `SOFIA_WORKSHOP_BOOTSTRAP_VM_ID`: the actual GUID of the owner-created Hephaestus VM.
- `SOFIA_WORKSHOP_BOOTSTRAP_OS_DISK`: the exact existing Hephaestus VHDX path.
- `SOFIA_WORKSHOP_BOOTSTRAP_ENABLED=1`: deliberately enables the otherwise unavailable protected host bootstrap operation.

A host admin must install and configure the Fleet agent and its pinned mTLS transport separately. **Do not paste passwords, signing keys, API tokens or host administrator credentials into an ISO, settings UI or Git.**

A production deployment should constrain the Artemis service identity to the necessary Hyper-V operations using JEA or equivalent host policy. Source-level command restrictions are a second defense; they are **not** an OS-enforced least-privilege boundary by themselves.

## Sofía owner workflow

Use **Tray Settings → Fleet → Hephaestus: owner-created blank VM handoff**.

- Supply exact enrolled Artemis node UUID, existing VM GUID, owner-created VHDX path, unattended ISO path and its independently verified SHA-256. Confirm the exact disk is blank.
- Select **Inspect my blank Hephaestus VM (read only)**. It performs only authenticated `workshop.inspect/blank_vm` and offline media SHA-256 inspection and records the result to the canonical state. It cannot create or start a VM.
- Review the actual blockers and immutable handoff fingerprint.
- Select **Review & approve one Debian installer boot (protected)** only when ready. That creates a one-use, exact, time-limited SAFE receipt, issues a short exact-node Fleet grant and invokes `workshop.bootstrap/start`. Both must pass.
- At the remote boundary, SAFE consumes the one-time approval **before** transport. The Artemis agent separately requires its host-admin enable flag, pinned VM GUID and disk, and verified offline ISO.
- Hyper-V's host command then rechecks VM identity, stopped state, Gen2, CPU/RAM/disk bounds, exact Private switch, Secure Boot, empty DVD slot and ISO hash. Only then may it attach the ISO, set **DVD first**, and start the exact existing VM.

The host result may be `INSTALLER_BOOT_STARTED` or `UNCERTAIN`. **Neither means Debian is installed.** A timeout/exception may hide a successful boot. Never retry automatically or reuse the same approval. Check Artemis' actual VM/DVD state and the Fleet request ledger before reconciling.

## Mandatory next acceptance and separation

The owner verification campaign, deferred until all coding, must independently observe:
- Hyper-V VM GUID unchanged, sibling VMs unharmed, one private NIC with no LAN/NAS/router/Internet route, no privileged host mounts.
- Debian installation actually finished on the pinned disk; approved installer media removed and OS disk boot restored via a **separate reviewed cleanup/recovery** operation.
- Non-root worker identity exists, passwordless sudo is disabled, no host secrets, no automatic network or OS package installs.
- Guest-side authenticated identity proof, OS and service heartbeat, and compatibility evidence prior to any **separately approved `fleet.enroll`**.
- Operator stop/quarantine, runtime uncertainty handling, actual CPU/RAM/disk reservations and one offline artifact receipt.
- Installer failure, partial PowerShell side effect, Artemis reboot, wrong VM GUID, conflicting disks/switch, ISO digest change, Fleet timeout, revoked grant and duplicate job never trigger blind recovery.

No installer was executed, guest provisioned, new VM created, source tests run or CI started during coding.

## Alternatives evaluated

| Path | Advantages | Reasons not selected as v1 |
|---|---|---|
| **Owner-created blank VM + reviewed unattended Debian ISO** | Explicit host ownership, exact GUID and disk, source review before any destructive step | Requires offline unattended media, OS installation proof and a later guest identity bootstrap |
| Sofía creates new Hyper-V VM | Repeatable allocation from capacity facts | Greater host mutation authority, collision/cleanup risk; unnecessary because the VM already exists |
| Preinstalled Debian cloud image + NoCloud seed | Fast reproducible guest setup with supported cloud-init | Requires a trusted prepared compatible VHDX/import or conversion workflow; cannot be silently substituted for the owner's existing empty VHDX |
| Manual Debian ISO/console | Simple operator ownership | Does not satisfy Sofía's autonomous installation objective and still needs separate guest hardening |

**Production rule:** A bootable ISO merely starts setup. Any successful OS install, verified guest configuration or research result needs independent evidence from the actual guest/host before advancing a task state.
