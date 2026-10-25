# Sofía 2.0 independent module development, Batch 9

**Repository:** `Crazysodaman/SofiaAdaLyra` (`main`). **Date:** 2026-10-25.  
**Status:** ALPHA module-source candidates, not installed, signed, release-accepted, production-wired or approved to execute actions.

## Boundaries and outputs

| Module ID | Capability | Operation profile | Bound (provisional) | Purpose |
| --- | --- | --- | --- | --- |
| MOD-RESEARCH | `research.compare_claim_sources.v1` | ADVISORY | CPU 75 millicores / RAM 48 MiB / GPU 0 | Compare supplied dated claim stances, flag contradictory and old evidence, preserve citation refs. Cannot authenticate, browse or fact-check sources. |
| MOD-BROWSER | `browser.review_navigation_candidates.v1` | ADVISORY | CPU 50 millicores / RAM 32 MiB / GPU 0 | Review pre-supplied HTTPS links against an explicit canonical host allowlist; deny IP literals, local domains, URL credentials and nonstandard ports. No DNS verification or navigation authority. |
| MOD-WORKSHOP | `workshop.review_experiment_plan.v1` | ADVISORY | CPU 75 millicores / RAM 48 MiB / GPU 0 | Check requested disposable VM resource bounds, isolation declaration, step order and destruction review. No VM, host, network, execution, or canonical database access. |
| MOD-PROJECT-FORGE | `project_forge.review_artifact_manifest.v1` | ADVISORY | CPU 75 millicores / RAM 48 MiB / GPU 0 | Check source-supplied artifact digest shape, criteria and review flags; output candidate blockers without running tests, publishing or changing Core goals. |

- All inputs are strictly bounded, timezone-aware, explicitly marked supplied/unverified, and have deterministic freshness checks. Results expose `effect: none` and never prove that external activity occurred.
- Capability registrations use the existing `Capability`/`CapabilityRequest` constructor shape. The isolated tests mirror these shape fields, **not** host services, authenticated SDK admission or a signed Platform gateway.
- Host constraints: Python 3.12+; platform-neutral, no hardware, filesystem, subprocess or network calls. Exclude all network, writable storage and device permissions. Allow only review of Platform-sanitized projections, not arbitrary user-provided privileged evidence.
- **Privacy/retention:** modules persist nothing; no raw source text, auth tokens, prompts, document bodies or confidential artifacts are accepted. No automated publication, email, downloads or execution.
- **Maintainability:** Source-level profile revision 1; provisional support window 0.1.x only; observational health probes to be registered by Platform; fail closed on malformed data; retry 0 for deterministic input failures. Quarantine repeated faulting packages through Platform; exact-revision rollback needs signed package artifacts. Never use source metadata as authority.
- **Workshop edge case:** An internal virtual switch declaration alone does **not** prove isolation. Platform's actual Hephaestus supervisor must verify switch, gateway, NAT, route, host-firewall, snapshot and restore behavior before any provisioning approval. Production Core/DB cannot become an experiment target.
- **Browser edge case:** DNS rebinding, redirect targets, IDNs and credential exfiltration are outside this offline review. Only the Platform browser/network boundary can revalidate DNS/egress targets and grant navigation. Query strings are deliberately refused.
- **Project Forge edge case:** A caller-supplied `test_result: passed` is just a *claim*. A `candidate_ready` item is not a trusted test receipt or delivery authorization.
- **Research edge case:** Source stances and citations are supplied *claims*, not assertions of factual truth. No fabricated source identity verification.

## Integration and operations remaining

1. Reconcile artifact digests and signed module manifest/maintenance profile with the Platform broker and appropriate exact-pinned source revisions.
2. Register capabilities through reviewed, authenticated Platform admission, not direct generic module discovery or an arbitrary descriptor string.
3. Add restricted process/container isolation, resource budget admission, shutdown and fault supervision, unauthorized principal/scope/revocation and malicious cross-module tests.
4. Integrate and verify with existing Platform digital twin, Hephaestus workshop, Project Forge/LIFE, and network/browser SDK routes **without duplicating authority**.
5. Run full repository CI and host acceptance on actual target platforms. Record Release Candidate review only after evidence-based security and fault-injection audit. Never infer Stage/Gate 4 from this source-only test run.

## Verification

Focused test command: `PYTHONPATH=src python -m pytest -q test/test_module_batch9.py`. Tests cover fresh/stale/future timestamps, invalid input, contradictory evidence, URL allowlist bypasses, isolation/readiness caveats, forged completion receipts, deterministic output and CapabilityRequest handler validation. A broader isolated regression can detect module interactions but is not equivalent to CI or deployment.
