# Per-Core Private Database

## Purpose

Project Aegis gives each approved Core an independent private persistence
boundary. The implementation lives in
`src/sofia/core/persistence/core_database.py`.

A Core's private database contains only that Core's:

- private memories and memory provenance
- evidence-derived preferences, beliefs and interests
- reflection batches, checkpoints, outputs and audit records
- identity evolution and lifecycle continuity records

Shared Platform systems remain outside this database. Platform chat,
inventory, governance, authentication and other cross-Core services do not use
a Core's private SQLite file.

## Path contract

The path is keyed only by the Core's immutable UUID:

```text
{root}/{core_uuid}/core.db
{root}/{core_uuid}/continuity.json
```

Display names, nicknames, slugs and Core numbers never select a database path.
Renaming presentation metadata therefore cannot move or rename the database.
An externally supplied nonzero UUID is required; this module never allocates a
Core UUID.

The approved Core numbers are `{1, 2, 3, 6, 7}`. Numbers `4` and `5` are
prohibited, and every other number is rejected. The number is stored as part
of the database ownership binding so that a database cannot be silently
reused for a different Core number with the same UUID.

## Installation and opening

`CorePrivateDatabase.create(...)` is the only creation path. Importing the
module performs no filesystem work and creates no database.

Creation is an explicit installation or activation operation. It:

1. validates the absolute root, approved Core number and nonzero UUID
2. rejects paths inside a Git worktree and paths naming `sofia.db`
3. rejects symlinks and junctions in every path component
4. creates the root and per-Core directory as owner-private paths
5. bootstraps one canonical SQLite file using the existing canonical
   bootstrap and guard primitives
6. writes a single ownership-binding row containing the schema, Core UUID and
   Core number

An existing database is verified, never reinitialized. A pre-existing SQLite
file without an ownership binding fails closed. A database copied into another
Core's UUID directory fails closed because its binding names a different UUID.
Reinstall with a different UUID cannot adopt another Core's database.

`CorePrivateDatabase.open(...)` requires an existing root, directory and
database. It never creates or repairs state. Opening verifies owner-private
permissions, the canonical application id, SQLite integrity, the stored Core
UUID and, when requested, the Core number.

All permission, redirection and ownership failures are fail-closed. No bytes of
private content are included in exception strings, representations or logs.

## Bound services

`CorePrivateDatabase` binds existing owner-scoped services to the same database
and UUID:

- `MulticoreMemoryStore`
- `MulticoreLearningService`
- `MulticoreReflectionService`
- `CoreContinuityStore`

This is composition, not a second memory engine. Existing service APIs and
tables are preserved. Each service remains bound to its single Core UUID, and
SQL ownership filters still run before retrieval or disclosure.

`CorePrivateDatabaseCatalog` provides the same explicit create/open operations
for an in-memory collection of per-Core databases and closes all of them when
it is closed. Its keys are Core UUIDs.

## Backup and rollback

Backups are non-destructive and require an explicit destination. A backup is a
new owner-private directory containing:

```text
{backup}/core.db
{backup}/continuity.json
{backup}/manifest.json
```

The SQLite copy is created through SQLite's consistent backup operation and
then checked with `PRAGMA integrity_check`. The manifest binds the backup to
one Core UUID and Core number and contains SHA-256 digests of both payload
files. The continuity record is also loaded and checked against the expected
Core UUID.

The destination must not already exist. An existing backup is never
overwritten silently. `backup(..., dry_run=True)` reports whether a destination
is available without writing anything.

`verify_backup(...)` verifies the manifest, digests, SQLite integrity, Core
ownership binding and continuity identity without changing the backup or any
live database.

`rollback(...)` restores a verified backup into a new, explicit root. It refuses
another Core's backup, refuses an existing destination and never modifies the
live database. Rollback is a staging operation: activation of the restored
database requires a separate authority decision. There is no live migration
path in this module.

## Boundaries and non-goals

- No module-level database creation.
- No display-name, slug or Core-number path keys.
- No shared Platform chat, inventory, governance or authentication tables.
- No creation, migration, deletion or renaming of the canonical
  `sofia.db`.
- No silent adoption of unbound or foreign SQLite files.
- No live backup overwrite and no in-place rollback.
- No claim that a database, Core or service is installed or active merely
  because creation or verification succeeded.
