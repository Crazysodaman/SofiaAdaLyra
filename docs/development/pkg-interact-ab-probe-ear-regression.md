# INTERACT A/B probe: September 21 Windows regression

**Status: candidate repair committed; Windows tests and real-model A/B still pending.**

## Observed evidence

At `682fb79`, Sparks pulled the feature branch in Windows PowerShell. The working tree had three pre-existing entries: modified `state/sofia.db`, modified `test/test_ollama_generation_contract.py`, and untracked `state/sofia.pre-interact-20260920-172910.db`. The focused pytest run stopped with **1 failed, 5 passed** in `test_interaction_ab_probe.py::test_probe_constructs_static_context_with_identical_synthetic_user_input[ear-*pats your ear*]`. The coordinated interaction/application run stopped on that same failure before other tests could run. Neither run establishes any further result, nor was an A/B Ollama output reported.

## Diagnosis and correction

The probe uses the exact earlier live text `*pats your ear*`. The canonical grammar resolves `left-ear`, `right-ear`, and `ears`, but an unspecified singular `ear` cannot be assigned a side without guessing. The normal engine returns a `clarify` decision with no canonical region. The synthetic A/B constructor incorrectly required `status == 'accepted'` and raised before making its comparison requests. In `ab_probe.py` the constructor now allows `accepted` **or** `clarify`, but rejects `None` and other statuses; both A and B preserve the original synthetic user message. `test_interaction_ab_probe.py` asserts that the ambiguous input yields `policy_status: clarify`, null region and gesture projection, while a separate explicitly left-sided gesture resolves to `left-ear` and is accepted. Neither code nor tests weaken the real parser, alter the stop ledger, or represent an ambiguous gesture as completed.

## Next Windows gates

Exit any running CLI. Do not reset/stash/discard the three existing local changes or alter the configured DB/backup. Pull `feature/pkg-interact-shared-engine` with fast-forward only. Pin `git log -1 --oneline`. Run:

```powershell
python -m pytest -q -x test/test_interaction_ab_probe.py test/test_interaction_context_hygiene.py test/test_interaction_expanded_service.py test/test_interaction_live_discussion.py test/test_interaction_live_stop_repetition.py
```

If passing, run the coordinated interaction/application suite again, then `python -m sofia.interaction.ab_probe` with the configured Ollama model, and inspect both outputs for each case. The probe is synthetic and does not use production history or SQLite; it cannot by itself accept live character quality. Follow with supervised live CLI review and only then full pytest, security/privacy review, and separately approved merge. PR #2 remains draft and unmerged.
