# AG-D030 | AI model landscape: frontier, local, coding, mature fiction and image generation

**Research snapshot:** 2026-11-09 (America/Chicago). **Status:** RESEARCHED / OWNER-REQUESTED TODO / NOT SCHEDULED. **No weights downloaded, no models installed, no live tests, no provider changes.**
**Project-wide scope (2026-11-09):** This is an owner-only, private noncommercial homelab project, not a model shipping business. See [Owner-only scope and license policy](AEGIS_OWNER_ONLY_SCOPE_AND_LICENSE_POLICY.md). Candidates with restrictions on commercial use may still be fully eligible for authorized private use if their exact license permits. Check copies/transfers separately; do not automatically require commercial redistribution rights merely for local model ranking.
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

## 0.1 Owner-only license and cost re-review (binding 2026-11-09)

[The owner-only 1.0 go-live crosswalk](../development/AEGIS_OWNER_ONLY_1_0_GO_LIVE_ACCEPTANCE_2026-11-09.md) makes private, noncommercial use a release constraint. **Re-ranking by legal eligibility must not be confused with re-ranking by measured quality.** The original general/coding winners are retained as **reference benchmarks**, not mandatory cloud dependencies or promises of free use. Candidate selection for an **actual local Aegis default** must establish hardware fit, exact model/voice weight license, no paid API, privacy and acceptable performance.

| Candidate / category | Personal/noncommercial access re-review | 12GB local fit | Revised Aegis role / status |
| --- | --- | --- | --- |
| Gemini 4 Carbon / Claude Opus 5.5 / GPT-6 Astra (frontier or hosted coding) | Hosted/API account and pricing/terms differ, **not** assumed free | **NO**, closed hosted models | Overall external reference only; none required for Platform/Core 1.0 |
| Qwen3.5 9B / Gemma 4 12B | Local models already in owner inventory; verify exact license + quant digest | **Likely**, context-dependent | Existing preferred general A/B stays; actual 12GB acceptance pending |
| Qwen2.5-Coder 14B / Qwen3.5 9B | Local self-hosted use with checkpoint-specific provenance | **Likely**, 14B tighter | Existing local coding A/B unchanged until same-hardware benchmarks |
| Huihui-Qwen3.5 9B / Stheno 8B / Rocinante 12B / Magnum variant | **Conditional:** exact fine-tune license + base model terms may differ; no blanket trust from "uncensored" | **8B/9B likely**, 12B quant/context dependent | Adult/private creative comparison eligible for owner-only deployment; local privacy and audience scopes required |
| **FLUX.1 [dev] / Kontext [dev]** | BFL **Non-Commercial License v2.0** explicitly covers specified personal/hobby use, but carries **non-production, use and distribution restrictions**; read exact variant terms before allowing planned use | **Unverified** on 12GB full pipeline; often needs aggressive offload | **Newly eligible conditional** photoreal/editing comparison, NOT automatic replacement for FLUX3/SDXL |
| **FLUX.2 [klein] 9B** | BFL states FLUX Non-Commercial license; noncommercial use may qualify, full terms must be checked | **Not assumed resident** on 12GB; 4B Apache variant is easier | Optional quality-versus-resource experiment; not default for Venus |
| **FLUX.2 [klein] 4B** | BFL lists **Apache-2.0**, local use and commercial rights subject to terms | **More practical** for consumer GPU | Retain as reliable compact comparison for FLUX3 |
| **FLUX 3 Image Klein INT8** | BFL publisher model card says **FLUX Kommunity License**, permitting certain noncommercial uses, **with specific production/other limits**; not Apache and not an unrestricted redistributable weight | **Publisher claims 8GB+ minimum**, end-to-end memory unmeasured | Still first local photoreal candidate; add legally permitted target-use/voice/Hub transfer review |
| Pony V6 / NoobAI / Animagine / Illustrious / WAI checkpoints | **Version/author-specific licenses**, sometimes noncommercial, attribution or platform-level restrictions; inspect exact checkpoint + merged base + LoRAs | Often **practical SDXL class**, not guaranteed | Keep local anime/adult candidates, with documented provenance and local-only model asset policy |
| F5-TTS / XTTS-v2 (voice crossover) | **F5 weights CC BY-NC 4.0; code MIT**. **XTTS-v2 CPML**, explicitly allows qualifying personal/hobby use. | **Benchmark**, not inferred from checkpoint size | Add to Voice AG-D032 adult-safe/private voice-quality comparison; does not require paid APIs |
| Fish Speech community family (voice crossover) | 2026-10-13 Fish Audio Community License permits certain noncommercial hobby use, but current S2-Pro weights retain separate Research License; commercial and **hosted-service** exceptions need precise classification | Drama 3 35B-A3B not 12GB-ready by file size; S2-Pro 4B requires measurement | Conditional research candidate; do not treat VM/Fleet personal access as automatically outside hosted-service terms |

**Not all published web/hosted models are free.** The *voice baseline* AG-D032 still requires genuinely zero-paid subscriptions/API usage. Private adult conversations/images must not go to an unapproved public model provider. Check FLUX's **non-production** and Fish's **hosted-service** clauses before treating "private" as permission for a deployed Aegis inference endpoint.

**License primary sources:**
- BFL personal/noncommercial rules: https://bfl.ai/legal/non-commercial-license-terms ; https://help.bfl.ai/articles/9272590838-self-serve-dev-license-overview-pricing
- FLUX 3 source + Kommunity license: https://huggingface.co/black-forest-labs/flux-3-image-klein
- FLUX.2 4B vs 9B license: https://github.com/black-forest-labs/flux2
- XTTS-v2 CPML: https://huggingface.co/coqui/XTTS-v2/blob/v2.0.3/LICENSE.txt
- F5 pretrained weights/code: https://huggingface.co/SWivid/F5-TTS and https://github.com/SWivid/F5-TTS
- Fish 2026 community/license family: https://github.com/fishaudio/fish-speech/blob/main/LICENSE ; https://github.com/fishaudio/fish-speech

## 0.1 Owner-only model-table re-evaluation (2026-11-09, GO scope clarification)

**Decision:** For a private hobby/personal-use Aegis, **free noncommercial checkpoints are eligible candidates** when the exact terms permit the intended use. This changes *license suitability and candidate pool*, **not** measured quality, VRAM, model safety or model publisher trust. The existing leaderboard picks below remain *historical 2026-11-09 research recommendations*; no updated hardware A/B comparison has occurred. [Binding GO/shakedown overlay](../development/AEGIS_OWNER_ONLY_GO_LIVE_ACCEPTANCE_2026-11-09.md) requires the Platform/Core to honor owner-only operation, but installing the models listed here remains optional.

| Original requested ranking role | Owner-only revision to prior table | Cost/license review status | 12GB GPU / privacy reality |
| --- | --- | --- | --- |
| Best overall general (hosted) | **No quality re-rank from private use.** Compare same frontier contenders under current independent evaluation | Provider use terms, data privacy and metered API costs; **not free local weights** | Not local; optional cloud only |
| Best general for homelab | Keep Qwen3.5 9B / Gemma 4 12B / Qwen3 14B **pending real comparison** | Exact upstream weight license, Ollama GGUF derivative and usage obligations must be pinned; not automatically rejected due commercial terms | Quantized 9B preferred baseline; measure context/VRAM |
| Best coding overall (hosted) | No quality re-rank; frontier agent performance remains benchmark-based | Cloud cost/provider privacy; separate from voice's mandatory free constraint | Optional only |
| Best coding for homelab | Keep Qwen2.5-Coder 14B vs Qwen3.5 9B | Per checkpoint and finetune license check; commercial distribution rights *not required* as a ranking prerequisite | 14B VRAM tight; 9B stronger context headroom |
| Best adult/mature text overall | Hosted low-refusal or roleplay ranking remains provisional | Provider age/terms and permitted mature output; cannot infer policy from model name | Prefer local if owner privacy matters |
| Best adult/mature text for homelab | Keep Huihui-Qwen3.5-9B plus Rocinante/Stheno/Magnum experiments, **no automatic exclusion of noncommercial weights** | Derivative weights may retain base-model and bespoke conditions; exact checkpoint unknown until pinned | 8–12B quantized comparison |
| Best photorealistic non-nude overall | Hosted candidate unchanged by personal-use license | Provider terms & credits vary | No local weights implied |
| Best photorealistic non-nude homelab | FLUX 3 Klein INT8 stays first experiment; **RealVisXL V5** additionally eligible in OpenRAIL++ family | Model card license [OpenRAIL++](https://huggingface.co/SG161222/RealVisXL_V5.0) is not plain MIT; obey terms | Check complete FLUX pipeline; SDXL fallback ~7GB |
| Best anime non-nude overall | Hosted NovelAI specialist remains preference-dependent | Hosted subscription/terms, not an automatically free product | Local anime candidates below avoid account dependency |
| Best anime non-nude homelab | **NoobAI XL v-pred**, **Animagine XL 4.0 Opt**, Illustrious variants; expand pool on personal-use terms | [NoobAI Fair AI Public License](https://huggingface.co/Laxhar/noobai-XL-Vpred-1.0); [Animagine CreativeML Open RAIL++-M](https://huggingface.co/iiYonko/animagine-xl-4.0). Must inspect exact derivatives/restrictions | Compatible SDXL variants, LoRA formats matter |
| Best adult photorealistic overall | Lustify vs CyberRealistic remains **editorial**, not validated benchmark winner | Specific adult model release/license and provider terms unknown until exact pin | Hosted output privacy varies |
| Best adult photorealistic homelab | CyberRealistic Pony / eligible Lustify SDXL / RealVisXL remain candidates; do **not** disqualify modified noncommercial licenses just for being noncommercial | Verify exact source and finetune terms. [Pony V6](https://huggingface.co/neryK/Pony_Diffusion_V6_XL) has commercial-hosting restrictions in modified Fair AI Public License; private hobby inference may be permitted, verify complete terms | SDXL ~7GB checkpoint class; headroom needed |
| Best adult anime overall | NovelAI hosted vs WAI/Illustrious open family, style and provider policy dependent | No universal standard adult quality leaderboard; no blanket eligibility claim | Prefer local for private prompts |
| Best adult anime homelab | WAI-NSFW-Illustrious vs Pony Diffusion V6 XL; personal noncommercial licensing enlarges usable pool | Exact weight/derivative terms and permission for copying across Aegis Fleet remain per-artifact checks | LoRA compatibility differs; generally SDXL-class |

**New free personal-use voice entries affecting AG-D032 (not the image ranking):**

| Voice model | Verified upstream model terms | Personal Aegis implication |
| --- | --- | --- |
| **F5-TTS pretrained weights** | [CC BY-NC 4.0](https://huggingface.co/SWivid/F5-TTS) for pretrained checkpoint; code MIT | Newly eligible **voice cloning/naturalness A/B candidate** for private authorized source voice; not automatically a broadly distributable default |
| **XTTS-v2 pretrained weights** | [Coqui Public Model License](https://huggingface.co/coqui/XTTS-v2/blob/v2.0.3/LICENSE.txt), explicitly allows personal hobby/private entertainment under noncommercial conditions | Newly eligible **multilingual clone/voice comparison**; cannot treat its output license as unrestricted |
| **Kokoro-82M** | [Apache-2.0](https://huggingface.co/hexgrad/Kokoro-82M) | Remains excellent zero-subscription/lightweight candidate; license not the only quality factor |
| **Qwen3-TTS / Pocket TTS** | Check exact checkpoint and voice reference artifact licenses | Remain original live/voice-design shortlist pending hardware tests |

**Important separation:** this new license interpretation is not an authorization to fetch weights, copy them to peers, publicly serve files, or run adult/private samples. Cross-node rights are a second separate decision after lawful personal local use. An NC model cannot automatically be shipped in Aegis signed public release bundles. A model's uncensored outputs or a person's voice likeness never authenticate the owner. A third-party public platform's model/content policies remain binding. **Evidence remains NOT TESTED; no new overall quality winner is declared by this update.**

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

## AG-D033 follow-on: Grok-style local private roleplay, initiative and continuity (2026-11-09)

Owner specified three deficiencies with hosted Grok RP: unwillingness to continue certain permitted adult fictional scenes, weak conversational initiative, and personality/relationship-memory drift. The dedicated [AG-D033 local RP and continuity design](AG_D033_LOCAL_RP_AND_CORE_CONTINUITY_RESEARCH_2026-11-09.md) is the authoritative follow-on to this landscape: first A/B Rocinante-X 12B Q4 vs existing Huihui-Qwen3.5 9B, then Anubis Mini 8B / Stheno 3.2 8B / Magnum v4 12B subject to exact license checks. **Never confuse a lower-refusal model with higher RP quality;** actual improvement also needs Core-owned initiative, scene recaps, privacy-scoped episodic retrieval and one persistent Sofía identity. Its RP-01..RP-16 test plan remains research TODO, not go-live evidence or a new Platform #201 blocker. No models were installed or measured on Venus by this research.

