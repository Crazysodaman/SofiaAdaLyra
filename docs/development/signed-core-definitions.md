# Signed individual Core definition contracts

`sofia.sdk.core_definition` defines immutable, authority-free data for one
individual Core: a supplied typed AEG-C UUID, display name, definition revision,
exact runtime release digest, SDK protocol, and digest/size/path references for
its Constitution and personality assets. It never generates an identity UUID.
Runtime code, mutable private memory/state and Platform identity are separate.
No state database, owner credential, executable plugin or permission grant is
created by this definition contract.

The exact schema is `aegis.core.definition.v1`. Unknown fields and noncanonical
identity encodings are rejected. The definition digest is lowercase SHA-256 of
`b'aegis.core.definition.v1\0'` followed by canonical UTF-8 JSON (sorted keys,
compact separators, finite JSON values). The detached Ed25519 signature signs
the ASCII hex digest, through the existing configured component-signature
verifier. No second keyring, principal store or approval engine is introduced.

`CoreDefinitionVerifier` requires the host-selected expected Core UUID, runtime
digest and positive minimum definition revision. These must come from trusted
host policy when used by a future controller, not the incoming definition.
The verifier rejects unsupported SDK protocols and missing/removed/wrong signer
keys. It validates the signature and expected target before observing personal
assets. Asset references are bounded, package-relative, distinct under portable
normalization, and cannot use traversal, drive-qualified, alternate-stream,
reserved-device or ambiguous Windows paths. Reads reject symlinks/junctions and
nonregular files, enforce signed size/digest (maximum 16 MiB per asset), and
check file identity/metadata around the read.

The read-only command is:

```text
python -m sofia.platform.ops.core_definition \
  --definition /absolute/package/definition.json \
  --assets-root /absolute/package \
  --trusted-public-key /approved/operator.pub --signer-key-id operator \
  --signature BASE64_SIGNATURE --expected-core-id EXISTING_CORE_UUID \
  --expected-runtime-sha256 EXACT_RUNTIME_SHA256 --minimum-revision 1
```

The bounded JSON reader rejects duplicate fields and nonregular files. Success
reports VERIFIED_DEFINITION and public identity/revision/digest metadata. This
is content verification relative to the explicitly configured trust root;
it is not installation, enrollment, selection, mutation or writer authority.
No owner secret or private signing key is a command argument.

Tests use separate disposable definitions named Synthetic Sofia, Synthetic
Roland and Synthetic John, with independently supplied UUIDs and synthetic
keys. They do not clone or modify Sofía's existing identity, Constitution,
private memories or assets. Removing a signer from the configured trust map and constructing the current
verifier makes subsequent verification reject the old signature. A controller
must refresh its trust snapshot when policy changes; this read-only verifier
does not implement a running key-revocation service. Verification never writes package
assets or creates a Core state database. Core-blocked source and actual wheel
probes verify package separation; native tests use a real Windows junction or
POSIX symlink for redirection rejection.

This is the signed-definition verification foundation. Actual production
individual Core definitions, durable approved revision ownership, definition
application, generic Core Runtime separation, private asset grants and writer
activation remain independent work. The existing Sofía runtime/worker/default
identity behavior is unchanged. A future runtime must revalidate current
artifacts and authorization at its activation boundary; a constructible SDK
definition or a past read-only verification result is never an activation
permit. No production keys, Core enrollment or services are activated here.
