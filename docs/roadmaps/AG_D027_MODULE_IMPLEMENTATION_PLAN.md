# AG-D027 | Approved module rationalization implementation campaign

**Owner direction:** 2026-11-08, "Okay lets do all the recomendations" in response to [AG-D026](AG_D026_MODULE_CATALOG_RATIONALIZATION_AUDIT.md).
**Execution state:** IN PROGRESS in reviewed batches; no implication all modules are installed, production ready, migrated, or merged. The conditional new candidates in AG-D026 remain conditional pending an independently justified use case. This plan authorizes engineering changes subject to existing repository safety, independent security/host approvals, test evidence and concurrency controls, **not** automatic host deployment, destructive migration, privileged grants, or weakening Platform #201 gates.
**Tracking:** [GitHub implementation issue #237](https://github.com/Crazysodaman/SofiaAdaLyra/issues/237); [draft batch 01 PR #238](https://github.com/Crazysodaman/SofiaAdaLyra/pull/238).
**Full scope:** 55 existing catalog entries, six conditional consolidation directions, shared providers/SDK, optional integration enhancements, and tests.
**Authoritative catalog:** [ownership matrix](../sofia2/MODULE_OWNERSHIP_MATRIX.md) and [module catalog](../sofia2/PLATFORM_AND_MODULE_CATALOG_V1.md). Existing package IDs/state references remain valid until independently reviewed migration.

## Immutable rules for this campaign

1. **No mass deletion:** consolidation first produces an explicit compatibility plan preserving original module IDs, capability names, owner policy, signed package digests, existing settings, data ownership, grants/revocation, event and job history. Alias does not inherit approval. Any actual module removal or state migration needs a separate owner-authorized stage and a tested rollback.
2. **Platform owns effects:** Core reasoning and its optional modules must not become the canonical writer, trust issuer, owner-secret store, protection bypass, installer authority or job scheduler. Permission levels may not be lowered just to support consolidation.
3. **One published API per capability:** shared SDK/event/observability/secret/approval/state contracts stay in Platform. Separately installed modules can reuse those interfaces without installing redundant service backends.
4. **Evidence truth:** module source and a passing advisory unit test are not installed signed module/host acceptance. RC requires real signed packages, applicable source-SHA tests, security review and reproducible lifecycle evidence.
5. **Concurrency and Git discipline:** work in small reviewable batches; inspect latest `main` and active drafts before making changes, avoid files actively changing under OpenCode, never merge untested broad refactors into main. Platform-only #201 has priority over extra optional modules unless owner separately reprioritizes.
6. **UI/TUI lifecycle:** both clients must show module connected/disconnected, installed/available/blocked, approval, settings and actual health automatically without restarting. Uninstalling any optional module never uninstalls the external service it connects to.

## Ordered execution batches

| Batch | Scope | Output and acceptance | Status |
| --- | --- | --- | --- |
| **B00** | Inventory/scope freeze | 55-entry [AG-D026](AG_D026_MODULE_CATALOG_RATIONALIZATION_AUDIT.md), read-only source inventory; precise recommendation for every entry | **CAPTURED** |
| **B01** | Safe Portainer/Containers observational foundation | Pure allowlisted, exact endpoint/stack ID metadata projection excluding Compose, URLs, credentials and environment. Tests for redaction, injection, wrong IDs. Later secure read-only connector binding to follow. | **IN PROGRESS**; 18 isolated focused tests passed on 2026-11-08 |
| **B02** | Shared SDK/module lifecycle and owner approval dependencies | Module identity/version/generation, canonical settings/receipts, signed packages, capability scopes, SAFE and STOP, live GUI/TUI updates, install block/reinstall, maintenance/rollback with tests | **PENDING**, depends on existing Platform work |
| **B03** | Six requested packaging/ownership consolidation candidates | See below; each requires compatibility alias/migration plan and independent unit/contract regression. Preserve the original catalog IDs until explicit, tested cutover. | **PENDING** |
| **B04** | First high-value IT provider modules | `MOD-IT-CONTAINERS` signed optional Platform module with Portainer TLS/secret binding, source-aware Compose validate/diff, approved deployment, jobs/health/rollback; `MOD-HOMELAB`, `MOD-IT-NETWORK`, `MOD-IT-SYSTEMS`, `MOD-IT-OBSERVABILITY`, `MOD-IT-HELPDESK`, `MOD-IT-SECURITY`, `MOD-IT-BACKUP-DR`, `MOD-IT-STORAGE`, `MOD-IT-DATABASE`, `MOD-IT-DEVOPS` source-backed providers and scopes | **PENDING** |
| **B05** | Companion channels, avatar, perception, voice, communication | Five release channels plus `MOD-AVATAR3D`, Studio, Interaction, VTube adapter, Vision, Desktop Act, Browser, Media, Communications, Documents, Smart Home and Sensors. Validate Core independence, consent, actual receipts, device safety. | **PENDING**, release channels may already be advanced |
| **B06** | Creative, personal, learning and maker modules | DEV, Research, Creative, Productivity, ML, VWORLD, Mentor, Generalization migration, Games, Robotics Gaia, Trains, CAD, Engineering, Electronics, 3D Print, Energy, Remote Access, Workshop, Digital Twin, Knowledge Library, Memory Import, Project Forge, File Watch, Household, Finance, Data Analytics, Calendar | **PENDING** |
| **B07** | Cross-cutting source/host verification | Exact source SHA installed Windows/Debian test, signed manifests, denial/failover/rollback, no duplicate effects, operator STOP, privacy, resource budgets, GUI/TUI parity, zero-Core operation for Platform services | **PENDING** |

**B04–B06 are workstream priorities, not an exhaustive dependency order.** Every one of the 55 is accounted for individually in AG-D026; re-run its corresponding candidate audit before granting any readiness label. This plan does not claim that 55 separate full services must be built.

## Six consolidation candidates (owner authorized investigation and implementation with strict migration reviews)

| Source | Preferred destination | Migration rule / required testing |
| --- | --- | --- |
| `MOD-GENERALIZATION` | `MOD-ML` evaluation subprofile | Preserve Core-native self-learning and external trial provenance; map old capability and grants without increasing authority |
| `MOD-CALENDAR` | `MOD-PRODUCTIVITY` optional calendar provider | Keep scoped calendar tokens, attendee privacy, invitation permission; alias old ID until reviewed removal |
| `MOD-PROJECT-FORGE` | `MOD-PRODUCTIVITY` workflows + `MOD-CREATIVE` artifact service | Keep goal ownership in Core and exact job/artifact lineage in Platform; plan state migrations |
| `MOD-FILE-WATCH` | Platform event broker + `MOD-IT-OBSERVABILITY` provider | Preserve authorized root scopes, never let a file change trigger unsanctioned effects |
| `MOD-DIGITAL-TWIN` | `MOD-HOMELAB` / `MOD-WORKSHOP` simulation profile | Keep simulate-only effects; consider independent process for heavy models |
| `MOD-AVATAR-STUDIO` | Avatar render/rig contracts + `MOD-CREATIVE` generation | Keep private/public wardrobe assets and personal Core expression choices protected |

**Shared plumbing but KEEP separate package/authority:** DEV vs IT-DEVOPS; Research vs Knowledge Library vs Documents; Observability vs Helpdesk vs Security; Smart Home vs Sensors vs Energy; 2D vs 3D renderers; Homelab vs IT provider adapters vs Platform Fleet. Merge **backend helpers** when useful, not distinct permission/secret boundaries.

## New module candidate disposition

- `MOD-IT-GAME-SERVERS` **CONDITIONAL / NOT REGISTERED**: first determine if owner needs standalone RCON/server administration beyond a `MOD-GAMES` provider profile and `MOD-IT-SYSTEMS`. If genuine independent lifecycle/permissions/data preservation, submit separate signed catalog proposal.
- `MOD-IT-IDENTITY-DIRECTORY` **CONDITIONAL / NOT REGISTERED**: external AD/LDAP provider only with an actual reviewed external directory use case. Never incorporate Aegis own owner identity/SAFE into it.
- Existing `MOD-IT-CONTAINERS` already owns Docker/Portainer; do not create another mandatory Docker module.
- DNS/Pi-hole/reverse proxy/Cloudflare integrations go to `MOD-IT-NETWORK`; game server specialized provider first to `MOD-GAMES`; Hyper-V/Proxmox through Homelab/IT-SYSTEMS with Fleet separation.

## Evidence log

| Date | Action | Evidence | Limitations |
| --- | --- | --- | --- |
| 2026-11-08 | Source/directory inventory + 55-entry recommendations | [AG-D026](AG_D026_MODULE_CATALOG_RATIONALIZATION_AUDIT.md) | Not a complete per-line security audit of all legacy source or deployed module test |
| 2026-11-08 | `portainer_projection.py` + `test_portainer_projection.py` on `chatgpt/module-rationalization-batch01` | **18/18 isolated local pytest tests PASSED** for exact IDs, secret redaction, control characters, status and source hints | Unit tests run in an isolated temporary source tree; **full repository pytest/CI, actual API calls, signed installation, GUI/TUI integration NOT RUN**. No effects or permissions exposed. |

## Next required technical gates

- Review existing `portainer.py`, `integrations/http.py`, `safe/permissions.py` and Core Link/Platform module SDK; determine safe Portainer HTTPS origin, redirect and token-secret boundary before registering the new snapshot projection in cognition/UI.
- Capture each current optional module ID's capability and tests, and plan six compatibility-preserving merge adapters with explicit negative permissions tests before altering installable manifests.
- Finish mandatory Platform-authenticated module lifecycle and native GUI/TUI read-only observation; no privileged external actions until trusted end-to-end effect receipts.
- Do not report B02–B07 as complete or commit all 55 to main in one untestable migration.
