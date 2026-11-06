# Platform-local state path protection

The Core-free module store reuses the canonical SQLite ancestor-path validator
on adoption, immediately before bootstrap publication and on each connection
validation. A symlink or Windows directory junction anywhere in the configured
path raises `LocalStateUnavailable`, including redirection to the same inode.
Existing role, host binding and file substitution checks remain in force.

This closes a local-store gap; canonical state already used these shared path
checks. It is not a claim of race-free directory-handle traversal or a complete
filesystem sandbox. No personal Core state is moved or modified.

Tests reproduce existing-parent adoption and post-open same-inode redirection,
simulate junction detection and provide a separate native Windows junction
probe. Native-only or unavailable symlink privileges are reported as skips,
not passed coverage.
