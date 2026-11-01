# G8 shakedown runbook — review draft

Status: NOT APPROVED FOR EXECUTION. This document prepares #129; it does not
close its 16 items or authorize host access. Development acceptance is tracked
in #120. SHAKEDOWN READY and production GO are separate decisions.

## Required inputs and authority

Before scheduling G8, the reviewer must attach the exact candidate source SHA,
Windows/Debian RC runs, all 22 package-family results, signed release manifests,
component identities and SHA-256 hashes, dependency locks, SDK/ABI/schema
compatibility, supported OS/Python versions, and the independent security and
recovery decision. An unsigned CI upload is not an approved signed release.

Name the operator, independent verifier and approving owner. Record the exact
source/target host identities, enrolled certificate fingerprints, allowed roles,
Core identity and state lineage, approval IDs and expiry, pinned model digest,
module grants and intended process generations. Discovery and hostname matching
never substitute for enrollment. Retain secrets in the approved secret store;
evidence contains opaque references, never credential values or private content.

Use fresh disposable identities, test credentials and synthetic state for the
rehearsal. Record absolute disposable roots and verify that they do not resolve
to the production state root, its parents, an existing production pointer, a
symlink/junction or a shared production backup location. Do not copy production
Constitution/persona/memories or recovery keys into a test fixture.

The operator must identify the reviewed installer and privileged handoff broker
entry points for this candidate. `prepare_pending_state_pointer` and
`review_operator_handoff` only prepare/review evidence; they do not themselves
prove source fencing or authorize activation. Missing broker composition is a
STOP condition, not permission to substitute manual database copying.

## Rehearsal sequence

1. **Preflight and recovery boundary.** Confirm candidate signatures/hashes and
   exact SHA on both hosts. Inventory canonical SQLite and state-plane assets,
   external references, audit receipts and platform-local operational stores.
   Agree RPO/RTO and the permitted interruption. Record source writer lease,
   process generation and current endpoint. Verify STOP works before effects.
   Define which operator may invoke rollback and how an uncertain writer is
   independently fenced. No automatic source resurrection is permitted.

2. **Core-free target Platform.** Install SDK/Platform through the reviewed
   installer into the disposable target environment. Check installed RECORDs,
   dependency lock and package digests; prove that Core and its protected assets
   are absent. Run the installed `companion-runtime status` command and record
   configured roles. Verify headless startup and the Windows/systemd service
   identity, private-state permissions and bounded watchdog/restart policy.

3. **Explicit enrollment and Core installation.** Obtain the exact scoped
   approval, authenticate/pin both endpoints, and stage only the signed reviewed
   Core artifact through the approved component coordinator. Record approval
   consumption, artifact verification, SDK/ABI/schema handshake and generation.
   Reject wrong identity/digest/signature/version, expired or revoked grants,
   and interrupted attempts without recording success. Do not start a second
   canonical writer during staging.

4. **Baseline continuity.** Bind a disposable Core Link desktop/tray to the exact
   enrolled Core identity. Record a synthetic conversation ID and history,
   memory provenance/corrections, persona settings, goals and pending actions.
   Verify a genuine pinned-provider answer and explicit failure behavior; a
   cached placeholder is not proof of inference. Exercise one reviewed signed
   module's settings/apply/restart/cancel/rollback without restarting unrelated
   Platform services. Verify optional modules may be absent.

5. **Protected snapshot and restore.** Quiesce/consistently snapshot synthetic
   canonical state and all inventoried assets via the approved backup path.
   Record independent hashes, snapshot time and asset completeness. Restore to
   an isolated inactive destination and verify identity/history and integrity
   without serving private state. Measure backup age, restore time and RPO/RTO.
   A successful backup command without a verified restore does not pass.

6. **Approved handoff.** Drain conversations/actions; persist idempotency and
   UNKNOWN-effect receipts. The independent broker must prove source worker
   exit and canonical-writer fencing, advance the durable epoch, authenticate
   transfer and verify complete destination state before activating one target
   generation. Record migration receipts, source fence proof, target attestation
   and independent exactly-one-writer evidence. A pending pointer or passing
   preflight review is insufficient evidence of a completed transition.

7. **Reconnect and host services.** Reconnect Venus through an authorized
   exact-identity endpoint/generation update. Confirm the same conversation,
   history, goals, memory and permissions; Venus remains a Core-free
   CORE_LINK/MODULE_HOST. Verify Discord has one authority and no duplicate
   outbound delivery. Exercise supported voice/avatar behavior and accurately
   record unsupported paths. Verify authenticated model/digest-pinned Venus GPU
   inference and module/provider independence.

8. **Failure matrix.** On disposable state only, inject source/target crash
   before, during and after fencing; corrupt/incomplete transfer; target outage;
   stale generation/lease/telemetry; clock rollback; network partition;
   Venus sleep/offline; provider outage/GPU pressure; revoked/expired approval;
   watchdog restart; and uncertain effect replay. For each, capture the observed
   writer count, allowed state visibility, STOP behavior, truthful outcome and
   bounded recovery. Deny unsafe activation and preserve UNKNOWN effects.

9. **Cognitive trace.** Under explicit observation consent, record the supported
   authenticated observation → Presence/V2 evidence → explained inference →
   typed goal → SAFE/RUN result → independently verified outcome → eligible
   learning → changed later decision trace. Include identity/provenance,
   audience, expiry and receipt IDs. Compare without-learning behavior, revoke
   evidence, restart and verify isolation/continuity. A Core-authored assertion
   alone is not an independent host-effect observation.

10. **Rollback and verdict.** Exercise reviewed rollback using synthetic state.
    Restore only a verified complete snapshot and only after independently
    fencing the uncertain/new writer. Never operate both generations to
    compensate for loss of contact. The verifier records PASS/FAIL/UNKNOWN per
    criterion and the owner makes the G8 GO/NO-GO decision. Real protected-state
    cutover requires its own separate explicit authorization and recovery plan.
    Only after that authorization and successful cutover may an agreed soak
    window begin; the owner defines duration and acceptance thresholds.

## Stop conditions

Stop on duplicate-writer risk, unprovable source fencing, unmatched or unsigned
artifacts, identity/pinning failure, missing broker/approval, unknown restore
integrity, private-state exposure, unexplained state loss, replayed effects,
silent model/host switching, failed STOP, or inability to converse after handoff.
Preserve evidence, quarantine uncertain generations and obtain independent
recovery review. Loss of contact alone never authorizes failover.

## Evidence record for every step

| Field | Required value |
|---|---|
| Candidate | Source SHA, signed manifest reference, exact artifact/lock digests |
| Environment | OS/Python, host identity/fingerprint, roles, disposable root reference |
| Authority | Operator/verifier, scoped approval ID/expiry, consent/grant references |
| Writer | Core identity/lineage, source/target generation and lease/epoch, fence proof |
| Observation | UTC start/end, expected behavior, actual behavior, PASS/FAIL/UNKNOWN |
| Integrity | Backup/restore/asset hashes, provenance and independent receipt references |
| Recovery | Injection point, retained UNKNOWN work, measured RPO/RTO, rollback result |
| Privacy | Redacted evidence location and reviewer; no secrets or conversation contents |

The runbook remains a draft until reviewed against the final installed artifacts
and completed operator/broker configuration. No step above has been executed by
creating this document.
