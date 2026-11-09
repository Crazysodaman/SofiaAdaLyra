# Aegis Platform 1.0 | Personal owner-only Library commissioning (developer preflight)

**Status: implemented source interfaces, NOT a certified installed-host procedure.**
**Audience:** one owner, personally operated Windows/Debian Platforms, one selected private Hub and explicitly enrolled peers. No SaaS, commercial CA, customer accounts, public catalog, paid subscription or default internet fallback.

This document is for a **disposable approved test installation** until the signed B1 installer, canonical Rust GUI/TUI, owner Fleet enrollment and LIB-01–16 acceptance are complete. It is not permission to change your existing host, move Sofía's protected state or distribute copyrighted/model/voice assets.

## Architecture: one owner, existing local authority

- A real signed Core-free B1 Platform installs its immutable Platform UUID and local SQLite database. The local Platform is usable with **zero Cores**.
- `OwnerLibraryTrustStore` stores **one active owner-selected publisher public key**, selected source Platform ID, revision floor and catalog generation **in that same local SQLite**. This is a per-Platform owner enrollment, not a new cloud publisher service.
- Trust is **never** established by a Hub response, filename, device nickname, certificate from the TLS handshake or first connection. The approved owner's existing SAFE system must consume an exact one-use enrollment action.
- The owner may store a **small complete Ed25519-signed catalog index** in the same database. Every local native reader revalidates its signature, audience, generation, current root and expiry. No model weights, protected memories or voice material are stored in this catalog table.
- Remote Hub/peer reads still require **independently enrolled mutual TLS**, distinct per-chunk SAFE grants, STOP checks and a second one-use B1 cache-admission grant. Catalog visibility is neither an install receipt nor permission to copy an artifact.
- This is intentionally **one owner across multiple installed Platforms**, not one owner account shared without authentication by every voice, process, LAN client or Core.

## Source-only CLI (not yet registered as final native `aegis` command)

On an installed authorized Platform, resolve its **actual** canonical local state and immutable Platform ID from the verified installer. Substitute the placeholders below without making new identities.

```powershell
$State = '<exact installed Platform-local SQLite path>'
$PlatformId = '<immutable installed target Platform UUID>'
$HubId = '<already enrolled Hub Platform UUID>'
$PublicKey = '<approved 32-byte RAW Ed25519 public-key file>'
$SignedCatalog = '<complete current publisher-signed index JSON>'

python -m sofia.platform.ops.library_owner_cli --state $State --platform-id $PlatformId status
python -m sofia.platform.ops.library_owner_cli --state $State --platform-id $PlatformId prepare-enroll --source-platform-id $HubId --public-key $PublicKey --catalog-generation 1 --minimum-revision 1
```

The preflight only prints the **exact SAFE capability and fingerprint**. It does **not** grant access. The owner must approve that exact fingerprint through the existing attended owner-secret or verified WebAuthn path before an `enroll --approval-id ...` call can succeed. Never paste the secret, approval token or key material in the repo, shell history, Discord or chat.

### Attended Venus Windows path, if already approved and configured

```powershell
# The existing attended 256-bit owner secret is enrolled once on the
# verified Windows owner account. Do not re-enroll if already configured.
python -m sofia.platform.safe.owner_secret_cli status --state-path $State

# Only if an owner secret is not already enrolled, on the actual
# authorized Windows owner console with host-bound SID:
# python -m sofia.platform.safe.owner_secret_cli init --state-path $State

# Exact one-use action, prompted locally with hidden secret:
python -m sofia.platform.ops.library_owner_cli --state $State --platform-id $PlatformId enroll-attended --source-platform-id $HubId --public-key $PublicKey --catalog-generation 1 --minimum-revision 1
```

**This path deliberately fails on Debian and unenrolled/remote Windows accounts.** On Debian, use `prepare-enroll` and the existing **separately authenticated approved owner proof** for that specific installed Platform. Do not copy a Windows owner's secret to an unattended Linux service, pass the secret in argv, or use a test signing key to claim production publisher trust.

### Import a current signed catalog, read truthful state and revoke

```powershell
python -m sofia.platform.ops.library_owner_cli --state $State --platform-id $PlatformId import-index --file $SignedCatalog
python -m sofia.platform.ops.library_owner_cli --state $State --platform-id $PlatformId status

# Revoke using an independently authenticated one-use action:
python -m sofia.platform.ops.library_owner_cli --state $State --platform-id $PlatformId prepare-revoke

# On verified attended Venus owner console, if its owner secret is enrolled:
python -m sofia.platform.ops.library_owner_cli --state $State --platform-id $PlatformId revoke-attended
```

Successful catalog import means **SIGNED_CATALOG_CACHED**, not download, installed, active, GO or publisher enrollment of another device. A current index can expire after minutes. Refresh requires a newly signed, current publisher index with strictly advancing signed issuance time and nondecreasing revision.

Owner trust revocation takes effect on the very next provider/reader check. The existing operator **STOP** makes the catalog unavailable and blocks imports; a separately owner-approved trust revocation remains possible during STOP. After revocation, re-enrollment requires a newly approved action and a **strictly increased catalog generation**; the rollback floor cannot decrease.

## What is still needed for production host operation

1. Actual owner-approved signed B1 release build and **live installed Windows/Debian** service, with independent publisher signing/root and revocation evidence.
2. Reviewed private Hub source and enrolled per-device mTLS delivery of signed catalog bytes to the internal service's `accept_installed_signed_library_catalog()`. The interim `import-index` is an **owner-selected file handoff**, not automatic discovery.
3. Actual cross-host SAFE owner proof on Debian; attended Windows secret must not be treated as a portable credential. The Rust GUI/TUI/CLI still requires verified installed-service pins and reviewed operator controls.
4. Genuine signed package transfer and stage/install/activate/rollback with dependency closure, crash-safe receipts and the separate one-use B1 action. A catalog alone never installs software.
5. Targeted local compilation/pytest, full CI last, then independent four-disposable-host installed tests and the original 16 Library + 38 Platform acceptance gates. **No acceptance row is promoted by this document.**

Relevant source: `src/sofia/platform/run/library_owner_trust.py`,
`src/sofia/platform/run/platform_service.py`,
`src/sofia/platform/ops/library_owner_cli.py`.

Focused test files: `test/test_library_owner_trust.py`,
`test/test_library_owner_cli.py`,
`test/test_library_single_owner_native_service.py`.
