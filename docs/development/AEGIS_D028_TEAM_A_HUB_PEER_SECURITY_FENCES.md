# AG-D028 / Team A | Hub and peer security fences (D028-00/03/04)

**Status: DRAFT CONTRACT INPUT, NOT IMPLEMENTED OR SIGNED OFF.** This is an addendum to
[Team A's one broker request/response candidate](AEGIS_D028_TEAM_A_AUTHENTICATED_LIBRARY_CONTRACT_PROPOSAL.md),
not a second IPC or public HTTP owner-auth mechanism. Source: draft #248,
issue #250, LIB-03/07/08/10/13/15. **No listener or package effect is enabled by this document.**

## Independent evidence chain (in order)

1. **Native service**: local caller uses the existing kernel peer/Windows token
   transport of #241. Remote Hub/peer requests require an independently
   authenticated encrypted transport with *mutual* pinned Platform service
   identities. A remote IP, DNS name, mDNS response, self-advertised
   certificate, Hub hostname or client-supplied principal field is never
   enrollment. No remote listener defaults to enabled. There is no shared
   owner secret delivered to Hub or peer.
2. **Installation identity**: pin the target installation's current canonical
   UUID, public-key fingerprint and RUN generation. Distinguish target
   Platform ID, logical Library ID, current primary catalog epoch, optional
   replica ID and source Platform ID; never alias to Core ID or display name.
   A future replica serves only a verified immutable snapshot, and cannot
   mutate primary catalog or authorize promotion. Owner-approved manual
   promotion must prove old-primary fencing first. No automatic failover.
3. **Owner proof**: use ONLY the Platform-local SAFE owner's existing exact,
   unconsumed, authenticated approval / currently valid standing grant as
   defined by Team A's canonical authority. Hub does not approve anything.
   Bind the host-bound principal + audience, operation, source+target
   installation UUID, artifact digest, data/license class, expected RUN
   generation and catalog revision, observed expiry, and any byte quota.
   Re-read current STOP and grant/credential version at the boundary.
4. **Signed publisher trust**: inspect the preconfigured *independent* B1
   publisher root, signature, signer revocation, manifest, release
   revision/antirollback floor, target OS/SDK/ABI, license distribution
   restrictions and exact content/manifest SHA. Hub or peer TLS identity
   authenticates the **sender**, never the artifact publisher.
5. **Transfer**: after both peers' exact enrollment is current, issue a
   target+source+digest+class+deadline+offset+quota scoped transfer permit.
   Prove anti-replay correlation/idempotency per generation. Each bounded
   chunk rechecks STOP/revocation, current source and target enrollment,
   signed manifest expiry, reservation and licensed distribution. A
   resume cursor cannot install or publish. Abort on identity/generation/
   revision changes, missing/overlapping chunks, digest swap, disk
   exhaustion or network interruption. Partial bytes are untrusted.
6. **Recipient completion**: independently reverify full bytes and
   publisher signature, compatible manifest, license, current revocation
   and quota before admitting into **existing local verified artifact cache**
   under Team B's approved storage policy. Source says *sent* or
   *received*, NOT *verified*, *installed* or *active*. Same-identity Core
   state is never copied. Installation requires a **separate** one-time
   governed Team B installer plan and SAFE approval; activation is separate.

## A-owned operation gates (pending B/C/D/E review)

| Operation family | Required current authority | What it may NOT do |
| --- | --- | --- |
| library.catalog/inventory/sources/history snapshot | exact enrolled target+audience; private redacted/read scope; current RUN and STOP | expose owner secrets, arbitrary paths, local Core contents or attest install from Hub |
| library.plan.acquire | read + explicit target and signed source/manifest dependency preview | enqueue transfer, bypass license/compatibility or install |
| library.acquire / transfer.cancel / verify | scoped acquisition or cancellation approval; manifest digest, allowed sender+receiver, expiry/quota | activate a Core, broaden sources or convert partial cache to verified |
| library.hub.offer / peer.fetch | BOTH authenticated enrolled platforms; per-peer artifact+data-class grant; signed distributability | serve another host's protected state or let LAN location imply trust |
| library.pin/unpin/retire.cache | dedicated retention approval; current pin/rollback graph + revision; dry-run impact | GC a live or rollback-pinned digest |
| library.install.execute / activate | **Team B/D existing** signed B1 installer/lifecycle and separately authenticated owner effect | execute via Hub, transfer token, source catalog, UI or SDK alone |
| library primary/replica promotion | separate explicit one-shot owner approval and old primary fenced | self-promote after network partition, Core crash or silent failover |

Read-only D028 previews should not gain new `platform.management.read`
standing scope via a wildcard. Add explicit enumerated Platform-local SAFE
capabilities **only after** a versioned A/B/C/D/E contract agreement, with
conservative defaults: unspecified family denies and no implicit Internet.

## Independent negative tests required (Team E LIB-03/07/08/10/13/15)

- Unknown, expired, rotated, revoked or forged peer identity; same IP/name but
  different key; wrong TLS audience; wrong primary epoch; replayed correlation.
- Unenrolled Windows SID / Linux GID even when transport can connect; local
  group membership alone is not an owner grant; STOP during indexed listing
  and during every transfer chunk.
- Wrong publisher root, valid SHA from untrusted signer, revoked signer,
  downgraded catalog, wrong OS/ABI or license non-redistributable.
- Core/Platform private SQLite, secrets, credentials, tokens, Constitution,
  memory, protected state path or model weights with no distribution rights.
- Resume token replay on other host/source/revision, partial digest and
  overlapping/out-of-range chunk, quota and cancellation/restart races.
- Hub+Core co-located but Core dead: Hub only continues if its Platform
  current RUN and owner-approved role still hold. Aegis Platform shutdown
  stops Hub. Dual-primary or replica writes always denied.
- Signed installer negative proofs from B; four independently pinned signed
  installed-host receipts from E. No 39th acceptance row or claimed LIB PASS.

## Blocking ownership decisions

**A**: same canonical broker, OS/mTLS peer identity, SAFE current proof and
response protocol, generation/revocation, transport-agnostic denies.
**B**: single B1 installer, trusted publisher roots, signed offline seed,
CAS/GC and native enrolled operator ACL/GID provisioning.
**C**: exact read-only status projections, UNKNOWN versus installed/active,
reconnect and revision/freshness UI fences.
**D**: signed component dependency/ABI/licensing, recipient-side verification,
real Core/module lifecycle only through approved existing executor.
**E**: exact-SHA independent four-host signed negative evidence, LIB-01–16.

Never use a second signer, shared writer, Hub-controlled permission authority,
Internet fallback, automatic Core activation, production deployment or main
merge. **Contract status remains unapproved until explicit coordinated signoff.**
