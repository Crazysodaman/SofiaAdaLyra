# AG-D025 | Portainer / Docker control and governed Compose stack editing

**Status:** OWNER-DESIRED DESIGN, SOURCE-AUDITED 2026-11-08; CAPTURED, NOT IMPLEMENTED OR SCHEDULED.
**Owner request:** Allow Sofía and other authorized Cores to control Docker through existing Portainer, including proposing and eventually applying changes to Docker Compose stacks, visible in the matching Aegis GUI and headless TUI.
**Scope:** Refines AG-D007, AG-D013 Security, AG-D020 Operations/Jobs, AG-D022 TUI, AG-D023 Core autonomy, AG-D024 GUI/TUI parity and the optional integration/module catalog (AG-D006/AG-D021); not a replacement Docker daemon, shell executor, privileged Docker socket proxy or second stack management database.
**Production safety:** No broad autonomous Portainer admin or direct arbitrary Docker API privileges; changes must be scoped, independently authorized by owner/Platform SAFE, reversible where possible, tracked by receipts and denied for critical resources unless separately approved.
**Release fence:** Planning only; does not authorize live changes, modify protected running services, revise the #201 Platform-only acceptance gate or bypass 256-bit owner security.

## 1. Source audit: what is already implemented

As of repository GitHub `main` snapshot `e9756dbfc73d8c34ab7249bc10b9167558a1e390` (Nov. 8, 2026):
- `src/sofia/modules/integrations/portainer.py` implements Portainer API `X-API-Key` adapter for list endpoints, containers, container inspect/logs/stats, engine info, images/volumes/networks, stack **list**, high-level summary and exact Docker-proxy **container restart**. No `stack_file`, stack details, compose validate, stack update, Git redeploy, stack deployment/reconciliation or rollback method.
- `src/sofia/modules/integrations/capabilities.py` wires these cognitive tools only when `SOFIA_PORTAINER_URL`, `SOFIA_PORTAINER_API_KEY` and `SOFIA_PORTAINER_ENDPOINT_ID` are present **at runtime composition/startup**. The current implementation is not a dynamically enrolled standalone Platform module or guaranteed live-updatable credential binding.
- `src/sofia/platform/safe/permissions.py` classifies `portainer.endpoints`, `portainer.containers`, `portainer.container`, `portainer.container.logs`, `portainer.container.stats`, `portainer.stacks`, etc. read-only; `portainer.container.restart` is `REVERSIBLE_SCOPED` (Level 3) and requires exact scoped standing grant or approval. **No existing stack-edit/stack-deploy capability is classified, so unknowns fail closed as protected.** Never reuse the container restart grant for updating or replacing a stack.
- `src/sofia/platform/distributed/agent_tools.py` has a remote Portainer agent integration for read-only Docker data and container restart with separate remote-host authority. This is not blanket Fleet access to all Portainer environments.
- `src/sofia/core/cognition/matrix/tool_exposure.py` already selects Portainer inspection tools for relevant conversation and restart tool when authorized. Compose edit and stack update are not registered.
- `TOOLS.md` §13 and `docs/development/tool-runtime-configuration.md` describe current connection values, read-only tools and scoped restart; never claim live deployment safety merely because a tool is registered.
- `src/sofia/modules/integrations/http.py` permits http:// as well as https:// for its general-purpose client. **New Portainer write transport must require validated HTTPS**, bound destination, controlled redirects, certificate verification and secret protection; do not reuse permissive default as proof of safety.
- Existing Portainer stacks are the source of truth for deployed compose; Aegis maintains only job receipts, expected digests, approved change proposals and audit, not a competing copy of mutable Portainer state.

**Existing feature truth:** Read-only observation + individually authorized container restart are coded; stack modification, production deployment, one-click GUI/TUI management, independent authorization, risk analyzer, status synchronization and installed-host verification are **not** implemented here.

## 2. Portainer API contract and edition/source handling

Official Portainer docs:
- API access per Portainer user and environment; create token at **My account > Access tokens**. Send `X-API-Key` over HTTPS; the token inherits that user's permissions: https://docs.portainer.io/api/access
- Existing `GET /api/stacks`; `GET /api/stacks/{id}`; `GET /api/stacks/{id}/file`. For **file/Web Editor based** stacks, Portainer supports `PUT /api/stacks/{id}?endpointId=<id>` with stack file content, env variables and optional pull/prune flags, as appropriate to installed version: https://api-docs.portainer.io/?edition=ce&version=2.39.0
- **Git-deployed** stacks must be edited in their Git repository, NOT by PUT of their current editor content. Use reviewed Git PR/commit and Portainer Git redeploy / GitOps after approval. Detaching Git is a separate explicitly authorized consequence, NOT a workaround: https://docs.portainer.io/user/docker/stacks/edit
- GitOps automatic polling/webhooks may deploy changes as soon as the tracked branch changes. Do not combine 'approved source PR' with an uncontrolled auto-deploy on a production branch without explicit deploy consent and safeguards: https://docs.portainer.io/user/docker/stacks/add
- Portainer UI/versions/editions have differing fields and supported deployment behavior. Introspect current server/version, environment type (Docker Standalone vs Swarm vs Podman vs Kubernetes), source (Web Editor/upload/Git), stack ID and current deployment metadata; disable unsupported operations rather than guessing request formats. Edge/fleet stacks are a distinct API.
- Do not rely solely on Portainer's in-app version history as a recovery plan: capture an approved immutable redacted/original manifest snapshot separately, with secrets never exposed to LLM, plus relevant data backup receipts. Redeploying old Compose does NOT restore lost database/volume contents.

## 3. Connection, identity and secret enrollment

**Initial read-only setup** (supported adapter foundation):
1. Create a dedicated least-privilege Portainer **non-admin user**, restrict to the intended Docker environment(s)/resources where the Portainer edition permits. NEVER use the main admin's API token as default Core access.
2. As that user generate a new API token at `My account > Access tokens`. Capture the token only in the reviewed host-owned secret manager/service configuration, never chat, model/tool arguments, YAML, Git, logs, CLI flags or raw browser URL. Do not display the token in GUI/TUI or give it to Sofía's LLM.
3. Bind exact HTTPS Portainer origin, CA/pinned certificate where appropriate, approved Portainer server identity, allowed environment/endpoint IDs and selected Aegis host. Deny HTTP downgrade, unexpected DNS/redirect, hostname/port drift, cross-host redirects, proxy to arbitrary Docker APIs and automatic propagation to unrelated Fleet hosts.
4. Existing startup fields are `SOFIA_PORTAINER_URL`, `SOFIA_PORTAINER_API_KEY`, `SOFIA_PORTAINER_ENDPOINT_ID`; current tool registration is startup-time. For production build a reviewed secret-store-backed connector enrollment, not a permanent raw environment secret. Reconfiguration should be a live permission/versioned adapter swap when independently implemented, with no host/Platform service restart. **Until then a Core/runtime tool rebuild/restart may be needed to pick up configuration**; do not claim current hot enrollment is complete.
5. Verify read-only stack/container listing with the real token and expected environment ID before any protected capability. If token lacks required permission, show denied and keep read-only; do not silently swap to admin or shared root permissions.
6. Portainer itself, reverse proxies, authentication, backups, DBs, DNS, gateways, networks and the Aegis host's own control plane are **protected-by-default targets**. These do not become autonomous cleanup candidates even when they are technically containers.

**Potential future Aegis Settings UI:** `Integrations > Portainer`, nested under existing Infrastructure/Settings/Containers rather than creating a second Fleet catalog; show VERIFIED/UNAVAILABLE/STALE binding, URL without secrets, endpoint ID, identity, role/capability grants, token expiry status if observable, last API check, and Edit/Revoke with independent approval.

## 4. Permission ladder and proposed operations

| Proposed capability / class | Function | Recommended authority |
| --- | --- | --- |
| Existing `portainer.stacks`, `portainer.container.logs`, `portainer.summary`, others | Bounded read-only inspection. Redact env/secrets/log tokens from LLM-facing views. | Observational, restricted to enrolled/authorized Portainer environment. |
| Existing `portainer.container.restart` | Exact ID, exact endpoint and narrow restart timeout. | Existing `REVERSIBLE_SCOPED` standing grant or one-use owner approval, rechecked at execution. |
| NEW `portainer.stack.inspect` / `portainer.stack.file.inspect` | Exact stack metadata/file/version/fingerprint (sanitized). | Classified authorized observation. No raw secret exposure. |
| NEW `portainer.stack.change.propose` | Compose YAML diff, versioned plan, impact and validation without deployment. | Core may propose via explicitly classified inert tool; no write effect. |
| NEW `portainer.stack.validate` | Parse/resolve Compose or relevant platform equivalent in a disposable, isolated validator with no Docker daemon mutation or secret expansion into LLM. | Bounded validation with safe inputs and runtime budgets; no host shell or install. |
| NEW `portainer.stack.deploy.approve` / `portainer.stack.apply` | Deploy exact hashed approved candidate to exact Portainer endpoint/stack/generation. | **Protected per-operation owner approval**, no general standing Core grant. |
| NEW `portainer.stack.git.propose` / `portainer.stack.git.redeploy` | Git-backed PR and approved deploy commit/branch via Portainer's source-aware API. | Source PR privileges independent of production deploy privilege; exact owner approval to update production. |
| NEW `portainer.stack.rollback.request` | Propose and, if newly approved, execute exact recovery to independently retained previous Compose/redeploy version with health verification. | Protected separate effect; cannot promise data restored by Compose alone. |
| NEW `portainer.stack.remove`, `portainer.volume.delete`, `portainer.network.delete`, privilege escalation, arbitrary Docker proxy/exec | Destructive or host-control operations. | Not available as Core self-actions. Separate owner-protected review or excluded entirely. |

Do not expose unrestricted `docker exec`, `docker.sock`, broad shell access, raw Portainer arbitrary proxy requests, arbitrary host binds, `privileged: true`, `network_mode: host`, `pid: host`, `cap_add: SYS_ADMIN`, privileged devices, writable host roots or volume deletion through a generic Core edit tool. A legitimate request to alter these requires explicit, more restrictive owner-managed review and cannot be auto-executed.

**Core autonomy:** Sofía may choose what to investigate and make versioned change proposals based on verified observations; she may autonomously edit only *drafts*, not active production stacks. A separately designed LAB-only disposable stack capability is the potential future bounded autonomous sandbox, not production deploy standing authority. No prompt may edit its own grant.

## 5. The workflow to edit a stack safely

**Step 0: establish target.** Verify selected Portainer server (HTTPS), Portainer endpoint ID, immutable stack ID, installed source type (file vs Git vs unsupported), current stack version/ETag or content digest, current management identity, exact Aegis target host and current trust/STOP.

**Step 1: collect read-only evidence.** Get bounded current Compose source and deployment metadata through Portainer, current env variable **names/references only**, container health, logs sanitized before model, images/digests, services, ports, dependencies, mounts, networks, resources and change history. Secrets may appear in Compose, .env, docker inspect, labels, environment and logs: never pass raw secret-bearing payloads to model/GUI/toast/LLM or PR. Keep sensitive bytes only in trusted executor/secret-store memory.

**Step 2: generate typed proposal.** Sofía proposes a specific change, not arbitrary unreviewed full YAML. Show field-level semantic and text diff, exact desired image digest/tag, expected restarts, downtime risk, storage/network impact, resource delta and justification/evidence. For Git-backed stacks, create a reviewable PR or constrained patch against authoritative repo/branch; for editor/upload stacks, build a candidate Compose file via safe parser/transform.

**Step 3: validate without effect.** Validate Compose syntax and merged multi-file config, referenced env variable names/presence without revealing values, image existence/platform, dependency graph, port conflicts, resource admission, named volumes/mounts, host path changes, networks, firewall/policy, ports, UID/GID, capability changes, privileged mounts and Portainer special flags. No guarantee `docker compose config` alone can prove deploy correctness. If validation requires access to Docker, use reviewed isolated validation endpoint or sandbox, not the Core's generic shell.

**Step 4: snapshot/backup.** Record the **actual original** signed/hash-bound Compose and Portainer source identity, repo commit if Git-managed, relevant env metadata and a tested-restore plan, separate data volume/database backup receipts where needed. A config-file snapshot is not a substitute for stateful service backup.

**Step 5: owner review and approval.** GUI and TUI Security > Proposed Docker Changes show source (Core identity), target Aegis host, Portainer URL/endpoint ID, stack ID/source repo, original digest, proposed digest, full redacted diff, risk score, downtime, dependent services, sensitive-field changes, backups and exact approval timeout. One-use independently verified owner proof bound to this plan and an expiry. Do not embed owner secret, Portainer token, encryption keys or unrestricted credentials in the LLM prompt.

**Step 6: revalidate and apply.** Verify STOP, grants, Portainer identity, current endpoint, signed package/source revision, current original digest and source class immediately before effect. If stack changed after draft, reject and require re-review. For file stacks use version-confirmed `PUT /api/stacks/{id}?endpointId=N` with exact approved `StackFileContent` and intended Env/PullImage/Prune semantics; use `Prune=false` default and do not unexpectedly pull mutable `:latest`. For Git stacks only deploy an approved source commit via reviewed GitOps/redeploy flow; no silent detach from Git.

**Step 7: verify outcome and recover.** Store request ID and per-step receipt; watch actual container/service health, network and DB readiness over bounded times. If deployed but unhealthy, propose an authorized rollback using original digest/repo commit after checking current state, potentially execute only under a pre-approved narrowly scoped recovery policy. Do not claim data rollback unless database/volume restore is independently verified. If lost connection or ambiguous Portainer reply, mark `OUTCOME_UNKNOWN` and reconcile before retry; never blindly redeploy.

**Step 8: live UI feedback.** Expose `PROPOSED`, `VALIDATING`, `AWAITING_APPROVAL`, `BACKUP_PENDING`, `DEPLOYING`, `HEALTH_CHECKING`, `SUCCEEDED_VERIFIED`, `ROLLED_BACK_VERIFIED`, `FAILED`, `DENIED`, `OUTCOME_UNKNOWN`, plus exact source/time. GUI and TUI show identical state without their restart, and closing UI doesn't halt approved backend jobs.

## 6. GUI/TUI design

New nested **Containers / Portainer** page under existing Infrastructure or Operations manager, not duplicate Fleet manager. Persistent selected exact Aegis Platform and Portainer environment/stack, with stale/unknown labels. Screen has:
- Environments / Containers / Stacks / Images / Networks / Volumes / Jobs / Change proposals / Connection settings.
- Stack details: source Web Editor vs Git, immutable ID, version digest, running/health, current compose (redacted), linked containers, schedules, dependencies, latest successful deploy receipt and known backup.
- `[1] Inspect`, `[2] Logs`, `[3] Edit proposal`, `[4] Validate diff`, `[5] Owner review / Deploy`, `[6] Review rollback`, `[7] History`, `[0] Back`. Only actual permitted controls enabled; read-only is default.
- A GUI diff with side-by-side view and per-resource change impact; TUI with line numbers and ASCII unified diff. Secrets redacted, service grants and host trust visible.
- The same user-customized Aegis black/violet/cyan/lime/HUD palette and keyboard-first headless fallback (see AG-D024 shared themes). No other GUI/TUI permissions path.
- Hot module/connector connections and disconnections are reflected without restarting the **Platform GUI/TUI** after their subscription/poll implementation. Current Core runtime adapter registration requires a rebuild/restart to change startup environment; full no-restart connector setup is future work.

**Example (illustrative, no real Portainer operations):**

```text
+----------------------------------------------------------------+
| AEGIS > PORTAINER > STACKS                                      |
+----------------------------------------------------------------+
| Portainer: <verified TLS endpoint>       Environment: <id>      |
| Selected:  <immutable stack ID>          Source: GIT/EDITOR      |
| Health:    <fresh verified or UNKNOWN>   Trust: <policy>         |
+----------------------------------------------------------------+
| [1] Inspect stack         [4] Review Compose diff              |
| [2] Container logs        [5] Request exact deployment         |
| [3] Propose change        [6] Rollback plan / Health            |
| [7] History               [0] Back                             |
+----------------------------------------------------------------+
| No changes apply without independent owner authorization.      |
+----------------------------------------------------------------+
```

## 7. Implementation batches and acceptance

- **P0: Security and observation hardening:** least-privilege Portainer user/token onboarding, bound TLS origin/endpoint, no leaked credentials/privileged env/log content to model, exact Portainer ID version/source read and current read-only tests. Audit current raw Docker-proxy reads for secret exposure and oversized/untrusted data. No additional active writes.
- **P1: Draft/validation:** stack inspect and source-aware file retrieval, safe redacted AST/YAML diff, Compose parser, required volume/mount/network/resource impact classifier and isolated validation on disposable environment. Typed inert Core proposal and shared owner review UI/TUI.
- **P2: Approved file-stack deploy:** protected exact owner approval, immutable candidate digest and compare-with-current, dry-run/backup plan, `PUT` only for reviewed file-based stacks, durable receipts, health/unknown-outcome reconciliation and separate rollback.
- **P3: Git stack deployment:** reviewed PR and merge to exact approved commit, GitOps compatibility, pinned/restricted deploy and source-verified receipts, no silent Git detach; distributed host permission checks.
- **P4: Production integration:** optional signed Portainer connector module packaging, live bind/rebind without Platform restart, multi-endpoint support, visible permissions, signed releases, Windows/Debian test evidence, same source/actor/receipt in GUI, TUI and Core.

**Tests required before live release:**
1. Read-only user token cannot call stack deploy or raw arbitrary Docker proxy; permissions enforced by BOTH Portainer and Aegis, including token revocation.
2. Token never appears in logs, prompts, Git diffs, Compose snapshots, history or error messages; env variables/Compose secrets and logs redacted.
3. Any wrong endpoint/stack ID, changed digest/ETag, stale Core/host generation, revoked trust, SAFE STOP, expired approval, altered approved candidate, auth redirect, HTTP downgrade or DNS mismatch fails closed.
4. Web-Editor stack change/health checks work on actual disposable Portainer CE and BE variants where supported, no accidental image pull, orphan delete or volume removal.
5. Git-managed stack edit stays in Git, not direct API edit; source PR approval and deploy approval distinct, no unreviewed branch auto-deploy bypass.
6. Syntax-only validation cannot claim app healthy; backup state and database rollback independent of previous YAML; force known failure and record verified/unknown outcome without silent retry.
7. User disconnection, Portainer restart, repeated request, crash, cross-host link loss and GUI/TUI exit do not create duplicate redeploy; jobs can reconcile receipts.
8. Critical Aegis/Portainer/security/DNS/database infrastructure is default-denied for autonomous mutation; lab-only optional self-tuning requires independently approved separate capabilities and disposable state.
9. Core request changes remain proposals; no broad Docker admin standing permission; production stack deploy requires fresh exact owner proof (existing owner 256-bit secret procedure integrated safely outside model).

**Status truth:** No live Portainer inspected, configured or modified by creating this design. The code audit and official Portainer API docs justify a feasible implementation, **not** deployment-ready behavior. Confirm Portainer version, edition, environment type and stack sources before writing executable actions.
