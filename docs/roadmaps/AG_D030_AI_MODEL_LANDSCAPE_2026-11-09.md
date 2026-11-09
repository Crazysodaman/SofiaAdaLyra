# AG-D030 | AI model landscape: frontier, local, coding, mature fiction and image generation

**Research snapshot:** 2026-11-09 (America/Chicago). **Status:** RESEARCHED / OWNER-REQUESTED TODO / NOT SCHEDULED. **No weights downloaded, no models installed, no live tests, no provider changes.**
**Linked backlog:** AG-D005 Aegis Model Manager; AG-D028 Artifact Library; AG-D029 agent harness/inference alternatives; AG-D007 Control Center.
**Release fence:** This is NOT a Platform 1.0 blocker; issue #201 keeps its existing 38 acceptance rows and AG-D028 LIB-01..LIB-16 are unchanged. The shortlist is a set of candidates, not a commitment to distribute models or license-controlled adult checkpoints.

## 0. Scope, hardware and evidence

The owner requests the strongest models currently available, best practical models for their home lab, coding (overall/local), adult/mature text (overall/local), and **eight** image categories: general/non-nude vs adult/nude, photorealistic vs anime, cloud/overall vs local/home lab.

It is impossible to certify literally *all* models; this is a cross-family shortlist using 2026-11-08/09 primary ranking snapshots, publisher model cards and community checkpoints. Models, quantizations and prices shift frequently. **Ranking evidence differs**:
- General intelligence: Artificial Analysis Intelligence Index (measured model settings); Arena text preference.
- Coding: Terminal-Bench 4.0, Agent Arena coding, coding text Arena (agent harness matters).
- Small local weights: Ollama model registry sizes + GPU budget; no owner-hardware model A/B measurements.
- Adult creative writing and images: community model cards/adoption + targeted uncensored rankings, weak standardized independent validation; **do not assign a measured universal #1**.
- General images: Artificial Analysis image leaderboard and Arena image preference, which can disagree or have provisional newer model samples.

**Host reference (prior owner configuration):** Venus, Windows 11, i7-9700K, 32GB RAM, RTX 3080 Ti **12GB VRAM**. Artemis is a Windows VM host with **no GPU**. GPU inference via explicitly enrolled Venus worker; no inferred VM GPU.
**Memory rule:** download or GGUF file size is NOT peak VRAM; include KV cache, context, framework, CUDA kernels, VAE/text encoder and running Windows display applications. For multi-model roles unload before loading another unless measured residency allows concurrency.
**Privacy and human rights:** Sensitive/adult tasks default to locally isolated stores and opt-in handling. Only consensual adults, no sexual content of minors or nonconsensual sexual deepfakes. Original character assets and private prompts must not auto-replicate to Hub/peers. No code or model may grant its own permissions.

## 1. Winners by requested category (research picks, NOT owner-benchmarked)

| User question | First candidate | Key alternates | Evidence / caveat |
| --- | --- | --- | --- |
| Best model overall | **Gemini 4 Carbon (High)** for Artificial Analysis intelligence and Arena text | **Claude Opus 5.5** for agent tasks; GPT-6 Astra for hard reasoning | AA Index: Gemini 60, Opus 59, Astra 57 on current snapshot; agent leader Opus |
| Best overall for homelab | **Qwen3.5 9B**, quantized, preferred starter | Gemma 4 12B; Qwen3 14B; Ministral 3 14B | Qwen model download 6.6 GB (often up to 7.6GB variant), Gemma 8GB, 14B 9GB; runtime context matters |
| Best coding model overall | **Claude Opus 5.5 (max)** for coding agent | Claude Sonnet 5.5, Gemini 4 Carbon, GPT-6 Astra, GPT-6.1 Sol | Terminal-Bench 4.0 Opus 64.8% in Claude Code; not model-only fair test |
| Best coding for homelab | **Qwen2.5-Coder 14B** quantized Q4, moderate context | Qwen3.5 9B for speed/context; Qwen2.5-Coder 7B for latency | 14B model ~9 GB; ~10GB+ VRAM with cache. 9B may win multi-file agent work when memory is constrained |
| Best adult/mature text overall | **DeepSeek V4.1 Flash 1017 Uncensored** for hosted low-refusal general ability, *not universal RP winner* | GLM 5.3 Flash Uncensored; roleplay specialists Magnum v4 72B, Euryale 70B, Cydonia 24B; NovelAI Xialong for story writing | OpenUncensored composite winner; community RP styles vary and have no reliable cross-provider universal benchmark |
| Best adult/mature text for homelab | **Huihui-Qwen3.5-9B-abliterated** at suitable Q4/Q5 quantization | Rocinante 12B; Stheno 8B; Magnum 9/12B variations | Verified upstream HF card and Ollama tag; abliterated ≠ guaranteed creative quality, tool reliability or security |
| Best non-nude photoreal overall | **GPT Image 2.6 Sunburst (max)** as latest AA image leader | GPT Image 2.5 Sunburst (Arena top on Nov 8), Nano Banana 2.1, MAI-Image 2.6 | AA newer 2.6 max ranking vs Arena 2.5 mature/preliminary vote counts; no universal absolute |
| Best non-nude photoreal homelab | **FLUX 3 Image Klein** INT8 via ComfyUI | FLUX.2 Klein 4B; RealVisXL V5; Juggernaut XL Ragnarok | BFL official Oct 2026; 5.6B, weights 5.6GB FP8 (text encoder separate), INT8 8GB-min supported; 12GB card plausible, test actual full pipeline |
| Best non-nude anime overall | **NovelAI Diffusion V5 Full** specialist hosted animation-style art | GPT Image 2.6 for broader instructions/typography, open NoobAI/Illustrious variants | NovelAI official says V5 current; specialized style editorial choice, not validated winner of common public leaderboard |
| Best non-nude anime homelab | **NoobAI XL v-pred** or **Animagine XL 4.0 Opt** | Illustrious XL v2 / community derivatives | SDXL-era ~7GB checkpoints, ~8–12 GB effective; different licenses and LoRA/tag ecosystems |
| Best adult/nude photoreal overall | **Lustify** explicit photoreal family, or CyberRealistic Pony for Pony-LoRA flexibility | Higher-VRAM FLUX adult finetunes where provenance and license verified | No comparable high-quality head-to-head leaderboard; Lustify v10 uses Krea 2 base; earlier SDXL version has different loader requirements |
| Best adult/nude photoreal homelab | **CyberRealistic Pony v18** (Pony V6/SDXL) | Lustify SDXL v2.x; Juggernaut XL Ragnarok | ~6.5GB checkpoint, practical 8–12GB; native adult LoRA ecosystem, score-tag prompting |
| Best adult/nude anime overall | **NovelAI Diffusion V5 Full** hosted specialist, **WAI-NSFW-Illustrious v17** as open weights choice | Pony V6 XL (especially furry/stylized) | No direct common quality benchmark; check provider's current adult-content rules before use |
| Best adult/nude anime homelab | **WAI-NSFW-Illustrious v17** | Pony Diffusion V6 XL; Hassaku/Nova Illustrious | ~6.5–7GB SDXL-derived checkpoint; community art preference. Pony and Illustrious LoRAs are not interchangeable |

### 1.1 General frontier details
Artificial Analysis current leader: **Gemini 4 Carbon (high) 60**, **Claude Opus 5.5 (max) 59**, **GPT-6 Astra (max) 57**. Arena Nov 8 text rankings place Gemini 4 Carbon high first provisionally; the Arena *agent* leaderboard places Opus 5.5 first. **No claim that one model leads every benchmark.**

### 1.2 Local text model shortlist and roles
| Exact family | Current practical quantized file | Recommended Aegis role | Fit judgement |
| --- | --- | --- | --- |
| \`qwen3.5:9b\` | ~6.6GB registry default | primary, vision, general reasoning, multimodal | best balanced 12GB start |
| \`gemma4:12b\` | ~8.0GB | alternate quality/vision comparison | promising; benchmark on owner hardware |
| \`qwen3:14b\` | ~9.3GB | reasoning challenger | tight, short context |
| \`ministral-3:14b\` | ~9.1GB | writing/long-form alternate | tight |
| \`qwen2.5-coder:14b\` | ~9.0GB | coding specialist (review/edit/test) | narrow agent context, careful RAM spill |
| \`qwen2.5-coder:7b\` | ~4.7GB | light code/inline | easier coexistence |
| \`huihui_ai/qwen3.5-abliterated:9b\` | quant variant dependent | adult/low-refusal creative fiction | isolate, do not merge into Core identity |
| Rocinante 12B / Stheno 8B | choose verified GGUF | character dialogue alternatives | style A/B tests required |

**Not practical fully resident at 12GB**: Qwen3-Coder 30B-A3B (~19GB file), Gemma 4 26B/31B, 27B+ dense models, 70B roleplay models, frontier closed models. CPU offload might technically run some but at substantially degraded responsiveness. Don't call them '12GB GPU fit' because system RAM exists.

## 2. Image generation: 2×2 styles, cloud/local

**Critical distinction:** ComfyUI is the **inference application/workflow**, NOT a model; NovelAI is a **hosted product**, V5 Full is the underlying model. For Aegis, native checkpoint and provenance/LoRA compatibility matter.

### General, non-nude images
- **Photoreal/overall:** GPT Image 2.6 Sunburst (max) is new AA image benchmark leader in a 2026-11-09 fetched updated embedding; Arena Nov 8 ranks GPT Image 2.5 Sunburst #1 overall and #1 photoreal, with larger vote sample. Keep both evidence snapshots and do not use a claim of universal superiority.
- **Photoreal/local:** **FLUX 3 Image Klein INT8**. Publisher documents 5.6B parameters, 11.2GB BF16 generator, ~5.6GB FP8 generator, INT8 RTX at 8GB+, supported ComfyUI/Diffusers and separate text-encoder; *verify complete 12GB pipeline including prompt upsampler*. Latest Oct 2026 native generation/editing/layout capability makes it a stronger new experiment than blindly reusing Flux.1 Dev.
- **Anime/hosted:** **NovelAI Diffusion V5 Full**, purpose-built hosted anime/furry model; compare against new GPT Image 2.6 or Nano Banana for non-anime semantic instructions. Product usage, policy and price differ.
- **Anime/local:** **NoobAI XL v-pred**, **Animagine XL 4.0 Opt**, **Illustrious XL v2**. All roughly SDXL size; different prompt tags, LoRAs and licensing. ComfyUI on existing GPU is appropriate.

### Adult/nude images of consenting adults and adult original characters
- **Photoreal overall/local candidate:** **CyberRealistic Pony v18**, **Lustify explicit photoreal**. Lustify v10 Krea2 line is *not the same* as older SDXL v2.x; pin exact version, loader and separate model license before making an Aegis artifact. Adult-labeled Flux finetunes are a separate high-VRAM comparative experiment and must not be presumed safe/compatible.
- **Anime overall hosted:** **NovelAI Diffusion V5 Full** as a major hosted anime specialist (check current generation policies); **WAI-NSFW-Illustrious v17** is the strongest community-documented open checkpoint candidate.
- **Anime local:** **WAI-NSFW-Illustrious v17** on Illustrious/SDXL, **Pony Diffusion V6 XL** for alternate character/LoRA ecosystem, especially stylized/furry. **Pony V7 is AuraFlow, NOT V6/SDXL-compatible**; its LoRAs differ and documented VRAM is less friendly to 12GB.
- No adult-specific model gets the label 'objective quality champion': standard SFW preference leaderboards do not evaluate adult content adequately. Separate evaluation using consented original subjects and private local data.

**Hardware warning:** A 12GB GPU cannot be assumed to keep a 9B chat LLM *and* an SDXL/FLUX image checkpoint loaded concurrently. Explicit unload/reload under the existing Platform compute owner. Store image models as DATA artifacts only where permissions/license allow, not as automatic host-executable installers.

## 3. Proposed Aegis model-catalog responsibilities (not implemented)

Extend AG-D005 without forking AG-D028:
- Versioned \`model_family_id\`, exact publisher+revision+digest, source, architecture (GGUF/Safetensors/SDXL/FLUX/etc), compatible backend/sampler/text encoder/VAE/control assets, quantization, VRAM observed+estimates, license, redistributability, adult content classification, provenance/trust state, install state, supported tasks.
- Role names: \`general.primary\`, \`general.secondary\`, \`coding\`, \`creative.mature\`, \`image.photo\`, \`image.anime\`, \`image.photo.mature\`, \`image.anime.mature\`. Role assignment **never** overwrites Core identity or protected state.
- Discovery and downloading require owner choice, approved origin and exact hash; imports verify bytes, format and license. Acquisition != install != activation, especially adult model artifacts.
- Model weights may be cached/distributed by AG-D028 only if publisher and license permit, with opt-in scope. Adult prompts and image outputs **not** mirrored by default.
- Tests must use actual consented disposable Windows and Debian hosts; GPU inference where available, CPU parity and meaningful failure receipts where not.
- Benchmark identical prompts, seed/quant/sampler, 8K/16K/32K context where feasible, TTFT, tokens/s, tool-call schema success, memory over long turns, OOM and STOP; for images: 1024p batches, subject consistency, anatomy/hand quality, text readability, instruction adherence, latency, peak VRAM and adult-appropriate isolated evaluation. No production claims until verified.

## 4. Research follow-ups / acceptance TODO

- [ ] **ML-01:** Reconfirm benchmark scores and model availability before installing; freeze exact 2026-11-09 snapshot/links.
- [ ] **ML-02:** Compare Qwen3.5 9B vs Gemma 4 12B on 3080 Ti for Sofía everyday cognition, 8K/16K with memory isolation.
- [ ] **ML-03:** Compare Qwen2.5-Coder 14B vs Qwen3.5 9B on an identical Aegis disposable code corpus using Pi and Goose harness when their optional modules exist.
- [ ] **ML-04:** Compare Huihui Qwen3.5 9B vs Rocinante 12B/Stheno 8B for consensual adult creative character style and multi-turn coherence. Never interpret "uncensored" as technical trust.
- [ ] **ML-05:** Verify FLUX 3 Image Klein INT8 on RTX 3080 Ti full ComfyUI workflow, including required text encoder and prompt upsampler, memory+speed; compare FLUX.2 Klein 4B and SDXL RealVisXL/Juggernaut for non-adult photoreal.
- [ ] **ML-06:** Evaluate NoobAI XL vs Animagine XL 4.0 vs Illustrious XL v2 for clean anime, exact LoRA and licensing.
- [ ] **ML-07:** Separately evaluate CyberRealistic Pony v18 vs compatible Lustify SDXL variant for adult photoreal and WAI-NSFW-Illustrious v17 vs Pony V6 for adult anime using safe, lawful, adult-only fixtures; preserve data privacy.
- [ ] **ML-08:** Produce per-model manifest with exact official publisher, variant, version, digest, file sizes, source/license and source verification; no unchecked Civitai file made automatically trusted.
- [ ] **ML-09:** Verify Model Manager role routing, unload/reload, gaming pressure on Venus and distributed inference path from Core VM, without sharing Core secrets or personal prompts.
- [ ] **ML-10:** Require comparative evidence before default selection; maintain existing Ollama inference adapter and full Platform Core-free operation.

## 5. Primary sources consulted (all 2026-11-09 unless noted)

**Measured general/coding:** 
- Artificial Analysis models: https://artificialanalysis.ai/leaderboards/models
- Arena Text: https://arena.ai/leaderboard/chat/text
- Arena Agent Coding: https://arena.ai/leaderboard/agent/code
- Terminal-Bench 4.0: https://www.tbench.ai/?version=4.0
- Arena text coding: https://arena.ai/leaderboard/chat/text/coding

**Official local text + selected community source:**
- Ollama Qwen3.5: https://registry.ollama.com/library/qwen3.5
- Local 12GB selection guide: https://local.lilaforge.com/guides/best-models-12gb-gpu/
- Qwen2.5 coding notes: https://localaimaster.com/vram/best-coding-llm-12gb-vram
- Huihui Qwen3.5-9B model card: https://huggingface.co/huihui-ai/Huihui-Qwen3.5-9B-abliterated
- Quant variants: https://huggingface.co/models?other=base_model%3Aquantized%3Ahuihui-ai%2FHuihui-Qwen3.5-9B-abliterated
- Community character writing comparisons: https://multiic.space/blog/best-local-llms-roleplay/
- Uncensored/composite ranking, not general intelligence benchmark: https://openuncensored.com/rankings
- Community adult model index: https://uncensorindex.com/llm

**Images:**
- Updated AA image T2I: https://artificialanalysis.ai/embed/text-to-image-leaderboard/leaderboard/text-to-image
- AA image: https://artificialanalysis.ai/image/leaderboard/text-to-image
- Arena general / photoreal: https://arena.ai/leaderboard/image/text-to-image and https://arena.ai/leaderboard/image/text-to-image/photorealistic
- BFL official FLUX3 details: https://bfl.ai/blog/flux-3-image-klein
- BFL source: https://github.com/black-forest-labs/flux-3-image-klein
- HF model family: https://huggingface.co/black-forest-labs/models
- NovelAI V5: https://docs.novelai.net/en/image/models/
- Anime model comparison: https://insiderllm.com/guides/best-anime-stylized-checkpoints-local-image-generation/
- WAI NSFW (community index): https://www.uncensorindex.com/models/wai-nsfw-illustrious
- Pony V6 (community index): https://www.uncensorindex.com/models/pony-diffusion
- CyberRealistic Pony (community index): https://www.uncensorindex.com/models/cyberrealistic-pony
- Lustify (community index): https://uncensorindex.com/models/lustify
- Local FLUX3 in Diffusers: https://huggingface.co/blog/flux-3

**Quality control:** All adult/style winners are editorial candidates, not numerical ratings; no owner-host inference executed. All publisher policy/license assertions remain pending exact artifact review before installation or distribution.
