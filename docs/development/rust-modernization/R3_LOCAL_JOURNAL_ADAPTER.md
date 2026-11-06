# R3 local broker journal adapter

The `sofia-ui-broker::journal::DurableBroker` adapter persists only UI-broker
quota, manual-hide, generation and day-watermark state. It never opens canonical
Core storage, authenticates an owner, creates windows, or starts a Core. It is
not wired into a production service or native tray.

A trusted Platform process provisions a private directory, authenticates all
settings/proposal requests, and supplies its independently retained minimum
journal revision and fresh process generation at recovery. The directory and
its ancestor path must be protected against untrusted replacement. On Unix the
adapter also rejects group/other-accessible directories/files, symlinked roots
or snapshots, and hard-linked files. Advisory OS locks exclude cooperating
writers and are released by the OS when a process exits. These checks are not a
sandbox against another malicious program running as the same OS user.

Initialization is an explicit first-install operation, separate from recovery.
An existing or interrupted snapshot cannot be silently replaced by an empty
ledger. Recovery requires the committed snapshot, checks its version, platform
identity, minimum revision, prior generation, semantic record validity and
SHA-256 checksum, and bounds reads to 4 MiB plus one sentinel byte. Snapshots
contain at most 4,096 records. Missing, corrupt, truncated, oversized, wrong-
identity or stale state fails closed. The checksum detects accidental corruption;
it does not authenticate a hostile replacement. Rollback detection depends on
the independently protected minimum revision; storing that checkpoint beside an
attacker-replaceable journal would not provide rollback protection.

A transition clones the current policy state, writes a new private staging file,
flushes that file, atomically replaces the committed snapshot, and flushes the
directory before returning admission. No admitted appearance is exposed before
that durability sequence succeeds. A storage failure poisons the handle and
makes its state unavailable: an uncertain commit outcome requires recovery with
a new generation, rather than continued admissions. Recovery discards interrupted
staging bytes, uses the committed snapshot, converts reserved/visible slots to
uncertain via the existing `BrokerState::restore` policy, and flushes the fresh
generation before returning. A corrupt committed snapshot is not repaired from
an unverified staging file.

The new `fs2` dependency is exact-pinned to 0.4.3, uses safe Rust at this crate's
boundary, and supplies OS advisory locks. Its MIT/Apache-2.0 licenses fit the
existing dependency policy. serde/serde_json/sha2 reuse exact versions already
in the workspace lock. No secret or credential is stored in this journal.

## Limits and remaining acceptance

Filesystem durability is currently Unix-only. Windows initialization and
recovery return `UnsupportedPlatform`; no optimistic fallback reports a durable
admission. Windows directory-flush and replacement semantics require a separate
implementation and Windows tests before activation. The Python/Tk fallback is
unchanged.

This is not native R3 completion. The trusted Platform directory/ACL provisioning,
independent checkpoint owner, authenticated IPC wiring, native tray, DND/session
observers, OS window receipts, timezone-transition/boot evidence, archive policy
for the record bound, and production service lifecycle remain outstanding. The
adapter retains existing policy day semantics; it does not infer timezone or
change scheduling authority. Tests exercise disposable files and child-process
exit without destructors, not hardware power loss, production restart, or G8.
