# Phase 03 / V18: canonical state must not reappear after loss

**Coding date:** 2026-10-11. **Branch:** main. **Testing:** deferred at the owner's request.

## Independently located production failure

The existing `LifeStore` and `LifelongThreadStore` validated the SQLite state path in their constructors, but opened every later connection with default `sqlite3.connect(path)`. If a removable/moved canonical `sofia.db` vanished after construction, a background LIFE tick or a Main history request could create an empty second SQLite file. `GoalEvidenceLedger` also opened its evidence table through implicit-create connections. `GoalEvidenceIndex` already used read-only SQLite URI mode but did not recheck for redirected symlink paths on every lookup.

## Committed source changes

- `d4576b9`: `src/sofia/life/store.py`, no-create `mode=rw` SQLite reads/writes and symlink/missing file checks, including later ticks.
- `31f29e7`: `src/sofia/conversation/lifelong.py`, same no-create guard for Main and project thread projections.
- `a30e27f`: `src/sofia/goals/evidence.py`, require existing canonical DB for GOALS evidence writes; revalidate the evidence reader path before source lookup.
- `9639985` / `c45289a`: `test/test_life_canonical_state_loss.py`, new missing-on-construct, missing-after-start and symlink-replacement regression cases. Test fixture file handles are explicitly closed before Windows deletion tests.

These are actual production source changes, not new scheduler, model, identity, authority or storage ledger implementations. The existing canonical tables are reused. A missing canonical DB now fails rather than being recreated by these three owners.

## Scope and remaining work

- **V18 CA-6804, CA-5201 and CA-6101: partial source hardening only.** Other SQLite owners may still create a file implicitly; run a project-wide connection audit before claiming universal state protection.
- First-install bootstrap remains separate from a *post-start* state-loss event. No writer machine is selected. Do not infer that Venus or Artemis is authoritative, do not move a live database, and do not promote read-only copies without authenticated fencing.
- This blocks accidental resurrection at selected store boundaries, **not** a complete cross-host failover protocol. An existing but wrong regular SQLite file also requires lineage, constitutional identity and writer epoch verification.
- No tests, Python import checks, CI, Windows filesystem deletion, Android build, Fleet host action or live production cutover were performed. Only source is committed; real acceptance is pending.

## Deferred acceptance commands

Run existing `pkg_life`, `pkg_goals`, `pkg_conversation` and state/recovery suites plus `pytest -q test/test_life_canonical_state_loss.py` at the final exact-SHA verification campaign. Use a Windows host to prove no surviving file handles prevent unlink, and verify disappearance/symlink attempts never create a new canonical DB.


## Additional SAFE and Presence boundary inspection

- `b77bac1` blocks implicit SQLite creation in production Presence world-sensor and outreach stores after canonical-state loss.
- `40f8a10` makes operator stop read/write fail when the canonical file vanishes and refuses a stop write that updated zero rows. `test/test_safe_operator_stop_state_loss.py` (`eac251e`) records missing-state and row-loss regressions.
- `155c761` makes the SAFE standing-permission owner require a preexisting non-symlink canonical file, rather than letting its constructor silently create permission authority. Subsequent grant reads/writes use `mode=rw`. `test/test_safe_permission_state_loss.py` (`4b69f10`) records loss and explicit seed cases.
- The existing `AuditChain` and other persistent owners still need a per-connection no-create audit, rather than accepting their current constructor-level checks as exhaustive. The `ConversationStore` first-boot/reopen boundary and `DurableWorkStore` RUN job store likewise require additional targeted source work.
- Some older test fixtures constructed `PermissionStore` and `OperatorStopStore` using nonexistent state paths, relying on the former implicit bootstrap. Those fixtures must be reconciled with the canonical `SQLiteStatePlane` bootstrap during the deferred test-coding/verification campaign; no passing assertion is claimed.
- **No host, permission, service, database, or Fleet configuration was changed**, and none of the newly authored tests was executed.
