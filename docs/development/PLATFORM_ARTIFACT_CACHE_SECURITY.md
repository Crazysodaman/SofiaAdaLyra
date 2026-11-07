# Platform installer artifact cache boundary

The offline cache is storage for already selected artifact bytes. A constructible
`PlatformArtifact`, its `signature_verified` field, or a successful cache import
does not authenticate a release or authorize installation. The independently
trusted installer must verify the signed release and exact owner authority.

Cache imports now use the shared bounded, identity-pinned artifact reader and a
single immutable source snapshot. Root, ancestor and leaf redirections are
rejected. Individual reads retain the shared 512-MiB artifact limit; the cache
budget applies to the sum of stored files.

A new cache has owner-private protection using the existing Platform filesystem
and Windows DACL helpers. Existing unsafe permissions are rejected without
changing them. Legacy caches created with public permissions require an explicit
reviewed transition; opening the cache does not silently repair or replace them.

Imports reuse the Platform's cross-process OS lock inside the cache directory.
Budget calculation and publication run while that lock is held. Contending
imports fail for retry rather than claiming success. The temporary file is
private, flushed, rehashed and atomically published without replacement. The
parent directory is flushed on Unix. Failure preserves pre-existing data and
removes only the importing operation's own temporary file. Successful reimports
and resolution always recheck the cached digest; existing corruption is never
silently repaired.

These checks do not create an installer backend, anti-rollback checkpoint,
backup/restore authority, service registration or production activation path.
