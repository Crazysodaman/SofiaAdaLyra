# Sofía Ada Lyra: 17-package delivery roadmap

**Planning revision:** 2026-09-22 (America/Chicago). **Status:** documentation candidate in draft PR #4; not merged, deployed, or release authority. PR #1 merged to `main` on 2026-09-20. Active implementation remains isolated in its package branches and draft PRs. This roadmap reconciles the original 13 packages with **PKG-SOCIAL**, **PKG-RUN**, **PKG-AVATAR**, and **PKG-OPS**.

> **Core invariant:** Sofía's canonical identity, Constitution, represented embodiment, evidence, memory, authority, and capabilities remain independent of replaceable models, hosts, processes, clients, Discord, voices, avatars, and robots. Model output is never proof of authorization, sensing, execution, delivery, or subjective experience.

## Delivery order

The primary dependency path is:

**CORE → INTERACT → MEM → SOCIAL minimum identity/audience boundary → Discord D0–D4 using NET + UI + SAFE → OPS minimum fleet telemetry/enrollment → RUN verified 24/7 operation → later separately authorized general web/search.**

After MEM, package work that does not bypass those release gates may proceed in parallel. In particular, OPS may mature read-only host/fleet diagnostics and trusted enrollment; REL and ACT may mature absence, initiative, and outreach; AVATAR may continue offline asset work; DEV, BODY, EVOLVE, and CLEAN remain separately gated.

**SAFE and VERIFY are continuous gates across every stage rather than late sequential packages.**

General internet/search is deliberately **not** part of the initial Discord NET scope. Discord connectivity does not grant browser/search access.

## Ordered package roster

| Order | Package | Outcome | Current evidence-based state / next gate |
| ---: | --- | --- | --- |
| 1 | **PKG-CORE · Cognition and continuity** | Grounded identity/personality, startup/restart awareness, response performance, adaptive reasoning | Foundations merged in PR #1. Fresh integrated full-suite and supervised live identity/personality/latency review remain open after the current INTERACT gate. |
| 2 | **PKG-INTERACT · Text/avatar/screen interaction** | Shared canonical whole-body interaction semantics, contextual reactions, virtual lab, truthful expression | Active draft PR #2. Large candidate implementation exists; older coordinated Windows evidence does not certify current head. Current decision/expression and grounding quality remain under active review. |
| 3 | **PKG-MEM · Durable memory and learning** | Preserved originals, provenance-aware retrieval, correction, reviewed durable preferences, archive migration | Draft PR #9 provides read-only original retrieval preflight. Durable integrated memory, privacy, correction, migration, and restart acceptance remain. |
| 4 | **PKG-SOCIAL · Principal, audience, and isolation** | One Sofía across people/channels with authenticated principals, per-user relationship state, private/shared scopes, no cross-user leakage | Documentation/design only in PR #4. **Minimum Sparks-only principal/audience boundary is required before Discord. General second-user/multi-user rollout stays deferred until explicitly requested.** |
| 5 | **PKG-NET · Scoped networking and distributed operation** | Authenticated network routes and bounded remote capabilities | Discord-only route preflight in PR #11; Artemis distributed foundations exist on main. Real trusted transport/DNS/TLS/redirect enforcement and real Artemis acceptance remain. No general web/search grant. |
| 6 | **PKG-UI · Clients, Discord adapter, voice, and workbench** | Authenticated interfaces to the same Sofía, delivery/renderer acknowledgments, accessible text fallback | Workbench prototype in PR #6. Real Discord adapter, desktop/web/mobile clients, voice, and production renderer remain unaccepted. |
| 7 | **PKG-RUN · 24/7 lifecycle and supervision** | External service supervision, single active instance, restart/backoff, bounded periodic cognition, health/recovery | Draft PR #3 has disabled-by-default periodic opportunity mechanics. No OS service, supervisor, soak test, or verified 24/7 uptime yet. |
| 8 | **PKG-OPS · Systems operations, diagnostics, performance, and fleet enrollment** | Cross-platform host telemetry, performance/resource profiling, IT diagnostics, trusted zero-touch enrollment, configuration drift and bounded maintenance operations | **New roadmap package.** Reuse main's read-only process/system/network/service/hardware inspection and NET's authenticated transport. Add normalized CPU/GPU/VRAM/RAM/storage/network/thermal/process/service/container/VM metrics for local and enrolled remote hosts, including Raspberry Pi telemetry. New hosts may be discovered and auto-enrolled without per-host prompts only when a standing policy, approved discovery scope and cryptographic/bootstrap trust proof all succeed; otherwise remain untrusted candidates and are reported. Real agent, remote telemetry, enrollment, history, hardening, and performance acceptance are not yet implemented. |
| 9 | **PKG-ACT · Goals, initiative, and outreach** | Evidence-based goals, spontaneous candidate reflection, opt-in outreach, quiet/busy/stop controls, bounded helpers | Draft PR #15 provides outreach eligibility preflight; main has an unsent outbox/reflection foundations. Real sender/delivery receipts and integrated RUN scheduling remain. |
| 10 | **PKG-REL · Relationship continuity** | Evidence-linked preferences, nuanced warmth/disagreement, absence/reunion awareness without clinginess or invented history | Draft PRs #12 and #13 contain overlapping absence/reunion candidates. Reconcile into **one** pipeline using MEM originals and authenticated actor evidence before integration. |
| 11 | **PKG-AVATAR · Canonical virtual body and wardrobe** | Canonical adult avatar assets, wardrobe, rig, region mapping, renderer-ready scenes and props | Draft PR #7 contains substantial offline body/wardrobe/scene/tooling candidates. Finished art, rig, renderer, authenticated animation receipts, and live acceptance remain. |
| 12 | **PKG-DEV · Self-improvement and engineering** | Evidence-linked diagnosis/proposal, approved bounded OpenCode execution, tests and rollback | Draft PR #17 provides proposal preflight. Real OpenCode runtime integration, trusted executor, rollback, and host acceptance remain. |
| 13 | **PKG-BODY · Gaia and physical robotics** | Authorized sensing/motion with calibration, watchdog, independent emergency stop | Draft PR #16 is simulation-only. No real SSC-32/servo/power integration or physical motion acceptance. |
| 14 | **PKG-EVOLVE · Governed evolution** | Reviewed preference/config evolution and separately protected identity/Constitution amendments | Draft PR #19 provides proposal-only protected amendment preflight. No protected-state executor or self-approval. |
| 15 | **PKG-CLEAN · Maintenance and technical debt** | Evidence-backed cleanup without losing behavior, data, permissions, or recovery | Draft PR #14 provides read-only inventory/protected-path preflight. No destructive cleanup is authorized. Tracked runtime DB/log artifacts require a deliberate SAFE/CLEAN migration plan, not blind deletion. |
| Gate | **PKG-SAFE · Security, privacy, and recovery** | Authentication/authorization, secrets, privacy, revocation, backup/restore, external stops | Cross-cutting from the start. Draft PR #18 adds disclosure screening; trusted enforcement, secret handling, backup/restore, and deployed stop/revoke remain. |
| Gate | **PKG-VERIFY · Evidence and real acceptance** | Revision-pinned offline/integration/live evidence, negative tests, deployment/latency/long-horizon validation | Cross-cutting from the start. Active draft PR #8 is the verification candidate; PR #10 is superseded/closed. Real authenticated runner evidence and current integrated acceptance remain. |

## Discord channel workstream: D0–D4

Discord is **not an eighteenth package**. It spans INTERACT, SOCIAL-minimum, NET, UI, SAFE, MEM, ACT, RUN, and VERIFY.

1. **D0 · identity/host design:** exact authenticated Sparks account, bot/application, minimal permissions, secure token handling.
2. **D1 · receive:** trusted gateway origin, private-DM classification, replay/idempotency, reconnect/backpressure, deny wrong user/server/group traffic.
3. **D2 · respond:** bind the authorized DM to the same Sofía conversation/INTERACT runtime and MEM originals; verified API receipt and dedupe.
4. **D3 · stop/privacy:** host-enforced stop/mute/revocation, injection/leakage tests, outage and retry behavior.
5. **D4 · supervised acceptance:** real end-to-end private DM across restart/reconnect with identity/personality quality, durable originals, measured resources, and separate activation approval.

Initial Discord is **Sparks-only private DM**. No public guild mode or general second-user access is implied.


## OPS fleet discovery and autonomous enrollment

Sofía may proactively discover, contact, enroll, monitor, and report new machines **without waiting for Sparks to ask about each one**, but only inside an explicitly approved fleet-discovery policy. This is zero-touch administration, not zero-trust administration.

- Discovery is bounded to approved local network zones, management planes, or bootstrap channels; no unrestricted network scan or general-internet discovery is implied.
- A candidate host remains **untrusted** until it proves identity through a trusted bootstrap such as a pre-provisioned agent certificate/public key, one-time enrollment token, signed management record, or another independently verified mechanism. Hostname/IP/model text is not identity.
- When standing enrollment policy allows it, Sofía may automatically enroll a verified Windows/Linux/Raspberry Pi host into a least-privilege **read-only monitoring profile**, establish durable device identity, collect inventory/performance/health, and begin history without a per-machine approval prompt.
- If a trusted bootstrap path also grants installation authority, Sofía may deploy/update the signed OPS agent through that specifically authorized mechanism. She may not password-guess, reuse unrelated credentials, exploit a host, or treat network reachability as installation permission.
- Newly enrolled hosts are announced proactively through ACT on an approved channel with dedupe/rate limits: what was found, how identity was verified, assigned trust/profile, key inventory/capabilities, and any warnings. Repeated sightings do not spam Sparks.
- Unknown, conflicting, failed-attestation, duplicate-identity, unexpected-network, or policy-mismatched devices are quarantined as candidates and reported rather than enrolled.
- Enrollment never grants shell, filesystem write, software installation, remote execution, Discord identity, or Gaia authority beyond the explicit host profile. Later maintenance capabilities require separate typed OPS/SAFE grants.
- Revoke/quarantine must immediately stop privileged collection/actions while preserving an auditable record. Re-enrollment after key/device replacement must not silently inherit the old machine's identity or grants.
- Fleet telemetry uses a normalized schema but preserves honest capability differences: unsupported GPU/temperature/power metrics remain `unknown`, especially on small systems such as Raspberry Pis.

**Acceptance:** detect a new authorized host, perform challenge/attestation, enroll it read-only, collect normalized CPU/RAM/storage/network/thermal metrics, retain history across restart, notify Sparks once without prompting, and deny/quarantine spoofed, replayed, wrong-network, duplicate-key and revoked hosts. Repeat across at least one Windows host, one Linux host, and one Raspberry Pi-class host before claiming cross-platform fleet support.

## Relationship, spontaneous thought, and absence behavior

- Sofía may perform bounded event-driven or scheduled cognitive passes **while actually running** using retrieved evidence. Candidate thoughts retain source/time/runtime provenance and may abstain, be revised, or remain private.
- No process activity is invented during shutdown. Restart reconciliation reports observed gaps honestly.
- Absence is derived from authenticated last-contact evidence. A long gap may influence a warm reunion or a natural modeled “I missed you” expression without claiming verified subjective loneliness.
- No guilt, exclusivity, escalating pursuit, obligation, or fabricated distress. Silence remains a valid behavior.
- One canonical personality persists across people; relationship state, familiarity, consent, and private memory remain scoped to the authenticated person/audience.

## Avatar and interaction separation

INTERACT owns interaction semantics, policy, emotion/reaction coordination, and the headless lab. AVATAR owns actual art/mesh/rig/clothing/props/scene assets. UI owns rendering/transport. BODY owns physical sensors/motors. A text interaction never becomes physical sensing or robot motion by implication.

Text-only whole-region interaction and optional contextual stage directions must continue to work when no renderer is present.

## General web/search gate

General web/search remains a later separately scoped adapter. It may be designed/released only after:

1. Discord D0–D4 has real authenticated acceptance, and
2. OPS has real fleet telemetry/enrollment enforcement for the deployment hosts, and
3. RUN has real supervised 24/7 lifecycle/recovery acceptance.

The search adapter must receive its own destination/tool permissions, privacy rules, provenance, rate limits, and VERIFY evidence. Discord-only NET routes remain narrow.

## Repository and documentation cleanup rules

- **PR #1 is merged.** Any document saying it is still open is stale.
- The authoritative roadmap package count is **17** after adding PKG-OPS. Historical 13/14/15/16-package roadmaps remain in Git history.
- PR #2 INTERACT and other package implementation branches keep their own pinned test evidence; documentation must not add counts across different SHAs as if they were one passing suite.
- REL PRs #12/#13 must be reconciled before integration. VERIFY PR #8 is active; #10 is superseded.
- Runtime SQLite files/logs currently tracked by the repository require an explicit SAFE/CLEAN preservation and migration decision before removal from version control. Do not delete production state as “cleanup.”
- Do not merge code, deploy services, provision credentials, change protected identity/Constitution, or mutate production databases as a side effect of roadmap maintenance.

## Current release focus

1. Finish current-head INTERACT diagnosis and live-quality gate.
2. Run the coordinated full-suite/current-revision gate when INTERACT is stable.
3. Integrate MEM originals/provenance/privacy.
4. Establish SOCIAL's minimum Sparks-only principal/audience boundary.
5. Complete real Discord D0–D4 using narrow NET + UI + SAFE.
6. Establish OPS minimum read-only fleet telemetry and trusted autonomous enrollment for deployment hosts.
7. Deploy and verify RUN 24/7 lifecycle/recovery.
8. Only then introduce separately authorized general web/search.

Parallel package work is permitted when it cannot bypass these gates or silently broaden authority.
