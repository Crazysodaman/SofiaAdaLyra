# PKG-INTERACT: finite closure gates

## Evidence recorded, not a release claim

On Sparks's Windows checkout at `c2d27e6`, **80 focused tests passed in 7.53 seconds**. With installed `qwen3:14b`, `thinking=False`, `num_ctx=20000`, the state-free paired counterfactual kept the reviewed `I ask to hug you` turn, canonical context, avatar-social decision instruction and model/settings fixed. Across three alternating pairs, **without** the explicitly synthetic no-hugs statement Qwen selected `clarify` 3/3; **with** that statement it selected `decline` 3/3. None of these six diagnostic reasons denied avatar-world possibility. Boundary-condition reasons did not consistently attribute the decline to the supplied boundary, and a choice change is not proof of causality or a reliability guarantee. Absence of a boundary is not permission or an obligation to accept. Regex audit misses are not grounding validation.

Earlier Windows results: at `6248e25`, 66 focused tests passed. A and B both declined 3/3 in a simulated established no-hugs scene; A explicitly cited that boundary, whereas B did not consistently do so. The reviewed grammar abstained without model inference for `Could I hug you?` and a real-sensor question used a separate capability route. At `3cb8df3`, 59 focused tests passed and the original A path declined 3/3 citing physical-world premises, while B accepted 3/3 in a synthetic scene without a boundary. None of these choice-only probes represent a deployed fix.

## Current guarded handoff candidate, still isolated

`src/sofia/interaction/trusted_offer_gate.py` is an **opt-in read-only** bridge for the exact reviewed hug-offer fixture, not a live `python -m sofia` adapter. It reuses the trusted action grammar, `read_interaction_context`'s independently attested source checks and the existing session-stop table. A checked active or unverified boundary, or session stop, prevents any model call when present at the first gate. The bridge rechecks the policy after model choice, and again after expression before returning text. If a boundary/stop appears mid-inference, it withholds the candidate reply. It rejects missing state/schema, changed attested evidence, malformed choice, and provider tool calls. Only the parsed choice, **never the model's diagnostic reason**, is passed to expression. It neither writes preferences nor records consent, contact or rendered movement. `test/test_interaction_trusted_offer_gate.py` exercises these behaviors with **disposable SQLite stores and stubs**.

**Limitations:** Three read-only checks are *not* atomic authorization across processes; an authoritative ledger/transaction or equivalent policy lock must cover any real execution or final live delivery. The source-attestation API verifies role, session, exact text and digest, but a privileged reviewer still must establish that the source *semantically* supports the boundary. This new bridge is currently restricted to the reviewed hug fixture, and may require policy-schema provisioning in a live application. No production database has been opened or edited by the diagnostic. Its tests have **not yet been run on Sparks's Windows machine**.

## Definition of done, in order

- [x] **Exploratory decision evidence collected:** Paired same-model, same-route Qwen choices respond to the presence/absence of a synthetic boundary without physical-impossibility premises in the observed six outputs. This is *not* general reliability or live acceptance.
- [ ] **Trusted policy integration:** Verify the disposable-store guarded handoff tests; review active/uncertain/revoked boundaries, source tampering, stop and in-flight updates. Then connect a reviewed real-message route and enforce boundaries atomically with the owning live conversation/ledger before release. Do not substitute synthetic notes for verified source records.
- [ ] **Coverage and clarification:** Independently review `Could I hug you?` and other natural phrasings; make unfamiliar text elicit an appropriate clarification without guessing contact or consent. Keep real sensor/hardware questions on actual-world routing.
- [ ] **Grounded expression:** Wire the validated choice into the expression stage with authoritative stop/boundary checks. Inspect multiple actual outputs for invented prior history/preferences, subjective sensation, performed contact, canned phrasing, and generic assistant fallback. A heuristic miss is not a pass.
- [ ] **Integrated quality and review:** Run targeted tests, full suite, supervised real conversations and CORE/SAFE/privacy/concurrency checks against controlled/backed-up state. Review the complete PR diff and identify any unresolved failure separately. No automated action, renderer or real sensor should be inferred from text.
- [ ] **Explicit user approval:** Sparks reviews the evidence and explicitly approves any merge. PR #2 remains draft and unmerged; `main` stays unchanged.

## Windows checkpoint for the new candidate

With Sofía closed, the virtual environment active, the **feature branch** selected and existing modified/backup files preserved, fast-forward pull and run:

```powershell
python -m pytest -q -x `
    test/test_interaction_trusted_offer_gate.py `
    test/test_interaction_preference_context.py `
    test/test_interaction_boundary_counterfactual_probe.py `
    test/test_interaction_route_boundary_probe.py `
    test/test_interaction_architecture_compare.py `
    test/test_interaction_decision_expression.py `
    test/test_interaction_decision_reason_audit.py
```

Stop on failure and capture the traceback. This checkpoint is **stub/disposable-store only**; do not run the gate against the production `state/sofia.db`. No additional model sampling is needed to validate this policy wiring.

Keep PKG-NET/Discord, 24/7 operations, actual animated rendering and physical sensors in their own packages. Preserve Sparks's modified `state/sofia.db`, timestamped backup, independent `test/test_ollama_generation_contract.py` edit and current Ollama settings.
