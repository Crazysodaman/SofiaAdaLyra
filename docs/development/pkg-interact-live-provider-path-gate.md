# INTERACT live provider-path gate, 2026-09-21

## Pinned evidence

Sparks reported 39 focused tests passing in 7.00 s and 288 coordinated interaction/application tests passing in 109.42 s at `02939c2`. A subsequent supervised live CLI at the same revision failed conversational quality: `Good girl, gently touches your butt` and `gropes your butt` produced identical generic refusals; `*pats your left ear*` produced only `*one ear flicks*`; and `I ask to hug you` produced another physical-contact disclaimer instead of acknowledging the offer as an offer. Startup awareness was concise. No newer Windows or live outcome has been reported. A green parser/ledger test does not establish a natural LLM response.

## Source inspection, without claims about unseen model inputs

The v2 grammar now recognizes both exact butt-touch phrases and a left-ear pat. `ExpandedConversationService` adds per-action system context to `InteractiveConversationService` requests; `SofiaRuntime.respond` and `CognitiveSystem` assemble provider-bound context; `OllamaProvider` translates messages to Ollama. Those source paths do NOT establish that any particular live request contained the expected instruction. The near-duplicate guard compares only drafts of at least 120 normalized characters, so a short refusal or ear cue does not show it fired. `*one ear flicks*` is an optional expression cue in v1, which the model may copy. No confirmed evidence yet separates missing context, instruction competition, inference defaults, and repeat-guard effects.

## Isolated next test

`test/test_interaction_provider_request_path.py` invokes real `SofiaApplication`/conversation/runtime composition with a temporary state DB and a stubbed `OllamaProvider._respond_once`. It captures transient requests only in memory and checks canonical status, offer-vs-description, original user text, bounded constitutional projection, tool-free scope, and the virtual gesture ledger. It does not call Ollama or read, overwrite, export, or reset the production `state/sofia.db`. This is a test *candidate*, not a reported Windows pass.

Run the isolated test first and stop on a failure. If it passes, inspect the model's response quality through a separately approved privacy-safe controlled comparison of provider inputs or models, not another broad instruction block or forced approval/refusal. Model outputs are not evidence of sensations, consent, physical contact, or avatar execution. The offered-hug, ear-expression and technical quality gates remain open.

The draft PR must not be merged; full pytest, CORE/SAFE, privacy/concurrency review and separate explicit merge approval are still pending. Keep the local database, backup and unrelated Ollama-test edit unchanged.
