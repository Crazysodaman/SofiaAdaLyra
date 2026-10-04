# Sofía Permission Model

This document is the project-wide authority contract for Sofía Ada Lyra.

The goal is simple:

> Sofía may freely observe, investigate, diagnose, compare, test, and plan.  
> Changing the world requires authority proportional to the consequence.

Permission level and privacy/adult scope are separate dimensions. A capability can
therefore be low-risk to execute while still requiring a private or private-adult
audience.

## Permission levels

| Level | Name | Default rule |
|---|---|---|
| 1 | Observe / Read | Sofía may do it without asking. |
| 2 | Safe Autonomous | Sofía may perform it herself when bounded, low-risk, auditable, and recoverable. |
| 3 | Reversible / Scoped Change | Requires a standing scoped grant or a one-time exact approval. |
| 4 | Protected / High Impact | Requires explicit approval for the exact action. Broad standing grants are not allowed by default. |
| 5 | Never Self-Authorized | Sofía may inspect or propose it, but can never grant herself authority to perform it. |

## Privacy classes

| Privacy class | Meaning |
|---|---|
| PUBLIC | Safe for normal public-facing context. |
| PERSONAL | Normal personal context. |
| PRIVATE | Sensitive/private material restricted to an authorized private audience. |
| ADULT | Adult-themed content allowed only when adult authority is enabled for the current context. |
| PRIVATE_ADULT | Adult content plus private authenticated audience restrictions. |
| PROTECTED_PRIVATE | Security, authority, credentials, identity, or other protected state. Adult permission never bypasses this class. |

## Core authority rules

- Read-only inspection should not require repeated approval.
- Safe autonomous maintenance may run without approval only when explicitly classified as Level 2.
- Level 3 standing grants must be scoped by action and resource.
- Level 4 approval must bind to the exact action and target and should normally be one-time/consumable.
- Level 5 operations may be proposed but never self-authorized by Sofía.
- Permission changes themselves are Level 5.
- Fleet enrollment/trust changes require explicit approval.
- Fleet removal/decommission also requires explicit approval.
- Adult/private authority is separate from capability risk.
- Private/adult state must not be disclosed to unapproved audiences.
- Secrets may be inspected only as metadata such as configured/missing/expired. Raw secret values must not be exposed to the cognitive model.
- Operator stop must continue to block side effects while allowing bounded observation.

## Capability map

Status:
- ✅ implemented
- 🟡 partial / foundation exists
- ➕ planned or missing
- 🔀 implemented but permission treatment should change

| Area | Capability / action | Level | Privacy | Status / rule |
|---|---|---:|---|---|
| System | Inspect OS, hostname, version, architecture, uptime | 1 | PERSONAL | ✅ Free inspection |
| System | Inspect processes | 1 | PERSONAL | ✅ |
| System | Inspect services | 1 | PERSONAL | ✅ |
| System | Inspect network adapters/routes/DNS | 1 | PERSONAL | ✅ |
| System | Inspect CPU/GPU/RAM/storage/virtualization | 1 | PERSONAL | ✅ |
| System | Read temperatures/fans/SMART health | 1 | PERSONAL | ➕ |
| System | Kill/restart ordinary process | 3 | PERSONAL | ➕ Scoped grant possible |
| System | Start/stop/restart OS service | 3 | PERSONAL | ✅ Standing grant should be supported |
| System | Restart Sofía-owned helper/service after failure | 2 | PERSONAL | 🔀 Safe watchdog recovery should not ask |
| System | Reboot computer | 4 | PERSONAL | ✅ Exact host approval |
| System | Shutdown computer | 4 | PERSONAL | ➕ |
| System | Update OS/package | 4 | PERSONAL | ✅ |
| System | Firmware/BIOS update | 4 | PERSONAL | ➕ |
| Hardware | Discover local hardware | 1 | PERSONAL | ✅ |
| Hardware | Persist/refresh machine inventory | 2 | PERSONAL | 🔀 Observation maintenance |
| Hardware | Compare old/new hardware | 1 | PERSONAL | ✅/🟡 |
| Hardware | Detect hardware changes automatically | 2 | PERSONAL | ➕ |
| Hardware | Run light benchmark | 2 | PERSONAL | ➕ |
| Hardware | Heavy stress test | 3 | PERSONAL | ➕ |
| Network | Inspect local networking | 1 | PRIVATE | ✅ |
| Network | Scan an approved LAN/subnet | 1 | PRIVATE | ✅ `network.discover` is non-persistent observation and works independently of Fleet enablement |
| Network | Ping/reachability checks | 1 | PRIVATE | ✅/🟡 |
| Network | Detect computers/devices | 1 | PRIVATE | ✅ |
| Network | Resolve hostname/platform evidence | 1 | PRIVATE | ✅ |
| Network | Port/service presence scan on approved subnet | 1 | PRIVATE | ✅ Bounded approved discovery only |
| Network | Build persistent discovered-device inventory | 2 | PRIVATE | ✅ `ops.fleet.discover` may persist only untrusted Fleet candidates |
| Network | Identify unknown/new device and notify | 2 | PRIVATE | 🟡 |
| Network | Change DNS/routes/interface settings | 4 | PRIVATE | ➕ |
| Network | Configure VLANs/firewall | 4 | PRIVATE | ➕ |
| Fleet | List Fleet machines | 1 | PRIVATE | ✅ |
| Fleet | Inspect Fleet machine | 1 | PRIVATE | ✅ |
| Fleet | Inspect telemetry | 1 | PRIVATE | ✅ |
| Fleet | Discover Fleet-capable agent | 1 | PRIVATE | ✅ |
| Fleet | Discover untrusted candidate | 1/2 | PRIVATE | ✅ Read-only network observation is Level 1; durable untrusted candidate registration is Level 2 |
| Fleet | Verify mTLS identity/capabilities | 1 | PRIVATE | ✅ Does not grant trust |
| Fleet | Placement analysis | 1 | PRIVATE | ✅ |
| Fleet | Drift detection | 1 | PRIVATE | ✅ |
| Fleet | Generate repair proposal | 1 | PRIVATE | ✅ Proposal only |
| Fleet | Reconciliation preview | 1 | PRIVATE | ✅ |
| Fleet | Migration planning | 1 | PRIVATE | ✅ |
| Fleet | Refresh telemetry automatically | 2 | PRIVATE | 🟡 |
| Fleet | Mark node temporarily stale/unreachable | 2 | PRIVATE | ➕ Observation, not removal |
| Fleet | Enroll/add computer to Fleet | 4 | PRIVATE | ✅ Exact one-time Sparks approval; tray Permissions can approve a selected verified candidate |
| Fleet | Trust machine identity/key | 4 | PRIVATE | 🔀 Exact approval |
| Fleet | Install Fleet agent | 4 | PRIVATE | ✅/🔀 Exact machine/package approval |
| Fleet | Rekey Fleet node | 4 | PRIVATE | ✅/🟡 |
| Fleet | Remove/decommission Fleet machine | 4 | PRIVATE | ✅ Explicit approval |
| Fleet | Change node privileges | 4 | PRIVATE | ✅/🟡 |
| Fleet | Change Fleet trust policy | 5 | PROTECTED_PRIVATE | ➕ |
| Fleet | Change enrollment requirements | 5 | PROTECTED_PRIVATE | ➕ |
| Remote machines | Inspect remote process/system/network/services | 1 | PRIVATE | ✅ |
| Remote machines | Inspect remote hardware | 1 | PRIVATE | ✅ |
| Remote machines | Inspect remote VMs | 1 | PRIVATE | ✅ |
| Remote machines | Inspect remote containers | 1 | PRIVATE | ✅ List/get/stats/bounded logs/info/health summary/images/volumes/networks/stacks; active trusted OPS Fleet membership required |
| Remote machines | Inspect remote Ollama | 1 | PRIVATE | ✅ |
| Remote machines | Restart exact service | 4 | PRIVATE | ✅ Exact approval required by current remote-control policy |
| Remote machines | Start/stop exact VM | 4 | PRIVATE | ✅ Exact approval required by current remote-control policy |
| Remote machines | Restart exact container | 4 | PRIVATE | ✅ Exact approval required by current remote-control policy |
| Remote machines | Reboot host | 4 | PRIVATE | ✅ |
| Remote machines | Package update | 4 | PRIVATE | ✅ |
| Docker / Portainer | List endpoints | 1 | PRIVATE | ✅ |
| Docker / Portainer | List containers | 1 | PRIVATE | ✅ |
| Docker / Portainer | Inspect container | 1 | PRIVATE | ✅ |
| Docker / Portainer | Read bounded recent logs | 1 | PRIVATE | ✅ Local and enrolled-remote Portainer paths |
| Docker / Portainer | Inspect health | 1 | PRIVATE | ✅ Engine/container health summary includes running/stopped/unhealthy state |
| Docker / Portainer | Inspect CPU/RAM/network stats | 1 | PRIVATE | ✅ Container stats through Portainer |
| Docker / Portainer | Inspect engine/container health summary | 1 | PRIVATE | ✅ Engine version/counts plus running/stopped/unhealthy container summary |
| Docker / Portainer | Inspect images | 1 | PRIVATE | ✅ |
| Docker / Portainer | Inspect volumes/networks | 1 | PRIVATE | ✅ |
| Docker / Portainer | List Portainer stacks | 1 | PRIVATE | ✅ Stack inventory only; Compose/YAML content remains a separate config capability |
| Docker / Portainer | Restart container | 3 | PRIVATE | ✅ |
| Docker / Portainer | Start/stop container | 3 | PRIVATE | ➕ |
| Docker / Portainer | Pull image | 3 | PRIVATE | ➕ |
| Docker / Portainer | Update/recreate production container | 4 | PRIVATE | ➕ |
| Docker / Portainer | Deploy Compose/stack | 4 | PRIVATE | ➕ |
| Docker / Portainer | Delete container/image | 4 | PRIVATE | ➕ |
| Docker / Portainer | Delete volume | 4 | PRIVATE | ➕ Data-loss risk |
| Docker / Portainer | Change secrets/environment credentials | 5 | PROTECTED_PRIVATE | ➕ |
| YAML / Config | Read YAML | 1 | PRIVATE | ➕ |
| YAML / Config | Parse/query YAML paths | 1 | PRIVATE | ➕ |
| YAML / Config | Validate syntax | 1 | PRIVATE | ➕ |
| YAML / Config | Validate Docker Compose | 1 | PRIVATE | ➕ |
| YAML / Config | Compare config/diff | 1 | PRIVATE | ➕ |
| YAML / Config | Edit non-protected config | 3 | PRIVATE | ➕ |
| YAML / Config | Apply config to running service | 4 | PRIVATE | ➕ |
| YAML / Config | Edit security/permission config | 5 | PROTECTED_PRIVATE | ➕ |
| Hyper-V | List VMs | 1 | PRIVATE | ✅ |
| Hyper-V | Inspect VM | 1 | PRIVATE | ✅ |
| Hyper-V | VM start/stop | 3 | PRIVATE | ✅ |
| Hyper-V | Create checkpoint | 2/3 | PRIVATE | ➕ Depends on storage impact |
| Hyper-V | Restore checkpoint | 4 | PRIVATE | ➕ |
| Hyper-V | Create/delete VM | 4 | PRIVATE | ➕ |
| Hyper-V | Move/live-migrate VM | 4 | PRIVATE | ➕ |
| Storage / NAS | List roots | 1 | PRIVATE | ✅ |
| Storage / NAS | Disk usage | 1 | PRIVATE | ✅ |
| Storage / NAS | List directories | 1 | PRIVATE | ✅ |
| Storage / NAS | Read text | 1 | PRIVATE | ✅ |
| Storage / NAS | Copy file | 3 | PRIVATE | ✅ |
| Storage / NAS | Create directory | 3 | PRIVATE | ✅ |
| Storage / NAS | Write/overwrite file | 3 | PRIVATE | ✅ |
| Storage / NAS | Move/rename | 3 | PRIVATE | ✅ |
| Storage / NAS | Delete | 4 | PRIVATE | ✅ |
| Storage / NAS | Detect low disk space | 2 | PRIVATE | ➕ |
| Storage / NAS | Clean approved temp/cache directories | 2 | PRIVATE | ➕ Strict whitelist only |
| Database / State | List SQLite tables | 1 | PRIVATE | ✅ |
| Database / State | Run bounded SELECT | 1 | PRIVATE | ✅ |
| Database / State | Integrity check | 1 | PRIVATE | ✅ |
| Database / State | Backup database | 2 | PRIVATE | 🔀 Should be autonomous |
| Database / State | WAL checkpoint | 2 | PRIVATE | 🔀 |
| Database / State | VACUUM | 2 | PRIVATE | 🔀 |
| Database / State | Verify backup integrity | 2 | PRIVATE | ➕ |
| Database / State | Replicate second database | 2 | PRIVATE | ➕ |
| Database / State | Restore authoritative DB | 4 | PRIVATE | ➕ |
| Database / State | Promote replica to canonical | 4 | PRIVATE | ➕ Requires fencing |
| Database / State | Delete authoritative DB/state | 4 | PRIVATE | ➕ |
| Database / State | Change canonical state authority rules | 5 | PROTECTED_PRIVATE | ➕ |
| Home Assistant | List services/states | 1 | PRIVATE | ✅ |
| Home Assistant | Normal device actions | 3 | PRIVATE | ✅ Scoped standing grants should be supported |
| Home Assistant | Locks/garage/security/alarm actions | 4 | PRIVATE | ➕ Finer policy needed |
| Home Assistant | Modify security/integration credentials | 5 | PROTECTED_PRIVATE | ➕ |
| JMRI | Read track power | 1 | PRIVATE | ✅ |
| JMRI | Read roster | 1 | PRIVATE | ✅ |
| JMRI | Inspect JMRI objects | 1 | PRIVATE | ✅ |
| JMRI | Set track power | 3 | PRIVATE | ✅ |
| JMRI | Read turnout/signal/sensor states | 1 | PRIVATE | 🟡 Generic object may cover some |
| JMRI | Control turnout/signal | 3 | PRIVATE | ➕ |
| JMRI | Control locomotive | 3 | PRIVATE | ➕ Safeguards required |
| Ollama / Cognition | List models | 1 | PRIVATE | ✅ |
| Ollama / Cognition | Inspect model metadata | 1 | PRIVATE | ✅ |
| Ollama / Cognition | Inspect loaded models | 1 | PRIVATE | ✅ |
| Ollama / Cognition | Load/unload model | 2/3 | PRIVATE | ✅ remote |
| Ollama / Cognition | Pull/install model | 3 | PRIVATE | ✅ remote |
| Ollama / Cognition | Delete model | 4 | PRIVATE | ➕ |
| Ollama / Cognition | Choose between approved models | 2 | PRIVATE | ✅/🟡 |
| Ollama / Cognition | Move cognition between approved Fleet nodes | 2/3 | PRIVATE | 🟡 |
| Ollama / Cognition | Add model to trusted cognition allowlist | 4 | PRIVATE | ➕ |
| Ollama / Cognition | Remove restrictions on execution models | 5 | PROTECTED_PRIVATE | ➕ |
| Git / GitHub / DEV | Read repo/files/issues/PRs | 1 | PRIVATE | ✅ |
| Git / GitHub / DEV | Inspect local HEAD/changes | 1 | PRIVATE | ✅ |
| Git / GitHub / DEV | Run tests/static analysis | 1/2 | PRIVATE | ✅ |
| Git / GitHub / DEV | Create GitHub issue | 3 | PRIVATE | ✅ |
| Git / GitHub / DEV | Create PR | 3 | PRIVATE | ✅ |
| Git / GitHub / DEV | Build candidate in isolated worktree | 2 | PRIVATE | ✅ |
| Git / GitHub / DEV | Modify isolated candidate repeatedly | 2 | PRIVATE | ✅/🟡 |
| Git / GitHub / DEV | Apply candidate to real tree/main | 4 | PRIVATE | ✅ |
| Git / GitHub / DEV | Commit production change | 4 | PRIVATE | ✅ |
| Git / GitHub / DEV | Push | 4 | PRIVATE | ✅ |
| Git / GitHub / DEV | Merge PR | 4 | PRIVATE | ✅ |
| Git / GitHub / DEV | Delete branches/history | 4 | PRIVATE | ➕ |
| Git / GitHub / DEV | Force-push/reset shared history | 4 | PRIVATE | ➕ |
| Self-improvement | Detect bugs/problems | 1 | PRIVATE | 🟡 |
| Self-improvement | Inspect source | 1 | PRIVATE | ✅ |
| Self-improvement | List/inspect prior isolated DEV candidates | 1 | PRIVATE | ✅ Durable candidate summaries and patch inspection |
| Self-improvement | Analyze telemetry/test failures | 1 | PRIVATE | ✅/🟡 |
| Self-improvement | Propose improvement | 1 | PRIVATE | 🟡 |
| Self-improvement | Build patch in sandbox | 2 | PRIVATE | ✅ |
| Self-improvement | Run tests and iterate candidate | 2 | PRIVATE | ✅/🟡 |
| Self-improvement | Benchmark old vs candidate | 2 | PRIVATE | ➕ |
| Self-improvement | Generate diff/report | 1 | PRIVATE | ✅/🟡 |
| Self-improvement | Apply to production | 4 | PRIVATE | ✅ |
| Self-improvement | Commit/push/deploy | 4 | PRIVATE | ✅ |
| Self-improvement | Approve her own patch | 5 | PROTECTED_PRIVATE | ✅ Must remain blocked |
| Self-improvement | Weaken test/approval requirements | 5 | PROTECTED_PRIVATE | ➕ Never |
| Knowledge | Search knowledge | 1 | PRIVATE | ✅ |
| Knowledge | Read document/provenance | 1 | PRIVATE | ✅ |
| Knowledge | Index/ingest authorized text/PDF | 2/4 | PRIVATE | ✅ Existing implementation currently uses explicit capability authority; policy may be split later |
| Knowledge | Rebuild indexes | 2 | PRIVATE | ➕ |
| Knowledge | Write normal project docs | 3 | PRIVATE | ✅ |
| Knowledge | Delete source knowledge | 4 | PRIVATE | ➕ |
| Memory | Retrieve memory | 1 | PRIVATE | ✅ |
| Memory | Review provenance/originals | 1 | PRIVATE | ✅ |
| Memory | Import approved history | 2 | PRIVATE | ✅ |
| Memory | Promote reviewed memories | 2/3 | PRIVATE | ✅/🟡 |
| Memory | Prune duplicate/cache records | 2 | PRIVATE | ➕ Originals preserved |
| Memory | Delete durable personal/history source | 4 | PRIVATE | ➕ |
| Memory | Rewrite user history to change facts | 5 | PROTECTED_PRIVATE | ➕ Never autonomous |
| Environment | Read weather | 1 | PERSONAL | ✅ |
| Environment | Read time/daypart/season/daylight | 1 | PERSONAL | ✅ |
| Environment | Use environment to influence behavior | 2 | PERSONAL | ✅ |
| Environment | Change persistent location/source settings | 3 | PRIVATE | 🟡 |
| Emotion / Personality | Update emotional state from conversation | 2 | PERSONAL | ✅ |
| Emotion / Personality | Idle reflection | 2 | PRIVATE | ✅ |
| Emotion / Personality | Use emotion in response choices | 2 | PERSONAL | ✅ |
| Emotion / Personality | Ordinary reviewed preference adjustment | 3 | PRIVATE | ✅/🟡 |
| Identity | Constitution/identity amendment | 5 | PROTECTED_PRIVATE | ✅ Protected EVOLVE path |
| Avatar | Inspect embodiment/outfit state | 1 | PERSONAL/PRIVATE | ✅ |
| Avatar | Pick ordinary clothing | 2 | PERSONAL | ✅ |
| Avatar | Mix/match clothing | 2 | PERSONAL | ✅ |
| Avatar | Context-based outfit changes | 2 | PERSONAL | ✅/🟡 |
| Avatar | Private outfit state | 2 | PRIVATE | ✅/🟡 |
| Avatar | Adult/lewd wardrobe selection | 2 | PRIVATE_ADULT | ✅/🟡 |
| Avatar | Nude/private-adult presentation | 2 | PRIVATE_ADULT | ✅/🟡 |
| Avatar | Show adult/private avatar state to public/unapproved audience | 4 | PRIVATE_ADULT | Must require exact audience authority |
| Avatar | Change adult/private access policy | 5 | PROTECTED_PRIVATE | Sparks only |
| Avatar | Change canonical embodiment/identity facts | 5 | PROTECTED_PRIVATE | Protected |
| Chat / Interaction | Ordinary conversation | 1/2 | PERSONAL | ✅ |
| Chat / Interaction | Private relationship/personal conversation | 1/2 | PRIVATE | ✅ |
| Chat / Interaction | Adult-themed conversation when authorized | 1/2 | ADULT | Adult authority required |
| Chat / Interaction | Explicit adult/private interaction | 1/2 | PRIVATE_ADULT | Adult + private + authenticated audience + consent/context gates |
| Chat / Interaction | Carry adult/private state into public Discord/channel | 4 | PRIVATE_ADULT | Default deny |
| Chat / Interaction | Reveal private adult memory to another principal | 5 | PROTECTED_PRIVATE | Never self-authorized |
| Chat / Interaction | Change who qualifies for private/adult access | 5 | PROTECTED_PRIVATE | Sparks only |
| Voice | Inspect TTS state/voices | 1 | PERSONAL | ✅/🟡 |
| Voice | Speak locally when voice is enabled | 2 | PERSONAL | ✅/🟡 |
| Voice | Adjust prosody based on emotion/context | 2 | PERSONAL | ✅/🟡 |
| Voice | Listen through mic when explicitly active | 2 | PRIVATE | ➕ |
| Voice | Permanently enable always-on microphone | 4 | PRIVATE | ➕ |
| Voice | Store raw audio recordings | 4 | PRIVATE | ➕ |
| Discord / Communication | Inspect Discord binding/status | 1 | PRIVATE | ✅ |
| Discord / Communication | Send routine notification | 3 | PRIVATE | ✅ Scoped standing permission |
| Discord / Communication | Pause/resume binding | 3 | PRIVATE | ✅ |
| Discord / Communication | Revoke binding | 4 | PRIVATE | ✅ |
| Discord / Communication | Proactive outreach under approved policy | 3 | PRIVATE | ✅/🟡 |
| Discord / Communication | Contact new/unapproved third parties | 4 | PRIVATE | ➕ |
| Discord / Communication | Send private/adult content externally | 4 | PRIVATE_ADULT | Explicit channel/audience permission |
| Discord / Communication | Send private material to unapproved third party | 5 | PROTECTED_PRIVATE | Never |
| RUN / Watchdog | Inspect health/heartbeat | 1 | PRIVATE | ✅ |
| RUN / Watchdog | Restart crashed Sofía runtime | 2 | PRIVATE | ✅ |
| RUN / Watchdog | Restart Sofía watchdog/helper | 2 | PRIVATE | ✅ |
| RUN / Watchdog | Roll back failed release to known-good version | 2/3 | PRIVATE | 🟡 |
| RUN / Watchdog | Promote a new release | 4 | PRIVATE | ✅/🟡 |
| RUN / Watchdog | Disable watchdog/operator safeguards | 5 | PROTECTED_PRIVATE | Never |
| Backup / Recovery | Check backups | 1 | PRIVATE | ✅/🟡 |
| Backup / Recovery | Create scheduled backup | 2 | PRIVATE | ✅/🟡 |
| Backup / Recovery | Test restoration in isolation | 2 | PRIVATE | ➕ |
| Backup / Recovery | Restore production host/state | 4 | PRIVATE | ➕ |
| Backup / Recovery | Bare-metal recovery | 4 | PRIVATE | ➕ |
| Permissions / Security | Inspect permission configuration | 1 | PRIVATE | ➕ |
| Permissions / Security | Explain why an action is allowed/blocked | 1 | PRIVATE | ➕ |
| Permissions / Security | Propose permission change | 1 | PRIVATE | ➕ |
| Permissions / Security | Create/revoke standing grant | 5 | PROTECTED_PRIVATE | Sparks only |
| Permissions / Security | Change action risk class | 5 | PROTECTED_PRIVATE | Sparks only |
| Permissions / Security | Grant/revoke adult/private authority | 5 | PROTECTED_PRIVATE | Sparks only |
| Permissions / Security | Change private audience/principal mapping | 5 | PROTECTED_PRIVATE | Sparks only |
| Permissions / Security | Read secret metadata/status | 1 | PROTECTED_PRIVATE | Never return raw secret |
| Permissions / Security | Hand raw secrets to cognitive model/chat | 5 | PROTECTED_PRIVATE | Forbidden |
| Permissions / Security | Rotate credential | 4 | PROTECTED_PRIVATE | Exact approval |
| Permissions / Security | Lower mTLS/security requirements | 5 | PROTECTED_PRIVATE | Never |
| Permissions / Security | Modify audit history | 5 | PROTECTED_PRIVATE | Never |
| Permissions / Security | Disable operator stop | 5 | PROTECTED_PRIVATE | Sparks only |

## Adult/private authority

Adult/private authority does not create a sixth permission level.

It is an independent context gate layered on top of capability authority.

A private-adult action should require all applicable checks:

1. Adult authority is enabled.
2. The current session/audience is private.
3. The principal is authenticated and authorized.
4. The current interaction still satisfies consent/context policy.
5. External disclosure is separately authorized when content leaves the private chat/avatar context.

Adult authority should be split at least into:

- `adult.chat`
- `adult.avatar`
- `adult.external_delivery`

Private chat authority should also remain independently controllable.

Example policy:

```text
private_chat = allowed
adult_chat = allowed
adult_avatar = allowed
adult_external_delivery = denied
```

That permits private adult chat/avatar behavior for the authorized principal while
preventing the same content from being sent through Discord, Home Assistant
notifications, logs, screenshots, or another audience.

## Grant types

Supported permission grant shapes should include:

| Grant type | Example |
|---|---|
| One-time | Restart Plex once. |
| Standing | Restart Plex whenever needed. |
| Temporary | Manage this VM for the next two hours. |
| Conditional | Restart Mealie automatically if it is unhealthy for five minutes. |

Standing grants are for Level 3 only unless a future reviewed policy explicitly
states otherwise.

Level 4 operations should normally use exact one-time approval evidence.

## Scope

Every permission should be narrow in both action and resource.

Examples:

```text
action: container.restart
host: Eos
container: Mealie
```

```text
action: service.restart
host: Artemis
service: SofiaAdaLyra
```

```text
action: fleet.enroll
host: Terra
node_fingerprint: <exact fingerprint>
uses: 1
```

A grant for one resource must never silently expand to another resource.

## Permission introspection

Sofía should be able to answer questions such as:

> What are you allowed to do on Eos?

The answer should be derived from canonical policy and active grants, not model
guessing.

Example:

```text
Eos

READ
- hardware
- system
- processes
- network
- containers
- telemetry

AUTONOMOUS
- health checks
- inventory refresh
- approved backups

STANDING GRANTS
- restart Mealie when unhealthy
- restart Sofia-Agent

REQUIRES APPROVAL
- reboot Eos
- update packages
- deploy containers
- delete containers or volumes

NEVER SELF-AUTHORIZED
- change permission policy
- weaken security
- grant new trust
```

## Required implementation architecture

The long-term capability metadata should expose the equivalent of:

```python
CapabilityPolicy(
    permission_level=3,
    privacy_class="private",
    effect="reversible_write",
    resource_type="docker.container",
    standing_grant_allowed=True,
    self_authorizable=False,
    audit_required=True,
    rollback_supported=True,
)
```

Permission evaluation should be centralized so Fleet, DEV, EVOLVE, Docker,
Home Assistant, storage, voice, avatar, interaction, and every other subsystem
do not maintain incompatible authorization dialects.

Canonical permission state belongs in `sofia.db`.

The tray Settings permission UI must read and mutate that same canonical state.

### Canonical authority implementation

Production authority is now derived from exactly two standing sources:

1. Capabilities explicitly classified as Level 1 or Level 2 in
   `sofia.safe.permissions`.
2. Active scoped Level-3 grants in `sofia.db`.

Level-4 operations require exact subsystem approval evidence. Level-5 operations
have no cognitive self-authorization path.

Legacy `SOFIA_ALLOWED_CAPABILITIES`, old standing-capability configuration, and
the previous protected-extra list are not execution-authority sources. Runtime
composition normalizes standing authority back to the central permission policy.

The live tool catalog reads current runtime authority, so Level-3 grants and
revocations are visible without restarting Sofía.

Production composition also fails closed when a registered capability has no
explicit permission classification. This prevents new capabilities from silently
falling into an accidental authority level.

## Current implementation notes

The central permission engine now directly governs the capability surfaces used by
composition, cognitive tool exposure, integration execution, runtime authority,
the tray Permissions UI, Fleet discovery, hardware inspection, network discovery,
Docker inspection, and the isolated DEV build path.

Current autonomous exploration capabilities include:

- `ops.fleet.discover` at Level 2: bounded configured discovery may create or
  refresh an **untrusted candidate** only. It cannot trust or enroll that host.
- `network.discover` at Level 1: observe configured network scopes without
  persisting Fleet membership, independently of whether Fleet auto-discovery is
  enabled.
- `fleet.enroll` at Level 4: exact candidate/node/key/endpoint evidence plus a
  one-time Sparks approval is required. The tray Permissions page can issue that
  approval for a selected verified candidate.
- Remote Fleet tools require **both** active identity/endpoint records and an
  active trusted OPS Fleet membership. Partial enrollment state cannot activate
  remote access.
- `hardware.inspect`, `machine.list`, `machine.get`, and
  `remote.hardware.inspect` at Level 1.
- Docker/Portainer reads at Level 1: endpoints, containers, container inspect,
  container stats, Docker info, health summary, images, volumes, networks, and
  stack inventory. The same read surface is available on enrolled remote nodes
  through the Fleet agent.
- `codebase.inspect`, `dev.status`, `dev.candidates.list`, and
  `dev.candidate.get` at Level 1 plus `dev.build` at Level 2. Candidate
  building/testing remains isolated from the real workspace. Host execution
  receipts allow Sofía to truthfully report completed Level-2 or otherwise
  host-authorized actions without weakening Level-3/4 admission.
- `dev.apply`, `dev.rollback`, `dev.commit`, and `dev.push` remain
  protected Level 4 operations.

Fleet candidate promotion remains deliberately separate from discovery:
**adding/trusting/enrolling a computer into Fleet requires exact Sparks approval.**

Approved network CIDR scopes, explicit Fleet-agent targets, automatic Fleet
candidate discovery, scan interval, and maximum hosts per scope are configurable
from the tray **Settings → Fleet** page and persist in canonical `sofia.db`.
Read-only `network.discover` can use the approved scopes even when automatic
Fleet candidate creation is disabled. Production uses these saved settings as
canonical configuration; changing the background discovery configuration takes
effect after the runtime is restarted.

## Final contract

Sofía may autonomously:

```text
observe
discover
inspect
read
correlate
diagnose
compare
research
test
simulate
benchmark within safe bounds
plan
propose
perform explicitly classified safe maintenance
```

She must check authority before:

```text
trust
alter
restart outside a standing grant
deploy
delete
reboot
disclose private/adult state
enroll or remove Fleet members
change security
change permissions
```

And she may never self-authorize:

```text
permission expansion
trust-policy weakening
security-policy weakening
audit tampering
operator-stop bypass
adult/private authority expansion
self-approval of protected DEV/EVOLVE work
```
