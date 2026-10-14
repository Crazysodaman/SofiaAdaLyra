# V18 Operating Layer: source-scoped decision packet (2026-10-14)

**Status:** Draft for independent technical review. This is real design work for
CA-4501, CA-4505, CA-5401, CA-5403 and CA-5408, **not** a Gate 1–4
certificate, deployed service, or approval to migrate canonical state.

## CA-4501: terms must not collapse into one another

| Term | Meaning | Sofía decision |
| --- | --- | --- |
| Operating-system kernel | Privileged scheduler, memory/driver/syscall boundary controlling hardware | Use maintained Linux/Windows kernels, do not create a new one |
| User-level agent operating layer | Ordinary applications/services for authenticated sessions, permissions, jobs, Fleet, and memory | Current Option A; each canonical owner remains authoritative |
| Dedicated Sofía appliance OS image | Reproducible, hardened Linux guest image packaging the same application and services | Option B, approved as a later packaging choice, not a new runtime authority |
| Desktop shell/launcher | User-visible Windows/Linux client or tray/workbench | A client, not a kernel, database owner or privileged service |

A desktop skin is not an OS. A Debian VM is an isolation/packaging boundary,
not evidence of a new kernel. The distinction prevents duplicated state
writers and permission brokers.

## CA-5401: Option A, approved now

Run the **existing** Sofía services on established Windows/Linux. Retain one
canonical identity and logical `sofia.db` writer. SAFE controls permission
decisions, RUN owns work/receipts, Fleet owns authenticated remote capabilities,
and conversation/MEM own their respective canonical records. Typed platform
capability drivers are OS-specific adapters behind SAFE-authorized interfaces;
no driver may bypass the central grant, lease or audit decision. Desktop/Discord
are clients/transports, not independent decision authorities. LLM providers
produce candidate text or plans, never grants, database writer leases or
physical action receipts.

The future Artemis Debian `Sofia` VM may host the canonical runtime only
after an explicitly verified single-writer migration and recovery exercise.
Until then, Venus remains the active canonical writer. Artemis without a GPU
can request authenticated inference from Venus; if Venus is offline, the
runtime may perform non-LLM work but must not invent a model answer or silently
change model roles.

## CA-5403: Option B, approved but deferred

A dedicated reproducible Debian-based appliance image is a **packaging
option**. It must reuse the same application, identity, canonical database,
SAFE/RUN/Fleet services and session APIs. Entry requires pinned CI, proven
startup/restart, backups and restore, authenticated Fleet, single-writer
fencing, measured CPU/RAM/VRAM budgets and rollback. No appliance build or
VM migration is authorized by this document. It must not create a second
always-on brain, separate permission issuer or simultaneous SQLite writer.

## CA-4505 and CA-5408: custom-kernel proposal deferred

A custom kernel is **outside active scope** unless a written hardware-control
requirement cannot be met by existing Windows/Linux drivers, userspace
services, containers or hypervisors. A future proposal must identify the
specific unmet capability, minimal alternatives, reproducible test, safety
boundary and explicit owner authorization before any implementation.

| Cost/risk | Existing maintained kernel | New custom kernel |
| --- | --- | --- |
| Security patches | Vendor/distribution maintenance path | Permanent project-owned CVE triage and patch burden |
| Device support | Mature GPU, network, USB and virtualization drivers | New or ported drivers with failure and compatibility risk |
| Recovery | Established rescue tools, snapshots, package rollback | New boot chain, diagnostics, backup/restore procedures |
| Homelab overhead | Existing Windows/Debian deployment and known tools | Separate CI, boot testing, release and signing infrastructure |
| Agent autonomy | Constrained by SAFE/RUN, not kernel branding | No intrinsic improvement in reasoning or permission safety |

**Decision:** no custom kernel development. Revisit only on measured,
unmet hardware requirements and a reviewed cost/security comparison.

## Source and acceptance boundaries

Relevant production owners to inspect in the exact reviewed checkout:
`src/sofia/application/bootstrap.py` (composition),
`src/sofia/safe/permissions.py` (grants),
`src/sofia/run/work.py` (work),
`src/sofia/conversation/store.py` (conversation),
`src/sofia/distributed/identity_durable.py` (Fleet identity), and
`src/sofia/verify/v18_gate4.py` (evidence-only progress). These paths are
inspection pointers, not a claim that all listed services were exercised.

**Open acceptance:** independent source review of this packet; check each
owner/caller and actual failure mode; pin reviewed commit; test any resulting
interface changes on Linux/Windows; obtain task-specific CI evidence. No
automatic gate promotion from this document, no live-host changes, no
credential/grant changes and no `sofia.db` migration.
