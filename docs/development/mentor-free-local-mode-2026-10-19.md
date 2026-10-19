# Free Local MENTOR: Two Ollama Models, No API Credit

**Date:** 2026-10-19 • **Intent:** AI-to-AI *synthetic* mentor practice with an installed local model as Sofía's student and a **different** local Ollama model as advisory reviewer.

## Cost and independence
- **OpenAI API charge:** $0; the local-only command never calls OpenAI or loads an API key.
- **Hardware cost:** still consumes local electricity, CPU/GPU RAM and time. Do not run it while gaming on Venus.
- **Do not confuse these roles:** the local mentor is *not* ChatGPT or GPT-6, is not an independent verified oracle, and cannot approve a source-code fix, SAFE/FIDO2 authorization or V18 task promotion.
- **Full Sofía conversation:** not yet wired. This is a deliberate model-only pilot with fixed synthetic test cases; it does not access Sofía's memory, personality pipeline, real desktop, hardware or tools.
- **Privacy:** the program uses the literal loopback endpoint `127.0.0.1:11434/api/chat` for both sides. It refuses dynamic remote endpoints, prompts and tools. No transcript is automatically persisted.

## Recommended model pair already present on Venus

| Role | Model already installed | Reason |
|---|---|---|
| Sofía local student | `qwen3.5:9b` | Project's primary 9B cognitive model |
| MENTOR local critic | `qwen3:14b` | Distinct 14B model for a second opinion |
| Optional alternative | `huihui_ai/qwen3.5-abliterated:4B` | Smaller experimental challenger only, **not** a safety or authority reviewer |

The 9B + 14B weights may not fit in your GPU concurrently. This code **sequentially** calls the models and sends `keep_alive:0` with every request to release residency after each reply. It sets `num_ctx:2048`, `think:false` and a bounded output token allowance. The 14B model may still need CPU spill or another host; monitor local resources if latency is high.

## Owner commands on Venus

```powershell
cd H:\Users\Crazysodaman\Programing\SofiaAdaLyra
git pull --ff-only
ollama list
# Preview does not call Ollama or OpenAI.
python -m sofia.mentor local-converse --scenario service-failure --student-model qwen3.5:9b --mentor-model qwen3:14b --rounds 2 --preview

# Explicitly run only if Venus is idle and not gaming.
python -m sofia.mentor local-converse --scenario service-failure --student-model qwen3.5:9b --mentor-model qwen3:14b --rounds 2 --confirm-idle
```

No `OPENAI_API_KEY` required. If the key is still set for unrelated work, the local bridge **does not read it**. You can clear it using `Remove-Item Env:OPENAI_API_KEY` for good security hygiene.

Built-in fixtures: `service-failure`, `memory-correction`, `screen-understanding`. Each produces alternating local-student and local-mentor entries and separate reported token counts where available. There are no arbitrary prompts or attached files in this mode, so this is safe to test without cloud transmission.

The `--confirm-idle` flag is an **explicit operator declaration**, not a proven automatic game/activity sensor. Do not run local MENTOR while playing a game. The future application-integrated version must use the actual activity/STOP/SAFE checks before it can run automatically.

## Running tests
```powershell
python -m pytest -q test/test_mentor_local_bridge.py
python -m sofia.mentor audit --repo . --markdown mentor-summary.md
```

This free model dialogue exists alongside the original opt-in OpenAI bridge. The external paid `converse` mode is optional and must never be an implicit failover.

## Next steps for actual continuous QA
1. Connect to the canonical `SofiaApplication` conversation engine with an authenticated, dedicated MENTOR principal/audience, without quietly making a second identity or canon DB writer.
2. Use the Atlas and Technical Reference as version-pinned retrieval inputs. Keep owner/private data local by default; a local mentor can evaluate local examples without cloud transfer.
3. Add ground-truth oracles, task evidence, independent host/CI test receipts and typed defect records. The larger critic's opinion is not a test result.
4. Have the existing background scheduler consider MENTOR tasks **only** under existing idle, STOP, consent and resource admission conditions. No gaming competition and no new scheduler thread.
5. Build isolated repair proposals, regression and rollback verification, evidence-grounded report delivery and gradual bounded self-maintenance. Human owner remains the final protected-action authority.
