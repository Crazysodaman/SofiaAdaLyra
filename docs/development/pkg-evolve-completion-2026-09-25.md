# PKG-EVOLVE completion candidate

**Revision:** 2026-09-25. **Branch:** `feature/pkg-evolve-completion`. **Status:** focused disposable/offline acceptance passed on the current Windows checkout. No production identity, Constitution, preference, or configuration state was changed.

## Two evolution lanes

### Reviewed ordinary revisions

`sofia.evolve.revision` provides storage-neutral reviewed evolution for non-protected **preference** and **configuration** values. A proposal is bound to exact before/after digests, evidence, reason, expiry, and rollback plan. An independent verifier must approve the exact proposal/action. A trusted adapter performs compare-and-swap apply/rollback and returns an opaque rollback token. EVOLVE records revision history without assuming where future settings are stored.

### Protected identity / Constitution amendments

`sofia.evolve.amendment`, `approval`, and `executor` provide an intentionally stricter path. Protected proposals receive a stable fingerprint. Apply and rollback each require an independently verified approval bound to the exact proposal and action.

The protected executor:
- operates only on explicitly supplied protected paths;
- verifies current source digest before change;
- validates proposed identity/Constitution content;
- creates pre-change backups;
- uses atomic replacement writes;
- updates and independently verifies the Constitution trusted hash;
- verifies persisted identity or Constitution after write;
- records a durable audit entry;
- refuses rollback if protected state drifted after apply;
- requires separate rollback approval.

There is **no self-approval implementation**. A model response, memory, Git permission, proposal object, or matching SHA string is not authorization.

## Focused offline acceptance

```powershell
python -m pytest -q test/test_evolve_amendment.py test/test_evolve_executor.py test/test_evolve_revision.py
```

Then run protected-state regressions:

```powershell
python -m pytest -q test/test_constitution.py test/test_constitution_integrity.py test/test_constitution_store.py test/test_identity.py
```

These tests must use disposable state/files. No real protected amendment is required for repository acceptance.

## Windows acceptance evidence

Executed on Sparks's Windows checkout on 2026-09-25:

- `python -m pytest -q test/test_evolve_amendment.py test/test_evolve_executor.py test/test_evolve_revision.py` → **36 passed in 4.32s**.
- `python -m pytest -q test/test_constitution.py test/test_constitution_integrity.py test/test_constitution_store.py test/test_identity.py` → **26 passed in 4.12s**.

Current EVOLVE offline evidence total: **62 passing tests across the focused and protected-state regression gates**. Production protected state was not modified.
