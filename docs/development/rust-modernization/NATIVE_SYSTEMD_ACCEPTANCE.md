# Native systemd contract acceptance

The Rust process and filesystem notify tests do not by themselves prove that
systemd can own the service with its production hardening and restart policy.
`test_rust_platform_systemd` runs the checked-in production unit template under
an actual systemd manager on an explicitly opted-in disposable CI VM.

The test generates unique account, service and filesystem names. It refuses to
adopt any existing resource. It copies only the independently installed
SDK/Platform runtime, provisions a separate immutable test Platform identity as
the dedicated service account, and substitutes only public runtime paths and
account names in the unit. Production Type=notify, private state/runtime,
PrivateTmp, ProtectSystem/ProtectHome, bounded stop, restart delay and start-limit
settings remain in effect.

Acceptance requires verified readiness, graceful stop with exit status zero and
no remaining supervisor/adapter PID, restart with an advancing durable generation,
controlled systemd recovery after intentionally killing this test's main process,
a second graceful stop, unchanged identity, and no personal `sofia.db`. Teardown
removes only the generated resources. Forced cleanup causes failure, never a
successful stop receipt. No production Platform is enrolled or modified.

Ordinary test runs skip this OS-provisioning test unless
`AEGIS_REQUIRE_SYSTEMD_ACCEPTANCE=1` is explicitly set. Do not set that variable
on a production or personal host. The dedicated workflow sets it only on its
disposable Ubuntu24.04 runner, requires actual PID1 systemd and noninteractive
administration, and checks that the resulting JUnit test was not skipped. A
missing native host fails that gate; the local managed container reproduced this
failure without creating an account or service.

This is Linux service-manager contract evidence, pending its actual CI result.
It is not approval or certification of Ubuntu as a release target, a signed OS
installer, Debian12 boot/reboot acceptance, production deployment, or G8. Debian12
container/process evidence and Windows SCM acceptance remain separately reported.
Both shakedown statuses stay NO until the full mandatory matrix is satisfied.
