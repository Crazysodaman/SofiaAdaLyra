# INTERACT A/B probe assertion after prompt deduplication

Status: **candidate test repair; Windows rerun pending**. On 2026-09-21, Sparks fast-forwarded the INTERACT branch to `e4562b6`, preserving local `state/sofia.db`, the timestamped database backup and a local edit to `test/test_ollama_generation_contract.py`. Windows `python -m pytest -q -x test/test_conversational_context_projection.py test/test_interaction_ab_probe.py test/test_interaction_expanded_service.py test/test_interaction_live_discussion.py` stopped with **1 failed, 6 passed**. The failing parametrized ear case in `test_interaction_ab_probe.py` required the literal `CURRENT-TURN EXPRESSION PRIORITY`, the block deliberately removed from the compact assembler to avoid repeating the personality guide. The preceding compact-assembler tests passed. This does not establish that the model's replies improved.

The feature-branch test-only patch at `e52f180` replaces the stale positive assertion with negative assertion for the removed heading and requires `PERSONALITY EXPRESSION BOUNDARY` exactly once. Existing checks still require the bounded constitutional projection, unchanged synthetic user messages, ear-region clarification without inventing a side, offered-action and hypothetical nonexecution evidence, and absence of a test database. The live engine, model configuration, Constitution and user's state files are unchanged by this test patch.

## Gates

1. Close Sofía and fast-forward pull `feature/pkg-interact-shared-engine` without resetting, stashing or cleaning existing local files.
2. Run the four-file focused Windows command above, stop at its first traceback if red.
3. If green, rerun `Get-ChildItem .\test -Filter 'test_interaction_*.py' -File` plus `test/test_affection_cue_phrasings.py` and `test/test_application.py` under `python -m pytest -q -x`. The **274 coordinated passes at `45d8b67`** predate the prompt-deduplication revision and do not verify this SHA.
4. Then run the synthetic A/B comparison if useful, and a supervised separate-turn live CLI review. Check short natural non-repetitive reactions, accurate offer-versus-action handling, truthful hypothetical history, and Windows PowerShell `sc.exe` versus `sc` correctness. Prompt deduplication alone is not live acceptance.
5. Fresh full suite, CORE/SAFE projection review and separately approved merge are later gates. PR #2 stays draft. No production SQLite, backup, `main`, Discord worker, or unrelated branch changed by these commits.
