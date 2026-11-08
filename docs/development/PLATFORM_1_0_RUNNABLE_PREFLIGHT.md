# Platform 1.0 | Executable acceptance preflight (2026-11-08)

**Authority:** [PLATFORM_1_0_ACCEPTANCE.md](PLATFORM_1_0_ACCEPTANCE.md) and issue #201.
**Release decision:** NO-GO. This document and its generated JUnit-derived report
are **component-level evidence only**, not acceptance evidence for a signed
production OS installation. There is no real Core activation or Venus/Artemis
service change.

## Exact current-main baseline

At commit `6b7db78a64497a8069c714d672a691ae8fb7a33c`,
[Platform-only Development Gate run 42446317117](https://github.com/Crazysodaman/SofiaAdaLyra/actions/runs/42446317117)
completed on both Windows and Debian 12:

- Windows: 370 passed, 9 skipped, plus Rust workspace/Clippy/format checks.
- Debian12: 369 passed, 10 skipped, plus Rust workspace/Clippy/format checks.

The native Windows SCM, two-boot Debian VM, signed release installation and
release candidate gates remain distinct evidence surfaces. The full project's
Ollama-dependent failures do not belong to Platform-only acceptance.

## Which acceptance rows have executable preflight probes?

The versioned read-only tool
[`tools/aegis_platform_row_preflight.py`](../../tools/aegis_platform_row_preflight.py)
maps **25 rows** to source test files; all 38 rows are present in the report.
The **13 other rows** currently have no sufficient runnable component mapping.

| Class | Rows | What can be done now |
| --- | --- | --- |
| Installation and Core-free process probes | 01–09 | Staging/verifier, component isolation, identity, process/SCM, fault/lock tests; no final signed OS acceptance |
| SAFE/Fleet local security probes | 11–14, 16 | SAFE/STOP, enrollment/revocation, stale-trust; no authenticated installed service management |
| Modules and signed Core rejection | 17–18, 21 | Local lifecycle/verifier contracts, not signed installed-host lifecycle |
| Update/recovery/compatibility preflight | 19–20, 25–29 | Local signed staging, lifecycle, writer fences, installed-wheel checks |
| Theme contract | 38 | Rust/JSON/Markdown token validation, not GUI/TUI installability or rendering |
| Missing full integration | 10, 15, 22–24, 30–37 | Implement authenticated CLI/IPC, remote naming, synthetic Core lifecycle, runbook, GUI/TUI management API and native clients |

## CI execution

The Platform-only development gate runs existing Python and Rust regression
suites and writes three **per-run, exact-checkout** artifacts:

1. `platform-only-tests.log`: full bounded pytest output.
2. `platform-only-junit.xml`: actual testcases, failures and OS skips.
3. `platform-row-preflight.json`: all 38 mapped rows with `COMPONENT_PASS_ONLY`,
   `COMPONENT_FAIL`, `PARTIAL_OR_OS_SKIPPED`, `PROBE_NOT_RUN` or
   `BLOCKED_MISSING_INTEGRATION`.

Every row remains `acceptance=NOT_CLAIMED`, and the report always says
`release_accepted=false` and `production_authorized=false`.
A missing JUnit file results in zero observed cases, not fabricated passing
results. For pull requests the Git checkout SHA, not the synthetic merge SHA,
is read from `git rev-parse HEAD`.

## Requirements for a final PASS

For **each** of rows 01–38, attach the exact commit, full Windows and Debian
scenario IDs, full signed release artifact digests/attestation, owner-authorized
disposable installed-host receipts, reboot/reinstall/rollback evidence as
applicable, and actual result. Only then edit the authoritative tracker.
The following are not equivalent to full acceptance:

- SDK/Platform wheel import without a signed OS installer.
- A mock Python launcher instead of signed installed Rust SCM/systemd service.
- Source/theme documentation without running GUI/TUI.
- A Core signature denial without governed synthetic Core installation/removal.
- A copied result from a different SHA or an unrelated earlier release.

## Remaining implementation order

1. Complete B1 governed signed Platform OS install/activate/rollback/recovery,
   fix all exact-head CI regressions, then prove Windows and Debian disposable
   installed-host operation and two boots.
2. Implement Platform-owned authenticated versioned management IPC/CLI,
   owner-secret approvals, STOP/revocation, receipts and stale-observation states
   (rows 10 and 31, prerequisite to the UI).
3. Implement Rust TUI (Windows and Debian) and native GUI with the shared
   22-token theme. Apply it to real manager views and independent installers.
4. Complete remote Fleet names, signed module lifecycle and governed
   synthetic Core install/start/stop/detach/remove. Never activate personal Core.
5. Run exact-release CI matrices, protected-state recovery, installer
   uninstall/reinstall, all GUI/TUI/CLI parity, and complete operator runbook.
6. Reconcile all 38 host receipts against #201 and hold a separate host GO vote.
