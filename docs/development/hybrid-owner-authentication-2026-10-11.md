# Workstream 1: Owner authentication Option C source status

## Option A supervised enrollment decision and implementation (2026-10-11)

**Approved:** First owner credential is created through supervised Windows Hello **on Venus**. A physical FIDO2 key is then registered through a separate signed owner ceremony; a backup key can be registered the same way. No database or runtime cutover is authorized.

The current source implementation now includes:

- `owner_enroll_browser.py` and `owner_enroll_cli.py`: operator-initiated first Windows Hello `navigator.credentials.create()` ceremony, localhost-only HTTP with a random session token, exact challenge and RP origin, user verification, Windows interactive session, and explicit manual command confirmation. The CLI does not accept a caller-supplied alternate database path.
- `owner_registration.py`: bounded non-attested WebAuthn/CBOR ES256 registration parser validating credential ID, COSE key, RP hash, UP/UV/AT, challenge and origin. First trust is irreversible once any credential has existed, including revoked credentials.
- Owner Windows **access-token SID**, not environment username/display name, is captured from the signed-in process and permanently bound in canonical `safe_owner_host_identity`. Other Venus logins cannot perform subsequent registration or revocation, or request local signed approvals on that copied authority.
- Subsequent key enrollment requires a fresh action-bound WebAuthn assertion by an already enrolled owner key and an atomic one-use credential registration receipt. Physical-key role remains **supervised classification, not attested manufacturer provenance** because enrollment intentionally requests WebAuthn `attestation: none`.
- `owner_approval_ui.py` identifies active, already enrolled security-key credentials for Settings. Model installation, Fleet enrollment and clearing operator stop use exact FIDO2-signed receipts from the one-shot browser, asynchronously with UI feedback. Emergency `operator.stop.on` remains immediate and requires no authenticator. CLI resume requires FIDO2.
- Credential revocation requires a distinct signed FIDO2 exact-action receipt and rejects removing the last active security-key credential. Revocation leaves an audit history and cannot reopen first-trust bootstrap.

### Operator-run commands, only after the owner completes Debian-independent local preflight

Run from the original signed-in **Venus Windows desktop**, with the current sole-writer state still on Venus:

```powershell
python -m sofia.safe.owner_enroll_cli list
python -m sofia.safe.owner_enroll_cli first-hello --acknowledge-sole-writer
python -m sofia.safe.owner_enroll_cli add-key --kind security_key --authorized-by <existing-owner-credential-id>
python -m sofia.safe.owner_enroll_cli add-key --kind security_key --authorized-by <existing-owner-credential-id>
python -m sofia.safe.owner_enroll_cli revoke-key --credential-id <old-key-id> --authorized-by <another-active-security-key-id>
```

These are **documented future operator-run commands**, not host changes performed by this development work. A reviewed current live backup, independent recovery route, native Windows Hello/browser support, trusted key hardware evidence and successful targeted tests are prerequisites before treating a live first enrollment as accepted. A revoked last security key cannot be forced through the normal CLI.

### Updated incomplete work

1. First enrollment, later FIDO2 registration, CLI, revocation and two major Settings approval routes are **source-coded but NOT EXECUTED**. Browser/platform behavior and physical-hardware provenance are not independently verified. Protect access to the canonical state file with operating-system ACLs.
2. Initial supervised Windows account authority and OS prompt do not constitute manufacturer-root attestation. Require separate attestation metadata/trust roots if cryptographic hardware origin is a non-negotiable requirement.
3. Other Settings/Tray approval buttons, `PermissionStore.grant/revoke` and Level-5 classification, DEV/EVOLVE approvals, authenticated operator recovery, cross-host receipt transport, offline root recovery and status UX still require production wiring. Level-4 paths already migrated fail closed until a valid owner credential is enrolled.
4. Keep all signed assertions, secrets, user approval and recovery rights outside model authority. Never automatically run enrollment or remove the last security key.
5. No tests, CI, setup commands, live enrollment or host operations have been executed. Do not mark V18 tasks accepted on source alone.



**Owner decision, 2026-10-11:** hybrid authentication: platform Windows Hello for convenient local approvals and separately registered FIDO2 security keys for protected/high-risk actions. This architecture is intended to migrate with the canonical runtime from Venus to the dedicated headless Debian 13 `Sofia` VM on Artemis, without moving private keys or allowing a second SQLite writer.

## What is actually implemented

- `src/sofia/safe/owner_webauthn.py`: canonical existing-state WebAuthn ES256 assertion verification, RP/origin binding, user-presence/user-verification requirements, exact action fingerprint, TTL, replay and counter enforcement, atomic hash-chained SAFE audit. No untrusted self-enrollment entrypoint.
- `src/sofia/safe/owner_browser.py`: one-shot `127.0.0.1` HTTP origin `http://localhost:<dynamic-port>` browser ceremony using `navigator.credentials.get`, secret ceremony URL token, exact on-screen action review, same-origin completion only and signed assertion validation. Loopback is not a remote identity gateway.
- `src/sofia/safe/execution_approval.py`: protected / unknown Level-4 and Level-5 capability names require fresh security-key WebAuthn proof linked one-to-one with existing exact-action approval in canonical SQLite. Old unbound approvals are rejected both during active capability projection, preflight and final consumption.
- `src/sofia/safe/approve_execution.py`: existing explicit local approval CLI routes protected requests into the browser ceremony rather than minting an owner receipt from `--approved-by Sparks`. Low-level reversible approvals retain existing policy pending Windows Hello UI migration.
- Tests authored for assertion validity, origin, UV, counter, expiration, replay, local browser proof, strong approval receipt binding and legacy record rejection. Existing protected-operation fixtures now create signed assertions in test-only synthetic enrollment, never in production.

**All source changes committed to main with `[skip ci]`. No tests or CI were run. This is NOT fully enrolled or host-accepted production authentication.**

## Remaining coding and trusted enrollment boundary

1. **First-credential enrollment is not implemented.** An enrollment endpoint that accepts `approved_by=Sparks`, browser-supplied `credential_kind`, or a self-asserted Windows username would be an authentication bypass. The owner must approve a first-trust procedure, such as attended local OS-broker verification plus verified WebAuthn registration and an independent recovery path.
2. WebAuthn's assertion validates a registered credential's key, not that the credential is a physical security key. The `credential_kind` field is currently trusted enrollment metadata; hardware assurance needs a reviewed enrollment/attestation policy. Do not claim hardware-backed proof solely from this string.
3. The desktop/tray Settings buttons for protected Fleet enrollment, workshop boot, model install and local services still create actor-only approval requests; they now fail closed at SAFE. Replace with owner-facing real challenge/ceremony and non-blocking result handling before saying the UI feature works.
4. The existing `PermissionStore.grant/revoke`, other protected approval owners (DEV/EVOLVE/Fleet release), operator-stop **resume**, and remote/cross-host security principals require a separate inventory and independent authenticated-owner enforcement. Emergency **stop** itself should remain fast and fail-safe.
5. Design and implement credential enrollment/rotation/revocation, backup keys, root recovery, signed receipt transfer across trusted clients/hosts, anti-phishing session binding, availability/degraded modes and independent audit verification. No owner credential or recovery secret may be generated by a model.
6. Run focused SAFE tests, exact-SHA full CI, Windows Hello + physical key ceremony, Debian/Artemis remote acceptance and denied-key/locked-screen/reboot/replay/race tests in the owner-deferred final verification campaign.

## Operational invariant

Venus remains the **only authorized runtime/`sofia.db` writer**. The owner-created Artemis Hyper-V `Sofia` VM is reported to be **installing Debian 13**. Installation does not authenticate the new writer, provision an owner authenticator, fence Venus, move state, or authorize a service start. Do not activate another canonical runtime until an independently approved and witnessed single-writer cutover.

## Source acceptance classification

The related V18 IDs (including CA-1904, CA-1102, CA-6507, CA-4103 and CA-2905) remain **partial or unassessed as already recorded**. Neither source-written regression tests nor a new class are evidence of complete behavior. **Zero new tasks accepted.**
