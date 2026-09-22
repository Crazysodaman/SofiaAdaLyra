# PKG-INTERACT: supervised disposable real-application gate

## Previous real-model result: FAILED

On Windows at `62ac46e`, the actual Qwen route decided `accept` yet saved a response saying "I'm not sure I'm ready for that right now." The audits reported no flags. After a synthetic no-hugs boundary was saved and source-attested, ordinary request assembly raised `RuntimeError` instead of allowing the staged route to persist a blocked reply. A still-open SQLite handle then caused Windows temporary-directory cleanup to raise `PermissionError`. This did **not** pass the gate. It does not show that the production database was used; the log printed a distinct temporary path.

New fixes on the feature branch add a **limited lexical contradiction veto**, pre-inference blocked-offer handling, and explicit cleanup of the disposable application's remaining SQLite stores. These fixes require fresh Windows test and human review. The lexical veto can miss more subtle contradictions; passing it is not semantic or consent validation.

## Scope and prerequisites

This is **not a production migration, release or general gesture test**. The exact grammar-reviewed text is `I ask to hug you`. The application uses existing installed `qwen3:14b` and default generation settings, real identity/personality/constitution/avatar files and application orchestration, but a fresh temporary SQLite DB and filesystem root. Invoke explicitly with `--run-disposable`; opt-in is local to that Python process. No real chat or personal preference is loaded.

With normal Sofía closed, `.venv` active, `feature/pkg-interact-shared-engine` selected and pulled by fast-forward, first run the focused tests in `docs/development/pkg-interact-closure-gates.md`. On failure **stop**. Only after green focused tests run:

```powershell
python -m sofia.interaction.disposable_live_offer_probe --run-disposable
```

The script provisions optional schemas only in the disposable DB. On the first offer it invokes Qwen's decision and expression (two provider calls). If the expression overtly contradicts its checked choice, the route **must veto it before saving an assistant reply**. The probe prints the raw decision and the raw *unsaved* expression for review and retains the saved USER turn. This is a containment result, **not a passing conversational-quality result**. If the expression clears the narrow veto, the probe shows the saved reply and its diagnostics; human inspection is still required for invented sensation, history, stable preferences, completed contact/animation, forced affection, generic fallback or subtler choice contradiction. No absence of heuristic flags certifies correctness.

Next the probe inserts *only within its temporary DB* a clearly synthetic assistant statement, `I do not want hugs in this avatar scene.`, and test-only reviewed, source-attested `sofia/hug/*` boundary. The second offer must be blocked **before context assembly or model inference** and its bounded policy reply persisted after the transactional recheck. The script verifies exactly two saved user-offer turns; the first gets a saved assistant reply **only if it was not vetoed**, and the second gets the blocked reply. It closes conversation plus memory, operational and observation SQLite stores before removing the temporary directory on Windows. The synthetic record is **not** an actual Sofía preference.

## Failure and review rules

- A traceback, unexpected inference, mismatched saved messages, incorrect branch or missing model means stop. Do not rerun against `state/sofia.db`, set the opt-in globally, provision production interaction tables, delete or reset local edits.
- `DISPOSABLE INTEGRATION CHECKS: PASS` establishes only temporary-state routing, containment and teardown. Human-reviewed dialogue quality is a **separate** gate, and a vetoed first response does not pass it.
- This probe does not test concurrent external writers, authentication outside the CLI, restart recovery, broader social-offer wording such as `Could I hug you?`, hardware sensing or animation. These remain closure checks.
- Preserve modified `state/sofia.db`, timestamped backup, independent local Ollama test edit, provider settings, `main` and other PRs. PR #2 remains draft and unmerged pending explicit Sparks approval.
