# R2 read-only Rust Core Link client

## Dependency and scope

R2 uses the existing Rust contract foundation. The crate remains a library; no production launcher or UI is replaced. Python owns the canonical binding store and the Python/Tk client remains the fallback.

The client implements only `status` and `conversation.history` for an already-authorized session. It cannot create, select, send, cancel, mutate results, update settings, or invoke modules. It owns no conversation database or state writer.

## Compatibility and authority

The Core Link request/response format is implemented independently from the R1 component envelope. Request JSON has no principal, audience, credential, grant, or scope field. Authority continues to derive from the client certificate enrolled by the Python host. The client checks the selected binding's local and remote Platform IDs, Core identity, exact generation, protocol `1.0`, endpoint path, active state, server hostname, CA chain, and enrolled server public-key pin before accepting a result.

Payload canonical size is limited to 64 KiB. Complete request and response bodies are independently limited to 72 KiB. Requests carry an exact creation time and deadline; expired or not-yet-active requests fail before transport. The client disables redirects and HTTP fallback, requires TLS 1.2 or newer, and returns bounded errors without content or key material.

## Failure and reconnect behavior

Each operation creates one connection attempt and one truthful result. R2 does not automatically retry because a lost response can be an uncertain effect even for operations expected to be read-only. Callers may issue a new read with a new request ID after reconciling the binding and deadline. Revoked/inactive bindings, changed identity or generation, wrong endpoint, certificate or pin failures, malformed or oversized responses, request-ID mismatch, timeout, and connection loss all fail closed.

## Evidence and limitations

Shared JSON fixtures are decoded by the Python oracle and Rust. Rust unit tests cover operation restriction, authority-field absence, strict response fields/status, duplicate keys, size bounds, history validation, binding mismatch, and deadlines. Existing Python Core Link tests retain the disposable mTLS server coverage for certificate rejection, public-key pinning, enrollment, scope, revocation, identity/generation, and transport loss.

The dedicated CI matrix runs Rust debug/release on Windows and Linux and the Python compatibility and Core Link suites on Python 3.12/3.14 on both operating systems. Live host behavior, production credentials, production network communication, launcher integration, and UI replacement remain outside R2 and require later acceptance.


## Canonical Platform status adapter

`PlatformStatusClient` admits status reads through the installed Core-free
Platform authority module, `sofia.platform.core_link.rust_authority`. It invokes
a trusted absolute Python executable in isolated mode with a fixed module,
bounded output, a monotonic deadline and exact per-request correlation. The
executable, binding-store path, minimum revision and endpoint/credential
references are operator configuration; they must never come from a renderer or
model. No second principal store, binding registry or enrollment path is added.

The Python adapter reuses `CoreLinkBindingStore.require_current_selected`,
requires ACTIVE selection, exact binding/store revisions, current SDK version
and `status.read`, and returns routing metadata without credential bytes. It
never selects, activates or enrolls a binding. The Rust adapter checks that
metadata against the configured endpoint/credential references and resolves TLS
material through the existing secret-owner callback only after admission.
Canonical selection is re-read before dispatch and again before response release;
failed authority reads never substitute a previous snapshot. A live-process high
water mark rejects rollback after a newer revision, including a denial, has been
observed. Restart rollback protection still depends on the independently trusted
minimum revision supplied by the Platform owner.

The canonical JSON store now rejects duplicate keys and bounds reads/writes to
2 MiB. Its existing 128-binding bound is also enforced before writes so an
addition cannot publish a file the next read rejects. Existing v1 serialization
and owner mutation APIs are retained.

The new diagnostic-feature probe exercises the production status adapter against
a disposable mTLS host and installed SDK/Platform-only Python environment.
Active reads, inactive/insufficient-scope denial before key resolution, wrong
host pin rejection and in-flight revocation are covered without logging status
content. This is not live-host, native-tray or complete R2/R3 acceptance. The
adapter exposes status only; it cannot send conversation, change settings,
create a Core or become a canonical writer.
