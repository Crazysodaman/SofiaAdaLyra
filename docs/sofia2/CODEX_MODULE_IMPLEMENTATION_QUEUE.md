# Codex module implementation queue

Snapshot source: `34bb825ce749eff3b11945040508ac7fd736a07d` plus the reviewed changes on
`codex/module-documents`. This queue accounts for all 55 entries in
`MODULE_OWNERSHIP_MATRIX.md`. It is a source audit and work order, not release
certification.

The static optional-module audit observed all 47 optional IDs, unique capability
IDs, parseable module-local source, semantic versions, operation profiles, and
resource declarations. It observed no source or cross-module collisions. That
only supports an **ALPHA** classification: it does not prove signed packaging,
Platform admission, runtime isolation, host health, lifecycle recovery, or an
independent review. The five release modules and three attached components also
have candidate source, but need their parent integration and release evidence.

| Queue | Catalog entries | Observed implementation | Current readiness | Next bounded acceptance work |
| ---: | --- | --- | --- | --- |
| 1 | MOD-DOCUMENTS; MOD-DATA-ANALYTICS; MOD-KNOWLEDGE-LIBRARY; MOD-RESEARCH | Four module-local, effect-free capabilities and focused tests | ALPHA | Preserve source provenance; then expand only reviewed format/retrieval contracts and package each through Platform |
| 2 | MOD-BROWSER; MOD-MEDIA; MOD-COMMUNICATIONS; MOD-PRODUCTIVITY | Four module-local advisory capabilities | ALPHA | Verify untrusted-input handling, audience separation, receipts, cancellation, and provider-unavailable behavior |
| 3 | MOD-IT-HELPDESK; MOD-IT-NETWORK; MOD-IT-SYSTEMS; MOD-IT-OBSERVABILITY | Module-local triage, diagnostics, analysis, and correlation | ALPHA | Prove read-only defaults, stale/unknown observations, redaction, bounded inputs, and target identity |
| 4 | MOD-IT-CONTAINERS; MOD-IT-STORAGE; MOD-IT-DATABASE; MOD-IT-BACKUP-DR | Module-local advisory implementations | ALPHA | Validate effect-free analysis and define separately authorized action/result interfaces without duplicating RUN |
| 5 | MOD-IT-SECURITY; MOD-IT-DEVOPS; MOD-HOMELAB; MOD-REMOTE-ACCESS | Module-local advisory implementations | ALPHA | Verify secrets/ACL redaction, exact host scope, disconnected targets, and no implicit mutation |
| 6 | MOD-CAD; MOD-ENGINEERING; MOD-ELECTRONICS; MOD-3D-PRINT | Module-local simulation/advisory implementations | ALPHA | Check units, numeric bounds, artifact provenance, unsafe-output labeling, and physical-effect separation |
| 7 | MOD-ENERGY; MOD-SENSORS; MOD-SMART-HOME; MOD-HOUSEHOLD | Module-local observation/advisory implementations | ALPHA | Prove device/source identity, freshness/calibration, privacy scope, unknown handling, and zero unapproved effects |
| 8 | MOD-ROBOTICS-GAIA; MOD-TRAINS; MOD-GAMES; MOD-VWORLD | Module-local simulation/advisory implementations | ALPHA | Preserve simulation labels; test STOP/cancellation contracts and keep physical dispatch blocked pending supervised trials |
| 9 | MOD-DEV; MOD-CREATIVE; MOD-PROJECT-FORGE; MOD-FILE-WATCH | Module-local proposal/review implementations | ALPHA | Verify malicious source is data, bounded path scope, artifact receipts, cancellation, and no publication authority |
| 10 | MOD-ML; MOD-GENERALIZATION; MOD-MENTOR; MOD-DIGITAL-TWIN | Module-local evaluation/simulation implementations | ALPHA | Verify train/eval separation, evidence lineage, counterexamples, deterministic replay, and no canonical-memory authority |
| 11 | MOD-VISION; MOD-DESKTOP-ACT; MOD-WORKSHOP; MOD-FINANCE | Module-local review/simulation implementations | ALPHA | Test capture/target scope, private-data minimization, VM isolation, and refusal of unapproved effects/providers |
| 12 | MOD-CALENDAR; MOD-AVATAR3D; MOD-AVATAR-STUDIO | Module-local analysis implementations | ALPHA | Verify provider-unavailable behavior, rig/asset compatibility, private asset scope, and truthful render claims |
| 13 | RM-DESKTOP; RM-DISCORD; RM-AVATAR2D; RM-VOICE | Substantial candidate companion source exists | ALPHA | Audit production entrypoints, audience isolation, process failure, real delivery/render/playback receipts, and package evidence |
| 14 | RM-MOBILE; MOD-INTERACTION; MOD-VTUBER-BRIDGE; MOD-MEMORY-IMPORT | Candidate parent/adapter source exists | ALPHA | Keep attached lifecycle ownership; verify pairing/revocation, renderer receipts, reviewed import candidates, and parent recovery |

## Catalog accounting

- Release modules: 5/5 queued.
- Optional modules: 47/47 queued and statically observed.
- Attached submodule/adapters: 3/3 queued.
- Total: 55/55 accounted for.

## Shared blockers that do not stop module-local work

- Signed immutable package and owner-reviewed package identity.
- Reviewed adapter factory bound to the signed digest.
- Platform compatibility/resource admission and lifecycle records.
- SAFE/RUN principal, audience, approval, STOP, and effect-receipt integration.
- Installed-artifact isolation, restart, update, rollback, and removal evidence.
- Independent security/privacy review and applicable disposable-host or G8 trials.

These blockers belong to the existing Platform owners. Module batches should
continue with validation, deterministic internal behavior, truthful diagnostics,
and package inputs while requesting shared interfaces rather than creating local
authority or lifecycle systems.
