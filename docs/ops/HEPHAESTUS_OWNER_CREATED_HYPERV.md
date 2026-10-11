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
- `SOFIA_WORKSHOP_MEDIA_OWNER_PUBKEY`: exact path to an independently ACL-pinned **public** Ed25519 key, separate from the offline ISO/media root; required for signed console-admin policy verification.

## Secure console account and owner-signed offline installer media

**Owner-selected first-boot design:**

- Debian 13 **headless**, no LAN or Internet access during installation.
- `sofia-admin` is the **local console administrator**. Its password is entered at a **local hidden prompt** when building the ISO; no plaintext credential is entered into ChatGPT, Settings, GitHub, commands, shell history or environment variables.
- Installer records only a salted **SHA-512 crypt** password verifier in the media. Debian root account is **locked**.
- `sofia-admin` may use `sudo`, but sudo **requires the password**. Any `NOPASSWD` rule aborts the guest-hardening stage.
- `sofia-worker` is a **separate non-login system account**, with locked password, no sudo membership and private home directory. It is not a secondary administrator.
- OpenSSH server is **not installed**; ssh/sshd units are masked. Enabling SSH, outbound networking or Fleet enrollment requires a separate later review and approval.
- The preseed aborts unless Debian Installer finds **exactly one disk**. It partitions the already owner-declared blank VHDX only, using source-verified offline Debian DVD packages. Installer is configured to **halt**, not reboot repeatedly from its still-attached ISO.

**Build media locally (owner-operated, not on Artemis):** Use a **Linux or WSL** machine with `xorriso`, `openssl` and Sofía's declared Python dependencies installed. Create a private Linux-filesystem folder (not a Git checkout or synced folder). The example source filename is a placeholder; independently verify Debian's official signed SHA-256 and obtain matching Debian 13 **amd64 DVD-1**, not a netinst or live image.

```bash
mkdir -m 700 -p "$HOME/sofia-owner-keys"
mkdir -m 700 -p "$HOME/sofia-private-iso"

python -m sofia.ops.workshop_media_attestation \
  --create-owner-key-dir "$HOME/sofia-owner-keys"

python -m sofia.ops.workshop_media \
  --source-iso "/approved/debian-13.X.Y-amd64-DVD-1.iso" \
  --source-sha256 "REPLACE_WITH_INDEPENDENTLY_VERIFIED_64_HEX_SHA256" \
  --output-iso "$HOME/sofia-private-iso/hephaestus-debian13-offline.iso" \
  --signing-key-file "$HOME/sofia-owner-keys/hephaestus-owner-private.pem"
```

The builder refuses to run without the verified source hash, required tools and **locally encrypted Ed25519 owner key**. It verifies the Debian UEFI GRUB installer paths, appends an unattended boot entry, embeds the preseed and worker-hardening script, preserves the original ISO's UEFI boot structures and verifies the output's boot descriptor and embedded files. The signed report contains:

- `hephaestus-debian13-offline.iso` with a SHA-256 digest
- `hephaestus-debian13-offline.iso.manifest.json` signed with your **private** owner key and binding the exact ISO digest, console-admin/SSH/worker policy and source DVD hash
- `hephaestus-owner-public.pem` for Artemis to **independently pin** (the owner private key stays ONLY in the owner's offline key directory)

Copy the **ISO and its adjacent .manifest.json** into the host-approved offline media root on Artemis. Pin the **public** key separately with host-admin ACLs. Configure `SOFIA_WORKSHOP_MEDIA_OWNER_PUBKEY` to point to that public key. Neither Sofía's model nor a remote caller may replace this key. Artemis **rejects unsigned ISOs, incorrect signatures, changed content and a policy other than `hephaestus-debian13-console-admin-v1`** during both media preflight and protected boot. Hash verification alone is insufficient.

**Security warning:** A salt-and-hash verifier inside an ISO is not plaintext, but someone who obtains the private ISO can attempt an offline password-guessing attack. Use a unique strong password, restrict media access, delete/revoke old copies after verified guest setup and rotate the account password if the ISO leaks. Do not publish media, manifest-with-ISO, credential verifier, or owner private key to GitHub.

**This installer is not a proven guest until the final tests:** A generated boot entry and media signature cannot prove the UEFI installer finishes, creates the approved accounts, configures sudo/SSH correctly or isolates the VM. Complete the physical Hyper-V and guest-side acceptance gates before marking those items production-verified.

**Debian unattended-media requirement:** The approved ISO must actually contain a working Debian Installer preseed and UEFI boot configuration that passes `auto=true priority=critical preseed/file=/cdrom/preseed.cfg` (or a separately reviewed equivalent). A standard interactive Debian ISO will only boot the installer menu; it cannot fulfill Sofía's hands-off installation task. The owner must review unattended partitioning because it can erase the exact OS VHDX. Use a verified offline DVD/package source if networking is prohibited. The image may contain only the locally generated salted administrator password verifier, never plaintext passwords, private signing keys, host credentials, arbitrary shell prompts or unapproved LAN connectivity. The boot ISO digest must be observed from Artemis each time before the protected boot operation. See Debian 13's official preseed guidance for UEFI/ISO details.

A host admin must install and configure the Fleet agent and its pinned mTLS transport separately. **Do not paste passwords, signing keys, API tokens or host administrator credentials into an ISO, settings UI or Git.**

A production deployment should constrain the Artemis service identity to the necessary Hyper-V operations using JEA or equivalent host policy. Source-level command restrictions are a second defense; they are **not** an OS-enforced least-privilege boundary by themselves.

## Sofía owner workflow

Use **Tray Settings → Fleet → Hephaestus: owner-created blank VM handoff**.

- Supply exact enrolled Artemis node UUID, existing VM GUID, owner-created VHDX path, **owner-signed** unattended ISO path and its independently verified SHA-256. Confirm the exact disk is blank. Artemis must independently attest the signed first-boot policy.
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
