# PKG-SAFE: private-reflection disclosure preflight

**Status:** offline code/tests on a draft package branch, not integrated, merged or deployed. This helper does **not** authenticate a person, verify a grant issuer, encrypt data, authorize publication, or read/decrypt private content. Boolean `trusted_actor`/`trusted_grant_origin` and `GrantRecord` fields are caller assertions, not cryptographic proof. The actual trusted UI/server boundary must independently establish origin and re-check permissions.

## Implemented

Typed source-linked `Artifact` with sensitivity class, immutable version, exact owner and evidence references; exact version/recipient/owner/time-bounded `GrantRecord`; fail-closed `evaluate` returning only denied, needs trusted grant or eligible for subsequent trusted enforcement. Private reflection is not automatically publishable even with a grant record; deliberate reviewed derivation/reclassification is a separate MEM/ACT process. Cross-user actor mismatch is denied. No general multi-user support is enabled.

**Test:** `PYTHONPATH=src python -m pytest -q test/test_safe_disclosure.py`. Equivalent isolated Linux Python 3.13.5 / pytest 9.0.2 source/tests passed **35 focused tests**. GitHub branch checkout, Windows, full suite, real auth and public-client privacy testing: **not run**.

## Review when SAFE/MEM/UI/Discord are integrated

- Bind authenticated Sparks Discord ID, local principal, session and viewer through a real trusted adapter. Do not accept text, avatar props, forged UI flags or model claims as actor proof. Store grants with independently authenticated issuer, exact artifact hash/version, revocation and expiration; a `trusted_grant_origin=True` flag from untrusted JSON is insufficient.
- Reconcile UI workbench's in-memory owner-only model with actual durable MEM scopes and private reflections. Review explicitly authorized promotion from private candidate to shared artifact, source/correction/deletion propagation, image thumbnails, notifications, exports, logs and screenshots. Do not reveal another actor's private metadata if multiuser is enabled later.
- Run real negative tests for spoofing, old versions, revoke-after-queue, restart/reconnect and rejected action no-leak. Verify backup, retention, key handling and independent stop at the host; this module is not a security boundary.

No real network, production data, identity/Constitution edits, merge or deployment. Preserve CORE → INTERACT → MEM → Sparks-only Discord → verified RUN → separately permissioned search.
