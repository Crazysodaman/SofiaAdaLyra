# Sofía 2.0 optional modules: release packaging implementation checkpoint

**Repository:** `Crazysodaman/SofiaAdaLyra`, `main`. **Baseline inspected:** `208f6b82843ff817ce2fba19329d8f506aaef760` on 2026-10-25. This checkpoint is **module-owned release-building code**, not a certification, package installation, owner signing approval or Host/Gate result.

## What is production code now

- `src/sofia/modules/optional_release_packages.py` creates complete Platform-format **unsigned** manifest signing requests for the 47 approved optional module catalog IDs. It reads actual source, derives SHA-256 artifact digests for the module source and `__init__.py`, pins the declared capability and operation profile, and constructs maintenance, permission-ceiling, resource, OS/arch, isolation, placement, migration and rollback contracts.
- An explicit `OwnerReviewedReleasePolicy` binds approved Platform package ID, per-capability parameter schema, publisher, trust root reference, Platform API minimum, target host classes, data classification, isolation and an external human review reference. A proposed normalized package ID is **not** auto-accepted as a reviewed mapping.
- `prepare_release_batch` fails **all 47** if any source, reviewed mapping, parameter schema, resource declaration, identity or digest is missing. Its output is a collection of non-executable drafts, not runnable module packages.
- `materialize_unsigned_draft` and `materialize_unsigned_batch` write fresh, bounded, **unsigned review-only** directories without overwriting an existing directory. File contents must continue matching the original source digest. Symlinked source or redirected parent paths are denied.
- `verify_operator_signature` requires an externally supplied signature and trusted public key and delegates **all actual manifest parsing and Ed25519 verification** to the Platform's existing `parse_signed_manifest` and `verify_module_package`. This tooling never creates a key, accepts a key from model output as authority, signs automatically, registers factories, grants capabilities, installs, or changes canonical state.
- `src/sofia/modules/optional_release_cli.py` offers one explicit operator-only CLI for preparing 47 unsigned drafts **after an approved review policy exists**.

## Run after operator policy review

A release engineer first creates a **reviewed, nonsecret** JSON policy with precisely these keys:

`package_ids`, `capability_schema_refs`, `publisher`, `trust_ref`, `platform_api_minimum`, `supported_os_arch`, `isolation_profile`, `allowed_host_classes`, `data_classes`, `review_receipt`.

`package_ids` must map all 47 catalog IDs to explicitly reviewed, canonical lowercase Platform package identities. `capability_schema_refs` must include the actual per-capability request contract names. `data_classes` must be distinct per module and must not inherit private grants from another domain. A policy file, `review_receipt` string, or unsigned output **cannot authenticate** the owner; operator/SAFE checks occur separately in Platform.

```powershell
python -m pytest -q test/test_optional_release_packages.py
python -m sofia.modules.optional_release_cli `
  --repo-root . `
  --policy .\reviewed-release-policy.json `
  --source-sha256 <externally-verified-SHA256-snapshot> `
  --output .\unsigned-module-review-candidates
```

The `--source-sha256` value is **caller supplied** and must be verified independently by the release orchestrator; the CLI does not claim it inspected Git identity. `review_receipt` is a reference, not proof of owner authorization. Review candidates must **not** be placed in the canonical Platform store as installed modules by this CLI.

## Evidence and limits

- New local test suite: **20 passed, 1 native Platform integration test skipped** in a partial source workspace. The skipped test requires the complete Platform `package.py`, real Ed25519 verification and actual `sofia.platform.resources` imports. It is present in the new test suite and must run in a full checkout before a release claim.
- Combined isolated regression: **633 passed, 1 skipped**. This uses lightweight historical Platform/SDK stand-ins for the older optional source handlers, and must not be represented as full-repository CI.
- 45 of 47 modules had full source present in the isolated release workspace; the prior two IT modules were source-inspected through the GitHub connector but unavailable in that workspace. **In a full repo checkout the batch builder requires all 47** and fails closed if even one is unavailable.
- This tool creates structurally complete **unsigned** drafts only. It has not produced 47 owner-signed, staged, installable, verified, or operational module packages.

## Remaining real release gates, per exact digest

1. **Owner decisions:** approve the catalog-to-Platform package IDs, trust roots, exact parameter schemas, target OS/arch, host classes, isolation, purpose-scoped data classes and release signing authorization.
2. **Package verifier:** run native real-Platform parser, Ed25519 signature and tamper tests, pinned source revision, and prove bundle paths remain safe. Never use the test-only random key as a deployment trust root.
3. **Reviewed factory:** implement digest-bound factories and health probes via `sofia.platform.modules.adapters`; ensure factory import/inspection is inert, factory/source identity matches signed manifest, module crash does not crash Core, no source directory scanning or unreviewed dynamic import. Coordinate with Codex before touching `Platform/application/bootstrap.py`.
4. **Lifecycle/permission:** test `ModuleOperationCoordinator`, compatibility/resources, SAFE/RUN authority/STOP, signed installation, staging, start failure, quarantine, disable and rollback on an approved isolated host.
5. **RELEASE CANDIDATE:** for the same exact package identity and source revision, gather passing tests, security audit, independent review, compatibility, interoperability and rollback evidence in Platform's evidence store.
6. **PRODUCTION READY:** add matching CI and real applicable host acceptance. Use the authoritative `evaluate_module_readiness`; never promote from module self-report, this Markdown or an unsigned release request.

**Current readiness verdict:** optional module source implementations **47**, newly added reproducible release-building machinery **1**, fully native-signed/installed releases **0 verified**, BETA/RELEASE CANDIDATE/PRODUCTION READY **0 verified**. Do not conflate artifact preparation with runtime integration.
