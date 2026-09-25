# PKG-NET: Discord-only outbound route preflight and review

**Status:** isolated offline code, not a firewall, live transport, or deployment. Base `main`; general web/search is deliberately out of scope until Discord and real 24/7 RUN acceptance.

## Coded slice

`src/sofia/net/discord_routes.py` supplies a disabled-by-default exact destination classifier for REST `https://discord.com/api/...` and Gateway `wss://gateway.discord.gg/` URLs on default or explicit port 443. It rejects deceptive host suffixes, IP/other hosts, plain HTTP/WS, unrelated paths, non-443 ports, userinfo, fragments and control characters. It cannot grant network access or authenticate traffic.

**Focused test:** `PYTHONPATH=src python -m pytest -q test/test_net_discord_routes.py`. Equivalent code in isolated Python 3.13.5 / pytest 9.0.2: **29 passed**, plus MEM's 23 and VERIFY's 20, **72 combined passed**. GitHub checkout, Windows, CI, real TLS/Discord connection and full suite **not run**.

## Review at package gate

- Validate current Discord endpoint documentation, gateway discovery, API version and actual library redirects. Never assume this short endpoint set covers attachments, OAuth, media/CDN, voice or service-specific hosts; request new exact scopes only as needed and with review.
- Enforce destination at the **actual transport** with pinned purpose, trusted config/issuer, DNS result/address family checks, connection target versus HTTP Host/SNI, TLS certificate validation, proxy environment and redirect blocking or reauthorization. URL string checking **cannot defeat DNS rebinding, proxy bypass, request smuggling or a malicious caller**. Revalidate reconnect and every outbound hop, including websocket upgrades; test negative cases with a controlled local network fixture.
- Reconcile with existing distributed NET capabilities, node/operation/expiry grants and PKG-SAFE rather than creating competing authority. Wire only after the single-user DM gate and authenticated Discord adapter are independently verified. No general HTTP client, browser, web search, arbitrary shell or broad network permission is granted here.
- Release only after bounded real gateway/API checks, revocation, outage/rate-limit/reconnect recovery, secrets handling, traffic audit and coordinated live acceptance. Do not merge or deploy from passing offline unit tests.


## Current branch implementation checkpoint (2026-09-24)

The branch now also contains durable node identity enrollment/retirement, exact durable endpoint approval, durable exact-scope grants and per-node revocation, durable replay/audit reservation, endpoint-bound and identity-bound gateways, coordinated retirement, and a DurableRemoteControl composition root. The complete local admission chain is therefore represented in code while the actual authenticated production transport remains intentionally injected and unimplemented.

The next action is the requested test gate. None of these newer files are claimed passing until Sparks runs the focused branch suite. Real DNS/TLS/proxy enforcement, authenticated Artemis transport, Discord live networking, outage/reconnect acceptance, firewall policy, and RUN 24/7 remain later live/integration gates.
