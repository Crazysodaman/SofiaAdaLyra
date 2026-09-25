# PKG-NET | readiness roadmap

**Accepted gate: 2026-09-24 | PR #11 merged to main.**

## Accepted implementation

The durable local admission gate is integrated on `main`. It now provides durable node identity enrollment/retirement, exact durable endpoint approval, durable exact-scope authorization and per-node grant revocation, durable replay/audit state, identity-bound and endpoint-bound gateways, coordinated retirement, and a `DurableRemoteControl` composition root around an injected authenticated transport.

Evidence recorded at acceptance: **57/57 focused PKG-NET tests passed** on the user's Windows Python 3.12 environment, followed by a reported **full repository pytest pass**.

This acceptance does **not** claim that a public-key fingerprint alone authenticates a peer. The actual production transport remains a separate boundary.

## Remaining gates

1. Implement a standard, peer-authenticated production transport. Do not invent custom cryptography.
2. Enforce real destination/network controls at the connector boundary, including DNS/address handling, TLS hostname/certificate validation, proxy behavior and redirects.
3. Add audited key rotation and stronger retirement/decommission journal semantics where multi-database operations must recover safely.
4. Wire the production composition root and run local-to-Artemis authenticated end-to-end operations with replay, revocation, outage and restart negatives.
5. Preserve the already accepted narrow Discord transport scope and keep general web/search separately gated until RUN/OPS prerequisites are met.

**Current state:** durable local admission gate accepted and merged. PKG-NET as a whole remains active until production transport and live Artemis acceptance are complete.
