# Sofía Project Tool & Operator Guide

**Status:** current production-tool guide for `main`, updated 2026-10-05.

This is the practical operator guide for Sofía Ada Lyra: how to start her, what
tools exist, what permission level each tool uses, how to enable consequential
tools, how to configure integrations, and how to invoke the tools from chat or
operator CLIs.

The canonical permission model is documented in [permission.md](permission.md).
The code source of truth is `src/sofia/safe/permissions.py`.

---

## 1. Start Sofía

From the repository virtual environment:

```powershell
python -m sofia
```

That launches the production desktop workbench and ensures the Windows tray
agent is running.

Terminal-only chat:

```powershell
python -m sofia --cli
```

Desktop UI directly:

```powershell
python -m sofia.ui
```

On Windows, right-click the Sofía tray icon and choose **Settings…** to open the
master settings window.

---

## 2. Permission levels

| Level | Meaning | How it is enabled |
|---|---|---|
| **1 — Observe / Read** | Read-only inspection, discovery, analysis, planning | Automatic. Do not grant anything. |
| **2 — Safe Autonomous** | Bounded, low-risk, auditable maintenance | Automatic. Do not grant anything. |
| **3 — Reversible / Scoped** | Reversible change | Standing scoped grant or one-time exact approval |
| **4 — Protected / High Impact** | Trust, reboot, destructive/deployment-style action | Exact approval only |
| **5 — Never Self-Authorized** | Permission/security/authority change | Local Sparks/operator action only; Sofía cannot self-grant it |

### Rule of thumb

```text
READ / INSPECT / DISCOVER / DIAGNOSE / PLAN = automatic
SAFE ISOLATED MAINTENANCE = automatic
REVERSIBLE CHANGE = scoped grant or exact approval
TRUST / DELETE / REBOOT / DEPLOY = exact approval
CHANGE PERMISSIONS / SECURITY = Sparks only
```

---

## 3. Inspect permissions

### From chat

Ask Sofía:

```text
What permissions do you have?
What are you allowed to do?
What standing grants are active?
```

The `permissions.inspect` capability is Level 1, owner-private, read-only.

### From CLI

List active grants:

```powershell
python -m sofia.safe.permissions_cli list --active-only
```

List all grants including expired/revoked:

```powershell
python -m sofia.safe.permissions_cli list
```

Inspect one capability:

```powershell
python -m sofia.safe.permissions_cli show portainer.container.restart
```

Show every capability grouped by permission level:

```powershell
python -m sofia.safe.permissions_cli levels
```

---

## 4. Turn on Level-3 permissions

### Preferred: tray Settings

1. Right-click the Sofía tray icon.
2. Choose **Settings…**.
3. Open **Permissions**.
4. Choose the Level-3 capability.
5. Enter a narrow **Scope JSON**.
6. Optionally enter an expiry.
7. Create the grant.

A standing grant becomes visible to live chat authority without restarting
Sofía.

### CLI

Example: allow restart of only the Mealie container:

```powershell
python -m sofia.safe.permissions_cli grant portainer.container.restart --scope-json '{"container_id":"mealie"}'
```

Example: allow restart of one local service:

```powershell
python -m sofia.safe.permissions_cli grant local.service.restart --scope-json '{"name":"SofiaAdaLyra"}'
```

Temporary grant:

```powershell
python -m sofia.safe.permissions_cli grant portainer.container.restart --scope-json '{"container_id":"mealie"}' --expires-minutes 120
```

A scope of `{}` is a broad grant for that capability. It is valid but should
normally be avoided in favor of exact resource scope.

Revoke a grant:

```powershell
python -m sofia.safe.permissions_cli revoke <grant-id>
```

Level-3 tools remain hidden from action turns when no standing grant is active.
When a matching grant exists, the tool may be exposed, but the execution layer
still checks that the actual parameters match the grant scope.

---

## 5. One-time exact approvals

General local protected/reversible execution approvals are recorded with:

```powershell
python -m sofia.safe.approve_execution --capability <capability> --parameters-json '<exact-json>'
```

Example:

```powershell
python -m sofia.safe.approve_execution --capability local.host.reboot --parameters-json '{}'
```

The command prints an `approval_id`. The approval is time-bounded, exact to the
capability and parameters, and consumable once. Active one-time approvals are
fed into live chat authority, so the protected tool becomes available only
while that approval is active.

Then make the matching request and include the ID, for example:

```text
Reboot this host using approval ID <approval-id>.
```

Execution verifies that the capability and exact parameters match before
consuming the approval. A mismatched, expired, or already-consumed approval is
rejected.

Not every protected subsystem uses this generic approval store. DEV, EVOLVE,
Fleet trust, and remote Fleet operations have specialized workflows described
below.

---

## 5A. Level-5 authority-policy operations

These names are part of the permission model but are **not cognitive tools Sofía
may invoke for herself**:

| Authority operation | Level | Meaning |
|---|---:|---|
| `permissions.grant` | 5 | Create/expand permission authority |
| `permissions.revoke` | 5 | Revoke permission authority |
| `permissions.classify` | 5 | Change a capability's risk classification |
| `privacy.authority.change` | 5 | Change private/adult authority |
| `fleet.trust-policy.change` | 5 | Change Fleet trust policy |

Use the local operator surfaces documented above, especially
`sofia.safe.permissions_cli` and the tray **Permissions** page. Sofía may
inspect or propose these changes, but the cognitive runtime cannot self-authorize
them.

## 6. Emergency operator stop

Status:

```powershell
python -m sofia.safe.operator_stop_cli status
```

Stop side effects:

```powershell
python -m sofia.safe.operator_stop_cli on --reason "maintenance"
```

Release the stop:

```powershell
python -m sofia.safe.operator_stop_cli off --reason "maintenance complete"
```

The stop is owned by Sparks and blocks side effects while leaving bounded
observation available.

---

# Production cognitive tools

The easiest way to run cognitive tools is to ask naturally in Sofía chat. The
examples below are phrased the way an operator would actually use them.

## 7. Core tool catalog, files, and code

| Capability | Level | What it does | Example chat request |
|---|---:|---|---|
| `tool.catalog` | 1 | Lists registered tools and authorization state | “What tools can you use right now?” |
| `permissions.inspect` | 1 | Shows live permission levels and grants | “What permissions do you have?” |
| `filesystem.inspect` | 1 | Read/list/search files inside the authorized project root | “Read src/sofia/runtime/runtime.py.” |
| `filesystem.changes` | 1 | Shows filesystem changes since the previous observation | “What changed since the last runtime?” |
| `codebase.inspect` | 1 | Structural Python codebase inspection | “Inspect the codebase architecture.” |

Filesystem tools are root-confined. Chat text cannot widen the filesystem root.

---

## 8. Local system and hardware

No permission setup is required for these reads.

| Capability | Level | What it does | Example |
|---|---:|---|---|
| `process.inspect` | 1 | Running processes, optional PID/limit | “Show me the top local processes.” |
| `system.inspect` | 1 | OS, hostname, identity, uptime | “What system are you running on?” |
| `network.inspect` | 1 | Interfaces, routes, DNS | “Inspect the local network configuration.” |
| `service.inspect` | 1 | Local services | “Show services containing Sofia.” |
| `hardware.inspect` | 1 | CPU, GPU, RAM, storage, adapters, virtualization | “Show this computer’s hardware.” |
| `machine.list` | 1 | Durable known-machine inventory | “List known machines.” |
| `machine.get` | 1 | One durable machine observation | “Inspect machine <machine-id>.” |
| `machine.discover.local` | 1 | Fresh local identity/hardware without persistence | “Discover this machine right now.” |
| `machine.refresh.local` | 2 | Refreshes and persists local inventory | “Refresh this machine’s inventory.” |

### Machine location operator CLI

Set local machine location:

```powershell
python -m sofia.machine.location_cli set-local --label "Home Lab" --timezone America/Chicago --latitude <lat> --longitude <lon>
```

List configured machine locations:

```powershell
python -m sofia.machine.location_cli list
```

---

## 9. Fleet and computers on the network

### Configure discovery from tray

Open **Settings → Fleet**.

Configure:

- **Approved network scopes**, such as `192.168.1.0/24`
- Optional explicit Fleet-agent targets
- Discovery interval
- Maximum hosts per scope
- Optional **automatic Fleet candidate discovery**

Important distinction:

- `network.discover` is read-only and does **not** add anything to Fleet.
- `ops.fleet.discover` may create/update an **untrusted candidate**.
- `fleet.enroll` is Level 4 and requires your exact approval.

You may leave automatic Fleet candidate discovery off while still allowing
read-only network discovery over approved scopes.

| Capability | Level | What it does | Example |
|---|---:|---|---|
| `network.discover` | 1 | Scans approved scopes and reports computers/devices without persisting Fleet membership | “Show me computers on the network.” |
| `ops.fleet.list` | 1 | Lists Fleet hosts/candidates | “List the Fleet.” |
| `ops.fleet.get` | 1 | Inspects one Fleet host | “Inspect Eos in Fleet.” |
| `ops.fleet.enrollment_evidence` | 1 | Shows exact observed node/key/endpoint evidence | “Is this candidate ready to enroll?” |
| `ops.fleet.discover` | 2 | Runs bounded discovery and persists only untrusted candidates | “Discover Fleet candidates.” |
| `fleet.enroll` | 4 | Promotes one exact verified candidate into trusted Fleet membership | Use tray approval below |
| `ops.telemetry.latest` | 1 | Latest telemetry for one Fleet host | “Show latest telemetry for Eos.” |
| `ops.placement.choose` | 1 | Chooses eligible workload placement without moving anything | “Where could this workload run?” |
| `ops.drift.detect` | 1 | Detects desired-vs-observed Fleet drift | “Check Fleet drift.” |
| `ops.drift.propose` | 1 | Produces conservative repair proposals | “Propose repairs for Fleet drift.” |
| `ops.reconcile.preview` | 1 | Preview canonical reconciliation | “Preview Fleet reconciliation.” |
| `ops.reconcile.active` | 1 | Active reconciliation observations | “Show active Fleet reconciliation.” |
| `ops.migration.plan` | 1 | Plans workload migration only | “Plan moving workload X from A to B.” |
| `ops.migration.execute` | 4 | Executes one exact approved typed workload migration | “Execute Fleet migration X with approval ID Y.” |
| `ops.migration.receipt` | 1 | Reads durable migration stage and receipts | “Show migration receipt X.” |
| `ops.maintenance.receipt` | 1 | Reads a verified maintenance receipt | “Show maintenance receipt <id>.” |

### Add a discovered computer to Fleet

Preferred path:

1. Run/allow discovery.
2. Open **Settings → Permissions**.
3. In **Fleet candidates**, select a candidate.
4. Confirm that node ID, certificate key, and endpoint are correct.
5. Click **Approve & enroll selected**.

The approval is Level 4, one-time, bound to the exact:

- host ID
- node UUID
- certificate public-key SHA-256
- endpoint hostname
- endpoint port

Changed or stale discovery evidence is rejected.

---

## 10. Remote Fleet computer reads

These are Level 1 once the node is enrolled and its mTLS endpoint is trusted.
No per-use grant is needed for reads.

| Capability | Level | Example |
|---|---:|---|
| `remote.nodes` | 1 | “List enrolled remote nodes.” |
| `remote.process.inspect` | 1 | “Show processes on Eos.” |
| `remote.system.inspect` | 1 | “Show system state on Eos.” |
| `remote.network.inspect` | 1 | “Inspect Eos networking.” |
| `remote.service.inspect` | 1 | “Show services on Eos.” |
| `remote.hardware.inspect` | 1 | “Show Eos hardware.” |
| `remote.vm.list` | 1 | “List VMs on Artemis.” |
| `remote.vm.get` | 1 | “Inspect VM Persephone on Artemis.” |
| `remote.ollama.inference_policy` | 1 | “Show Eos Ollama inference policy.” |
| `remote.ollama.models` | 1 | “List Ollama models on Eos.” |
| `remote.ollama.running` | 1 | “What Ollama models are loaded on Eos?” |
| `remote.ollama.show` | 1 | “Show qwen model metadata on Eos.” |
| `remote.container.list` | 1 | “List Docker containers on Eos.” |
| `remote.container.get` | 1 | “Inspect the Mealie container on Eos.” |
| `remote.container.stats` | 1 | “Show Mealie CPU/RAM stats on Eos.” |
| `remote.container.logs` | 1 | “Show the last 200 Mealie logs on Eos.” |
| `remote.container.info` | 1 | “Show Docker engine info on Eos.” |
| `remote.container.summary` | 1 | “Check Docker health on Eos.” |
| `remote.container.images` | 1 | “List Docker images on Eos.” |
| `remote.container.volumes` | 1 | “List Docker volumes on Eos.” |
| `remote.container.networks` | 1 | “List Docker networks on Eos.” |
| `remote.container.stacks` | 1 | “List Portainer stacks on Eos.” |
| `remote.release.current` | 1 | “Show the active release on remote host Eos.” |

---

## 11. Remote Fleet agent setup

Controller transport configuration:

```text
SOFIA_REMOTE_CA=<CA PEM>
SOFIA_REMOTE_CLIENT_CERT=<controller client cert PEM>
SOFIA_REMOTE_CLIENT_KEY=<controller private key PEM>
SOFIA_REMOTE_MAX_INVENTORY_AGE_SECONDS=300
```

Agent environment includes:

```text
SOFIA_AGENT_NODE_ID=<UUID>
SOFIA_AGENT_NODE_NAME=<name>
SOFIA_AGENT_LISTEN_HOST=0.0.0.0
SOFIA_AGENT_LISTEN_PORT=7443
SOFIA_AGENT_SERVER_CERT=<server certificate>
SOFIA_AGENT_SERVER_KEY=<server private key>
SOFIA_AGENT_CLIENT_CA=<CA PEM>
SOFIA_AGENT_CLIENT_PUBLIC_KEY_SHA256=<controller public-key fingerprint>
SOFIA_AGENT_LEDGER=<agent SQLite ledger>
```

Run foreground agent:

```powershell
python -m sofia.distributed.agent_main
```

Or with a config file:

```powershell
python -m sofia.distributed.agent_main --config <agent-config>
```

Windows Fleet-agent service:

```powershell
python -m sofia.distributed.windows_agent_service_admin install --config <agent-config>
python -m sofia.distributed.windows_agent_service_admin start
python -m sofia.distributed.windows_agent_service_admin validate --config <agent-config>
python -m sofia.distributed.windows_agent_service_admin stop
python -m sofia.distributed.windows_agent_service_admin remove
```

Low-level operator provisioning remains available:

```powershell
python -m sofia.distributed.operator fingerprint-cert <server.pem>
python -m sofia.distributed.operator enroll --node-id <uuid> --name <name> --server-cert <server.pem>
python -m sofia.distributed.operator endpoint --node-id <uuid> --hostname <host> --port 7443
```

The tray candidate-enrollment flow is preferred for normal new-machine trust
because it binds approval to live discovery evidence.

---

## 12. Remote Fleet mutations

Remote mutations are protected and also require an exact durable remote grant.

| Host capability | Remote grant capability/operation |
|---|---|
| `remote.service.start` | `service.manage / start` |
| `remote.service.stop` | `service.manage / stop` |
| `remote.service.restart` | `service.manage / restart` |
| `remote.host.reboot` | `system.manage / reboot` |
| `remote.package.update` | `package.manage / update` |
| `remote.vm.start` | `vm.manage / start` |
| `remote.vm.stop` | `vm.manage / stop` |
| `remote.ollama.pull` | `llm.manage / pull` |
| `remote.ollama.load` | `llm.manage / load` |
| `remote.ollama.unload` | `llm.manage / unload` |
| `remote.container.restart` | `container.manage / restart` |

Create a time-bounded remote grant:

```powershell
python -m sofia.distributed.operator grant --node-id <uuid> --capability service.manage --operation restart --hours 2
```

Revoke it:

```powershell
python -m sofia.distributed.operator revoke-grant --grant-id <grant-uuid>
```

Retire a node and revoke identity/endpoint/grants:

```powershell
python -m sofia.distributed.operator retire --node-id <uuid>
```

---

## 13. Docker / Portainer

Configure the cognitive Portainer adapter:

```text
SOFIA_PORTAINER_URL=https://<portainer>
SOFIA_PORTAINER_API_KEY=<local secret>
SOFIA_PORTAINER_ENDPOINT_ID=<endpoint-id>
```

Agent-side Docker inspection uses:

```text
SOFIA_AGENT_PORTAINER_URL=https://<portainer>
SOFIA_AGENT_PORTAINER_API_KEY=<local secret>
SOFIA_AGENT_PORTAINER_ENDPOINT_ID=<endpoint-id>
```

### Read-only Docker tools

All are Level 1.

| Capability | Example |
|---|---|
| `portainer.endpoints` | “List Portainer endpoints.” |
| `portainer.containers` | “List Docker containers.” |
| `portainer.container` | “Inspect container Mealie.” |
| `portainer.container.stats` | “Show Mealie container stats.” |
| `portainer.container.logs` | “Show the last 200 Mealie logs.” |
| `portainer.info` | “Show Docker engine info.” |
| `portainer.summary` | “Check Docker health.” |
| `portainer.images` | “List Docker images.” |
| `portainer.volumes` | “List Docker volumes.” |
| `portainer.networks` | “List Docker networks.” |
| `portainer.stacks` | “List Portainer stacks.” |

Container logs are bounded by `tail` and `max_bytes`; the adapter does not
offer an unbounded log stream.

### Restart a container

`portainer.container.restart` is Level 3.

Grant only Mealie:

```powershell
python -m sofia.safe.permissions_cli grant portainer.container.restart --scope-json '{"container_id":"mealie"}'
```

Then ask:

```text
Restart the Mealie container.
```

The live authority will expose the restart tool because the standing grant is
active; execution still verifies the container ID against the grant.

---

## 14. Home Assistant and notifications

Cognitive integration variables:

```text
SOFIA_HOME_ASSISTANT_URL=http://<host>:8123
SOFIA_HOME_ASSISTANT_TOKEN=<local secret>
SOFIA_NOTIFICATION_HA_SERVICE=<optional notify service name>
```

The Settings UI also owns Sofía's durable environment/Home Assistant context and
protected token storage. Environment/weather settings hot-reload; integration
tool registration is still determined at runtime composition, so restart Sofía
after changing integration availability.

| Capability | Level | Example |
|---|---:|---|
| `home_assistant.services` | 1 | “List Home Assistant services.” |
| `home_assistant.states` | 1 | “List Home Assistant entity states.” |
| `home_assistant.state` | 1 | “What is sensor.office_temperature?” |
| `home_assistant.service.call` | 4 | Protected exact service call |
| `notification.send` | 3 | “Send me a Home Assistant notification.” |

`notification.send` is specifically the configured Home Assistant notification
tool. Sofía's autonomous companion outreach does not require Home Assistant: it
can use the desktop tray notification channel and, when Discord is configured,
the owner DM channel. Those deliveries are produced by the outreach runtime,
not by this Home Assistant cognitive tool.

For routine notification permission:

```powershell
python -m sofia.safe.permissions_cli grant notification.send --scope-json '{}'
```

Use narrower scope when the exact message/title is predetermined.

---

## 15. JMRI

Configure:

```text
SOFIA_JMRI_URL=http://<jmri-host>:12080
```

| Capability | Level | Example |
|---|---:|---|
| `jmri.power` | 1 | “What is track power?” |
| `jmri.roster` | 1 | “Show the locomotive roster.” |
| `jmri.object` | 1 | “Inspect JMRI turnout LT1.” |
| `jmri.power.set` | 3 | “Turn LocoNet track power on.” |

Grant a scoped power action by matching the request parameters you intend to
allow, or use a one-time approval.

---

## 16. GitHub

Configure:

```text
SOFIA_GITHUB_REPOSITORY=Crazysodaman/SofiaAdaLyra
SOFIA_GITHUB_TOKEN=<local token, optional for some public reads>
```

| Capability | Level | Example |
|---|---:|---|
| `github.repository` | 1 | “Show repository metadata.” |
| `github.issues` | 1 | “List open GitHub issues.” |
| `github.file` | 1 | “Read ROADMAP.md from GitHub.” |
| `github.pull_requests` | 1 | “List open PRs.” |
| `github.issue.create` | 3 | “Create an issue titled X.” |
| `github.pull_request.create` | 3 | “Create a PR from branch X to main.” |
| `github.pull_request.merge` | 4 | Protected merge |

This project policy currently uses `main` directly for our repository work;
do not create branches merely because the GitHub adapter supports PR creation.

---

## 17. Ollama

Configure:

```text
SOFIA_OLLAMA_URL=http://127.0.0.1:11434
```

| Capability | Level | Example |
|---|---:|---|
| `ollama.models` | 1 | “List installed Ollama models.” |
| `ollama.running` | 1 | “Which Ollama models are loaded?” |
| `ollama.model.show` | 1 | “Show qwen3:14b metadata.” |

Remote Ollama inspection and management are described in the Fleet sections.

---

## 18. Discord

Run Discord:

```powershell
python -m sofia.discord run
```

Operator status:

```powershell
python -m sofia.discord status
```

Other direct operator controls:

```powershell
python -m sofia.discord pause
python -m sofia.discord resume
python -m sofia.discord revoke
python -m sofia.discord reenroll
```

Cognitive capabilities:

| Capability | Level |
|---|---:|
| `discord.status` | 1 |
| `discord.pause` | 3 |
| `discord.resume` | 3 |
| `discord.revoke` | 4 |

Discord owner/bot/channel settings and the bot token can be configured under
**Settings → Integrations → Discord**.

---

## 19. Local services, reboot, and package maintenance

Available on Windows/Linux.

| Capability | Level | Parameters |
|---|---:|---|
| `local.service.start` | 3 | `name` |
| `local.service.stop` | 3 | `name` |
| `local.service.restart` | 3 | `name` |
| `local.host.reboot` | 4 | none |
| `local.package.update` | 4 | `package` |

Example standing grant:

```powershell
python -m sofia.safe.permissions_cli grant local.service.restart --scope-json '{"name":"SofiaAdaLyra"}'
```

Typed fixed command templates are used. A generic shell is not exposed.

---

## 20. Hyper-V

Windows only.

| Capability | Level | Example |
|---|---:|---|
| `hyperv.vms` | 1 | “List local VMs.” |
| `hyperv.vm` | 1 | “Inspect Persephone.” |
| `hyperv.vm.start` | 3 | “Start Persephone.” |
| `hyperv.vm.stop` | 3 | “Stop Persephone.” |

Grant one VM start:

```powershell
python -m sofia.safe.permissions_cli grant hyperv.vm.start --scope-json '{"name":"Persephone"}'
```

---

## 21. Storage / NAS

Additional roots:

```text
SOFIA_STORAGE_ROOTS=<root1>;<root2>
```

On non-Windows platforms use the OS path separator.

Configured roots always include the authorized filesystem root and state
directory. Paths are root-confined; traversal/symlink escapes are denied.

| Capability | Level |
|---|---:|
| `storage.roots` | 1 |
| `storage.usage` | 1 |
| `storage.list` | 1 |
| `storage.read_text` | 1 |
| `storage.write_text` | 3 |
| `storage.mkdir` | 3 |
| `storage.copy` | 3 |
| `storage.move` | 3 |
| `storage.delete` | 4 |

Example:

```text
List storage roots.
List the docs folder in storage root 0.
Read docs/notes.txt from storage root 0.
```

---

## 22. SQLite state tools

| Capability | Level | Use |
|---|---:|---|
| `sqlite.state.tables` | 1 | List tables |
| `sqlite.state.query` | 1 | Bounded SELECT/read query only |
| `sqlite.state.integrity` | 1 | `PRAGMA integrity_check` |
| `sqlite.state.backup` | 2 | Consistent backup |
| `sqlite.state.wal_checkpoint` | 2 | Explicit WAL checkpoint |
| `sqlite.state.vacuum` | 2 | VACUUM |

Arbitrary SQLite writes are not exposed.

Example:

```text
Run an integrity check on your state database.
Back up your state database.
```

### Backup/recovery operator CLI

Create:

```powershell
python -m sofia.ops.backup_cli create --key <key> --destination <directory> --failure-domain <name>
```

Verify:

```powershell
python -m sofia.ops.backup_cli verify --key <key> --backup-dir <directory>
```

Rehearse restore:

```powershell
python -m sofia.ops.backup_cli rehearse --key <key> --backup-dir <directory> --verifier <name>
```

The CLI also provides `restore`, `rotate`, and `objectives`; inspect help
before production restore:

```powershell
python -m sofia.ops.backup_cli --help
```

---

## 23. Knowledge tools

| Capability | Level | Example |
|---|---:|---|
| `knowledge.search` | 1 | “Search project knowledge for Fleet fencing.” |
| `knowledge.document` | 1 | “Read knowledge document <id>.” |
| `knowledge.ingest.text` | 2 | “Ingest docs/manual.txt.” |
| `knowledge.ingest.pdf` | 2 | “Ingest manuals/controller.pdf.” |
| `knowledge.document.write` | 3 | “Write docs/design-note.md.” |

Text/PDF ingestion is bounded safe-autonomous indexing. Project document writing
requires a scoped Level-3 grant or one-time exact approval.

---

## 24. Self-improvement / DEV

The safe path deliberately separates **build/test** from **apply/commit/push**.

| Capability | Level | What it does |
|---|---:|---|
| `dev.status` | 1 | Git HEAD + working-tree status |
| `dev.candidates.list` | 1 | List durable isolated candidates |
| `dev.candidate.get` | 1 | Inspect one candidate/patch |
| `dev.build` | 2 | Build/test in detached isolated worktree |
| `dev.apply` | 4 | Apply reviewed candidate to real workspace |
| `dev.rollback` | 4 | Roll back exact applied candidate |
| `dev.commit` | 4 | Commit exact approved candidate paths |
| `dev.push` | 4 | Push exact approved HEAD |

Normal use:

```text
Inspect your current code status.
Work on self-improvement for <problem>.
Build and test an isolated candidate restricted to <paths>.
Show me the candidate diff.
```

`dev.build` does not require approval and does not modify the real workspace.

### Approve DEV apply/rollback/commit/push

Example apply approval:

```powershell
python -m sofia.safe.dev_approve --operation apply --proposal-id <proposal-id> --parameters-json '{"proposal_id":"<proposal-id>"}'
```

Commit approval requires the exact commit message in the parameter JSON:

```powershell
python -m sofia.safe.dev_approve --operation commit --proposal-id <proposal-id> --parameters-json '{"proposal_id":"<proposal-id>","message":"<commit message>"}'
```

Push approval requires the exact branch/remote parameters expected by the tool.

After recording the approval, make the matching chat request and include the
returned ID:

```text
Apply candidate <proposal-id> using approval ID <approval-id>.
Commit candidate <proposal-id> with message "<message>" using approval ID <approval-id>.
```

Active DEV approvals are fed into live authority, so only the approved DEV
operation becomes available. DEV approvals are short-lived, exact, one-time,
and Sparks-only.

---

## 25. Governed evolution / EVOLVE

EVOLVE turns durable evidence into reviewable proposals. Proposal creation,
isolated code-candidate construction, verification, and outcome acceptance are
bounded autonomous operations. Applying or rolling back canonical state/code
still requires the exact external approval appropriate to that operation.

| Capability | Level | What it does |
|---|---:|---|
| `evolve.evidence.list` | 1 | Lists durable, provenance-backed evolution evidence |
| `evolve.proposals.list` | 1 | Lists proposals and lifecycle states |
| `evolve.proposal.get` | 1 | Inspects one complete proposal |
| `evolve.proposal.revision.create` | 2 | Proposes a bounded preference/config revision from evidence |
| `evolve.proposal.amendment.create` | 2 | Proposes an identity/Constitution amendment from evidence |
| `evolve.proposal.code.create` | 2 | Proposes a bounded code change from evidence |
| `evolve.code.candidate.build` | 2 | Builds/tests the code proposal in DEV's isolated worktree |
| `evolve.code.candidate.verify` | 2 | Runs the fixed candidate verification gate and attaches immutable evidence |
| `evolve.code.release.accept` | 2 | Records measured acceptance of a completed protected rollout |
| `evolve.apply` | 4 | Applies one exact externally approved state/amendment proposal |
| `evolve.rollback` | 4 | Rolls back one exact externally approved applied proposal |
| `evolve.code.candidate.apply` | 4 | Applies the candidate using a separate exact DEV approval |
| `evolve.code.candidate.commit` | 4 | Commits the verified candidate using a separate exact DEV approval |
| `evolve.code.candidate.rollback` | 4 | Rolls back an uncommitted candidate using a separate exact DEV approval |

EVOLVE can formulate and test changes; it cannot approve its own protected
identity, Constitution, code-application, commit, or rollback operation.

---

## 26. Environment / weather / time context

Persistent settings:

```powershell
python -m sofia.environment.settings_cli show
```

Set location:

```powershell
python -m sofia.environment.settings_cli set-location --label "Home" --timezone America/Chicago --latitude <lat> --longitude <lon> --subject user --enable-nws
```

Central time shortcut:

```powershell
python -m sofia.environment.settings_cli central-time --label "Home"
```

The environment subsystem also exposes internal read capabilities
`environment.nws.read` and `environment.home_assistant.read` at Level 1.
These support grounded runtime context rather than general unrestricted network
access.

---

## 27. Voice

List Windows voices:

```powershell
python -m sofia.voice --list-voices
```

Probe backend:

```powershell
python -m sofia.voice
```

Speak a test phrase:

```powershell
python -m sofia.voice --say "Hello, Sparks."
```

Choose a voice:

```powershell
python -m sofia.voice --voice "<voice name>" --say "Voice test."
```

Current production voice support is TTS-focused. A first-class microphone/STT
tool is not yet part of the production capability catalog.

---

## 28. Windows Sofía services

Install/update runtime + watchdog services:

```powershell
python -m sofia.run.service_admin install
```

Validate:

```powershell
python -m sofia.run.service_admin validate
```

Remove:

```powershell
python -m sofia.run.service_admin remove
```

Use an explicit state database when needed:

```powershell
python -m sofia.run.service_admin validate --state-path <path-to-sofia.db>
```

---

## 29. Release and cleanup operator tools

Release evidence:

```powershell
python -m sofia.dev.release_cli --help
```

Supports:

- `construct`
- `verify`
- `sign`

Safe cleanup/recovery:

```powershell
python -m sofia.clean snapshot --state-path <sofia.db> --recovery-root <directory>
python -m sofia.clean plan --releases-root <directory>
```

Cleanup application requires both a verified recovery snapshot and explicit
`--confirm`.

---

## 29. Private/adult permission controls

These are authority/privacy settings, not a sixth permission level.

Show:

```powershell
python -m sofia.safe.permissions_cli private show
```

Enable private adult chat + avatar, while leaving external adult delivery off:

```powershell
python -m sofia.safe.permissions_cli private set --adult-chat on --adult-avatar on --adult-external-delivery off
```

They can also be changed under **Settings → Permissions**.

Changing this authority is Sparks-only. Sofía cannot enable it for herself.

---

## 30. Tool availability versus permission

A tool needs **both**:

1. registration/configuration; and
2. permission.

Examples:

- Portainer reads are Level 1, but they do not exist unless Portainer is
  configured.
- A Level-3 container restart grant does not create a Portainer connection.
- Remote hardware reads are Level 1, but the machine must already be enrolled
  with valid mTLS identity/endpoint.
- Fleet enrollment approval does not substitute for missing verified candidate
  evidence.

Ask:

```text
What tools can you use right now?
```

to see the runtime catalog.

Ask:

```text
What permissions do you have?
```

to see authority/grants.

---

## 31. Tools that are not production-runnable yet

These are important roadmap items, but do **not** currently have a registered
production capability and should not be treated as working tools.

### Gaia / hexapod / SSC-32 robot control

PKG-BODY currently contains behavior/matrix code, but the repository does not
currently register an SSC-32, servo, gait, pose, or robot-control cognitive
capability.

**Current status:** not runnable from Sofía chat yet.

Before enabling physical motion, add a typed robot capability layer with:

- read-only controller/servo status
- bounded pose/gait commands
- physical emergency stop
- servo limits
- collision/current safeguards
- Level-3 motion grants
- Level-4 calibration/destructive configuration

### Dedicated YAML tools

There is no first-class production capability yet for YAML parse/validate/edit.

Today Sofía can:

- read YAML using `filesystem.inspect`
- search YAML files
- reason about their contents

A future YAML tool should add typed parse/query/validation before write support.

### Generic shell

There is intentionally no unrestricted shell cognitive tool.

### Arbitrary database write

There is intentionally no arbitrary SQLite mutation tool.

---

# Quick permission recipes

## Allow Sofía to restart Mealie

```powershell
python -m sofia.safe.permissions_cli grant portainer.container.restart --scope-json '{"container_id":"mealie"}'
```

Then:

```text
Restart Mealie.
```

## Allow Sofía to restart her Windows service

```powershell
python -m sofia.safe.permissions_cli grant local.service.restart --scope-json '{"name":"SofiaAdaLyra"}'
```

## See computers on the network without adding them to Fleet

1. Settings → Fleet
2. Add approved CIDR scope
3. Fleet auto-discovery may remain **off**
4. Ask:

```text
Show me computers on the network.
```

## Discover possible Fleet members but do not trust them

Enable automatic Fleet discovery or ask:

```text
Discover Fleet candidates.
```

This may persist untrusted candidates only.

## Add one computer to Fleet

Settings → Permissions → Fleet candidates → select → **Approve & enroll
selected**.

## Check hardware without asking permission

```text
Show this computer's hardware.
Show Eos's hardware.
```

Local/enrolled-remote hardware inspection is Level 1.

## Check Docker without asking permission

```text
Check Docker health.
Show the last 200 Mealie logs.
List Docker images and volumes.
```

All of those reads are Level 1.

## Let Sofía work on self-improvement without applying code

```text
Work on self-improvement for <problem>. Inspect the code, build an isolated
candidate, run the relevant tests, and show me the result.
```

Inspection is Level 1 and isolated `dev.build` is Level 2. Apply/commit/push
still require exact approval.

---

# Package test commands

The repository defines package markers. Run one package at a time when
diagnosing:

```powershell
pytest -q -m "pkg_safe and not integration"
pytest -q -m "pkg_ops and not integration"
pytest -q -m "pkg_net and not integration"
pytest -q -m "pkg_integrate and not integration"
pytest -q -m "pkg_dev and not integration"
pytest -q -m "pkg_ui and not integration"
pytest -q -m "pkg_voice and not integration"
pytest -q -m "pkg_run and not integration"
pytest -q -m "pkg_body and not integration"
```

For a full local run:

```powershell
pytest -q
```

---

# Final safety contract

Sofía may explore broadly **inside configured/approved resource boundaries**.

She may autonomously:

- read
- inspect
- discover
- correlate
- diagnose
- compare
- test
- simulate
- plan
- build isolated DEV candidates
- perform explicitly classified Level-2 maintenance

She may not silently:

- add a computer to Fleet
- create trust
- reboot a host
- delete storage
- merge/deploy/apply production code
- alter permissions
- weaken security
- disclose protected/private state

Those boundaries are enforced in code, not merely described in prompts.
