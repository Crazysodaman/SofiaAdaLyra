# PKG-INTEGRATE | applications, services, and self-tooling

**Planning date:** 2026-09-22. **Status:** documentation contract only. No new live adapters or self-generated tool activation are implemented by this document.

## Outcome

Give Sofía typed, permission-scoped integrations to applications and services without turning generic shell/network access into a universal escape hatch. INTEGRATE owns service adapters and the governed path by which Sofía can create new tools from documentation.

## Initial integration targets

Potential adapters include:

- Home Assistant
- JMRI/LocoNet
- GitHub
- Docker/Portainer
- Hyper-V/VM management
- Cloudflare
- Ollama
- SQL/SQLite and other approved databases
- NAS/storage systems
- notification systems
- later email/calendar and web/search-backed services after their separate gates

An integration may be local-only, fleet-local or external. NET supplies transport; SAFE supplies authority/trust; INTEGRATE supplies service semantics.

## Tool contract

Every tool/adapter declares:

- stable tool ID and semantic version;
- service/vendor/protocol/version compatibility;
- input/output schema;
- side-effect class: read-only, reversible write, disruptive, destructive/irreversible;
- required capability/authority;
- host/account/destination scope;
- principal/audience/privacy scope;
- secret dependencies by reference, never hard-coded secret values;
- timeout/retry/idempotency rules;
- receipts/evidence proving what happened;
- rollback/compensation when possible;
- health/version probe;
- rate/resource limits;
- tests and known failure behavior.

## Self-tooling workflow

Sofía may create a new tool when she encounters a missing capability:

1. identify the exact missing operation;
2. use KNOW to retrieve approved, versioned documentation;
3. extract schemas, preconditions, side effects, errors and version constraints;
4. design the minimum-authority typed adapter;
5. have DEV generate the candidate implementation;
6. statically inspect dependencies, destinations, secret handling, protected paths and arbitrary-execution escape hatches;
7. use VERIFY for positive, negative, malformed-input, timeout, retry, replay/idempotency and security tests;
8. exercise the candidate in a sandbox/canary target where feasible;
9. have SAFE classify the required activation grant;
10. register only under an existing valid activation policy or explicit approval requirement;
11. retain real receipts/errors/version evidence;
12. disable/rollback automatically if live verification detects incompatible or unsafe behavior.

## Activation policy

Tool creation and tool authority are separate.

Sofía may design, implement and test candidate tools in the bounded DEV/VERIFY environment when those capabilities are authorized. A generated tool receives **no runtime authority merely because Sofía wrote it or its tests pass**.

A standing policy may permit automatic activation only for narrowly scoped, read-only/reversible tools against already-authorized resources after VERIFY and SAFE gates pass. Write, disruptive, destructive, credential-expanding, protected-state, security-policy, fleet-removal, and physical-control tools require their separate authority/approval gates.

## Tool evolution

When vendor/service documentation or versions change:

1. KNOW marks affected contracts potentially stale;
2. INTEGRATE/DEV generates or updates a candidate;
3. VERIFY runs compatibility/regression tests;
4. canary rollout occurs where safe;
5. the new version replaces the old only after the activation gate succeeds;
6. previous known-good versions remain available for rollback where feasible.

## Tool registry and introspection

Sofía should be able to inspect her own registered tools and answer:

- what tools are available;
- what version each tool is;
- what it can/cannot do;
- which host/account/service it targets;
- what authority it currently has;
- whether it is healthy;
- when it last succeeded/failed;
- which documentation/version defines it;
- whether its contract is stale.

Unknown or disabled tools stay unavailable rather than being simulated in prose.

## Acceptance

Do not claim INTEGRATE/self-tooling complete until Sofía can:

1. register and invoke a typed read-only adapter;
2. deny calls outside its host/account/destination scope;
3. preserve receipts and idempotency behavior;
4. build a candidate adapter from real versioned documentation;
5. link generated code/tests back to those docs;
6. pass malformed-input/security/failure tests;
7. canary the candidate against a safe target;
8. refuse activation when required authority is absent;
9. automatically activate one policy-approved read-only/reversible tool;
10. require explicit higher-risk approval for a disruptive/write tool;
11. disable/rollback an adapter when live behavior/version compatibility fails;
12. survive restart without losing tool version, authority, provenance or health state.
