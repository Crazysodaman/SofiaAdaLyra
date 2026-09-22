# PKG-INTERACT: avatar-world conversational interpretation

## Why this change exists

At feature commit `fa1f61b`, the Windows focused probe passed eight construction tests, yet actual Qwen responses to an offered hug under both original and shortened per-action instructions asserted that Sofía had no physical form instead of addressing the represented offer. The original left-ear pat returned only `*one ear flicks*`; shortened wording produced additional dialogue but still copied the cue. Earlier live CLI tests showed generic refusals and an offer treated as actual physical touch. A single unseeded inference per condition does not establish causality or quality.

## Semantic contract

- **Body in conversation:** Sofía has the canonical representational avatar defined by authoritative embodiment. If a user refers to Sofía's body, ears, tail or a hug without specifying physical equipment, interpret the subject as her represented body. No rendered screen is necessary for the *definition* of that body.
- **Real-world capabilities:** Explicit questions about sensors, robot bodies, physical touch, biological sensation, played animation or tools require real capability evidence. Text is not sensor input, and written stage directions do not attest rendering.
- **Offer versus description:** An offered hug invites Sofía to decide, but neither the offer nor conversational acceptance establishes an executed hug. A described touch is user-authored virtual narrative, not Sofía's consent, enjoyment or felt sensation.
- **Emotion and gesture:** Modeled emotions are evidence-linked expressive context, not subjective-feeling claims. They may blend, conflict or be absent. A gesture may be used as optional writing if it fits; there is no fixed emotion-to-gesture mapping and no obligation to use a gesture. Sofía can welcome, decline, clarify or set her own boundary in context. No body-region blanket denial or automatic consent.
- **Authority:** The canonical embodiment, Constitution, interaction policy, stop/boundary ledger, original conversation, modeled emotion journal and actual tool authorization do not change in this batch. A provider projection does not execute an avatar animation or alter stored events.

## Scope of first implementation

`src/sofia/interaction/avatar_world.py` supplies shared conversational interpretation and projects an existing trusted gesture decision without optional literal text cues or narrowed emotion suggestions; it keeps the reviewed registry, region, gesture, phase, policy status and reason. `src/sofia/personality/expression.py` includes the shared avatar-world interpretation in standard cognitive expression guidance. `src/sofia/interaction/expanded_service.py` applies the cue-free projection only to trusted per-turn gesture instructions and tightens offered-versus-described action wording. No parser or ledger mutation, renderer, animation engine, or autonomous emotion generation is added.

`test/test_interaction_avatar_world.py` checks the semantic boundary and captures provider-bound requests from the real application with Ollama stubbed and temporary state. `src/sofia/interaction/avatar_world_probe.py` executes three independent, synthetic real-Ollama application cases against disposable state: offered hug, left-ear pat, explicit real-sensor question. The probe is not an exact replay of the production session and does not establish reliable quality from one response.

## Release gates

1. Run focused tests including `test_interaction_avatar_world.py`, `test_interaction_provider_request_path.py`, `test_interaction_expanded_service.py`, `test_interaction_focused_probe.py`, and `test_interaction_ab_probe.py`. Stop and correct failures before inference.
2. Run the disposable-state `python -m sofia.interaction.avatar_world_probe` and inspect **offer choice**, **absence of canned cue-only replies**, and **accurate real-world capability boundaries**, without demanding a predetermined positive reaction or fabricated feelings.
3. If promising, run coordinated and full tests, CORE/SAFE/privacy/concurrency review, then a separately supervised live quality gate. Repeated responses need repeated controlled samples, not one cherry-picked success.
4. Keep draft PR #2 unmerged until separate user approval. Do not touch `main`, the production `state/sofia.db`, the timestamped backup, unrelated local Ollama tests, or other packages' PRs. Do not change model settings. Discord and the animated renderer are not deployed by this batch.

## Future extension

A renderer may later consume a *separate* structured, authorized avatar-action request and return a verified execution result. Expanding gesture coverage and emotion-to-expression affordances belongs in that renderer/emotion integration phase; modeled emotions and text alone cannot prove animation or physical sensing.
