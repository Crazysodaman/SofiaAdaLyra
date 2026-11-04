# R1 Rust SDK contract foundation

R1 adds an experimental, authority-free Rust representation of the existing
Python component SDK contracts. Python remains authoritative. This work does
not implement transport, database access, UI, process supervision, SAFE, STOP,
credentials, signing, or production activation.

## Boundaries

- `contracts/schemas/` describes the reviewed v1 endpoint, authority projection,
  request, and response document shapes.
- `contracts/fixtures/` is the shared positive and negative corpus.
- `src/sofia/sdk/contract_wire.py` adds bounded strict JSON framing around the
  existing Python dataclasses.
- `sofia-contracts` mirrors those validations and exposes a corpus tool used by
  Python/Rust parity tests.
- `contracts/compatibility.toml` records the supported version and encoding.

Neither an authority projection nor a successfully decoded envelope grants
authority. Callers must still authenticate the channel and use the existing
Platform authority boundary.

## Canonical encoding and digest

Canonical JSON is UTF-8 RFC 8259 JSON with recursively sorted object keys, no
insignificant whitespace, JSON booleans/null, and no non-finite numbers.
Duplicate object keys are rejected before typed decoding. SHA-256 is lowercase
hex over those canonical bytes. R1 canonical digests allow strings, booleans,
null, arrays, objects, and integers in `-2^63..2^64-1`; fractional numbers are
rejected because Python and `serde_json` do not guarantee identical spellings.
Messages are rejected above 65,536 bytes and documents deeper than 64 nested
array/object levels are rejected before typed validation.

## Ambiguities discovered

1. Existing component request and response payloads have no top-level schema
   discriminator. R1 therefore selects request versus response outside the
   document. Adding a discriminator would be a new protocol version.
2. A request carries a payload digest but not the payload bytes. Typed envelope
   parsing can validate digest syntax only. The R1 harness verifies content
   when the external payload is supplied; production transports must bind the
   same bytes explicitly.
3. Existing typed parsing accepts any syntactically valid protocol version.
   The R1 wire layer supports exactly `1.0` and fails closed on other versions.
   Broader minor-version negotiation requires reviewed fixtures first.
4. Audience and destination generation are dispatch context, not document-shape
   properties. R1 tests them through explicit external context and does not
   infer either value from display names or caller input.
5. Python emits UTC timestamps with `+00:00`; RFC 3339 also permits `Z`. R1
   validates either spelling but canonical JSON does not normalize timestamp
   strings. A future protocol must define timestamp normalization before using
   whole-envelope canonical digests.
6. Python integers are unbounded while the Rust generation representation is
   `u64`. The language-neutral R1 wire schema bounds generations to
   `1..18446744073709551615`; the Python wire validator applies the same bound
   before constructing the existing dataclass.
7. The existing SDK does not define floating-point canonicalization. R1 rejects
   fractions in canonical-digest input rather than claim false parity. A future
   protocol can adopt a separately reviewed decimal or RFC 8785 representation.

## Dependency policy

Dependencies are exact-pinned in `Cargo.toml` and locked by `Cargo.lock`.
`cargo-deny` enforces registry, advisory, license, wildcard, and source policy.
CI produces a CycloneDX SBOM, runs formatting and Clippy with warnings denied,
tests debug and release builds on Windows and Linux, and runs Python 3.12 and
3.14 compatibility legs against the same fixture corpus.

## Test coverage limits

- JSON Schema validates document shape and RFC 3339 syntax. Cross-field time
  ordering, current time, audience, destination generation, and external
  payload digest remain runtime/context checks because JSON Schema cannot
  establish those facts.
- The deterministic corpus covers the message-size boundary, nesting boundary,
  invalid UTF-8, duplicate keys at multiple levels, trailing data, unsupported
  versions/schemas, numeric bounds, Unicode, response status, and corrected
  cross-field rules. It is not an exhaustive byte-level fuzzer.
- Windows and Python 3.14 evidence is produced by the dedicated GitHub matrix;
  local validation in this development environment is Linux/Python 3.12.
