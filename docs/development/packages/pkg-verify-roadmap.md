# PKG-VERIFY | Measured testing, acceptance and operations

**Branch:** `feature/pkg-verify-foundation`, forked from `main` at `2141879`. **Status:** immutable verification-metadata prototype only. Nothing has executed on this branch and its recorded outcomes are NOT test attestations.

## Goal
Provide trustworthy, revision-pinned results across unit, integration, Windows, live Ollama, Artemis network, Discord, voice/avatar and Gaia hardware tests. A green narrow fixture test does not prove an end-to-end feature or natural personality; an apparently fluent model output does not prove a real action.

## Slices
1. **V0 evidence inventory:** collect exact commit, tree/dirty status, command, environment, dependencies, duration, sample inputs and full result, keeping originals and privacy-safe references. Separate CI reports from user-supplied Windows logs and synthetic runs.
2. **V1 provenance schema:** `src/sofia/package_foundations/verify.py` holds only SHA/environment/outcome/ref metadata; independent log signature/source verification is still required. Never invent a pass from metadata or move results across SHAs without explaining differences.
3. **V2 structural suites:** deterministic negative tests, import/order, schema and coverage checks, resource/time budgets, fault injection and mutation/recovery on copied state.
4. **V3 supervised model:** real same-provider A/B with pinned settings, consistent prompts, multiple seeds/trials where supported, full observed replies and measured latency. Human review of distinct personality, grounded history, technical usefulness and model hallucinations is a separate gate.
5. **V4 external systems:** real two-node NET checks, Discord sender/recipient receipts, voice/animation acknowledgments and Gaia bench/hardware E-stop; use stubs for early design only and label them fixtures.
6. **V5 release pipeline:** exact diff and dependency lock, security/privacy/migration review, rollback drill, backup/restore on copies, branch/PR ownership, explicit merge and deployment decisions. Track unresolved tests as `not_run`, never silently skip.
7. **V6 operational follow-through:** health, availability, stop, responsiveness, warning and incident evidence with retention/redaction and user-controlled monitoring, not a surprise always-on daemon.

## Initial verification
Run `python -m pytest -q -x test/test_pkg_verify_foundation.py` and verify the code at that exact SHA. Then build independently audited evidence ingestion, forged-log and truncated-output tests, run matched full-suite checks per branch and supervised live acceptance for the active INTERACT package. Branches forked from `main` cannot inherit INTERACT's 274-pass result or latest compact-context repair. SAFE owns security criteria; individual packages own feature expectations; VERIFY owns honest measurements and release records. No merge or continuous monitoring is activated by this roadmap.
