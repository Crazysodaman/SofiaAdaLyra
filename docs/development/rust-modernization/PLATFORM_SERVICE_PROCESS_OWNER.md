# Rust Platform service process owner

The `aegis-platform-service` binary owns one fixed installed Python Platform
state adapter over inherited anonymous pipes. It never launches a Core or
opens personal Core state. Its trusted OS configuration supplies an absolute
Python interpreter, pre-existing private installation identity and LOCL state,
and pinned Platform UUID/public-key digest. These are public identity references,
not an owner secret or authorization to enroll peers.

The adapter loads PR192 identity, verifies current private storage and exact
MODULE_HOST binding, and acquires the existing RUN `platform-service` lease
plus OS lifetime lock. The durable lease epoch fences each process generation. The service lifetime
lock is in the private state directory, so systemd PrivateTmp cannot create an
independent lock namespace for the same state.
It reads the existing SAFE STOP store. A stale/expired lease, identity replacement,
missing state, unsafe ACL, or corrupt STOP state denies health. It never silently
creates identity or a missing local database.

Rust controls the child's process handle, checks actual child/parent PIDs and
pinned identity before readiness, and validates bounded typed replies. Sequence
and epoch must match exactly; duplicate/unknown JSON fields fail closed. The
Python request decoder is bounded, duplicate-rejecting and operation-specific.
Only internal status/heartbeat and cooperative shutdown are supported. This
pipe is not a public management endpoint and cannot grant owner permissions.

SIGINT/SIGTERM (Unix), console controls (Windows) and native SCM Stop/Shutdown
request cooperative draining. An acknowledged shutdown is followed by observed
OS process exit before success. A five-second failed drain poisons shutdown;
Rust cleans up only its own child and reports failure. Unexpected adapter exit
fails the supervisor, rather than reporting healthy or starting a Core. EOF on
the parent-owned pipe releases adapter authority after abrupt parent exit.

Windows `--scm` registers the native `AegisPlatform` dispatcher and reports
StartPending/Running/StopPending/Stopped. SCM authorizes OS controls, not Aegis
owner operations. The systemd unit in `packaging/services` uses a dedicated
unprivileged `aegis` account, restrictive state directories and hardening,
Type=notify, bounded shutdown and restart/start-limit policy. Its environment
file contains only the five public configuration values; never owner secrets.

This source unit is not an alternate installation path. Service registration,
account/directory provisioning, signed Rust artifact selection and repair must
be integrated with the existing verified component/release installer before
claiming installer acceptance. No service is registered or activated by a build.

Remaining acceptance: installed SCM and real systemd observations on disposable
targets, native Windows signal behavior, boot/reboot/reinstall and upgrade
receipts, authenticated external SAFE-backed CLI/IPC, governed module process
supervision/resource limits, broker wiring, remote Fleet naming, and governed
Core stage/activate/remove. The current adapter's explicit MODULE_HOST-only
state binding does not adopt differently configured existing installations.
Neither Platform-only nor full-project shakedown is certified by this batch.

The shared singleton lock now refuses symlinks, hard links, foreign ownership
and broad read ACL/mode permissions before writing. It creates new private
files exclusively and checks opened-file identity. Unsafe legacy lock files
fail closed and are not silently re-ACL’d; reviewed installation repair remains
necessary for those installations. Python/Tk singleton behavior is regression
tested with fresh private files; no rendering policy or entry point is removed.

The RUN epoch is retained in existing LOCL state. Whole-state rollback across
restarts still needs the independently retained release/recovery checkpoint
composition; this batch does not certify rollback-resistant service recovery.
