# Signed Platform code candidate staging

`sofia.platform.ops.platform_release_staging.stage_platform_release` bridges
the existing signed release verifier and neutral runtime artifact verifier.
It prepares code in a fresh private directory; it does not install a Platform.

The caller supplies the configured release verifier and exact source, target,
revision floor, parent digest and state-schema expectations. Signature and scope
verification occur before candidate or artifact paths are observed. The candidate
parent must already have owner-private protection. An existing destination is
rejected without replacement or permission repair.

Each selected artifact is copied from one identity-pinned immutable snapshot,
with its signed size and hash rechecked. The copied asset tree is independently
verified again. The signed runtime archive is then validated and materialized
against the outer release's target and exact Python patch version. Code files
and metadata are flushed; Unix directories are flushed before success returns.
A failure retains the fresh partial candidate for explicit review; retry never
silently resets or adopts it.

`aegis.platform.code-stage.v1` receipts report verified code bytes only. They
explicitly report no activation, OS service registration, Platform state
initialization or service-health verification. No Platform UUID, signing key,
canonical Core state, owner principal store or permission grant is created.
The stager does not execute the interpreter or service, install wheel packages,
resolve dependency closure, or certify the semantics of hash-bound dependency
locks, SBOMs or provenance. Its receipt is neither current owner authorization
nor a persisted anti-rollback checkpoint.

A future governed installer must recheck current release trust/revocation,
verified exact owner approval and durable revision policy, verify the candidate
again, and complete installed-environment and OS service acceptance before
selection or activation. None of those gates is satisfied by staging.

Regression fixtures use disposable signatures, real SDK/Platform wheels, and
explicitly inert native/runtime header fixtures that are never executed.
Actual runtime execution and two-boot service acceptance remain separate tests.
