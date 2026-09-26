# PKG-SAFE | branch readiness roadmap

**2026-09-21 | draft PR #18 | baseline head `4a38e9110d938b2525f612cfe2b9d434a155d172`.** Companion `pkg-safe-disclosure-review.md`, original SAFE contract and constitutional integrity/authority. No model-generated permission becomes an actual grant.

## Existing work / evidence

Source-linked reflection/document disclosure preflight checks exact artifact revision, owner, recipient, time and revoked grant, with private-reflection display denied by default. **35 focused tests passed on equivalent isolated Linux source.** `trusted_actor`/`trusted_grant_origin` are *caller flags*, NOT authentication. `eligible_for_trusted_enforcement` is NOT permission to disclose, send or run anything. No real host auth, Discord, UI audience, backup/restore or Windows full-suite test.

## Work and acceptance gates

1. Reconcile existing authority, grants, replay/audit, Constitution/identity verifier, secrets, persistent state and privacy scopes. Use one verified principal/session at each real entrypoint, Sparks-only DM initially; validate provenance at transport boundary, not model text or an untrusted JSON flag.
2. Implement independently enforced least privilege: exact action/resource/audience/expiry/grant issuer, stop/revoke across queue/renderer/network/robot, replay and time uncertainty denial, audit with redacted content. Distinguish read, share, annotate, message, OS control, robot motion and protected amendment rights; none inherits another.
3. Test private thoughts/notes, object existence, image thumbnails, drafts, cached previews, logs and notification metadata for inadvertent disclosure. Revocation and deletion propagate across MEM/UI/AVATAR/Discord, including offline/restart state. Age-unknown/restricted avatar visibility and body interactions deny by default.
4. Validate backups, encryption/secrets handling, restore on disposable data, corrupt state, failed migrations, independent physical BODY stop and external RUN supervisor; neither software stop nor a model promise replaces hardware isolation.
5. Perform actual current GitHub/Windows focused, security-negative, application and full tests on pinned SHA; test real authenticated DM, renderer and outage scenarios separately when available. Inspect actual permissions and deployment settings, no secret values in PRs.

## Questions at SAFE review

Which trusted identity provider/session boundaries, actual Discord bot identity, recovery/key rotation and deletion/retention policy, screenshot/stream privacy defaults, audit access and approval paths for adult-restricted avatar view and high-impact actions. General multiuser deferred, but the single-account verification must be real.

**Exit:** offline disclosure preflight only; trusted auth/enforcement, backups/recovery and live security acceptance NOT RUN. No credentials, protected file mutation, merge or deployment.
