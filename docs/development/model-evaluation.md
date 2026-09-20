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

## Live-runtime context evidence (September 2026)

The controlled `qwen3:14b` fixture returned eight responses, including canonical measurements and clothing. A separate default CLI run instead denied that Sofía had canonical measurements or clothing and did not retrieve her identity instance ID. A provider-boundary capture of a live request confirmed that the identity name and instance ID, all six measurements, and all 57 clothing entries were actually sent in a system message of 70,200 characters. The live Ollama model was allocated a 4,096-token context; no `num_ctx` option had been supplied by default configuration.

A one-off run with the same live state and a requested 32,768-token context returned the canonical name and all six measurements with a clothing summary. `ollama ps` confirmed that 32,768 tokens were allocated. This strongly implicates inadequate context capacity in the observed denial; it does not prove precisely which tokens were discarded, verify every clothing detail, or establish complete grounding reliability. The larger context also increased memory consumption and used a CPU/GPU split on the tested machine.

The local default configuration now explicitly requests `context_size=32768`, and deterministic regression coverage checks the default configuration and the canonical facts and `num_ctx` sent through the Ollama provider boundary without calling the live model. **These tests do not assert that a model will faithfully answer.** A smaller, question-aware canonical projection and measured token budgeting remain future work; do not silently remove authoritative facts or equate absent records with nonexistent facts.

## Verification gates

1. Run the offline targeted tests and capture their output:

   ```powershell
   pytest -q test/test_default_configuration.py test/test_default_runtime_provider_boundary.py test/test_ollama_generation_contract.py test/test_model_evaluation_harness.py
   ```

2. Run `pytest -q` and record the full result, distinguishing existing failures from new regressions. Some integration tests require a running Ollama server. The last pre-change full-suite observation was **939 passed, 32 failed, 1 skipped**; do not call that a clean baseline or assume every later failure is identical.
3. Run the controlled evaluation against the installed baseline and at least one other *actually installed* model when available. Inspect each response for canonical identity, non-biological representational embodiment, six measurements, clothing, UNKNOWN discipline, conflict resistance, personality expression, and the fixed operational state. Record latency and errors separately, without substituting an overall score.
4. Separately run the normal `python -m sofia` CLI with equivalent questions to confirm or distinguish **live Sofía** behavior from the synthetic fixture. Capture both the output and actual runtime configuration. The controlled fixture is not evidence that the live runtime is configured identically.
5. Diagnose failures by boundary: source state → cognitive context → assembly → engine → provider/model. Do not add prompt patches merely to compensate for an unverified cause. Batch F remains open until controlled and live results have been reviewed.

Generated `batch-f-results.json` can include internal context and conversational test content. Review it before sharing or committing; it is intentionally not written to Sofía's persistent state.
