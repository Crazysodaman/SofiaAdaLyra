# Local Fleet callsign authority v1

**Local authoritative registry implemented, remote Fleet integration outstanding.**
This is development source. No production authority, enrollment, migration,
Core selection, hostname or personal state is activated by installing it.

## Ownership and setup

`sofia.platform.ops.callsigns.CallsignAuthority` owns one designated SQLite
registry. It requires an **existing** `PlatformLocalStore` with the LOCL
application ID, MODULE_HOST role, no Core binding, and the authority host's
immutable Platform UUID. It refuses canonical Core databases before naming
bootstrap writes. The authority host identity comes from the existing
`InstallationIdentityStore` (#192), not a hostname, serial or Core name.
Ordinary open never creates a missing database or repairs missing naming state.

Approved Platform composition must explicitly create the independent local
store and independently provision its existing SAFE owner authentication.
`initialize_parameters()` produces the exact review document; `initialize()`
consumes a one-use SAFE `fleet.callsign.authority.initialize` approval in that
same database. No credential enrollment or secret generation is implemented
here. The authority UUID, host UUID, path and canonicalization policy are bound
in an installation-private witness. Other hosts are clients of this designated
authority; there is no automatic promotion or per-host global fallback.

Each target registration requires an owner-approved immutable Platform UUID
and installation public-key fingerprint. It creates a NULL reservation, shown
as UNASSIGNED. Target identity/key binding cannot be replaced by a rename.
Cryptographic NET enrollment is separate; a naming registration does not enroll
a peer. The AEG-P serial remains the SDK-derived public projection. Physical
hostname and personal Core data are absent from the naming schema.

## Names and public contracts

Public request, receipt and projection schema: `aegis.fleet.callsigns.v1`.
Canonicalization policy: `nfc-nfkc-casefold-latin-v1:ucd-<Unicode version>`.
The Unicode database version is persisted and checked on every open: upgrading
to a different policy requires explicit migration, not implicit renormalizing.

Names contain 1–80 input code points and at most 240 UTF-8 display bytes.
Display uses NFC. The uniqueness key is NFKC(NFKC(display).casefold()). Accept
Latin letters (including accents), attached nonzero combining marks (at most
two), ASCII digits/spaces and ASCII `'-.,:&()` punctuation. Require at least
one letter/digit; reject leading/trailing or doubled spaces, compatibility
presentation glyphs, non-Latin/confusable scripts, variation selectors,
controls, invisible formatting, surrogates and unattached marks. UNASSIGNED is
a state, not a reservable name. This bounded alphabet is not a ship-name list:
owner-approved original names such as “Sofía's Quiet Reckoning” are allowed.
There is no semantic Halo classifier, automatic UNSC prefix or numeric suffix.

The local CLI is `python -m sofia.platform.ops.callsign_cli`, with explicit
`--database` and `--installation-home`. Commands:

- `review-initialize` / `initialize --authority-id ...` (initialization also
  requires `--approval-id`).
- `review` / `apply`: exact operation, target UUID, expected revision,
  request UUID and bounded JSON payload; apply requires an existing approval ID.
- `show --platform-id ...` and `core-rename` with a canonical request and
  base64 one-use signature.

Review output is inert. SAFE's existing independent owner approval procedure
must authenticate and approve it in the designated database. No raw owner
secret is accepted as an argument, exposed, or transported. Exit 0 means a
verified read/review or durable committed operation; conflict/stale is 3,
denial/invalid input is 2, and unconfirmed authority availability is 4.

## Owner and Core permissions

Owner operations: register, rename (explicit `override_lock` boolean), lock,
unlock, attach, detach, grant and revoke. Each exact review includes authority
UUID, target Platform UUID, operation, expected registry revision, request UUID
and payload. Direct operations use existing `ExecutionApprovalVerifier`;
grant/revoke use the existing `PermissionStore` and exact SAFE standing approval
contracts, with that review context inside the grant scope/revocation payload.
No display string or constructible identity DTO authenticates an action.

An owner-approved naming attachment binds Core UUID, generation, public
Ed25519 key and a monotonically increasing attachment revision in the same
authority database. It is a naming authority binding, not an implicit physical
Core launch, Core Link enrollment or live remote attachment attestation.
The later runtime/transport bridge must keep this binding current on real
attach/detach events; real-host integration is outstanding.

Core grants allow only `fleet.callsign.core.rename`, including first assignment,
for that exact authority/Platform/Core/generation/attachment and an explicit
expiry. A registry-issued grant link is required in addition to the SAFE grant:
a generic standing grant cannot bypass naming admission. Existing SAFE owner
proof bindings and current authenticator status are rechecked, so owner
credential revocation invalidates derived naming rights. Core requests sign a
bounded canonical JSON document with domain
`aegis.fleet.callsign.request.v1\0`, authority/target/Core/grant UUIDs,
generation, attachment and registry revisions, a unique request UUID, exact
name, issued-at and expiry (maximum five minutes). The current owner-approved
public key verifies the signature **inside the authoritative transaction**.
Wrong Core, Platform, authority, signature or generation is denied. Locks deny
Core rename; unlock restores only still-valid rights. Detach/switch increments
the attachment revision, invalidating old grants without changing the name.

## Transactions, receipts and recovery

Reservations, registry CAS, request replay ledger, SAFE proof consumption,
standing grant changes and SAFE audit records share BEGIN IMMEDIATE and one
SQLite commit. `normalized_name UNIQUE` enforces current ownership; NULL permits
multiple unassigned Platforms. Historical receipts preserve previous/current
names, actor, grant, time, operation, revision, request and result, plus a hash
chain and a digest of owned registry state. A normal name conflict consumes
its approved attempt and commits a CONFLICT receipt/revision; it never changes
the old reservation. Stale or unauthorized requests do not consume authority.
All current owner mutations use one-use exact approvals, including lock override.

A shared OS process lock coordinates the private witness across connections;
it does not replace SQLite constraints or transactions. Before commit the
witness records a pending next revision/hash/time. After commit it records the
committed revision before success returns. Restart accepts only the exact old
or pending committed state, validates history/state hashes, and reconciles that
unacknowledged intent. An acknowledged database rollback against the preserved
witness fails closed. Restoring both database and witness to an older whole-host
snapshot requires an independent external recovery checkpoint; hardware/remote
rollback protection and production recovery orchestration are not implemented.

A precommit/database/audit failure rolls back reservation, proofs, grants and
history. A postcommit witness-confirmation failure is **UNCONFIRMED**, not proof
that no side effect occurred: inspect the request's durable receipt after
reconnection; never blindly retry. Recovery never fabricates a second authority.
The authority DB and installation witness are external to package files and
survive Platform uninstall/reinstall. They must be retained as one recovery set
with the latest independent checkpoint; automatic reset is intentionally absent.

`CallsignDisplayClient` persists public last-verified display in owner-private
installation storage. Offline display is marked CACHED; new naming requests
are UNCONFIRMED. Its current adapter is explicitly local and verifies the
configured authority object/binding. There is no network transport or offline
global reservation authority. A future remote adapter needs authenticated
transport, authority identity, current binding/revocation and response proofs.

## Fleet findings addressed

Three original negative tests reproduced stale telemetry resurrecting a
removed trusted host, direct durable `authenticate_candidate` admission, and
trusted `register_candidate` injection. Durable writes now CAS against the
revision actually loaded with the cached host; telemetry and lifecycle writes
reject stale updates. Verified enrollment/removal refresh that cache revision.
Direct durable authentication and trusted candidate injection are refused;
legacy JSON cannot promote new trusted membership or restore retired trust.
Existing canonical state remains readable. The in-memory legacy projection is
not durable admission. Old synthetic trusted test setups use explicit privileged
test-only fixtures; production enrollment/removal still exercise real SAFE proof.

## Required acceptance matrix

| Cases | Evidence |
|---|---|
| 01–04 | UNASSIGNED, owner reserve, casefold and NFC/casefold collisions |
| 05–07 | Separate spawned processes, competing Platforms/same Platform, stale CAS |
| 08–09 | Audit/commit fault injection, restart/history preservation |
| 10–12 | Core lock denial, unlock, exact owner lock override |
| 13–19 | Missing/wrong grants, identities, generation, attachment, revocation, expiry |
| 20–21 | Spent approval/request and forged owner display metadata denied |
| 22–23 | Offline UNCONFIRMED/cache and acknowledged DB rollback refusal |
| 24–25 | Hostname/Core selection independence, detach/swap grant invalidation |
| 26–28 | Real wheel uninstall/reinstall, distinct grant scopes, Core-blocked probes |
| 29–30 | Committed audit/hash/state agreement, existing Fleet migration regressions |

Separate platform import and extracted/installed wheel probes block sofia.core.
Windows/Linux CI runs the same authority and spawned-process matrix. Live
multi-host authority/transport, approved recovery and runtime attachment behavior
remain unverified. SHAKEDOWN READY remains NO; G8 stays deferred.
