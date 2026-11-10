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

## Review current personal SAFE grants without manually assembling JSON

These source-only commands work against the **existing installed** Platform
identity and its current RUN lease. They create **no grant**, do not consume an
owner approval, and do not start a Hub or a Core:

```powershell
python -m sofia.platform.ops.library_owner_cli --state $State --platform-id $PlatformId prepare-local-read
python -m sofia.platform.ops.library_owner_cli --state $State --platform-id $PlatformId prepare-local-read --operation library.sources.snapshot.v1
python -m sofia.platform.ops.library_owner_cli --state $State --platform-id $PlatformId prepare-private-hub --bind-host 127.0.0.1 --bind-port 47321
```

The second local read is a **separate** source-status permission. It permits
your attended native reader to observe the current publisher pin, signed
catalog and Hub worker state, even on a fresh uncommissioned Platform. It
does not authorize catalog browsing, peer transfers or installations. Its
single-owner status vocabulary deliberately distinguishes:

- `publisher_state = UNENROLLED/CURRENT/REVOKED/UNKNOWN`
- `catalog_state = UNAVAILABLE/CURRENT/UNVERIFIED`
- `hub_state = CLOSED/OPEN_IDLE/SERVING/UNKNOWN`

`SERVING` only means the current owner-approved local Hub worker is
observed serving; it is not a test of remote reachability, package
activation, model availability, TLS enrollment or Core health. An absent
external publisher signer/Hub is normal. The response contains no
password, signing key, private asset path, Owner proof or personal data.

Each prints the current `run_generation`, exact `capability`, JSON `scope`
and compact `scope_json`. The private Hub preview only permits canonical
numeric private/loopback addresses, never `0.0.0.0`, public IPs or DNS names.
The local-read preview derives the **actual** current OS operator UID/GID
on Linux or verifies the attended Windows owner SID; it does not accept a
caller-supplied client identity. A missing/expired RUN lease or STOP is a
hard denial, not a fallback to a fabricated local Platform.

To actually create the narrowly scoped 10-minute grant, the owner separately
uses the existing attended SAFE permission command with the exact displayed
`capability` and `scope_json`. For example, on the **authorized host's
attended console**, copy the exact JSON produced by the preflight:

```powershell
python -m sofia.platform.safe.permissions_cli --state-path $State grant platform.library.read --scope-json '<exact JSON scope from prepare-local-read>' --expires-minutes 10
```

The SAFE CLI requests the existing 256-bit owner secret or verified WebAuthn
approval. It does **not** accept a preflight preview as an owner grant. On
an unattended Linux Platform, local Windows-only owner-secret authentication
deliberately refuses; enroll by the separately approved host-specific owner
workflow, not by copying credentials into a Linux service.

An owner-approved Hub grant and an enrolled peer TLS certificate/grant remain
**separate**. A `prepare-private-hub` result is not proof a publisher
signing key, eligible signed package or remote mTLS identity is installed.
Likewise, a local Library-read grant does not permit transfer, installation
or deletion.

## Owner-selected private LAN publisher, with no signing key in Aegis

The primary Hub can construct a **complete Ed25519-signed catalog index**
using `publish_signed_owner_catalog` in
`src/sofia/platform/ops/library_owner_catalog_publish.py`.
`HostedLibraryHub.publish_current_signed_catalog` binds that operation to
its already independently verified signed B1 artifact, exact recipient and
current owner-approved private Hub RUN. Its `sign_external` callback must
come from the owner's **existing separately approved local signer**, not
from a remote peer, model output, public catalog, or a private-key file
invented during startup. No private signing key is stored by the Platform.

**License policy is enforced before signing:** Only artifacts whose
independent package proof and exact license review explicitly permit
peer copying may appear as LAN transfer items. A locally lawful
noncommercial/personal-use model that forbids copying to another personal
computer remains available for its separately approved local use, but its
name, digest and weights must not be advertised to peers. Never assume
`free` equals `may redistribute`.

The recipient uses its own enrolled owner publisher record in the original
Platform SQLite by default. `accept_installed_signed_library_catalog` is
an internal source-to-service handoff, not an unauthenticated management RPC.
The file-based CLI `import-index` is a temporary attended, offline handoff,
not a public network endpoint. Signed catalog verification proves metadata
integrity only; it does not grant TLS admission or install software.

**Focused source regressions:** `test/test_library_owner_catalog_publish.py`,
`test/test_library_host_catalog_publish.py`, and
`test/test_library_personal_recipient_source.py`. They are disposable
synthetic fixtures, **not real installed-host acceptance**.

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
