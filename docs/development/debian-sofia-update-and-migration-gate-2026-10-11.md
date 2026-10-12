# Sofia Debian canonical migration: independent update path and active gates

**Date:** 2026-10-11. **Branch policy:** main only.
**Writer today:** Venus. **Target:** Hyper-V Sofia Debian 13 VM on Artemis.
**Execution policy:** source implementation and deferred tests now; no unapproved
live-system deployment, guest-side canonical DB, service activation or cutover.

## Guest provisioning evidence supplied by operator

Owner-provided SSH/console output establishes:
- Debian 13 (Trixie), Python 3.13.5, Git, installed Sofía wheel from initial
  pinned repository commit `a76897e7c3bb314576ec9509962c2bf4671b4648`.
- Guest hostname `Sofia`, `eth0` static `192.168.1.68/24`,
  gateway `192.168.1.254`, public DNS resolving github.com/debian.org.
- Authorized operator SSH connectivity from Venus; its existing UI/GPU stay there.
- Guest-local ext4 `/dev/sda4` backing the persistent bind mount
  `/home/sofia-state` -> `/var/lib/sofia-ada-lyra`, with ~211 GiB free.
- Restricted `sofia-runtime` UID/GID 988 owns mode-0700 mounted state directory.
- `/opt/sofia` created; service preview explicitly selects
  `User=sofia-runtime`, `Group=sofia-runtime` and requires an existing DB.
- Guest's actual Fleet identity, operator-signed writer pointer, mTLS pairing,
  privileged old-writer fencing and authoritative backup receipt **not verified**.

Do not promote these console outputs into cryptographic proof of enrollment or
evidence that the old writer is independently fenced.

## Source changes committed for independent updates

1. `run/github_update_watch.py`: bounded `git ls-remote` for exact GitHub
   main, immutable SHA parse, separate atomic status receipt, optional
   **signed and fully evidence-validated** staged-bundle recognition.
   Never pulls code into the live checkout, writes canonical SQLite,
   activates a release or restarts Sofía.
2. `run/systemd_update_watch.py`: a separate DynamicUser oneshot and
   15-minute timer renderer. These are only renderers; nothing was installed
   in the Debian guest. The timer is **discovery**, not deployment.
3. `run/debian_release_prepare.py`: privileged, nonactivating preparation
   of an exact signed release and independently hash-locked dependencies
   in root-managed `/opt/sofia/releases`; Debian/Python version admission
   and signature verification are required. No canonical DB access.
4. `run/systemd_release_launcher.py`: read-only selector for the
   authoritative active release; rejects absent/tampered stamps and
   unprivileged release directories, then `execve`s that interpreter
   as the same systemd service PID. The default bootstrap only runs when
   no signed active release has been selected.
5. `run/systemd_runtime.py` render-unit now uses the stable selector,
   keeping its independent Debian OS/pointer/writer safeguards.
6. `run/release.py` rollback verifies the old release supports the
   **current** state, Fleet and config schema before mutating pointers.
   Never revert canonical SQLite state with old backups to undo a bad update.
7. `.github/workflows/debian-lock-snapshot.yml` builds an independent
   REVIEW-ONLY hash-pinned Debian Python 3.13 dependency lock artifact.
   It **does not** automatically approve or commit the lock.
8. New regression tests cover watcher admission, bounded ref parsing,
   unsigned and invalid signature denial, read-only launcher, root admission,
   Linux Python mismatch and schema-incompatible rollback. Test files being
   committed is not a passed test report.

## Updater completion gates still open

**Automatic activation is deliberately disabled:** GitHub main is a source
notification, not deployment authority. The current production-signing
workflow builds Windows Python 3.12 releases and a Windows-specific lock.
A separately reviewed Linux 3.13 hashed lock, reproducible Debian build,
exact-SHA VERIFY evidence, platform-bound signed promotion and key
distribution are required before Debian updates can be approved.

A separate privileged host deployment broker must stage verified releases,
validate owner-approved automatic-update policy, wait for a provably idle
runtime, verify available backup/rollback and compatibility, stop the single
canonical service cleanly, activate the signed manifest, restart that same
service, obtain a live health/identity/writer receipt and perform only a
**compatible code-only rollback** when safe. It must log uncertainty, preserve
newer state, and refuse automatic recovery where schema/identity/erasure
history changes make rollback unsafe. This externally privileged updater
and its host acceptance are not yet implemented/approved as production.

**Do not enable any updater systemd unit or timer on the VM yet**. The guest
contains the operator-installed a76897e wheel and will not automatically
receive later GitHub source commits until its independently reviewed
deployment pipeline is installed.

## Migration-critical phases and unresolved gates

- **00 / architecture**: final writer endpoint publication, Venus GPU-only
  identity, Linux thin client topology, approval and deployment authority.
- **01 / release**: Linux reproducible locked + signed release, independent
  privileged auto-installer, full rollback compatibility and host validation.
- **03 / canonical migration**: externally privileged Hyper-V old-writer
  fencing and monotonic epoch issuance; complete encrypted backup; staged
  restore; deletion journal; operator-approved promotion and recovery.
- **NET / RUN**: separate Sofia VM enrollment, pinned mTLS to Venus inference,
  exact capabilities, supervised lifecycle and offline-safe behavior.
- **UI / desktop**: Windows tray and chat currently open and write a LOCAL
  SofiaApplication/sofia.db; a separate authenticated Main/history/controls
  protocol and Windows thin client must be production-wired before cutover.
- **VERIFY**: source tests, exact main CI, Debian Hyper-V host proof, authenticated
  end-to-end chat/GPU, Windows tray, game protection, adverse-restart,
  split-brain drill and backup restoration.

Other V18 phases, especially LIFE/COMPANION/HEPHAESTUS, can proceed after
canonical migration provided they do not grant a second writer or unreviewed
tools. No full migration or 700-task production acceptance is claimed.

## Operator command boundary

Current source changes are on GitHub main but **not** in the pinned a76897e
wheel installed on the guest. Do not run untrusted `git pull && pip install &&
systemctl restart`. Before live activation the operator and maintainer must
validate the complete signed package + trusted Linux lock + pinned Fleet PKI
chain and independent old-writer fence. Safe read-only Linux guest commands
remain `findmnt`, `id`, `ip route`, `systemctl is-active` and
`python -m sofia.run.systemd_runtime verify-guest` from the **installed**
bootstrap wheel.

## Linux release supply-chain update (same day)

- Exact Debian 13 / Python 3.13 runtime hash lock committed at
  `requirements.lock.linux-py313.txt`. Its Git blob SHA
  `ec28d5436e87bb2f99c1eacd3f595d1043a2a579` matches the exact
  byte contents of the successful GitHub lock snapshot artifact from run
  `38186119612`.
- Verified universal-wheel build and VERIFY tool locks at
  `requirements.build.lock.linux-py313.txt` and
  `requirements.verify.lock.linux-py313.txt`.
- `.github/workflows/debian-release-candidate.yml` builds two Linux
  Python 3.13 wheels from byte-identical clean Git source, requires
  reproducible SHA-256, executes the installed-wheel provenance/VERIFY gate,
  and uploads **unsigned** evidence for human-supervised promotion.
- `.github/workflows/release-promotion.yml` now checks the run's exact
  name, success, main branch and manifest Git SHA before permitting either
  Windows or Debian release candidates to be signed using the protected
  release-signing environment. No automatic signing or secret delivery.
- `distributed/pki.py:issue_node_pair_from_existing_ca` can issue distinct
  server/client leaf credentials for Sofia against the already operator-owned
  Fleet CA without copying the CA private key to the VM. This is source-only;
  no credentials were issued by ChatGPT, copied to the guest or enrolled.
- Debian candidate workflow acceptance and the actual Debian guest
  package/connection tests are still open. The pipeline is not a validated
  production update path until exact-SHA CI and host receipts pass.

**Critical distinction:** the signing chain and nonactivating staging are now
coded, but no independently privileged *automatic activation* process has
been accepted. The updater timer must not be enabled as an auto-installer.
