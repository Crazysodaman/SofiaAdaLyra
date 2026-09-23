# PKG-INTERACT: finite closure gates

## Verified Windows evidence

- At `f126521`, Sparks reported **67 focused tests passed** and a supervised real-Qwen disposable probe with a relevant clarification and synthetic boundary enforcement.
- At `01f52ae`, Sparks reported **97 focused tests passed in 81.60 seconds**. The actual application and installed `qwen3:14b` ran against an independent temporary SQLite database: a declarative hug offer produced a `clarify` choice and avatar-scene question; the narrow `Could I hug you?` route returned an avatar-versus-real-world clarification without inference; synthetic, source-attested no-hugs policy blocked both forms. Four turns used **two provider calls total**, and Windows temporary cleanup succeeded. The first Qwen question was slightly circular, and these cases do not prove broad conversational quality or consent.
- On the SAME `01f52ae` checkout, `python -m pytest -q -x` stopped at **1 failed, 1337 passed in 2416.25 seconds**. The sole reported failure is in the *pre-existing locally modified* uncommitted `test/test_ollama_generation_contract.py::test_ollama_generation_configuration_is_translated`: it constructs `ProviderConfiguration(context_size=18000)` but expects `options['num_ctx'] == 32768`. The provider passes through configured `context_size` to `num_ctx`, and the committed test constructs and expects `32768`. **Do not overwrite the user's local edit or change provider/model settings to mask this mismatch.** Because `-x` stopped at this test, later cases remain unchecked. The complete regression gate is NOT green.
- GitHub reports draft PR #2 `mergeable=false`. The `main` branch and feature branch have diverged: feature is **267 commits ahead and 55 behind** as of this comparison. This is a merge-review blocker; the status alone does not identify individual conflicting files. No rebase, merge or force push has been performed.

## Next gates (in order)

1. **Complete test coverage without discarding local work:** run all tests except the exact mismatched local test using `python -m pytest -q -x --deselect=test/test_ollama_generation_contract.py::test_ollama_generation_configuration_is_translated`. This qualified run is not an unqualified full pass. Preserve the entire modified file and its second test; reconcile the user's intended `18000` versus `32768` independently before any edit.
2. **Audit additional concurrency and policy integrity:** restart/replay, other two-writer orderings, source-attestation tampering, boundary scopes, privacy and authentication/tool authorization. Existing tests include one two-connection stop-before-release ordering, not exhaustive concurrency proof.
3. **Review PR scope and actual main conflicts:** examine overlapping files and plan reconciliation of the 55 newer base commits without silently merging, rebasing, resetting or overwriting another package. Review any optional interaction-schema migration before production use.
4. **Human acceptance and separate merge approval:** Sparks reviews the real dialogue, explicitly accepts PKG-INTERACT, and separately authorizes any merge. PR #2 stays draft and `main` unchanged until then.

## Safety and scope

The exact declarative offer and narrow reviewed-question routes are **opt-in off by default**. Synthetic boundary evidence is test-only. Never use the disposable probe on production `state/sofia.db`, enable `SOFIA_INTERACT_STAGED_OFFERS` globally, migrate production schema without review, infer real consent or contact, or alter the installed model settings. Preserve the modified database, timestamped backup, independent Ollama test edit, CORE PR #1 and RUN PR #3. Discord/PKG-NET, reliable 24/7 runtime, actual avatar animation and physical sensors remain separate packages.
