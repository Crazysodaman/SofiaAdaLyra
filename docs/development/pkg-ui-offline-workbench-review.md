# PKG-UI · Offline workbench slice and review ledger

**Status:** isolated headless code committed on `feature/pkg-ui-workbench-offline`, not merged, integrated, rendered or deployed. This file belongs to UI, not Discord. The root roadmap remains authoritative until the draft roadmap expansion is reconciled.

## Prepared code

- `src/sofia/workbench/model.py` and `__init__.py`: owner-scoped in-memory page, sticky-note, notebook, binder and book records; ideas/reflections require stable source IDs; candidate/reviewed/rejected/superseded states; explicit presentation; optimistic revision and operation-ID replay handling; validated snapshot/restore. No automatic disclosure of unpresented private entries.
- `test/test_workbench_objects.py`: focused offline cases for kinds, source/revision integrity, access denial, restore corruption, archival, correction and presentation.

**Verification:** source and tests were run together with the independently prepared AVATAR files in a separate Python 3.13.5 / pytest 9.0.2 workspace using `PYTHONPATH=src`: **96 passed** across three files (workbench 38, wardrobe and scene 58). These are fixture-level results from the staged equivalent files, not a GitHub CI or Windows test of this branch. GitHub blob hashes for `model.py` and `test_workbench_objects.py` were compared to the tested bundle and matched. Run `python -m pytest -q test/test_workbench_objects.py` on this branch as an independent checkout and record its pinned SHA before approval.

## Review when UI is reached

1. Authenticate the owner at the real host and never accept actor IDs from an LLM, user text or arbitrary API payload. `owner_id` comparison alone is **not authentication**. Only owner-authorized, explicitly presented entries may reach a shared/display surface. A private idea's existence, title, timestamp and previews may themselves be sensitive.
2. Bind `source_ids` to actually existing, scope-approved MEM original event/journal IDs. Provide transactional encrypted/atomic persistence, version migrations, deletion/retention and restore on disposable data. The current class is in-memory and its plain snapshot is not a security boundary.
3. Reconcile UI events with INTERACT PR #2's normalized actor/action and CORE/SAFE authority. Reuse REL/ACT reflection records; do not create a duplicate emotion journal or new thought generator. Explicit presentation is a policy decision outside model text, not evidence that a thought is factual.
4. Implement the *actual* accessible text box, book/binder/page view, private shelf, client-state machine, drafts and search of authorized material. Keep chat usable without renderer/voice/Discord and prioritize foreground first-token response on measured hardware.
5. The avatar may manipulate only approved virtual-workbench action IDs after a trusted receipt. A drawn hand, model-produced claim or simulated receipt is not an executed action. Test duplicate, crash, cancellation and renderer-off fallback.
6. Review accessibility, reduced motion, privacy-safe thumbnails, public screenshots, structured logging and future audience isolation before any second-user expansion. No general web search before Discord and verified RUN.

**Acceptance still not run:** pinned branch Windows 3.12.9 tests; integration with actual conversation/MEM/INTERACT and full pytest; a real text client, renderer and UI action receipt; live personality/latency/accessibility and recovery checks. No changes to protected identity, Constitution, production database or deployments. Rollback: omit/revert this branch's added files; existing stores remain untouched.
