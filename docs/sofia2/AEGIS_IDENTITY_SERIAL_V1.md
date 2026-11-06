# Aegis UUID identity and readable serial v1

`sofia.sdk.identity.AegisIdentity` is an immutable, authority-free projection.
A Platform and a Core have distinct typed identities. Neither a serial nor a
successfully decoded UUID authenticates a peer, grants permissions, proves
ownership, or admits a protected-state writer.

## Encoding

The canonical identity is the complete 128-bit UUID, printed as lowercase
`8-4-4-4-12` hexadecimal text. The serial contains exactly those same bits in
four eight-hex-digit groups, with uppercase ASCII hex:

- Platform: `AEG-P-01234567-89ABCDEF-FEDCBA98-76543210`
- Core: `AEG-C-01234567-89ABCDEF-FEDCBA98-76543210`

Both examples encode UUID `01234567-89ab-cdef-fedc-ba9876543210`, under different
identity kinds. The kind is part of the typed identity and serial. A deployment
must independently allocate different canonical UUIDs for its Platform and
Core; changing the prefix does not allocate a new UUID.

No bytes are truncated, hashed, or inferred from a host name, callsign, personal
name, credential or package name. Conversion is bijective for each kind: group
separators are removed to recover exactly the original 32 hex digits. Conversion
therefore adds no collision probability. Collision resistance of newly allocated
identities depends on the allocator's UUID entropy, which this codec does not
provide. All 128-bit values round-trip, including reserved/null UUID values;
validation of whether an identifier may be allocated or enrolled belongs at the
Platform admission boundary.

The parser accepts ASCII case differences and emits the canonical uppercase
serial. It rejects whitespace, shortened UUIDs, braces, URNs, missing groups,
Unicode lookalikes, unknown kind prefixes and arbitrary version suffixes.
The codec cannot detect a valid hex typo: fingerprint confirmation and enrolled
cryptographic identity remain necessary for trust.

## Versioned projection

The wire projection contains exactly:

```json
{"schema":"aegis.identity.v1","kind":"platform","uuid":"01234567-89ab-cdef-fedc-ba9876543210"}
```

`kind` is `platform` or `core`. Unknown schema versions and additional fields are
rejected. The serial is derived presentation data, not a second stored authority.
A future serial grammar requires an explicitly reviewed decoder/schema version;
this parser never guesses a new format.

## Lifecycle boundaries and compatibility

This slice provides conversion and validation, not installation persistence,
key provisioning, signed recovery, Fleet enrollment, callsign reservation, or a
Core lifecycle. It does not create identities at import, construct a Core,
select a default Core, or replace legacy identifiers in existing stores. The
portable SDK wheel owns the module; it imports only Python's standard library.

Reinstallation must reuse a verified persisted identity when continuity is
intended. Approved recovery must restore the original UUID and authenticated
key binding through the existing protected recovery authority. Missing or
unverified continuity evidence must not be treated as successful recovery or
silently remapped by this codec. Those behaviors remain implementation and
acceptance work; codec tests do not certify them. Sofía's existing identity,
Constitution, memories and writer lineage remain untouched.

## Rust/Python conformance

`sofia_contracts::identity` exposes the same inert identity using exact 16-byte
UUID storage, with no allocation or credential dependencies. Both implementations
consume `contracts/identity/fixtures.v1.json`: canonical and case-normalized
positive examples, maximal/null UUIDs, unknown versions/kinds, malformed lengths,
whitespace, non-ASCII lookalikes, missing fields and forged authority fields.
Each implementation also tests every one of the 128 UUID bit positions. The
shared fixture tests compare decoded payloads and canonical serials with the
same expected values; they do not certify a transport, enrollment or lifecycle.
