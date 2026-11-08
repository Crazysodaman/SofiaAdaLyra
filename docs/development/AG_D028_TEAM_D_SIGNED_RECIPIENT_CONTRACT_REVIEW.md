# AG-D028 D-004 | Team D recipient-to-catalog contract review

**Status:** CANDIDATE / REVIEW REQUIRED. This document is neither an SDK v1 schema freeze nor authority to accept or install artifacts. Canonical owner: Team A's native-authenticated Rust Platform management service, Team B's existing publisher trust/installer/cache, Team C's shared UI, Team E's independent witness.

**Pinned source heads when written:**
- Team D [#251](https://github.com/Crazysodaman/SofiaAdaLyra/pull/251), recipient verifier, module closure, catalog bridge and negatives.
- Team A [#241](https://github.com/Crazysodaman/SofiaAdaLyra/pull/241), authority-free \`sofia.sdk.platform_library\` strict \`request.v1\`/\`response.v1\` syntax and separately authenticated Platform management service.
- Team B [#244](https://github.com/Crazysodaman/SofiaAdaLyra/pull/244), canonical B1 signed installer, \`OfflineArtifactCache\`, \`platform_library_admission\`, publisher root/release verifier.
- Team E [#245](https://github.com/Crazysodaman/SofiaAdaLyra/pull/245), 38-row and LIB-01..16 negative installed-host evidence.

## 1. Single authority, five separate states

A's *currently enrolled native/remote service* authenticates principal + audience + Platform ID + generation + state revision + expiry and checks SAFE/STOP/revocation. Never take these from a Hub, JSON field, ModuleRecipientPin or SDK client. A typed \`UntrustedLibraryResponse.parse\` proves only syntactic correlation, **not** a signed publisher index or authorized principal.

1. **INDEXED:** A-owned catalog projection, source + freshness, no file or install claim.
2. **DOWNLOADED:** source bytes received; no digest/signer verification claim.
3. **VERIFIED:** B publisher root/revocation, signed artifact/index receipt, exact content bytes and D signed package manifest+file digests independently checked; no install claim.
4. **STAGED / INSTALLED_DISABLED:** only B installer and D Module Manager's versioned host receipts authorize these.
5. **ACTIVE:** only Team A/Core or D's governed running-worker lifecycle authority may assert current generation and health. Never infer from Hub TLS, cache hit or status code.

The Hub may offer immutable bytes via A-governed transfer but cannot sign for the publisher, mint an owner grant, change the active Core writer or assert installed/active.

## 2. A/B acceptance interface, required before D's consumer is wired

The **existing** A response shape stays exactly \`aegis.platform.library.response.v1\` with its 12 fields; the catalog data stays exactly its documented seven fields and each item exactly its 17 fields. Do not create a second wire schema.

**A must attest:**
- Authenticated service session, target Platform, current principal, peer enrollment, server-owned catalog generation+revision floor, valid correlation, response expiry and request nonce. A's \`current_request_admit\` is before even publisher-index key lookup; A's \`current_host_scope_admit\` is before archive/file/public-key reads and rechecked after archive and signature verification.
- Signed-index evidence is **not** the unsigned catalog JSON itself: it must bind the precise canonical item/page digest, catalog generation/revision/expiry, trusted signer ID and signature over exact bytes. Exact signer algorithm, canonical byte encoding, signed receipt reference, key provenance and revocation floor must be frozen with B before D can use the \`signed_index_admit\` port.
- Source and transfer eligibility must bind enrolled source/target identities, artifact class, content digest, immutable catalog revision, allowed license, quota and STOP/revoke at each chunk. No implicit Internet fallback.
- A's callbacks/ports cannot be constructed by untrusted client code; every boolean approval must originate from an authenticated in-process authority call. Truthy strings, ints, dictionaries, stale cache and missing service reject. If this cannot be enforced, the bridge must remain unreachable from any client.

**B must attest:**
- Resolve only independently pinned publisher roots, key ID/ref, current revocation and release floor. Never accept a peer's public key as a trust root.
- Verify **archived content SHA256** and independently signed source receipt *before* extracting or opening package files; tightly bound path, symlink, expanded size, quota and target admission.
- Distinguish catalog \`manifest_digest\` from full signed manifest bytes versus D's \`SignedModuleManifest.package_identity_digest()\` (canonical **unsigned** policy identity) and \`artifact_set_identity_digest()\` (legacy maintenance artifact identity). Team A/B/D must choose and freeze ONE canonical mapping. **Do not equate the three digests by convention.**
- Keep B1 installer, installed receipt history, cache pins and rollback authority singular. No Team D "installer" or duplicate publisher signature service.
- Publish an authenticated license/distribution policy decision for each artifact and its whole transitive closure; \`unknown\`, private, protected or nonredistributable assets may never be offered as generic peer packages.

**D must attest:**
- Explicit selected \`artifact_id\`, \`manifest_digest\` and \`content_digest\`; only one matching catalog row; no wildcard, implicit "latest", auto-fetch, auto-install or auto-Core activation.
- Recheck each signed module manifest Ed25519 signature, exact artifact file SHA256, publisher/trust ref, OS/platform API, isolation profile, resources and selected operation profile using canonical \`verify_module_package\` and \`evaluate_module_compatibility\`.
- Each transitive dependency requires exact version+digest, current signed installed/staged receipt, rollback retention pin and licensed source. Ambiguous or conflicting dependencies deny. A VERIFIED candidate is still uninstalled.
- Synthetic worker crash, stale generation, STOP/revocation and rollback receipt tests must run on disposable Windows/Debian hosts before rows 17/18/22/23/24 may be accepted.

**C must attest:** CLI/TUI/WinForms display only the shared authenticated A response, labeled \`CURRENT\`, \`STALE\`, \`UNKNOWN\`, \`REVOKED\`; never translate \`received_bytes == total_bytes\` into VERIFIED or ACTIVE.

**E must attest:** frozen A/B/D/C exact SHAs, signed roots + metadata/ABI/license/manifest receipt hashes; actual Debian12/Windows installed host, native service enrollment, non-default-deny receiver and peer negative tests. Retain the original 38-row ledger and 16 LIB rows; no partial source test marks PASS.

## 3. Current D draft boundaries and known unresolved issues

\`src/sofia/platform/modules/library_plan.py\` is **inert** deterministic exact-digest dependency preview; \`library_recipient.py\` re-verifies signed package files with caller-supplied A/B policy gates; \`library_catalog_adapter.py\` maps A candidate catalog fields to D's module verifier. Tests are synthetic Ed25519 packages with deliberate *fake* A/B callbacks: passing them NEVER proves actual service authentication, real signed index bytes, B archive verification, transfer, OS installed-host lifecycle, license authority or Core activation.

Blocking before enabling service routing: A/C frozen strict Rust/Python contract; B pinned signed index/root+receipt bytes; exact mapping of full manifest vs canonical identity; current peer/SAFE per-chunk host path; B1 installed receipt; E's signed Windows/Debian evidence. Keep all privileged actions fail-closed until signed-off.

**Signoff checklist:** A authenticated transport + index signature evidence (not a JSON assertion); B publisher archive/index root, ABI/license/retention and one installer; D module dependency/recipient semantics; C UI typed status; E negative installed-host proof. Record exact approving SHAs and reviewer ACKs. Until then status = **HOLD / NO-GO**.
