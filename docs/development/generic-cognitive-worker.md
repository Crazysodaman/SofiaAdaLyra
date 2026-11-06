# Generic cognitive worker boundary

The SDK owns the provider-neutral `CognitiveEngine`, `CognitiveEngineError`,
`LLMProvider` and `LLMProviderError` contracts in `sofia.sdk.cognition_engine`.
Requests and responses continue to use the existing versioned SDK cognition
wire contract. These interfaces grant no owner, tool, identity or state-writer
authority.

The Platform owns provider delegation and the explicit deterministic test
backend in `sofia.platform.core_worker.engines`. Existing Core cognition imports
are aliases to the same classes, preserving exception handling and `isinstance`
behavior for installed integrations. Generic worker module imports and the
`provider` and `test` process backends require no personal Core package.

The `rule` backend remains a legacy personal Core implementation. Selecting it
explicitly loads `sofia.core.cognition.rules` inside the worker; it is unavailable
without that optional package. Its personal behavior is unchanged.

## Verification

The import regression was reproduced before separation with Core imports
blocked. Source and installed-wheel isolation inventories now include the SDK
interfaces and Platform worker modules. Compatibility checks assert legacy
imports retain exact class identity.

Real SDK/Platform-only virtual environments spawn both deterministic and
provider-backed workers with disposable, independently generated identities and
Platform-local operational databases. The probes run in isolated Python mode,
assert the personal Core package is absent, attest the installed runtime digest,
observe a distinct worker PID, exchange SDK messages, verify provider execution
in the parent Platform process, and shut down/release the operational lease.
The existing process suite retains generation, authenticated IPC, revocation,
restart, drain and failure-path coverage. Linux and Windows PR jobs exercise
process behavior and actual component wheel installation.

## Remaining work

This is a dependency separation within the existing process machinery. It does
not implement signed individual Core package installation/activation, durable
approved definition revisions, a generic authoritative personal-state runtime,
private constitution/personality asset admission, remote Fleet transport,
Windows native tray/journal, Companion or Workbench applications. A disposable
worker's operational lease is not production enrollment or permission to become
a canonical personal-state writer. No existing personal identity, constitution,
memory, Fleet state or production service is migrated or activated.
