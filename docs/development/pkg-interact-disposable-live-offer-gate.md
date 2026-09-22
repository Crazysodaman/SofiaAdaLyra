# PKG-INTERACT: supervised disposable real-application gate

## Scope and prerequisites

This **is not a production migration, a release or a general gesture test**. The exact grammar-reviewed user text is `I ask to hug you`. The application uses the installed `qwen3:14b` with its existing default generation settings, actual constitution/identity/personality/avatar files and real application conversation orchestration, but a fresh temporary SQLite database and temporary filesystem root. The probe is explicitly invoked with `--run-disposable`; its local environment opt-in is scoped to the Python process. It does not import any real saved chat or personal preference. Close normal Sofía before testing and keep `SOFIA_INTERACT_STAGED_OFFERS` disabled outside the probe.

After feature-branch fast-forward and focused tests, run:

```powershell
python -m sofia.interaction.disposable_live_offer_probe --run-disposable
```

The script provisions the temporary conversation, stop, revision and source-attestation schemas before starting the application. First it saves a real user-turn fixture and lets the actual Qwen decision and expression stages produce one reply. It prints the original candidate decision, diagnostic reason, heuristic flags and saved reply. **Inspect that reply yourself**: no invented physical sensation, prior history, stable preference, completed contact or animation, no forced yes/no, no generic assistant fallback. Absence of a regex flag does not certify it. The provider should be invoked twice for this first offer (decision and expression).

Next, *only within the temporary database*, the probe inserts an explicitly synthetic assistant statement, `I do not want hugs in this avatar scene.`, independently source-attests it with a test-only reviewer identifier and records a matching active `sofia/hug/*` boundary. The same offer must be blocked by trusted policy and saved with no additional provider call, regardless of the first reply. This synthetic evidence **does not represent a genuine Sofía preference**. The script checks exactly two saved offer turns and a corresponding saved assistant reply for each, then closes the app and exits the temporary directory.

## Failure and review rules

- A traceback, unexpected inference, mismatch of saved messages, incorrect branch or missing model means **STOP**. Do not rerun against `state/sofia.db`, set a global environment flag, manually provision production interaction tables or clear local modifications.
- A passing printed `DISPOSABLE INTEGRATION CHECKS: PASS` establishes only that these two cases ran through the application on temporary state. Quality acceptance requires reading the raw output. A Qwen response may still be ungrounded or awkward even if every assertion passes.
- This probe does not test concurrent external SQLite writers, user authentication outside the CLI, restart recovery, natural alternatives such as `Could I hug you?`, real hardware sensing, or animated actions. Those remain separate closure checks.
- Preserve the pre-existing modified `state/sofia.db`, its timestamped backup, independent local Ollama test edit, all provider settings, `main` and other PRs. PR #2 remains draft; merge only after Sparks explicitly approves it.
