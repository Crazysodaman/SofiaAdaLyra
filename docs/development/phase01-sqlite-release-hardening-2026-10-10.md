# Production SQLite / release collection ownership audit (October 10, 2026)

Scope: Source-based repair against GitHub `main` (parent `004fde66`), one branch only. **No test execution, CI dispatch or live host changes in this commit.**

## Complete concrete code repairs

- `SQLiteAccess.connect`: PRAGMA and row-factory setup failures close the opened SQLite handle and release the bounded-reader token exactly once. Previously the failure handler released the token but not the Windows file handle, risking locked `sofia.db`.
- `_seed_sqlite`: creates a consistent backup using SQLite backup API in a private file, integrity-checks and checkpoints it, closes source/destination connections, then publishes via an atomic non-overwriting same-filesystem hard link. Failed or competing publishes clean staging files and never replace an active replica. Existing replicas are left intact and subsequently checked by the existing SQLiteStatePlane.
- `pyproject.toml`: test discovery is constrained to owned `test/` directory. Production provider modules and nested archived checkouts cannot be collected as duplicate tests.
- Regression tests are authored for consistent WAL backup, idempotence, corrupt sources, conflicting publication and SQLite initialization cleanup.

## Production acceptance still separately required

These are complete implementations of the specified repair paths, not a claim of full 17-phase completion or passing Windows tests. Test the exact new SHA on Windows/Linux and verify failures from prior `pkg_verify`, `pkg_body` and Release Candidate workflows independently. The new changes do not promote a new writer, change Fleet grants, move canonical state, install models or bypass release approval.
