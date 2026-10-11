# V18 main-only workstream coordination contract

**Proposed by Workstream 1, 2026-10-11.** Source policy for avoiding unnecessary main-branch write collisions across concurrent development chats. This is a coordination document, not a lock manager and not evidence that other sessions have adopted it.

## Work ownership by assigned execution phases

| Workstream | Phases | Primary subject ownership |
|---|---|---|
| WS1 | 00, 01, 02 | Canonical architectural/SAVE authority contracts, Windows build/release entrypoints, operator permission and stop controls, task/CI evidence taxonomy |
| WS2 | 03, 04, 05, 06 | Canonical database migration/recovery, model-independent survival, cross-device conversation and memory |
| WS3 | 07, 08, 09, 10 | Archive stewardship, emotions/companion autonomy, LIFE/GOALS, skill use and integration |
| WS4 | 11, 12, 13, 14, 15, 16 | Model/resource selection, screen input, isolated Hephaestus, training lab and NEURO science |

Ownership above is about **change intent**. A production file can be shared by several subsystems; inspect its existing callers before editing. No workstream may silently alter another's security policy or release contract to make its feature pass.

## Shared files: serialization instead of concurrent blind writes

1. Prefer workstream-specific evidence documents for daily audits and source commits. For example, `docs/development/v18-workstream1-*.md`, distinct WS2/WS3/WS4 reports, rather than competing updates to `ROADMAP.md`.
2. Treat `ROADMAP.md` and `docs/development/v18-task-evidence.json` as **serialized merge artifacts**. WS1 proposes to reconcile these from source and other workstreams' evidence; other workstreams should publish source commits and per-workstream evidence first. This convention needs to be read by each workstream; no automatic protection is installed.
3. If a shared source path changed between reading and committing, reread the latest `main` content and reapply only the intended hunk. On HTTP 409, never force push, overwrite or reset somebody else's changes.
4. Source reports must distinguish `unassessed`, `partial_wiring`, `code_present_unverified` and accepted test evidence. Unknown or missing test receipts cannot become a pass.
5. A workstream must not set a task to `accepted` solely because it authored tests or saw an existing method. Use exact code/revision evidence, then owner-requested focused/CI/live acceptance.

## Production-first bounded batch

- **Batch A: audit** an assigned group once, record exact current caller, authoritative writer, context/permissions, and missing production sink.
- **Batch B: implement** related source owners in one reviewable coherent commit or coordinated file edits. No stubs, shadow implementations or competing SQLite owners.
- **Batch C: author** targeted regression source and state the deferred execution gate. Never suppress failing selectors or weaken a safety check.
- **Batch D: reconcile** evidence and report each source-complete package, plus blocked owner decisions.
- User has requested **main only**, **testing at final campaign**, **no automatic Venus/Artemis host changes**, and **no unapproved canonical writer migration**. Preserve these constraints.
- Workstream 1's first consolidated task triage is `docs/development/v18-workstream1-consolidated-audit-queue-2026-10-11.md`; it is a candidate file map, not a pass or proof of code gaps.

## Cross-workstream review rule

Before changing `src/sofia/safe/*`, `src/sofia/state/*`, production composition/startup code, CI/release gates or an Artemis/Hephaestus provisioning boundary, inspect the current `main` authoritative owner and any already-merged sibling change. Request a design decision from the owner only if no safe default exists. Testing remains deferred, but static source/security review is never optional.
