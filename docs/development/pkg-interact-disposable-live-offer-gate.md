# PKG-INTERACT: supervised disposable real-application gate

## Verified Windows evidence at `f126521`

Sparks reported the formerly failing atomic test **1 passed**, then the focused regression suite **67 passed**, and the disposable real application/Qwen probe completed. Qwen selected `clarify` and asked whether the user meant a warm virtual embrace or wished to express something through the offer. No heuristic findings were printed. A **SYNTHETIC** source-attested no-hugs boundary blocked the next identical offer with no additional provider calls. Temporary SQLite cleanup succeeded. This is one human-readable supervised sample, not a guarantee of future Qwen quality. Earlier `62ac46e` produced an accept/refusal mismatch and a failed cleanup; `c7ad0ab` produced a redirect masquerading as clarification. Those regressions remain.

## New phrase candidate AFTER that verified run, UNTESTED on Windows

The opt-in scope adds an independently reviewed **question clarification**, not another avatar-action grammar rule: `Could I hug you?`, `Can I hug you?`, `May I hug you?`, and their exact `give you a hug` forms, case-insensitive. A question does **not** establish that its referent is avatar fiction versus real contact, or that Sofía accepts. The host saves the original question, checks independently source-attested boundaries/stops, and atomically saves a short disambiguation question **without calling Qwen or granting permission**. Existing ordinary action grammar still rejects question marks. Hypotheticals, multi-action text, actual sensor questions and other unreviewed wording continue on the existing conversation path. This fixed clarification is narrow and not a general personality/semantic language solution. The original `I ask to hug you` Qwen route is unchanged.

## Scope and prerequisites

This is **not a production migration, release or general gesture test**. The application uses existing installed `qwen3:14b` and generation settings, real identity/personality/constitution/avatar files and real application orchestration, but a fresh temporary SQLite database and temporary filesystem root. Invoke only with `--run-disposable`; opt-in exists only in this process. No real chat or personal preference is loaded.

With normal Sofía closed, `.venv` active, `feature/pkg-interact-shared-engine` selected and fast-forwarded, first run focused tests from [closure gates](pkg-interact-closure-gates.md). On failure **stop**. Only after green tests run:

```powershell
python -m sofia.interaction.disposable_live_offer_probe --run-disposable
```

The updated probe exercises four turns: (1) the reviewed declarative offer with real Qwen choice and expression, either a saved coherent reply or a correctly vetoed raw candidate; (2) `Could I hug you?` which must ask whether the user means avatar or real contact, save both turns and make **zero extra Qwen calls**; (3) the original offer after a clearly labeled synthetic source-attested no-hugs boundary, blocked before inference; (4) `Can I hug you?` under that same synthetic boundary, also blocked with zero extra calls. The probe verifies saved-message counts, veto isolation and Windows cleanup. Total expected Qwen calls: **2** for the first offer only. The synthetic record is NOT an actual Sofía preference.

## Failure and review rules

- A traceback, unexpected inference, mismatched saved messages, incorrect branch or missing model means stop. Do not rerun against `state/sofia.db`, enable the opt-in globally, provision production interaction tables, or clear unrelated local edits.
- `DISPOSABLE INTEGRATION CHECKS: PASS` establishes only temporary-state routing, containment and teardown. A vetoed first answer shows containment, **not** acceptable conversational quality. Read the raw reply for choice/reply consistency, unsupported sensations, invented history or stable preference, executed motion, and generic redirects. Heuristic flags are not validation.
- This probe does not exercise general social-offer phrasing, all concurrent-writer schedules, outside-CLI authentication, restart/replay, rendered animation, hardware sensing, or production migration. The separate two-connection writer-order test covers only the specifically staged stop-before-reply interleaving.
- Preserve modified `state/sofia.db`, timestamped backup, independent local Ollama test edit, provider settings, `main` and other PRs. PR #2 remains draft and unmerged pending explicit Sparks acceptance and separate merge approval.
