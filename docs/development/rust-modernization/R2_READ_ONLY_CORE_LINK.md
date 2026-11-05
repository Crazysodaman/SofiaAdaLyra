# R2 read-only Rust Core Link client

## Dependency and scope

R2 is stacked on unmerged R1 commit `b065b58c601400f431aefd1ffa805e67237d4167` and must not merge before R1 PR #134. The crate is a library and is not referenced by any production launcher. Python remains authoritative and the Python/Tk client remains the fallback.

The client implements only `status` and `conversation.history` for an already-authorized session. It cannot create, select, send, cancel, mutate results, update settings, or invoke modules. It owns no conversation database or state writer.

## Compatibility and authority

The Core Link request/response format is implemented independently from the R1 component envelope. Request JSON has no principal, audience, credential, grant, or scope field. Authority continues to derive from the client certificate enrolled by the Python host. The client checks the selected binding's local and remote Platform IDs, Core identity, exact generation, protocol `1.0`, endpoint path, active state, server hostname, CA chain, and enrolled server public-key pin before accepting a result.

Payload canonical size is limited to 64 KiB. Complete request and response bodies are independently limited to 72 KiB. Requests carry an exact creation time and deadline; expired or not-yet-active requests fail before transport. The client disables redirects and HTTP fallback, requires TLS 1.2 or newer, and returns bounded errors without content or key material.

## Failure and reconnect behavior

Each operation creates one connection attempt and one truthful result. R2 does not automatically retry because a lost response can be an uncertain effect even for operations expected to be read-only. Callers may issue a new read with a new request ID after reconciling the binding and deadline. Revoked/inactive bindings, changed identity or generation, wrong endpoint, certificate or pin failures, malformed or oversized responses, request-ID mismatch, timeout, and connection loss all fail closed.

## Evidence and limitations

Shared JSON fixtures are decoded by the Python oracle and Rust. Rust unit tests cover operation restriction, authority-field absence, strict response fields/status, duplicate keys, size bounds, history validation, binding mismatch, and deadlines. Existing Python Core Link tests retain the disposable mTLS server coverage for certificate rejection, public-key pinning, enrollment, scope, revocation, identity/generation, and transport loss.

The dedicated CI matrix runs Rust debug/release on Windows and Linux and the Python compatibility and Core Link suites on Python 3.12/3.14 on both operating systems. Live host behavior, production credentials, production network communication, launcher integration, and UI replacement remain outside R2 and require later acceptance.
