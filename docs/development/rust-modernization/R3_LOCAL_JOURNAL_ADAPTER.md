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

Relative directory arguments are bound to an absolute path at initialization or
recovery. A later process working-directory change cannot redirect journal writes.

A transition clones the current policy state, writes a new private staging file,
flushes that file and atomically replaces the committed snapshot. Unix then
flushes the parent directory. Windows uses native
`MoveFileExW(REPLACE_EXISTING | WRITE_THROUGH)` on that same protected directory,
without a cross-volume copy/delete fallback. No admitted appearance is exposed before
that durability sequence succeeds. A storage failure poisons the handle and
makes its state unavailable: an uncertain commit outcome requires recovery with
a new generation, rather than continued admissions. Recovery discards interrupted
staging bytes, uses the committed snapshot, converts reserved/visible slots to
uncertain via the existing `BrokerState::restore` policy, and flushes the fresh
generation before returning. A corrupt committed snapshot is not repaired from
an unverified staging file.

Windows requires a local fixed drive and an owner-private DACL. It reads the
current process token's user/default-owner SIDs and the opened file's security
descriptor; caller-supplied account display names are never authentication.
Only ordinary allow ACEs for that user, SYSTEM, Administrators or OWNER RIGHTS
are accepted, with explicit owner read/write data rights. NULL/empty DACLs,
foreign owners, broad readers, denies and conditional/object ACEs fail closed.
The adapter does not repair existing permissions or provision a directory.
These OS storage checks do not authenticate an Aegis owner or authorize a UI
setting/proposal.

Windows retains directory handles for every ancestor without delete sharing,
rejects reparse points and pins the lexical path while the writer is active.
Files are opened without delete/write sharing, checked through their handles,
and rejected when hard-linked or redirected. UNC/device paths, parent escapes,
remote/mapped/non-fixed drives and unsupported security descriptors are denied.
Platform provisioning must supply a suitable local directory beforehand.

Exact-pinned dependencies supply OS locking (`fs2` 0.4.3), safe token operations
(`winsafe` 0.0.29), handle metadata (`winapi-util` 0.1.11), descriptors
(`windows-permissions` 0.2.4) and write-through replacement (`atomicwrites` 0.4.4).
The latter four are Windows-only. Workspace `unsafe_code = "forbid"` remains
unchanged; no project-local raw FFI or unsafe blocks are added. Existing
serde/serde_json/sha2 formats are reused. No secret or credential is stored.

## Limits and remaining acceptance

Other operating systems without the Unix/Windows durability contract remain
unsupported. Windows must pass native runtime, security, restart and child-exit
tests; cross-compilation alone is not execution evidence. The Python/Tk fallback
is unchanged.

This is not native R3 completion. The trusted Platform directory/ACL provisioning,
independent checkpoint owner, authenticated IPC wiring, native tray, DND/session
observers, OS window receipts, timezone-transition/boot evidence, archive policy
for the record bound, and production service lifecycle remain outstanding. The
adapter retains existing policy day semantics; it does not infer timezone or
change scheduling authority. Tests exercise disposable files and child-process
exit without destructors, not hardware power loss, production restart, or G8.
