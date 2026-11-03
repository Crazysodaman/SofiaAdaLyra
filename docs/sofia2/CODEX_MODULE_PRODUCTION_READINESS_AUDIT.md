# Module production-readiness audit

**Audit date:** 2026-11-03  
**Branch:** `codex/module-documents`  
**Source commit:** `f22c8ecf5d76fc22d49c80fb4d30a2b151832d9e`  
**Source tree:** `dae8ae96443daf95bc3024ca73dd89b460c54a1b`

## Decision

The 55 catalog entries are **not production ready**. The module source is in a
reviewable release-preparation state, but this checkout contains no real signed
module package, admitted lifecycle record, trusted readiness-evidence record,
reviewed adapter factory, or installed-host acceptance result. The appropriate
current classification remains **PARTIAL / ALPHA** for every entry.

This is an evidence decision, not a source-quality failure. Local testing proves
the fail-closed packaging and lifecycle mechanisms and the bounded module
handlers. It cannot supply owner signing authority, independent review, matching
GitHub CI, or host acceptance.

## Binding readiness rule

`src/sofia/platform/modules/readiness.py` is the authoritative evaluator. It
binds evidence to the module ID, exact package digest, exact source SHA, trusted
issuer, passing result and revocation state. A module cannot issue evidence for
itself. The lifecycle manifest identity must match the evaluated artifact.

Release-candidate status requires these six evidence classes for the same
identity:

1. test;
2. security audit;
3. independent review;
4. compatibility;
5. interoperability; and
6. rollback.

Production-ready status additionally requires:

7. matching CI; and
8. host acceptance.

Readiness status does not authorize activation. Platform lifecycle admission,
SAFE authority and the canonical writer remain separate controls.

## Evidence inspected

| Area | Observed evidence | Result |
|---|---|---|
| Catalog/accounting | 55 unique entries in `CODEX_MODULE_IMPLEMENTATION_REPORT.md`; 47 are optional source modules and 8 are release companions/attached components | Complete inventory; no readiness promotion |
| Optional source preflight | All 47 optional identities have bounded source implementations and release-draft coverage | Source-preflight capable |
| Release packaging | `optional_release_packages.py` creates unsigned review drafts and delegates real Ed25519 verification to Platform | Fail-closed, but no approved policy/signature/package exists |
| Owner release policy | No `OwnerReviewedReleasePolicy` instance or reviewed policy artifact exists in the repository | Blocked on owner/release authority |
| Signing identity | No approved deployment public key, signature, or signed module bundle was found | Blocked on approved signing workflow |
| Runtime factory/health | Draft manifests explicitly carry no live health probe and flag reviewed factory/live health as unverified | Blocked before lifecycle admission |
| Lifecycle/readiness state | The checkout's `sofia.db` has none of the Platform module lifecycle or readiness tables | Zero admitted or evidence-backed modules observed |
| GitHub evidence | `gh auth status` reports the active `GH_TOKEN` is invalid | Current-SHA remote CI cannot be independently reconciled here |
| Physical host | No G8 host operation was performed | Correctly deferred |

Absence from this development database does not prove another deployment has no
records. It does prove that this checkout supplies no records that can support a
production-readiness claim.

## Verification performed

The production-readiness audit suite passed:

```text
78 passed in 109.52s
```

It covered optional-module source preflight, unsigned release preparation,
native Platform package verification, readiness evidence, module lifecycle and
the isolated process worker. The completed implementation batches also retain:

- 598 passing optional-module/package tests;
- 493 passing release-companion tests; and
- 607 passing attached-component tests.

These are local source-tree results. They are not substitutes for installed
artifact testing, matching CI, independent review or host acceptance.

## Per-entry disposition

All 55 entries have the same binding release blockers, so duplicating an
identical assertion per row would add no evidence. The complete per-entry source,
capability, test group and G8 dependency are recorded in
`CODEX_MODULE_IMPLEMENTATION_REPORT.md`.

| Population | Count | Current maximum status | Missing binding evidence |
|---|---:|---|---|
| Optional modules | 47 | PARTIAL / ALPHA | Reviewed package identity/policy, approved signature, reviewed factory and health contract, lifecycle admission, all eight readiness classes |
| Release companions | 5 | PARTIAL / ALPHA | Release package definition, approved signature, installed lifecycle/recovery, all eight readiness classes |
| Attached components | 3 | PARTIAL / ALPHA | Release package definition, approved signature, installed lifecycle/recovery, all eight readiness classes |
| **Total** | **55** | **0 production ready** | **No entry has a complete exact-identity evidence chain** |

## Path to production readiness

The next authorized release batch must preserve this order and exact identity:

1. An owner/release authority approves the 47 catalog-to-package mappings,
   capability schemas, trust reference, host/OS scope, isolation and data classes.
2. The approved signing workflow signs immutable package manifests. The trusted
   public identity must be provisioned through Platform; test-generated keys are
   ineligible.
3. A reviewer supplies digest-bound adapter factories and observable health
   probes without adding import side effects or a second lifecycle owner.
4. Platform verifies, installs and stages each package in a disposable host, then
   tests start, configure, apply, restart, update, rollback, quarantine, STOP and
   removal behavior.
5. Trusted issuers record the six release-candidate evidence classes for the
   exact module ID, package digest and source SHA.
6. Current-SHA CI is independently reconciled and recorded as matching-CI
   evidence after GitHub authentication is restored.
7. Applicable host acceptance is recorded only after the deferred G8 work is
   separately authorized and succeeds.
8. Platform evaluates readiness; an owner separately decides activation.

## External blockers

- Owner approval of package identity, policy, trust roots and release signing.
- Approved signing identity/workflow and immutable signed artifacts.
- Independent security and release review from trusted issuers.
- Valid GitHub API authentication for current-SHA CI reconciliation.
- G8 installed-artifact and physical/provider acceptance where applicable.

No production key, trust root, canonical writer, protected state or physical host
was changed during this audit.
