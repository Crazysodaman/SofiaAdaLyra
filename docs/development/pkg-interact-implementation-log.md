# PKG-INTERACT: implementation log and acceptance gates

## Slice I1: shared headless semantics (feature branch; not accepted)

The existing canonical `Embodiment` drives `InteractionEngine`. Explicit fox ears and tail are checked against its feature/anatomy data; human body part names are **form-derived coverage**, not a claim that those parts have rendered geometry. The versioned registry contains left/right parts, ear and tail subregions, and explicitly classified restricted regions. Unknown forms or new canonical appendages fail visibly rather than silently disappearing.

One `InteractionEvent` and one `InteractionDecision` are used by `from_text` and `from_lab_pointer`. Equal actor/region/gesture/phase has equal semantic meaning, policy status and candidate modeled responses across both fixtures. Source, event ID and evidence references deliberately differ. A real mouse click is **not** a pat: the pointer adapter takes only an already-resolved synthetic gesture fixture. Real hit testing and authenticated input do not exist here.

`InteractiveConversationService` extends the existing `EmotionalConversationService` instead of replacing its SQLite journals, conversation store or startup behavior. It adds trusted decision context to the cognitive request for an explicit, recognized text gesture. Original persisted messages remain unchanged. When no renderer runs, expression candidates may include optional `*one ear flicks*` or `*tail curls closer*` stage directions. This is guidance to the LLM, **not** proof that it actually produces varied natural responses. It does not claim physical feelings or that an animation occurred.

The first-slice parser deliberately recognizes only short, complete, explicitly addressed action phrases and abstains on general prose, negation, hypotheticals, code and quotes. Ambiguous or composite phrases are not accepted as completed touch. Private regions are mapped and denied by default; this slice does not implement or assume adult-mode authorization. There is no live renderer, full real-client sensor provenance, per-session stop persistence, approved intimate mode, external screen executor, persistent new-gesture emotional event, preference promotion, UI hit geometry, or physical lab. Existing narrow head-pat journaling remains in place. Simulated pointer fixtures **never** confer user authorization or real-world observation.

## Verification ledger

- Source inspection: canonical `avatar.json`, `Embodiment`/`AvatarStore`, `EmotionalConversationService`, `EmotionalJournal`, `SofiaApplication` and the authoritative avatar contract.
- Added offline tests: versioned anatomy coverage, representative text/pointer parity, unknown and ambiguous targets, restricted-region denials, stop/cancel/partial phase, source distinctions, no invented renderer, preserved chat messages and no interaction from technical questions/code.
- Focused Windows pytest: **not run yet** on this new branch. Live Ollama/CLI: **not run**. Real avatar/UI tests: **not run; renderer absent**. Full suite: **deferred by Sparks until after INTERACT**.

## Subsequent slices before PKG-INTERACT acceptance

1. Run focused tests, fix genuine failures without weakening coverage, then check a short real CLI exchange in playful, serious, correction and declined contexts. Distinguish structural tests from human-reviewed naturalness.
2. Extend the grammar without inventing actions from discussion. Give every canonical actual part and selectable layer a reviewed alias and classified verb policy; version changes with anatomy. Design and independently verify durable interaction evidence and corrections using the existing `EmotionalJournal`, without double-logging head pats or lab fixtures.
3. Implement persistent, externally enforced stop/permission states and duplicate-event protection. Add a truly isolated replayable scene harness with bound/run budgets and redacted trace output.
4. Design a renderer only when UI design is agreed; establish trusted actor, current pose/geometry and hit testing, occlusion, transparent pixel and overlay isolation, gesture classification and acknowledgment. The real client must call the SAME semantic kernel; a genuine click-to-pat claim requires a real gesture sequence.
5. Separately gate authorized screen-object operations, any adult-specific mode, voice or hardware. Complete package-specific focused/live acceptance and the agreed full-suite checkpoint before declaring INTERACT complete or proceeding to MEM.
