# Phase 5 platform, world, and creation acceptance

Status vocabulary is evidence-sensitive: **wired** means the canonical
application constructs and reaches the owner; **host-unverified** means source
and controlled tests exist but this Linux cloud runner did not execute the
workflow on the stated real host or device.

## Production ownership audit

| Capability | Status | Canonical owner / evidence |
|---|---|---|
| Dependency and feature registry | wired | `sofia.ops.dependencies`; required, feature, and optional requirements resolve per platform and retain per-host observations in `sofia.db`. |
| Fleet discovery and enrollment | wired | Existing OPS discovery creates untrusted candidates; existing exact Fleet approval remains mandatory before enrollment/trust. |
| Windows Fleet bootstrap | wired; host-unverified | Existing CIM/X.509 bootstrap plus the Phase 5 signed artifact, offline cache, receipt, health, and recovery contracts. Requires a supervised Windows target. |
| Linux Fleet bootstrap | coded; host-unverified | Offline hash-pinned atomic release/systemd workflow, receipt verification, rollback target, and rollback recovery. Requires an authorized Linux root/provisioning boundary. |
| Hardware/network/Docker/virtualization/storage/backup/security/monitoring | wired foundations | Existing MACHINE/NET/OPS/Fleet/Portainer/Hyper-V/backup/release authorities remain intact; the dependency/evidence registry now exposes lifecycle prerequisites without granting execution. |
| Home Assistant/JMRI/application integrations | wired when configured | Existing typed integration adapters and permission gateway remain authoritative. Missing configuration is unavailable, not healthy or nonexistent. |
| Multi-space virtual world | wired | `VirtualWorldStore` owns canonical metadata in `sofia.db`; application startup creates three independent local-owner spaces idempotently. |
| World editor/inventory | wired | Revision-checked space/object mutation, transforms, grouping, containers, connections, archive/restore, imports, undo, pagination, and mutation history. |
| Avatar/object interaction | wired foundation; renderer host-unverified | Interaction decisions bind the exact object revision and only acknowledge rendering while that scene revision remains current. |
| Preferences | wired | General taste registry is separate from interaction consent, separates Sofía/Sparks/shared records, and retains strength, confidence, reason, evidence, context, audience, and history. |
| Nicknames | wired | Proposals require authenticated recipient feedback; context, decline dedupe, retirement, revocation, audience scope, and canonical identity separation are enforced. |
| Creative adapters | wired | Native text/story/SVG/OBJ/animation/WAV/game/simulation creation produces real hash-verified artifacts; code import requires an existing governed DEV candidate receipt. |
| Creative inventory/explorer | wired | Projects and revisions live in `sofia.db`; bytes are content-addressed in managed external storage; preview integrity, history, recovery, privacy, license, authorship, and ownership are retained. |
| Settings/workbench diagnostics | wired | World, Creative, Preferences, dependency health, platform receipt, and interaction receipt panels use the canonical database. |

## Invariants

- Discovery is not trust or enrollment.
- A dependency being registered is not proof it is installed.
- A world preference ranks only choices already allowed by the caller.
- A world object or scene action grants no physical capability.
- A creative artifact is not an execution receipt.
- Code artifacts cannot bypass DEV/OpenCode approval boundaries.
- Nicknames never change canonical identity.
- General preferences never replace interaction consent or permissions.
- Large assets do not live as blobs in `sofia.db` and are rehashed before
  preview or placement.

## Live acceptance still required

The following require independently controlled hosts and are not claimed by
this cloud test environment:

1. Provision a clean approved Windows host using the signed package and record
   service, version, signature, capability, rollback, and interruption receipts.
2. Provision a clean approved Linux host through an authorized root boundary;
   verify systemd health, restart, offline reinstall, rollback, and failed
   rollback recovery.
3. Run supervised Fleet discovery and prove the candidate stays untrusted until
   the exact node/key/endpoint approval is consumed.
4. Exercise configured Docker, Hyper-V, backup, Home Assistant, JMRI, and other
   integrations against real services through existing permissions.
5. Visually render an authored world object and avatar/object gesture, then
   record the renderer acknowledgement for the exact scene revision.

These limitations are host acceptance, not converted into synthetic success.
