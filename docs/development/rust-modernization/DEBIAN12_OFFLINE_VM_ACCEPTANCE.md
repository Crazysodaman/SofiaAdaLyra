# Offline Debian12 VM service contract

`python -m tools.aegis_debian_vm --help` describes an explicitly disposable
verification tool. It is not an alternative Platform installer, release signer,
owner approval or production deployment interface. It requires a new output
path and an installed Linux Rust1.88 toolchain. Run it from the project test
harness on a disposable Linux Docker host, with `--disposable-vm` explicitly set.

The controller uses the existing Git-object source stager and SDK/Platform
component builder. Only neutral wheels, Rust source, production service template
and test scaffolding enter the helper context. It rechecks the observed source
commit/clean tracked tree after staging and execution. No personal Core package,
protected identity, canonical database or real Fleet state is copied into the VM.

The official Python3.12 Debian12 base image is pinned by digest. An ordinary
helper container builds the current Rust service against Debian12's ABI, resolves
only mandatory SDK/Platform binary dependencies, and constructs a fresh test
filesystem with Debian's signed kernel/systemd packages. Input and built-artifact
hashes are retained. These are conformance build observations, not byte-for-byte
release reproducibility or a substitute for signed runtime/dependency delivery.

QEMU uses CPU emulation, no KVM or privileged container, and no guest network
interface. The guest runs the unchanged production service unit under PID1
systemd, a dedicated service account and private persistent Platform state. On
each of two actual boots it requires verified readiness, duplicate-supervisor
denial without disturbing the running instance, graceful stop/no orphan,
restart, automatic recovery after an intentional service crash, another graceful
stop, unchanged identity and no Core/Ollama/personal database. Across boots the
boot IDs must differ while UUID/key fingerprint persist and generations advance.
Partial, stale, replayed or inconsistent receipts do not produce a success summary.

The Docker endpoint is explicitly local; inherited context/TLS/endpoint selectors
are removed while proxy, CA and registry configuration remain. Only returned
container IDs are cleaned up. A cleanup failure cannot produce success. Existing
output and redirected parent paths are refused. No host service or account is
provisioned by this runner. OS provisioning occurs inside its test guest only.

VM images contain disposable private Platform keys. Keep the output owner-private
and never publish the image or extracted root filesystem. CI uploads only public
input/artifact digests, test receipts and bounded-by-test-duration boot/build logs.
The explicit receipt flags remain `production_authorized=false` and
`release_accepted=false`. A green VM test does not complete signed installation,
upgrade/rollback, owner management, remote Fleet or the full release matrix.
Both shakedown verdicts remain NO; G8 remains deferred.

An initial manual source-ccc911a8 probe already observed Debian12 kernel
6.1.0-54-amd64 / Python3.12.16, two distinct systemd boot IDs, same Platform
UUID/key fingerprint, generations 1–3 then 4–6, four graceful stops and two
crash recoveries with no Core/Ollama. That probe used a prior Debian-built Rust
binary with an empty Rust/Cargo.lock source diff to the tested revision; it was
not represented as a final signed release. This workflow rebuilds current Rust
source and records exact checked-out SHA evidence instead of reusing that binary.
