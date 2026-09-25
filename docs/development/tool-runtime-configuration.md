# Sofía Runtime Tool Configuration

**Status:** tool-completion branch configuration contract.

This document describes how concrete runtime tools are enabled. Tool code being registered does not itself authorize use. Provider-visible tools are filtered by `SofiaConfiguration.standing_allowed_capabilities`, and consequential capabilities must be explicitly granted.

## Safety model

- Safe local inspection tools are standing-authorized by default.
- Mutating DEV, service, VM, container, database, storage, notification, and remote operations are not standing-authorized unless explicitly listed in `SOFIA_ALLOWED_CAPABILITIES`.
- Remote operations additionally require an active durable exact-scope grant for the exact node/capability/operation.
- No generic local or remote shell is exposed.
- Secrets belong in local environment/service configuration, never Git.
- General web/search remains deferred.
- **Cloudflare integration is intentionally not implemented or configured. Do not add it unless Sparks explicitly requests it later.**

## Additional capability grants

Comma-separated capability names:

```text
SOFIA_ALLOWED_CAPABILITIES=dev.build,dev.apply,home_assistant.service.call
```

This is a host/operator configuration boundary. A chat request cannot modify it.

## Home Assistant

```text
SOFIA_HOME_ASSISTANT_URL=http://hestia-or-proxy:8123
SOFIA_HOME_ASSISTANT_TOKEN=<local secret>
SOFIA_NOTIFICATION_HA_SERVICE=<optional notify service name>
```

Read tools include services, states, and entity state. Service calls and `notification.send` still require capability authorization.

## Portainer / Docker

```text
SOFIA_PORTAINER_URL=https://...
SOFIA_PORTAINER_API_KEY=<local secret>
SOFIA_PORTAINER_ENDPOINT_ID=1
```

Provides endpoint/container inspection and exact container restart.

## JMRI

```text
SOFIA_JMRI_URL=http://athena:12080
```

Provides power, roster, typed object inspection, and explicit power changes.

## GitHub

```text
SOFIA_GITHUB_REPOSITORY=Crazysodaman/SofiaAdaLyra
SOFIA_GITHUB_TOKEN=<local secret, optional for public read>
```

Provides repository/file/issues/PR inspection plus separately authorized issue/PR creation and PR merge.

## Ollama

```text
SOFIA_OLLAMA_URL=http://127.0.0.1:11434
```

Defaults to the local Ollama endpoint and exposes model/running-model inspection.

## Storage / NAS roots

Additional roots use the OS path separator:

```text
SOFIA_STORAGE_ROOTS=<root1><path-separator><root2>
```

All paths are resolved beneath configured roots. Traversal/symlink escapes are denied. Usage/root inventory is safe by default; file read/write/move/copy/delete require explicit capability grants.

## Local maintenance

On Windows/Linux the following typed operations are registered:

- `local.service.start`
- `local.service.stop`
- `local.service.restart`
- `local.host.reboot`
- `local.package.update`

They map to fixed argv templates and reject shell/script/argv injection. They are not standing-authorized by default.

## DEV

Registered DEV tools:

- `dev.status`
- `dev.build`
- `dev.apply`
- `dev.rollback`
- `dev.commit`
- `dev.push`

Only `dev.status` is standing-authorized by default. OpenCode build runs in a detached worktree. Apply, rollback, commit, and push remain separate grants.

## KNOW

Registered tools include durable search/document inspection, text ingestion, PDF/manual ingestion through `pypdf`, and bounded project-document writing. Search/document inspection is standing-authorized by default; ingestion/writing requires explicit grants.

## Secure remote fleet transport

Controller configuration:

```text
SOFIA_REMOTE_CA=<CA PEM>
SOFIA_REMOTE_CLIENT_CERT=<controller client cert PEM>
SOFIA_REMOTE_CLIENT_KEY=<controller private key PEM>
SOFIA_REMOTE_MAX_INVENTORY_AGE_SECONDS=300
```

When configured together, remote cognitive tools are registered. Transport uses CA validation, mutual TLS, approved durable endpoints, server public-key pinning, durable enrollment, exact human grants, and durable replay ledgers.

### Agent configuration

Each remote host runs the explicit foreground agent entry point with:

```text
SOFIA_AGENT_NODE_ID=<UUID>
SOFIA_AGENT_NODE_NAME=<name>
SOFIA_AGENT_LISTEN_HOST=0.0.0.0
SOFIA_AGENT_LISTEN_PORT=7443
SOFIA_AGENT_SERVER_CERT=<server cert PEM>
SOFIA_AGENT_SERVER_KEY=<server key PEM>
SOFIA_AGENT_CLIENT_CA=<CA PEM used to verify the controller cert>
SOFIA_AGENT_CLIENT_PUBLIC_KEY_SHA256=<controller cert public-key fingerprint>
SOFIA_AGENT_LEDGER=<durable agent ledger SQLite path>
```

Optional agent-side Portainer mapping:

```text
SOFIA_AGENT_PORTAINER_URL=https://...
SOFIA_AGENT_PORTAINER_API_KEY=<local secret>
SOFIA_AGENT_PORTAINER_ENDPOINT_ID=1
```

Start explicitly:

```powershell
python -m sofia.distributed.agent_main
```

Nothing imports this module to start networking automatically.

### Provisioning controller state

Fingerprint a certificate public key:

```powershell
python -m sofia.distributed.operator fingerprint-cert <certificate.pem>
```

Enroll a node using its server certificate public key:

```powershell
python -m sofia.distributed.operator enroll --node-id <uuid> --name <name> --server-cert <server.pem>
```

Approve the exact HTTPS endpoint:

```powershell
python -m sofia.distributed.operator endpoint --node-id <uuid> --hostname <hostname> --port 7443
```

Create a time-bounded exact operation grant:

```powershell
python -m sofia.distributed.operator grant --node-id <uuid> --capability system.inspect --operation system --hours 24
```

Retirement revokes the identity, endpoint, and all remaining grants:

```powershell
python -m sofia.distributed.operator retire --node-id <uuid>
```

## Explicitly unfinished/live acceptance

Source implementation is not live acceptance. Before production use:

1. run compile/focused/full tests;
2. provision certificates outside Git;
3. smoke-test read-only integrations first;
4. exercise one reversible write per adapter;
5. deploy the remote agent to one test host first;
6. verify wrong key, stale grant, revoked endpoint, replay, and outage behavior;
7. expand to the fleet only after those gates pass.

Workload drain/checkpoint/start/readiness/fencing/failover still depend on the RUN/workload execution layer and real-host acceptance. The tool layer does not pretend those are complete merely because OPS orchestration objects exist.
