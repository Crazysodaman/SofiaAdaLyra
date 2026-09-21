# PKG-NET | Authenticated, scoped homelab operations

**Branch:** `feature/pkg-net-foundation`, independent from `main` SHA `2141879`. **Status:** roadmap and pure `RemoteGrant` prototype; **no listener, agent, transport, scan or remote action**. Existing CORE/Artemis PR #1 and RUN PR #3 are distinct and must not be overwritten.

## Intended outcome and evidence
Sofía can describe observed machine topology and perform individually authorized, audited operations on enrolled nodes. Existing peer, grant and replay foundations and Artemis VM inventory are starting points, not proof that Artemis has a deployed authenticated agent, GPU or working OpenCode. Treat user-provided topology as reported unless observed and timestamped.

## Slices
1. **N0 inventory and threat model:** inspect the actual NET data models, grant tables, VM/network topology, firewall and transport choices on pinned SHAs. Identify node enrollment, credential storage, trust roots, privilege levels and existing Artemis conflicts.
2. **N1 authenticated enrollment:** provision a stable machine identity and explicit owner-approved enrollment; key rotation, expiration and emergency revocation. Peer names/IPs are labels, not proof of identity. Store secrets outside Git and model prompts.
3. **N2 granular capability gate:** node, actor, operation, target, grant issuer, expiry and replay nonce must match. `src/sofia/package_foundations/net.py` only checks a narrow node/capability/time condition; it is NOT sufficient authorization or integrated code.
4. **N3 read-only first:** probe observed service status, node health and measured resource constraints with timestamps and clear unknown/offline states. Do not claim a different machine has a package just because Venus does.
5. **N4 bounded execution:** separate allowlisted executor per operation, independent timeout, output limits, audit, retry/idempotency and outage handling. No unbounded remote shell, ambient LAN scan or inherited admin token.
6. **N5 deployment/recovery:** safe Artemis service identity, Windows/UNC scope verification, fresh connection and permission checks, offline queue handling without claiming execution and revocation after restart.

## Acceptance and safety
Run `python -m pytest -q -x test/test_pkg_net_foundation.py`; then add auth spoof, replay, expired/revoked/wrong-node tests, network disconnect, bounded-output, credential rotation and safe upgrade cases. Only actual two-host Windows/Artemis observation and an authorized bounded task with result evidence meet live acceptance; simulated transport does not. Record exact SHAs, host versions, timestamps, latency, privilege and rollback. Do not enable a service while Sparks is away. **Dependencies:** CORE/SAFE identity and authorization, ACT bounded work, VERIFY two-machine checks, DEV only for separately approved code operations. A future Discord DM does not grant NET authority. Full-suite and separate PR/merge/deploy approvals remain pending.
