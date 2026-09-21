# PKG-NET | branch readiness roadmap

**2026-09-21 | draft PR #11 | baseline head `04efbcac15d9ba2886f59647929762fb384d12ac` before this note.** Read `pkg-net-discord-route-review.md` and the original distributed-homelab roadmap contract. **Discord network connectivity now; general browsing/search only after Discord D0–D4 and verified RUN 24/7.** The broader authenticated Artemis transport is a separate NET acceptance stage, not secretly included in Discord-only allowlisting.

## Prepared and limits

Disabled-by-default lexical Discord REST/Gateway URL classifier; 29 focused tests passed on equivalent isolated source (72 when combined with unrelated MEM/VERIFY fixtures). URL shape inspection is **not** a firewall, trusted host identity, DNS/IP binding, redirect defense, TLS validation or access grant. No live outbound traffic occurred.

## Work/test gates

1. Pin checkout and inspect existing peer enrollment, grants, capability inventory, replay ledger and transport; avoid a second authorization system. Audit documented Discord REST/Gateway destinations and required paths against current provider behavior at review time.
2. At trusted connector boundary, constrain scheme, exact host, DNS result/IP, TLS hostname/certificate, proxy/redirect and outbound firewall policy; disable redirects and arbitrary DNS rebinding. Keep network grants scoped to a bot/session and needed Discord operations, expire/revoke/audit; no generic HTTP client or search API in this phase.
3. Integrate with INTERACT + SAFE + PR #5 verified Sparks-only private DM gate; independently validate gateway origin. Deny other user, guild/group, bot/webhook, stale session, forged metadata, redirect/lookalike domains and revoke mid-connection.
4. Focused tests on actual branch and Windows, then disposable integration with fake DNS/proxy/TLS/network outage; real Discord reachability, reconnect, retry and authenticated send/receive are **distinct live D0–D4 gates**. Record precise endpoints and redacted logs, never secrets.
5. Separately plan the original NET outcome: authenticated Artemis agent and peer enrollment, node/capability/operation/expiry grants, local-to-Artemis end-to-end execution, replay denial after restart, revocation, outage and audited results. No unrestricted shell, ambient network scan, presumed remote GPU or service install.

## Review decisions

Which deployment host, bot identity and approved egress route; actual Windows firewall/Cloudflare/proxy/DNS topology; required Discord endpoint changes; Artemis identity/transport/service permissions and safe task allowlist. Do **not** infer credentials, actual user Discord ID or production topology from example fixtures.

**Status:** offline route classifier only; actual branch checkout/Windows/CI/full suite/Discord and Artemis live transport = NOT RUN. No internet search, merge, deployment or production state changes.
