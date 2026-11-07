# Platform-only signed release bytes

The legacy personal Core release manifest requires a Constitution hash. A
Platform release must be independently verifiable without inventing personal
assets or installing a Core. `sofia.sdk.platform_release` defines the separate
`aegis.platform.release.v1` contract. Existing Core-definition payloads,
signatures and their 16-MiB personal asset limit retain their public contract.

A manifest pins its source SHA, canonical release version, monotonic revision,
optional predecessor digest, Windows x86_64 or Debian12 x86_64 target, SDK
protocol, exact Python 3.12 runtime version and supported local state schema.
Required signed asset references identify SDK and Platform wheels, Rust service,
Python runtime, dependency lock, SBOM and provenance. Additional dependency
artifacts can be listed. No Core, owner credential or installed Platform UUID
belongs in this distributable contract. References use bounded, relative paths,
SHA-256 and exact byte counts; the bundle is capped at 1 GiB / 96 assets.

`sofia.platform.ops.platform_release.PlatformReleaseVerifier` reuses the existing
trusted Ed25519 component signature verifier. It checks exact expected source,
target, predecessor, caller-supplied revision floor, SDK and state compatibility
before reading artifact paths. Signature denial does not inspect the asset root.
Root, ancestor and leaf redirection are rejected. Bounded file-descriptor reads
check opened identity and detect changes before returning a digest.

SDK/Platform archives are bounded and checked for dependency and package
separation, ambiguous names and symlink entries. Payload must remain within its
owned SDK/Platform package or distribution metadata; wheel `.data` relocation
and case-variant foreign packages are denied. Dependency headers are parsed
case-insensitively and singleton identity metadata must be unambiguous. The SDK remains dependency-free;
Platform cannot require Core or baseline Ollama. Hashing and archive inspection
use the same immutable byte snapshot. This also fixes the pre-existing
`inspect_wheel` path-reopen race: its reported digest and metadata now describe
one snapshot even if another process replaces the path.

Service checks inspect ELF/PE architecture declarations and reject declared
glibc requirements above Debian12's 2.36. These header checks do not prove a
healthy executable. Runtime, dependency, SBOM and provenance assets currently
receive signed-byte verification only; this is not a semantic provenance
attestation verifier or an interpreter installer.

## Read-only operator command

Run `python -m sofia.platform.ops.platform_release --help` for required public
inputs. The public release signature is safe to pass as an argument; owner
credentials are neither accepted nor used. Success returns
`VERIFIED_PLATFORM_RELEASE_BYTES` with `activated: false`; verification denial
returns structured `REJECTED` and exit status 2. No service registration,
installation selection, state database or identity is created.

## Acceptance boundary

This is a release verification primitive, not a second installation path.
Verification does not grant owner approval, activate code, establish a durable
anti-rollback floor, or certify the provenance of a Python runtime. Installation
must reverify selected bytes through the existing governed lifecycle, retain
revocations and identity, and supply an independently trusted durable revision
checkpoint. A signed producer, complete dependency/runtime construction,
restart-safe selection/rollback, and installed Windows/Debian acceptance remain
outstanding. Neither shakedown status becomes READY from these tests.

Tests include independent SDK/Platform wheels, disposable signing keys, malformed
and forbidden archives, source/target/signature/revision/schema rejection,
path redirection, a reproduced archive-reopen attack, Windows PE declarations,
Debian glibc bounds, CLI denials and source/installed Core-free import isolation.
Synthetic service headers and runtime blobs are inert test data and are never
represented as runnable release artifacts.
