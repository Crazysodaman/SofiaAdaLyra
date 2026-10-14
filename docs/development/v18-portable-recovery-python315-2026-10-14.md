# V18 portable backup restore filename hardening

Date: 2026-10-14. Recovery/archival portability implementation relevant to
CA-6104 and CA-6108 design objectives. No design/research task acceptance.

## Observed evidence

The Debian 3.13 release run
[38650361705](https://github.com/Crazysodaman/SofiaAdaLyra/actions/runs/38650361705)
reported 1,468 warnings. Hundreds included the use of
`PureWindowsPath.is_reserved()` in production backup manifest validation.
That API is deprecated and scheduled for removal in Python 3.15. Removing
its check would weaken portable Linux-to-Windows restore safety.

## Production integration

`BackupEntry` already has safe logical-path and encrypted payload-name
validation. Both call sites now use a single `_windows_reserved_name()`
helper backed by `ntpath.isreserved` where available (Python 3.13+),
falling back to `PureWindowsPath.is_reserved` on Python 3.12. This checks
Windows device names while running on Debian or Windows, without a platform
specific bypass. No path-normalization or restore authority was weakened.

## Focused regressions and outstanding verification

Tests reject CON, NUL.txt, AUX.log, COM1 and LPT9.prn in both manifest
namespaces, while allowing existing safe production names. On modern Python,
a DeprecationWarning is now treated as a test failure. Final proof requires
exact-commit Linux Python 3.13 and Windows Python 3.12 tests, installed-wheel
restore verification and separately authorized real-host drills.

Changes are read-only input validation. No backup was created or restored
on Venus/Artemis; no canonical writer, keys, retention, credentials or
permissions changed. Reverting the commit needs no data migration.
