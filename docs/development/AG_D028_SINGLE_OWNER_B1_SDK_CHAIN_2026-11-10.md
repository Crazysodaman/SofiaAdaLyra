# Project Aegis | D028 single-owner B1 SDK trust chain

**Date:** 2026-11-10
**Release verdict:** source integration added; exact-SHA tests have NOT been executed or independently certified.
**Scope:** one owner's Windows/Debian homelab, owner-approved enrolled devices, no SaaS, paid signing service, customer roles or public artifact marketplace.

## What is implemented on `main`

### 1. Reuse original B1 publisher policy instead of caller booleans

- `src/sofia/platform/ops/platform_release.py`: `PlatformReleaseVerifier.verify_manifest_reference` now performs the **same** canonical Ed25519 signature, source Git SHA, target/SDK protocol, state schema, parent digest and anti-rollback checks as the full installer. It deliberately verifies metadata without requiring the remote recipient to download all other release assets. `verify` still reuses this method and independently checks every complete local release artifact before installation.
- `src/sofia/platform/ops/library_b1_sdk_publisher.py`: canonical complete signed B1 SDK envelope (release manifest + detached signature + signer ID), exact SHA-256 for the D028 transfer manifest, independent original B1 verifier, current signer/revocation, installed rollback floor and the selected SDK's bounded content hash plus wheel dependency/Core boundary. It returns a `PlatformArtifact` for B1 cache review, **not** an installer receipt.
- `review_personal_b1_sdk_offer`: source Hub may prepare a copyable SDK offer only from a matching canonical B1 installed release receipt, exact signed SDK file, current trusted signing key, no unresolved B1 installation attempt and explicit **current** personal-copy license approval. A test signer or a model file marked `personal` is not blanket permission for peer distribution.

### 2. Actual recipient workflow and offline owner approval retry

- `src/sofia/platform/run/platform_service.py`: `acquire_owner_approved_library_sdk` builds the real signed B1 SDK verifier inside the existing Core-free Platform session and sends it through the original authenticated recipient coordinator. A generic `verified=True` boolean from a Hub is never accepted as a signature.
- `src/sofia/platform/ops/library_chunk_receiver.py`: `pending_signed_cache_admission` checks exactly matching private signed transfer metadata and a completed content-addressed quarantine object, guarded by the original OS-backed single-writer lock. An unbound completed object is **rejected**, not adopted or automatically redownloaded.
- `src/sofia/platform/ops/library_recipient_pipeline.py`: after fresh owner SAFE/STOP and current signer checks, completed quarantined bytes are retried into B1 without TLS. Only the existing independent package verifier, full SHA-256, one-use `platform.library.cache_admit_enrolled_peer` SAFE approval and original B1 import can promote them to `CACHED_VERIFIED`. The returned state remains `installed=None` and `active=None`.
- Existing `library_verified_handoff.py` retains signed provenance through denial and crash recovery. A denied owner approval does not destroy the complete bytes or turn them into installed code.

### 3. Headless personal commissioning is genuinely read-only

- `src/sofia/platform/run/lease.py`: `LocalRunLeaseStore.peek_existing` observes the existing inode-pinned RUN lease through read-only SQLite, without constructing a writer, migrating tables or claiming a remote Fleet quorum.
- `library_owner_grant_preflight.py`: exact private-Hub and current-OS-operator read grant previews now consume this nonmutating observer. Absent/expired/corrupt RUN, STOP, public bind addresses and unrecognized peers remain denied. They issue **no grant**; attended owner authentication remains separate.

## Focused tests authored, not executed

```bash
python -m compileall -q src/sofia/platform/run src/sofia/platform/ops test
python -m pytest -q test/test_library_owner_grant_preflight.py test/test_library_recipient_pipeline.py test/test_library_verified_handoff.py
python -m pytest -q test/test_library_b1_sdk_publisher.py test/test_library_personal_b1_sdk_service.py test/test_library_personal_b1_sdk_admission.py
python -m pytest -q test/test_platform_release_verifier.py test/test_platform_release_contract.py test/test_ops_platform_installation.py
```

The signed SDK test uses the original `fixture_release` to produce a genuine disposable Ed25519 signed B1 release and SDK wheel. The linked test crosses signed source B1 receipt, separately signed private catalog, transfer plan, completed quarantine, verified recipient wheel and real disposable SAFE one-use proof into canonical cache, **without** calling the network or claiming a production host PASS.

## What still blocks GO

1. Finish full Platform release bundle verification, ordered installation, activate/rollback and retained receipt path over separately owner-approved B1 effects. The new single-SDK verifier is intentionally not a release installer.
2. Provide real owner-installed publisher key/revocation, existing Fleet pairings, B1 signed issuer records and target-specific certificate enrollment on the user's disposable Debian/Windows hosts. No imported test keys or self-enrollment.
3. Freeze D028-00 authenticated SDK/native/Python parity, wire the installed read/approval responses into native GUI/TUI and Windows headless operator controls, and test STOP/reboot/mismatch/revocation through the actual OS supervisor.
4. Complete hardware and RAM efficiency checks and independent full multi-machine shakedown evidence. The original **LIB-01..16** and **Platform #201 38-row** ledgers remain authoritative and must not be promoted by test-file existence.
5. Run focused tests and only later the owner-directed final full GitHub CI, reconcile any reds, then prepare the signed release for authorized live owner testing. No production cutover or host migration was performed.

**Important contract distinction:** `sha256(canonical_signed_b1_sdk_envelope)` is a D028 **complete signature-bearing manifest** identity. `PlatformReleaseManifest.digest` is the older domain-separated B1 signed-policy digest used in installer receipts. `asset.reference.sha256` is the actual SDK code bytes. These three digests must never be substituted for one another. Owner-private use removes commercial overhead, not signature or SAFE checks.
