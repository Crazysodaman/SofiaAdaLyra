# Artemis host: protected read-only Hyper-V snapshot bridge

## Observed host evidence (owner supervised, 2026-10-12)

- Exact reserved Sofia Hyper-V VM: `d4f9f4ae-caec-46f0-852b-8e65e9de8d2f`.
- Administrator `Get-CimInstance -Namespace root/virtualization/v2 -ClassName Msvm_ComputerSystem`
  lists Sofia with `EnabledState=2` and several other guests.
- `NT AUTHORITY\\LOCAL SERVICE` WMI query access itself succeeds, but BOTH
  `Name='<exact VM UUID>'` and `ElementName='Sofia'` produce **zero**
  VM records. Hyper-V's `Get-VM` and `Get-VMSwitch` explicitly refuse the
  restricted identity with insufficient permission.
- Therefore namespace access is **not** evidence of VM-object observation.
  The speculative direct WMI observer is kept as a testable diagnostic, but
  is NOT the production monitoring source.
- Previous LocalService journal reports `unavailable`; the journal remains
  independently hash-chained and verified. No VM or canonical DB mutation.

## Isolation and privilege separation

- The existing `SofiaArtemisController` Windows SCM service stays under
  `NT AUTHORITY\\LocalService`; do NOT join it to `Hyper-V Administrators`
  or `Administrators`. It never invokes a privileged Hyper-V command.
- An operator-installed Windows Task Scheduler task runs as
  `NT AUTHORITY\\SYSTEM` on Artemis only. Its single fixed action is
  `python -m sofia.ops.artemis_host_snapshot export --config <pinned_config>`.
  Producer checks its SYSTEM identity and exact Artemis hostname, reads the
  pinned Sofia VM using the existing Get-VM Hyper-V inventory path and checks
  exact UUID/name. It writes ONLY a bounded, atomic host observation file.
  It contains no VM lifecycle, writer, fence, DB or network-control operations.
- Snapshot: `C:\\ProgramData\\SofiaAdaLyra\\ArtemisController\\trusted\\sofia-host-vm-observation.json`.
  The `trusted` directory MUST be independently created by an elevated
  operator with inherited ACLs disabled. Only Administrators and SYSTEM
  may write; LocalService gets **Read+Execute only**. Never store this
  authority-bearing snapshot in the LocalService-writable `audit` folder.
- On the consumer, snapshot has exact schema/source/host/name/VM GUID and
  a 180-second maximum age with 15-second future skew. Missing, stale,
  malformed, wrong VM and redirected files fail closed; journal receipt
  remains `unavailable`.
- On valid snapshot, journal marks `requires_review` with exact VM ID,
  read-only observed power state and blockers `privileged_snapshot_only`
  and `live_guest_os_and_writer_state_unverified`. It never claims a
  guest OS attestation, live writer fencing or migration authorization.
- A SYSTEM scheduled task is privileged despite executing fixed read-only
  source. It must be installed explicitly by a host administrator, with
  Task Scheduler task action/ACL verification, code revision pinning,
  local ACL verification, and a rollback/disable procedure.

## Acceptance

1. Source and targeted tests are authored; execution proof remains separate.
2. Operator stages pinned package, provisions protected `trusted`, and
   registers one exact SYSTEM task on Artemis. Never auto-install elsewhere.
3. Task is manually triggered; inspect scheduler LastTaskResult,
   snapshot GUID/age and filesystem ACL. Verify it did not mutate VM state.
4. Start or restart LocalService `SofiaArtemisController`.
5. Verify a **new** `requires_review` receipt with the exact Sofia VM GUID,
   nonempty host state and monotonic hash chain.
6. Keep all canonical DB migration/fencing gates disabled until separately
   approved and verified. Production readiness is not implied by this
   monitoring-only observation.
