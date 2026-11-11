# Aegis Security Profile C: high Core autonomy

**Decision date:** 2026-11-11. **Owner:** sole owner of this private homelab
Aegis ecosystem. **Status:** owner design requirement; implementation is
partial and evidence is explicitly separated from acceptance.

This profile supersedes the older **Option B** autonomy-graduation decision in
[v18 CA-6505](v18-ca-6505-owner-approved-autonomy-graduation-2026-10-12.md).
The historical record remains intact and is not rewritten. Option B also
remains available as a narrower policy choice if the owner selects it; it is
not the current direction.

## 1. What Profile C authorizes

Profile C gives Sofía's Core higher everyday autonomy **inside an
owner-established, durable, revocable policy boundary**. It does not give the
Core authority to create or widen that policy. The Core may not self-approve,
self-enroll, or treat capability as authority.

Two consequential automatic paths are in scope:

1. **Automatic Fleet admission** of a new installation that proves possession
   of its own installation identity/key and presents a valid signed
   installation provenance statement.
2. **Autonomous Core migration** between owner-approved hosts while preserving
   canonical identity, Constitution, memory, history, lineage, and exactly one
   active writer.

Everything else remains governed by the existing SAFE permission model.
Capability does not imply authority.

## 2. Non-negotiable owner-only boundaries

The following remain owner-only and are never reachable through an autonomy
policy or a Core-originated proposal:

- changing permissions, grants, or the autonomy policy itself;
- accessing the owner secret or owner credential material;
- bypassing SAFE/STOP;
- permanent Fleet removal or decommission;
- changing trust policy, enrollment requirements, or protected signer sets;
- rotating or revoking owner/trust credentials;
- constitutional identity changes;
- deleting protected memory or protected state;
- disabling audit, backup, recovery, or STOP enforcement;
- exposing services publicly or weakening network/audience boundaries;
- moving protected data between Cores;
- granting unrestricted SYSTEM/root or protected authority;
- production release signing and release activation.

A high-autonomy policy can make an automatic path *eligible*. It cannot make a
forbidden path authorized.

## 3. Owner-established autonomy policy

The canonical record is `safe_autonomy_policy` in `sofia.db`, implemented by
`src/sofia/platform/safe/autonomy_policy.py`.

- Schema: `aegis.safe.autonomy-policy.v1`.
- Policy establishment consumes one exact, one-use owner approval for
  capability `safe.autonomy.policy.change`.
- The capability is explicitly classified **NEVER_SELF_AUTHORIZED**. Sofía may
  propose a policy revision but may never establish or approve one.
- Every revision is sequence-checked. Reusing an approval, replaying a stale
  revision, or altering the stored payload fails closed.
- The stored policy remains valid only while the consumed owner proof remains
  current. Owner credential revocation or secret rotation invalidates
  resolution; dependent automatic paths then deny.
- The default is no policy: absent an active policy, automatic admission is
  denied and explicit owner enrollment remains required.

Implemented profiles are:

| Profile | Meaning |
| --- | --- |
| `observe` | No automatic Fleet admission or Core migration. |
| `adaptive` | Bounded autonomous operation without the two Profile C automatic paths. |
| `high_autonomy` | Enables the owner-selected automatic Fleet admission and/or Core migration paths. |

A `high_autonomy` policy must still carry explicit booleans for each automatic
path. Enabling a profile alone does not enable either path.

## 4. Automatic Fleet admission

Implemented in `src/sofia/platform/ops/automatic_admission.py` and
`src/sofia/platform/ops/enrollment.py`.

Automatic admission requires all of the following:

1. An active `high_autonomy` policy with `automatic_fleet_admission=true`.
2. `signed_installation_provenance_required=true` and a nonempty
   owner-approved admission signer key set.
3. A short-lived Ed25519 attestation (maximum ten minutes) naming the exact
   installation identity, node UUID, installation public-key SHA-256, release
   manifest digest, and signer key ID.
4. The attestation signer must be both trusted by the verifier keyring and
   allowlisted by the active policy.
5. The signed node UUID and key digest must match the verified discovery record.
6. The candidate must be an untrusted discovery candidate, not an already
   trusted or enrolled host.
7. The exact approved HTTPS endpoint, machine binding, node enrollment, and
   authenticated peer evidence must still agree.
8. The initial permission level is bounded by the policy and may never exceed
   level 3; protected authority is never assigned automatically.
9. Policy and grant are re-resolved and rechecked inside the same SQLite
   transaction that publishes trust and audit. Any mismatch rolls back the
   entire admission and leaves the candidate untrusted.

The actor recorded for automatic admission is `policy:<policy_id>`, not the
owner and not the model. The audit receipt binds the policy revision,
attestation digest, signer key ID, initial permission level, and the normal
enrollment evidence.

Discovery, reachability, hostname, a LAN position, or an mTLS handshake alone
never enroll a host. Automatic admission is an explicit owner policy exception,
not a change to the default trust model.

## 5. Autonomous Core migration

**Status: DESIGN ONLY, NOT IMPLEMENTED OR TESTED.**

The autonomy policy schema currently carries
`automatic_core_migration` and requires
`verified_backup_required_for_migration=true` when it is enabled. That
reservation is not execution authority and no automatic migration path is
wired to the policy yet.

Any implementation must preserve all of the following:

- the canonical Core UUID and signed identity;
- the canonical Constitution and protected identity;
- canonical memory, history, lineage, and provenance;
- exactly one active writer at every instant;
- verified backup and restore readiness before cutover;
- fencing that denies activation whenever writer ownership is uncertain;
- durable receipts for preparation, cutover, verification, and rollback.

Uncertainty must deny activation. A timeout, lost response, or ambiguous lease
is not proof that the old writer stopped. No automatic retry may create a
second writer.

The first real Venus-to-Artemis migration remains separately owner-approved.
Autonomous migration must first be validated against disposable state. A
policy flag alone never authorizes a live migration.

## 6. Implementation evidence

| Area | Status | Evidence |
| --- | --- | --- |
| Owner-established autonomy policy | CODED + TESTED | `src/sofia/platform/safe/autonomy_policy.py`; `test/test_safe_autonomy_policy.py` |
| Policy capability classification | CODED + TESTED | `src/sofia/platform/safe/permissions.py` |
| Signed installation attestation | CODED + TESTED | `src/sofia/platform/ops/automatic_admission.py`; `test/test_ops_fleet_automatic_admission.py` |
| Policy-governed Fleet admission | CODED + TESTED | `src/sofia/platform/ops/enrollment.py`; disposable SQLite tests |
| Shared Python/Rust admission contract | CODED + TESTED | `src/sofia/sdk/fleet_admission.py`; `rust/crates/sofia-contracts/src/fleet.rs`; `contracts/platform/fleet-admission-valid-v1.json` |
| Autonomous Core migration | DESIGN ONLY | No implementation, no live state movement |
| Installed-host / G8 acceptance | NOT TESTED | No claim of installed-host or release acceptance |

These are source tests on disposable state. They are not installed-host
evidence, production acceptance, or G8 completion.

## 7. Historical decision reconciliation

- `docs/development/v18-ca-6505-owner-approved-autonomy-graduation-2026-10-12.md`
  remains the historical Option B record and is marked superseded.
- Existing SAFE owner approvals remain canonical. Profile C adds a durable
  policy bound to an exact owner approval; it does not replace the approval
  machinery.
- Fleet permanent removal remains owner-only. Profile C adds no removal path.
- Peer federation social trust remains separate from cryptographic admission
  and execution authority.
