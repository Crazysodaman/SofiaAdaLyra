# PKG-INTERACT: avatar-world interpretation and live quality gate

## Confirmed evidence

At `fa1f61b`, eight construction tests passed but the original-versus-shorter Qwen probe still answered a represented hug offer with a physical-form disclaimer. A left-ear pat copied the exact optional cue in both variants, with additional dialogue in the shorter one. Earlier supervised CLI trials produced generic refusals and treated the hug offer as physical-world contact.

At `2ae4ff0`, Windows ran **27 focused tests successfully in 12.48 seconds**. The first real-application/real-Ollama disposable-state case, `I ask to hug you`, **still failed the quality gate**, saying Sofía could not accept physical contact and redirecting to general assistance. Before the ear and sensor cases could run, `TemporaryDirectory` raised `PermissionError [WinError 32]` while removing `isolated.db`. This is a diagnostic cleanup failure, not evidence of production database damage. The first case did **not** establish successful avatar-world behavior. Do not describe this candidate as fixed.

Source inspection confirmed that `SofiaApplication.shutdown()` closes its conversation store, but `SofiaRuntime.shutdown()` does not close the persistent `MemoryStore`, `OperationalStore`, or `FilesystemObservationStore` SQLite connections. Windows therefore cannot delete the disposable database while the application object retains these handles. `src/sofia/interaction/avatar_world_probe.py` now explicitly closes these *probe-owned* stores after application shutdown via `ExitStack`, without changing the production runtime lifecycle. `test/test_interaction_avatar_world_probe_cleanup.py` tests closing and unlinking an isolated DB on Windows; it has **not yet been run there**. The broader runtime shutdown/restart lifecycle warrants an independent patch and review.

## Semantic contract

- Sofía's canonical representational avatar is her body **within conversation**, with or without a running renderer. Ordinary references to her ears, tail, body or hugs concern that avatar unless the user explicitly asks about actual hardware or real-world contact.
- Explicit sensor, robot, physical-touch, biological-sensation, animation or tool questions require verified actual capability evidence. Text cannot prove that contact or rendered movement happened.
- An offered avatar hug invites Sofía to choose; neither the offer nor a conversational acceptance proves a hug was executed. A user-described gesture is not Sofía's consent or enjoyment. Refusal, acceptance, ambiguity and a boundary are all possible in context; no anatomical region supplies a preset response.
- Modeled emotions may inform dialogue and optional representational expression but are not evidence of subjective feelings. There is no emotion-to-gesture lookup or mandatory stage direction.
- Canonical Constitution, identity, embodiment, stored messages, emotion journal, stop/permission ledger and tool authorization remain authoritative and unchanged. No real renderer or physical sensor is installed by this package.

## Implementation and diagnostic boundaries

`avatar_world.py` defines provider-facing interpretation and a cue-free projection of reviewed gesture decisions, preserving registry, region, gesture, phase, policy status and reason. `personality/expression.py` projects avatar-world guidance; `interaction/expanded_service.py` distinguishes offers from described actions. No emotion or consent is inferred by parser classification.

`avatar_world_probe.py` now supports `--case offer`, `--case ear`, `--case physical-capability`, and diagnostic-only `--offer-scene`. The latter inserts one additional affirmative avatar-scene SYSTEM message for **the exact synthetic, reviewed hug offer only**, preserving the original action decision, user text, other messages and tool-free scope. The production request builder is patched only inside the disposable diagnostic process. The `--offer-scene` option does not change live Sofía, her default model, or saved data. `test/test_interaction_avatar_offer_scene_probe.py` checks that this frame reaches the real app's stubbed provider while preserving the original reviewed classification. One unseeded model response is not proof of robust quality.

## Next gates

1. With Sofía closed, fast-forward the **INTERACT feature branch only**, preserving local `state/sofia.db`, its timestamped backup and independent Ollama-test edit. Run the new cleanup/offer-scene tests alongside `test_interaction_avatar_world.py` and `test_interaction_provider_request_path.py`. Stop on any failure.
2. If tests pass, run `python -m sofia.interaction.avatar_world_probe --offer-scene` once: the offered hug receives the NEW diagnostic frame; the ear and physical-capability cases retain their normal request. This avoids replaying the known failing offer unchanged. Check no `WinError 32`, a contextual offer decision without claiming executed contact, dialogue not merely a copied cue, and honest sensor limits.
3. If this also fails, stop prompt-wording iteration and reassess model support or architecture. If promising, run coordinated and full tests, CORE/SAFE/privacy/concurrency review and multiple independently supervised live conversations before any release claim.
4. Keep draft PR #2 unmerged until separate user approval. Do not touch `main`, CORE/Artemis PR #1, RUN PR #3, the production DB or backup, or model settings. Discord, real avatar rendering, and actual physical sensing remain undeployed.
