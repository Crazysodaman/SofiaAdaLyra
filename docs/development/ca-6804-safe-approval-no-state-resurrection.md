# CA-6804: SAFE approval authority cannot resurrect a missing canonical DB

The central production configuration resolver already reports a chosen
canonical database path without creating it. Nevertheless,
`ExecutionApprovalVerifier` previously created parent directories and
used ordinary `sqlite3.connect(path)`, which opens a new empty SQLite
database if the configured one is missing. Repeated approval polling after
a volume was unmounted or a writer moved could thereby create an
alternate audit and approval store, contrary to CA-6804's no-secondary-
identity recovery requirement.

The SAFE execution approval owner now demands a preexisting regular
non-symlink canonical database before constructing `AuditChain` or its
own tables. Every subsequent approval database connection uses explicit
SQLite `mode=rw`, which fails instead of creating a new `sofia.db`
if the file vanishes while the host is running. No parent directories,
empty approval stores or new audit chains are manufactured. The existing
owner audit chain and exact one-use approval semantics remain in place.

This is scoped to the **execution approval** path; many other legitimate
bootstrap/storage components still require a coordinated first-install
and fenced-recovery architecture. Do NOT infer that the entire
`create_production_configuration` first-bootstrap contract has been
made safe or that the canonical host has been chosen. Complete CA-6804
requires a full production-state factory cutover/restore audit,
operator-visible candidate choices, and active external-action gating
when the canonical path is lost.

Regression source cases were authored for missing path, missing parent,
and disappearance after approval was registered. They were NOT run.
No host DB was moved or created.
