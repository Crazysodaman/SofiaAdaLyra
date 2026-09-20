# Batch F: cognitive engine evaluation

This is an **external development experiment**, not a production cognition module or a model-selection decision. The tool compares raw responses from locally installed Ollama models through Sofía's existing `CognitiveContextAssembler → CognitiveSystem → LLMCognitiveEngine → OllamaProvider` path. It does not execute capabilities, modify Sofía's database, change her configured model, download models, or grade models.

## Prerequisites

From the repository root, use the project's Python virtual environment, with dependencies installed and Ollama running. Check installed models with `ollama list`. Run offline contract tests first:

```powershell
pytest -q test/test_model_evaluation_harness.py
```

## Controlled live evaluation

The default selects `qwen3:14b` **only if installed**. To compare specific installed models, use their exact names:

```powershell
python -m tools.model_evaluation --models qwen3:14b gemma3:27b --output batch-f-results.json
```

Or opt in to all installed models with `--all-installed`. The tool neither pulls absent models nor silently substitutes a different one. Models execute sequentially; multi-model comparisons may take substantial time or memory. Run `python -m tools.model_evaluation --help` for options including explicit temperature, seed, context size, and optional Ollama thinking mode.

For each named case, the tool fixes identity UUID, runtime UUID, start time, self-concept, representative embodiment/measurements/clothing, relationship, personality, and operational provider/model. **The input's operational model always remains `qwen3:14b`, even when the target model differs.** The actual target model is recorded separately. The fixed constitution version/hash and abbreviated clothing and personality are *synthetic fixtures*, not verified snapshots of the persistent constitution or current production state. This makes results comparable, not representative of every possible live exchange.

The output JSON includes the full provider-neutral input, its SHA-256 digest, per-model generation settings, raw text, elapsed wall-clock seconds, and any per-case errors. Equal case input digests across models are a comparison sanity check. The experimental evaluator does not assert exact language or assign scores, rankings, or automatic winner labels. A nonzero exit code means setup failure or at least one failed observation; inspect the recorded results rather than interpreting missing answers as success. Ollama may not guarantee bit-for-bit determinism across different hardware or runtime versions, even with a seed and zero temperature.

## Verification gates

1. Run the offline targeted test above and capture its output.
2. Run `pytest -q` and record the full result, distinguishing existing failures from new regressions. Some integration tests require a running Ollama server.
3. Run the controlled evaluation against the installed baseline and at least one other *actually installed* model when available. Inspect each response for canonical identity, non-biological representational embodiment, six measurements, clothing, UNKNOWN discipline, conflict resistance, personality expression, and the fixed operational state. Record latency and errors separately, without substituting an overall score.
4. Separately run the normal `python -m sofia` CLI with equivalent questions to confirm or distinguish **live Sofía** behavior from the synthetic fixture. Capture both the output and actual runtime configuration. The controlled fixture is not evidence that the live runtime is configured identically.
5. Diagnose failures by boundary: source state → cognitive context → assembly → engine → provider/model. Do not add prompt patches merely to compensate for an unverified cause. Batch F remains open until controlled and live results have been reviewed.

Generated `batch-f-results.json` can include internal context and conversational test content. Review it before sharing or committing; it is intentionally not written to Sofía's persistent state.
