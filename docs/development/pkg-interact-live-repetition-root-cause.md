# INTERACT: September 21 live repetition review and scoped repair

**Status: FAILED live conversational-quality gate. Candidate repair NOT yet tested on Windows or Ollama.** The 16 focused and 274 coordinated Windows passes belong to `0557591` only, before this repair. Keep PR #2 draft/unmerged.

## Observed supervised CLI result at `0557591`

- Startup announcement mentioned an earlier runtime and **23 workspace changes**. On the next `*pats your ear*` and `*pats your left ear*` turns, Sofía ignored the gesture and asked about those changes. The unspecified ear also did not get the required concise left/right clarification.
- `I ask to hug you` and `Good girl, gently touches your butt` yielded nearly identical generic wording about being a hands-on companion, practical talk and troubleshooting. The latter utterance combines praise with an unreviewed implicit-subject action and is **not proof of accepted contact or consent**.
- `smacks hand` elicited `Ow`; this is model-generated language, **not sensed physical pain**. The user did not specify a first-person actor or recipient.
- The Windows service response gave a generic checklist and suggested `sc query` without `.exe` despite running in PowerShell. The existing expression guidance specifies `sc.exe` to avoid the PowerShell `sc` alias.
- Repeated ear movements and `What's on your mind?` closing questions remain a model-quality failure. No reliable inference about subjective emotion, past contact, real motion, or the LLM's internal cause follows from the transcript.

## Confirmed source paths

`ConversationService.deliver_pending_awareness()` saves the startup announcement as an **assistant message** in the active session. `ConversationService._build_request()` passes the entire saved session to the model. Separately, `CognitiveContextAssembler` can project `runtime_continuity`, `workspace_changes` and `operational_self_model.workspace_changes` into SYSTEM context. The application also records source-linked workspace emotional/reflection observations, and `EmotionalConversationService._build_request()` sends recent journal projections. These are **four independent avenues** for old workspace information to dominate unrelated dialogue. None proves the model's exact cause without an instrumented, privacy-reviewed live provider capture.

## Narrow code candidate

The Ollama-only `ConversationalContextAssembler` now omits these **from the provider view of ordinary unrelated tool-free conversation**: the recognizable first assistant-only startup announcement; journal JSON rows explicitly linked to `workspace-snapshot:` or `workspace-change:` (including whole mixed-source reflection rows); and the extra runtime/workspace observation sections. Other user messages, subsequent assistant conversation, independently sourced journal rows, current canonical self-state, personality, constitutional hash, and interaction guard messages remain. Explicit workspace/restart questions and initial no-user startup awareness preserve the observations. Full-context tool and constitutional requests remain on the default full assembler path.

This filter does **not** delete or modify SQLite history, original observations, emotional revisions, the protected Constitution, the CLI startup message, stop controls, or permissions. It does not suppress all possible unrelated memory summaries or prevent the model from inventing/repeating generic phrasing. The body-action grammar, model and generation settings are unchanged.

## Acceptance gates

1. Pin the feature SHA; close the CLI. Preserve `state/sofia.db`, its timestamped backup and the local `test/test_ollama_generation_contract.py` edit. Fast-forward pull only.
2. Run `test/test_conversation_workspace_projection.py`, `test/test_conversational_context_projection.py`, `test/test_interaction_ab_probe.py`, `test/test_interaction_context_hygiene.py`, `test/test_interaction_expanded_service.py`, and `test/test_interaction_live_discussion.py` with `pytest -q -x`. The new no-DB unit tests check relevant-vs-unrelated contexts, preservation of other messages and observations, and no-user startup awareness.
3. Run the 274-test coordinated interaction/application subset on the same SHA. Do not report the older 274 passes as current.
4. Run supervised CLI turns: `*pats your ear*`, `*pats your left ear*`, `I ask to hug you`, `What changed in the workspace?`, `Good girl, gently touches your butt`, `smacks hand`, Windows service diagnosis. Evaluate current-turn relevance, ambiguous intent, nonrepetition, no fabricated touch/sensation and `sc.exe` in PowerShell. Avoid treating model answers as actual physical interactions or enforcement evidence.
5. If behavior still fails, inspect reviewed actual provider request/response metadata or evaluate an alternate model under identical prompts before adding a repetition detector. Do not retry requests that might execute tools or reapply state-changing actions. Full repo pytest, privacy/security review and explicit merge decision remain separate.
