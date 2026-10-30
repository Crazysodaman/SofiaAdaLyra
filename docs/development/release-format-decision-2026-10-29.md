# Decision Record: Release Format (Legacy Single-Wheel and Separated Components)

- Date: 2026-10-29
- Batch: G2-B.2 production packaging integration
- Status: Decided and implemented (`ReleaseManifest.components`, optional; default legacy)

## Approved Spec Constraint

Sophia's approved GO LIVE spec defines independent Platform/SDK and Core
runtime/identity artifacts. The repository's production release machinery
historically binded exactly one integrated distribution:

- distribution `sofia-ada-lyra` (integrated wheel)
- `ActiveReleaseResolver.resolve()` required exactly one `*.whl` inside the
  artifact directory.
- `ReleaseEnvironmentManager.ensure()` installed exactly that wheel with
  `--no-deps` after the hash-locked dependency install.
- `construct_release_evidence()` staged exactly one wheel into
  `release-evidence/artifact/` and hashed the directory (one-wheel contract).

## Decision

Both release formats are supported, explicitly, with mutual exclusivity:

1. LEGACY INTEGRATED FORMAT — unchanged:
   - exactly one wheel in the artifact directory,
   - manifest without `components` (canonical bytes are byte-identical to all
     existing manifests; signed evidence remains valid),
   - resolver returns `wheel_path` + empty `component_wheels`,
   - environment manager installs one wheel,
   - verify: release artifact must contain exactly one wheel.

2. SEPARATED COMPONENT FORMAT — new:
   - exactly three wheels in the artifact directory (`sofia-sdk`,
     `sofia-platform`, `sofia-core`), plus `requirements.lock`,
   - manifest carries `components`: a tuple of `ComponentArtifactIdentity`
     entries binding component -> distribution -> exact version -> exact
     SHA-256; canonical JSON sorts by component name and the Ed25519 release
     signature covers these identities (a swapped or forged digest breaks
     verification),
   - `construct_release_evidence(wheel_path=None, component_wheels={sdk,
     platform, core})` binds identity facts from the wheel bytes themselves
     (`inspect_wheel`), requires exactly the three components, and requires
     the platform component's version to equal the release application
     version,
   - resolver validates each wheel against the bound identity (name, version,
     digest, exact wheel count) and returns `component_wheels` in
     sdk/platform/core order with `wheel_path=None`; it refuses any extra,
     missing, duplicated or tampered wheel,
   - environment manager installs the hash-locked dependencies first, then the
     three component wheels with `--no-deps` in component order (sdk, platform,
     core), then `pip check`; the environment stamp includes component wheel
     names so a mismatched mixed-format reuse is impossible.

The two formats are mutually exclusive in one release: passing both an
integrated wheel and component wheels to construction raises; the resolver
rejects an artifact that contains neither exactly one Integrated wheel nor
exactly the three bound components.

## Why, Not a Choice, But a Reconciliation

- The approved spec requires independent Core runtime/identity artifacts.
- Existing signed releases, deployed environments, staged release state, and
  accepted release history continue to be valid without any data migration.
  The separated format is additive state (`components` key in canonical
  bytes), never a rewrite of past release identity.
- Production installers already provision the dependency lock separately, so
  component wheels install with `--no-deps` and `pip check` provides the
  cross-component dependency assertion (Core requires sofia-platform and
  sofia-sdk; platform requires sofia-sdk).

## Component Ownership Facts (binding)

- User-facing packaging manifest: `packaging/components.toml`
  (schema `sofia.platform.components.manifest.v1`).
- `sofia/__init__.py` is owned by the SDK wheel (declared extra file). Platform
  and Core wheels must not contain it. This is what allows all three wheels to
  install into one site-packages directory while every wheel's RECORD stays
  exact.
- Core owns constitution/identity/embodiment/personality assets and nothing
  from `sofia.platform` or `sofia.sdk`. Verified by both the release CI
  separation step and the installer content check.

## Core Installation Authority

- Installing or replacing Core on a Platform host stays a gated operation:
  explicit `InstallAuthority` plus a trusted Ed25519 signature verification
  over the wheel digest (`Ed25519ComponentSignatureVerifier`); the installer
  recomputes the wheel digest itself, never accepting caller-declared trust.

## Out of Scope for This Record

- G2-C Core hot-swap uses these receipts/identities; its own lifecycle and
  fencing sequence will be recorded separately.
