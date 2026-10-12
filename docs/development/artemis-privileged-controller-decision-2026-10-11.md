# Artemis independent controller: owner-selected architecture and delivery

**Decision:** Owner explicitly selected **Artemis Windows Hyper-V HOST** as
Sofía's independent migration/update/recovery controller. The permanent
canonical runtime and `sofia.db` will run in **Sofia Debian VM** only after
the supervised fencing and state-promotion gates. **Venus remains the sole
writer today.** Hephaestus remains an isolated lab VM.

## Trust boundaries

- Artemis controller is not Sofía's LLM, not the Sofia VM's `sofia-runtime`
  Linux user, not the Venus desktop tray, and not the existing pinned-mTLS
  Fleet agent. It has separate Windows SCM identity and a host-local receipt
  journal. **Do not install it as LocalSystem or an administrator.**
- The initial controller service **only observes** the exact named Sofia VM,
  checks a separately supplied Hyper-V VM GUID and the exact Artemis hostname,
  and journals bounded read-only review/health observations. It cannot
  stop/start VMs, change SCM configuration, deploy updates, create or recover
  `sofia.db`, start an existing writer, issue writer epochs or activate a
  pending pointer. A healthy Hyper-V result is *not* guest attestation.
- The controller's hash-chained receipts are local, tamper-evident audit
  records; they are NOT externally witnessed immutable fencing certificates.
  They never claim a Venus writer fence, trusted guest OS, or migration
  authorization. A malicious full host administrator could rewrite the chain;
  independent external witness and protected backups remain mandatory.
- The privileged **fencing and release deployment** capability is separate
  future code/authorization, not quietly enabled by the monitoring service.
  It must have explicit exact-machine/delegated permissions, verified owner
  approval, independent Venus STOP + restart suppression + watchdog exclusion,
  monotonic old/new writer epoch, durable evidence, anti-replay and fail-closed
  recovery. After a successful new writer commit, don't fail back to an old
  Venus copy, and never roll back data to repair an application upgrade.
- A small dedicated service identity is required. Current administrator
  supports explicitly selected `NT AUTHORITY\\LocalService` or a provisioned
  domain gMSA, installed in **manual-start mode**. LocalService typically has
  no Hyper-V read permission by default; grant only the independently
  reviewed read-only WMI/Hyper-V inspection rights needed for inventory.
  Do **not** solve an access failure by putting it into Hyper-V Administrators.
  No password is accepted in arguments or saved in the repository.

## Production code wired on main

- `src/sofia/ops/artemis_controller.py`: Artemis-only config loader with
  fixed host/VM, required reviewed UUID, read-only HyperVAdapter inventory,
  bounded status, hash-chained append-only JSONL journal, crash/corruption
  rejection, locking and independent process loop. The journal lives OUTSIDE
  canonical sqlite and requires operator-provisioned private local storage.
- `src/sofia/ops/artemis_controller_service.py`: distinct Windows SCM service
  `SofiaArtemisController`, no network listener, clean stop event, and
  fail-closed missing/invalid config.
- `src/sofia/ops/artemis_controller_admin.py`: explicit named restricted
  service account, manual install/start, registration/status verification and
  no SCM automatic restart or administrative override.
- `test/test_ops_artemis_controller.py`: typed service identity, host refusal,
  verified VM GUID, missing/deceptive Hyper-V evidence, journal tamper/crash,
  operation scope and account denial regression cases. CI acceptance is
  separate from authorship of these tests.

## Operator preflight only (NO installation yet)

On **Artemis PowerShell as an explicitly authorized operator**, inspect:

```powershell
Get-ComputerInfo | Select-Object CsName, WindowsProductName
Get-VM -Name Sofia | Select-Object Name, Id, State, Generation, ProcessorCount
Get-VMNetworkAdapter -VMName Sofia |
    Select-Object VMName, SwitchName, MacAddress
```

Check the exact observed UUID against the intended Sofia VM on Artemis;
never copy a made-up UUID from tests or docs. The Sofia guest LAN IP is
reported by owner as `192.168.1.68`; this does **not** establish the host
Hyper-V VM GUID. The earlier `192.168.1.234` DHCP address is retired.

When the service/ACL security review is complete, an administrator must
create private **local** ProgramData controller/config/audit directories
and an exact six-field JSON configuration with independently observed
`expected_vm_id`, fixed `expected_host: "Artemis"`, `vm_name: "Sofia"`,
`schema: 1`, `poll_seconds: 60`, and absolute private
`audit_directory`. `controller.once` performs one read-only inspection;
service installation is a separately supervised action using
`python -m sofia.ops.artemis_controller_admin install --config <approved-absolute-path>
--service-account "NT AUTHORITY\\LocalService"` once restricted read access
is verified. Do not run installation from an unverified service account.

## Remaining migration and update gates

1. Exact Hyper-V VM UUID and Artemis host identity observed from **live host**
   evidence; re-confirm protected local audit/config directory ACLs.
2. Independent, pinned-mTLS enrollment of Sofia VM and Venus inference,
   exact grants and source/guest epoch identity.
3. Dedicated independently privileged **Venus writer-fencing mechanism**
   including Windows runtime service AND watchdog recovery suppression.
   Existing service STOP and signed pointer checks are insufficient.
4. Trusted encrypted full-state and external deletion-journal backup/restore;
   operator approval bound to verified source/destination and fresh epoch;
   atomic pending-pointer promotion with uncertain failure reconciliation.
5. Real Windows chat/tray remote clients bound to the canonical Debian
   application API. Current local UI still reads a local canonical state;
   its current code must not be used after writer migration.
6. Separately signed **Debian Python 3.13** release build, staged deployment,
   independent updater broker, coherent idle draining and accepted rollback;
   current GitHub watcher detects updates but deliberately does NOT activate.
7. Exact-SHA Windows/Linux CI and live supervised cross-host acceptance
   including reconnect, no double writer, crash/restore, game mode and fail
   closed stale-writer prevention.

**Absolutely no live Artemis host, Venus machine, Sofia VM, certificate,
Windows service, network rule or canonical `sofia.db` has been changed by
these commits.** The operator's earlier manual Debian preparation remains
as reported and is not cryptographically verified here.
