# AG-D032 | Free, local-first Aegis Voice: research, architecture and evaluation TODO

**Captured:** 2026-11-09 (America/Chicago)  
**Status:** OWNER-REQUESTED / RESEARCHED / DESIGN TODO / NOT SCHEDULED / NOT BUILT OR HOST-CERTIFIED.  
**Project-wide scope (2026-11-09):** Owner-only, private, noncommercial Aegis across the owner's personally operated Fleet. See [Owner-only scope and license policy](AEGIS_OWNER_ONLY_SCOPE_AND_LICENSE_POLICY.md). Legally permitted free personal-use/noncommercial voice models are eligible even if they may not be publicly redistributed. Evaluate the exact weight/voice/reference license and whether private cross-device copying is allowed before import or transfer. The separate zero-subscription/zero-paid-API voice requirement still applies.
**Core 1.0 acceptance linkage (2026-11-09):** [Binding 1.0 owner-only shakedown crosswalk](../development/AEGIS_OWNER_ONLY_1_0_GO_LIVE_ACCEPTANCE_2026-11-09.md). If this optional companion is claimed supported at Core 1.0 GO, verify zero-paid, consented local STT and actual audio playback with G8 host evidence; Platform remains independent. Personal noncommercial licenses permit candidate evaluation only when actual terms and intended private/Fleet usage allow.
**Binding cost requirement:** The complete baseline listening + speaking path MUST be locally runnable **without subscriptions, paid API keys, metered speech calls, paid model downloads or ongoing hosted-service charges**. Optional external paid services are outside AG-D032's target release. Free usage does **not** remove GPU electricity, hardware or bandwidth cost.  
**Platform release fence:** Does NOT add a Platform 1.0 / AG-D028 blocker or alter issue #201's 38 acceptance rows. No installation, download, live microphone activation, owner-host execution, VM migration or Fleet enrollment authorized by this TODO.
**Ownership:** Expand the existing \`src/sofia/modules/voice/\` and RM-VOICE companion module. Do NOT create a competing voice Core, identity, general permission authority, second task ledger or duplicate module registry. 
**Cross-links:** AG-D005 Model Manager; AG-D028 Artifact Library; AG-D029 agent/inference alternatives; AG-D030 model landscape; AG-D031 Fleet efficiency / Sofía VM; RM-AVATAR2D; \`docs/sofia2/NON_CORE_MODULE_PLAN.md\`; \`docs/development/companion-v0.1.md\`.

## 1. Existing main-branch inventory verified 2026-11-09

| Current file | Observed capability | Caveat / replacement work |
| --- | --- | --- |
| \`src/sofia/modules/voice/tts.py\` | TTS backend protocol, queue, enabled state, backend probes, QUEUED/SPOKEN/FAILED/REJECTED/CANCELLED receipts, speaker text cleanup | Extend through adapter and transport streaming; avoid breaking synchronous legacy SAPI contract |
| \`src/sofia/modules/voice/sapi.py\` | Windows SAPI output with voice selection, rate and volume | Windows-specific fallback only; not an expressive neural cross-platform synthesizer |
| \`src/sofia/modules/voice/stt.py\` | Privacy-first one-shot input with default-disabled/mute/cancel, receipt validation; Windows \`System.Speech\` PowerShell recognizer | No native Whisper/Moonshine backend; limited to default Windows input, not cross-platform streaming |
| \`src/sofia/modules/voice/factory.py\` | Constructs SAPI TTS and Windows \`System.Speech\` STT | Currently rejects non-SAPI TTS backend; change via additive provider registry, not duplicate factory |
| \`src/sofia/modules/voice/prosody_matrix.py\` | Evidence-linked bounded emotion, rate, pitch, volume, energy, pause controls and tone tags | Must translate only supported control subset per TTS provider, with truthful receipt of applied controls |
| \`docs/development/companion-v0.1.md\` | Labels voice input/output wired/coded but explicitly **host-unverified** | Windows microphone, real playback, interruption and avatar sync still need installed-host tests |
| \`docs/sofia2/NON_CORE_MODULE_PLAN.md\` | RM-VOICE intended to expose TTS/STT, latency, mic consent and interruption receipts | Reuse as capability target; not evidence of a complete live voice assistant |

**No unverified readiness promotion:** Code presence != actual audio captured, synthesized, audible, interrupted or accepted by a verified user. A separate capture/listening event is not evidence of recognizing the owner. SAPI cannot provide the planned neural quality on its own.

## 2. Definition of FREE: product and licensing contract

- **Zero service fees:** no ElevenLabs/OpenAI/Azure/Google paid speech API, premium wake-word license, SaaS account, mandatory authentication token or usage quota on the baseline path. The system must function offline once approved model/assets are installed.
- **Source & weights differ:** runtime library LICENSE, actual checkpoint/model card, tokenizer/phonemizer/voice packs, reference speech audio, third-party codec, GPL obligations and model outputs may have different terms. Pin exact source revision, SHA-256, license and expected distribution permissions.
- **Free personal use ≠ permission to redistribute:** Aegis may use an approved non-commercial model privately only after its policy review, but no global Hub redistribution without actual permission. Prefer MIT/Apache2 weights for default redistributed optional modules. GPL engines may be viable with proper obligations and separate packaging.
- **No surprise downloads:** Approved source selection and signed, digest-verified library acquisition from AG-D028. Never let a TTS package auto-fetch arbitrary model/voice code during Platform bootstrap.
- **No paid-only Fallback:** Outage of a chosen voice engine degrades to another approved free local engine or text, never silently sends private audio to cloud.
- **Consent and voice rights:** Only clone owner-authorized source voices, with identity/source/consent traceability; default original synthetic Sofía voice profile. Do not create non-consensual impersonation/deepfake, spoof owner identity or treat speaker similarity as authentication.

## 3. Candidate stack based on publisher/official documentation

### 3.1 Speech to text (STT/ASR)
| Candidate | Code/model cost and licensing evidence | Strength | Tradeoff / Aegis role |
| --- | --- | --- | --- |
| **Moonshine Voice Streaming** | Publisher says local/no account; streaming STT models **MIT**; legacy non-streaming **some non-English models non-commercial** | Streaming latency, CPU/device support incl Windows, Linux, Android/RPi | **First live CPU-oriented STT pilot**, measure English model quality, noise and false-starts. Do not claim publisher performance applies to 9700K/VM |
| **faster-whisper** (CTranslate2) | Open source runtime, Whisper weights by exact source/version | Strong full-utterance transcription, efficient GPU/int8; good quality baseline | **Accuracy benchmark / optional GPU STT**, may contend with Venus LLM for VRAM |
| **whisper.cpp** | Open C/C++, CPU-only and CUDA/Windows/Linux support | Portable local fallback, predictable native interface | **Primary native fallback / comparative benchmark**; optimize model size per host |
| **Vosk** | Apache-2.0 API, model-specific license to verify | Lightweight streaming and command grammar, Pi/CPU compatible | **Constrained-CPU alternative**, accuracy must be measured |
| **RealtimeSTT** | MIT orchestrator, engine and model dependencies vary | Ready-made recorder/VAD/partial-transcription orchestration | Optional reference implementation, not mandatory core dependency or new authority |
| **Windows System.Speech** | Existing OS backend | Already wired in code | Keep as offline Windows compatibility fallback; not assumed multilingual/streaming |

### 3.2 Text to speech (TTS)
| Candidate | Exact source/license caveat | Suitability | Decision |
| --- | --- | --- | --- |
| **Qwen3-TTS VoiceDesign 1.7B** | Qwen official Apache-2.0 checkpoint; HF files about **4.52 GB**, but runtime peak memory unmeasured | Design a *new*, consistent feminine, warm, medium-pitch, slightly smoky Sofía voice | **Voice-identity authoring candidate**, run on approved GPU only for voice creation; not necessarily permanently resident |
| **Qwen3-TTS Base 0.6B** | Apache-2.0; downloadable files about **2.52 GB**, including tokenizer/assets | ~3-sec reference cloning, streamed synthesis, multilingual | **Expressive live voice candidate** after approved original reference; compare real VRAM and cold/warm timings |
| **Kokoro-82M** | Apache-2.0 weights, 82M params | Lightweight preset voice, CPU-friendly, no natural reference voice cloning | **First dependable non-GPU TTS fallback**; compare ONNX builds |
| **Pocket TTS (Kyutai)** | MIT code, confirm exact voice/weight license/attribution; 100M CPU model and smaller English variants Oct 2026 | CPU streaming, published ~200ms first-chunk reference, original/authorized voice embedding | **Strong CPU-first live-voice pilot**; Rust standalone binaries exist for Windows/Linux, pin exact package |
| **Piper (OHF-Voice)** | **GPL-3.0 engine**; voice model licenses vary, inspect per voice | Extremely small/offline/CPU; compatible with existing Home Assistant ecosystem | **Low-end/VM fallback**, not silently bundle GPL binary/voice without complying |
| **Fun-CosyVoice 3** | Apache-2.0 repository, verify exact weights and dependencies | Zero-shot multilingual voice, streaming, controllable prosody | Quality A/B candidate; higher integration complexity |
| **VoxCPM2** | Publisher says Apache-2.0 code/weights; 30 languages, 48kHz, voice design/cloning | Potential high-quality voice, but 2B may be heavy for concurrent 12GB GPU | Offline voice-design/quality comparison only initially |
| **Supertonic 3** | MIT sample code; **OpenRAIL-M** model (use/redistribution restrictions) | 31 languages, ONNX CPU, expressive tags; no mandatory subscription | Optional **licensed** comparison, not assume Apache-like redistribution |
| **Chatterbox V3/Nano** | MIT archive; **official upstream retired and unmaintained since Aug 2026** | Historical quality and cloning baseline | **Research comparison only**, not preferred maintained production dependency |
| **F5-TTS (pretrained)** | **MIT code; weights CC BY-NC 4.0** per official source | Free local voice-cloning/quality challenger for private noncommercial evaluation | **Eligible conditional for owner's personal use**; no automatic Hub redistribution; benchmark real CPU/GPU latency |
| **XTTS-v2** | **Coqui Public Model License (CPML)** explicitly includes qualifying personal/private noncommercial use and outputs | Established multilingual cloning/voice identity comparison | **Eligible conditional for owner's personal use**, exact runtime/weights + voice-consent check, not an implied unrestricted redistribution right |
| **Fish Speech: current Drama 3 / S2-Pro family** | **2026-10-13 Fish Audio Community License** allows some private noncommercial uses, but **S2-Pro weights have separate Research License** and hosted-service conditions may apply | High-quality expressive voice candidate, **Drama 3 35B-A3B too large to assume 12GB resident**; S2-Pro 4B must be measured | **Research conditional; legal hosted-service + exact checkpoint approval required** before VM/Fleet pilot, not a mandatory baseline |

**Owner-only license reconsideration (2026-11-09):** The project is a **private personal/noncommercial** AI ecosystem. Accordingly, **F5-TTS pretrained CC-BY-NC 4.0 weights** and **XTTS-v2 CPML weights**, while not suitable as unrestricted commercial redistribution defaults, are now **eligible for free local personal-use research and quality comparison** when their exact terms are satisfied. [F5-TTS official weights](https://huggingface.co/SWivid/F5-TTS), [XTTS-v2 official license](https://huggingface.co/coqui/XTTS-v2/blob/v2.0.3/LICENSE.txt). Add an optional **V3 voice-design A/B test** comparing original authorized Sofía voice: Qwen3-TTS vs Pocket TTS vs F5-TTS vs XTTS-v2, under identical sentences, CPU/GPU/latency/privacy measurements; do not claim XTTS/F5 are the optimal live runtime without tests. Voice remains strictly **zero subscription, free offline baseline**. Exact source/checkpoint license, reference recording consent and rights to clone/copy across Fleet must still be verified independently. [Owner-only GO acceptance](../development/AEGIS_OWNER_ONLY_GO_LIVE_ACCEPTANCE_2026-11-09.md) applies, but this candidate expansion is **not a mandatory Platform/Core 1.0 voice feature**.

**NO definitive naturalness champion:** No direct independent listening evaluation of the owner's desired voice and budget was run. Separate *provider marketing quality claims* from actual same-sentence blind ABX listener tests.

### 3.3 Supporting components
- **VAD:** Silero VAD MIT on CPU/ONNX for speech detection, endpointing and automatic interruption; independent mic consent. WebRTC VAD is an alternative with lower footprint; evaluate short/noisy utterances.
- **Wake phrase:** Prefer push-to-talk for first release. Future opt-in on-device wake detection with recorded wake phrase, physical mic indicator and false-trigger rejection. **openWakeWord code is Apache-2.0, but bundled pretrained wake models CC BY-NC-SA**; use only after checkpoint rights review, or evaluate custom entirely self-owned wake data/model. No hidden always-listening switch.
- **Noise suppression/echo cancellation:** Evaluate WebRTC Audio Processing / AEC (and optionally RNNoise) before duplex mode. Playback leaking into mic must not self-trigger Sofía.
- **Audio transport:** device capture/playback on approved authenticated client; in-process ring buffers or bounded local IPC; optional versioned authenticated Fleet audio stream only after explicit per-device consent. Prefer PCM locally, Opus for bandwidth-sensitive remote streams after licensing and security review. None is remote by default.
- **Speaker recognition:** Treat as identity *hint* only, never owner authentication or proof that command is approved. Exact owner/operator auth is Platform-owned.

## 4. Proposed pipeline

\`\`\`text
  User explicitly enables PTT / consented listening
        | (local device + mic indicator; never hidden)
        v
  Audio capture (device ID / generation / STOP gate)
        -> optional AEC / noise reduction
        -> Silero VAD + endpointing
        -> STT adapter: Moonshine / faster-whisper / whisper.cpp / Vosk
        -> bounded transcript + confidence/provenance + user visibility
        -> existing INTERACT/CognitiveRequest and canonical Sofía Core
        -> settled, audience-appropriate reply and approved expression intent
        -> existing prosody matrix
        -> TTS adapter: Qwen3 / Pocket / Kokoro / Piper / SAPI
        -> interruptible, chunked playback by **actual approved client**
        -> proven playback receipt + audio timing to optional Avatar lip sync
\`\`\`

**Trust separation:** Speech samples and transcriptions are untrusted observations. VAD is not human presence proof; voice ID is not authentication; LLM claims about being heard/spoken are not receipts. Only a verified capture backend can claim LISTENING and a verified output sink can claim playback, with distinct generation/output IDs. No new Core writer. No direct module-originated system effects.

**Recommended first-person experience:** Audio input OFF until explicitly activated. Push-to-talk mode first, visual mute/talking state, transcript confirmation or correction, streaming reply audio, immediate barge-in when PTT pressed, text always available. Later full duplex and wake-word as separately reviewed opt-in.

## 5. Voice identity and expression policy

**One enduring Sofía voice profile**, not tied to one TTS model or one saved random audio sample. Candidate descriptive voice: *feminine; warm/confident; medium pitch; slightly smoky; natural conversational pauses; understated dry wit; flexible energy; not cartoonishly high, robotic, exaggeratedly flirtatious or constantly breathy.* It is an owner-reviewable aesthetic goal, not proof that a pretrained model can hit every dimension.

Protected voice asset manifest (exact format to version): \`core_identity_id\`, \`voice_profile_id\`, voice design text/revision, authorized origin/reference WAV/digest/consent/licensing, optional approved speaker embedding, compatible TTS backends + model digests, permitted languages, normalizer/phonemizer version, pronunciation lexicon, prosody baseline, expression mapping and rollback lineage. Voice belongs to Core protected assets and is not replicated through public Hub by default.

Aegis existing \`VoiceProsodyProfile\` maps bounded rate/pitch/energy/volume/pause and evidence-linked tone/emotion tags. Map only controls **actually supported** by each backend; preserve unknown/unsupported as explicit skipped controls in playback receipts. Emotion comes from Core-reviewed state and authorized audience projection, **not** from an untrusted prompt telling TTS to act angry/romantic. For adult/private conversations the voice *uses the existing audience authorization and scoped memory*, never public Discord or unauthenticated listeners. The voice engine itself must not decide that private words can cross an audience boundary.

**Voice authoring test:** Qwen3-TTS 1.7B VoiceDesign optionally generates original seed samples; owner chooses approved reference, then evaluate Qwen3-TTS Base 0.6B vs Pocket TTS's authorized voice embedding. Verify consistent identity across phrases, longer content and emotion shifts. Do not require GPU voice authoring for ordinary daily speech. Clone another human's voice only with permission and clear provenance.

## 6. Fleet and compute efficiency (AG-D031)

- **Artemis/Sofía VM:** canonical Core and interface orchestration; no assumed GPU. Voice capture/playback follows the owner's actual client device, not a headless VM microphone. CPU STT/TTS only if observed budget permits; do not assume VM's CPU is free.
- **Venus RTX 3080 Ti (12GB VRAM):** optional GPU STT/high-quality TTS, not both permanently resident with a Qwen 9B/14B LLM unless **measured** full model+KV+CUDA+display headroom. Voice is latency-sensitive: preferred design **Moonshine/Pocket or Kokoro on CPU, LLM on GPU**; batch design Qwen3 voice seed creation while primary LLM is unloaded.
- **Third compute node:** capabilities UNKNOWN until hardware inventory. Do not promise audio-device presence or spare memory.
- **Resource arbitration:** reuse Aegis one Platform/Fleet scheduler and GGUF/model roles; free CPU does not mean infinite throughput, and tiny ONNX graph doesn't imply negligible host battery/power. Preload one tiny CPU voice only where useful. Do not duplicate the same voice model in many VMs without an explicit latency/privacy justification.
- **Network:** if approved, remote model STT/TTS exchange uses bound principal/audience/device, per-session consent, exact host and worker generation, encryption, replay protection and bounded buffers. Server loss or stale connection => text-only/local fallback, NOT hidden cloud route.
- **Operator-facing visibility:** real-time mic mode, selected devices, active audio host, voice model/backend/digest, GPU/CPU usage, idle unload timer, p50/p95 ASR and TTS latency, privacy setting, streaming state and last verified receipt in one Aegis Control Center/TUI interface.

## 7. Functional requirements and state machine

States for optional free voice session: DISABLED -> IDLE -> ARMING -> LISTENING -> ENDPOINTING -> TRANSCRIBING -> CORE_TURN -> SYNTHESIZING -> PLAYING -> IDLE; side states MUTED, INTERRUPTING, CANCELLED, DEGRADED, FAILED, STOPPED. Mode can be PTT, hold-to-talk, explicit hands-free, future opt-in wake word. Distinguish capture/transcribe/turn/synthesize/playback stop domains and generations.

**Critical engineering edges:**
1. **Interrupt/barge-in:** PTT held while speaking stops output immediately, discards old generated chunks, revokes playback generation and begins new permitted capture; no prior TTS chunk can replay after STOP/revocation.
2. **No ghost voice:** generated WAV file is not SPOKEN; only actual output-sink complete confirmation can assert output attempt/completion. Receipt must distinguish audio **queued**, **generated**, **played by sink**, **audible to user UNKNOWN**.
3. **Turn binding:** audio chunk IDs / utterance ID / canonical turn ID / consent revision / audience / principal/device / worker generation / model digest / deadlines / settings revisions / audio sink ID. Reject replays and stale jobs.
4. **Safety/privacy:** PTT is default; disable mic and raw-audio persistence by default. Opt-in short buffer with TTL; separate approval for retention/training, wake-word operation, remote streaming, or reference voice capture. Audio never trains any model by default.
5. **No accidental commands:** STT transcription of TV/YouTube/Sofía's own TTS or a guest cannot grant owner privilege. Protect against prompt injection and voice replay. Confirmation required for sensitive operations through existing SAFE mechanisms.
6. **Audio quality:** test 16k mono mic to STT, convert to backend-specific TTS output sample rate, correctly resample, compensate echo and volume normalize; explicit device-unplug/replug recovery and headset/speaker differences.
7. **Spoken content:** normalize Markdown, code fences, URLs, dates, acronyms, punctuation and numbers; allow silent text segments. Avoid speaking secret values / private data at an unsafe audience.
8. **Avatar:** separate audio amplitude/viseme timings and actual rendered-frame receipts; never claim avatar lip sync just because TTS emitted metadata.
9. **Offline and failure:** CPU fallback preferred for voice; text remains available without mic/TTS, without auto-downloading models, and without mandatory external cloud services.

**Candidate live interaction design targets, NOT measured or acceptance claims:** PTT-to-recognition display p50 < 1.5 s after speech endpoint; voice response first-audio p50 < 1.0 s after initial text available; barge-in sink mute < 250 ms; no unintended mic capture. Thresholds to be refined on approved actual hosts and observed p95.

## 8. Interfaces and package design (proposed, not implemented)

Extend, rather than replace, current \`SpeechInputBackend\`, \`SpeechInputService\`, \`TTSBackend\`, \`TextToSpeechService\`, probes, receipts and \`VoiceProsodyProfile\`. Add versioned optional streaming capabilities negotiated after original synchronous methods. Existing Windows paths keep working.

**Proposed types** (adapt to neutral SDK versions before writing code):
- \`VoiceInputDeviceInfo\` and \`VoiceOutputDeviceInfo\` (host, device ID, availability, privacy mode, observed timestamp and last failure).
- \`SpeechStreamRequest\` (authenticated session, principal/audience, device, capture generation, consent scope, sample rate, channel count, deadlines and caps).
- \`SpeechSegmentEvent\` (start/end timestamps, partial/final transcript, confidence if calibrated, language, provider and evidence ref).
- \`SpeechSynthesisRequest\` (canonical turn + utterance ID, text chunk, voice profile revision + license-approved ref, prosody, deadline and permitted output device).
- \`AudioChunkEvent\` (sequence, PCM or reviewed codec, sample rate, timings, bounded bytes and generation) and \`AudioPlaybackReceipt\` (queue/synthesize/played/interrupted/error).
- \`VoiceEngineManifest\` (source/digest/license/voice pack/model dependencies, CPU/GPU requirements, supported controls/languages, text tokenizer, VRAM budget, sandbox permissions, exact installed revision).
- \`VoiceStatusSnapshot\` + an authenticated bounded event stream consumable by GUI/TUI/CLI and user-approved mobile clients.

Implement neutral \`stt.moonshine\`, \`stt.whisper_cpp\`, \`stt.faster_whisper\`, \`tts.qwen3\`, \`tts.pocket\`, \`tts.kokoro\`, \`tts.piper\` *as optional provider identities within existing RM-VOICE registry*, NOT eight standalone mandatory Platform services. Names are candidates, no registration completed. Optional \`vad.silero\`; planned \`wake.openwakeword\` ONLY if licensing and opt-in safety approved.

Audio devices generally belong to user clients; do not force open-device calls from the canonical Core VM or public Fleet process. A headless Platform install remains Core-free, voice-free and healthy. Model/speech engine workers run confined with no privileged Aegis file/secret/tool access.

## 9. Stage plan / candidate work packages

| ID | Batch | Exit evidence (not yet executed) |
| --- | --- | --- |
| V0 | License and exact model artifact review; documented no-cost dependencies | Approved per-checkpoint source/revision/digest/redistribution ledger; reject paid/metered requirement |
| V1 | Existing code seam tests and compat provider registry | Windows SAPI and \`System.Speech\` still behave; new providers opt-in; Platform startup Core-free with zero audio dependencies |
| V2 | CPU-first push-to-talk prototype | Moonshine vs whisper.cpp actual transcripts, Pocket vs Kokoro/Piper real audio; observed CPU/RAM, endpointing and cancellation |
| V3 | Voice identity authoring and neural synthesis | Qwen3-TTS voice design and 0.6B cloning, consistent original Sofía timbre, voice asset manifest, rollback and consent checks |
| V4 | Interruptible streaming + avatar projection | Chunked playback, barge-in, sink receipts, visemes/amplitude and real GUI indicator, no ghost audio |
| V5 | Distributed voice endpoints and optional alternate GPU backend | VM -> approved client audio; optional Venus native TTS/STT under AG-D031 budgets; no cross-Fleet secret exposure |
| V6 | Hands-free, wake word and noise/echo hardening (opt-in later) | False trigger/spoof/replay/TV test matrix, hardware mute indicator, AEC, no voice-based owner authentication |
| V7 | Windows+Debian installed-host comparative signoff | Exact SHA, licensed signed package, cold/warm speed and quality, crash/STOP/mute/revocation/device unplug, no hidden cloud/payments |

## 10. Independent future acceptance matrix (ALL NOT TESTED)

1. **VOICE-01:** Platform-only Windows/Debian install with no Python voice libs, microphone, model, GPU, Core or internet remains healthy.
2. **VOICE-02:** Actual SAPI/Windows System.Speech compatibility tests on a disposable approved Windows host; existing receipts and fallback preserved.
3. **VOICE-03:** Per-code/per-model/per-voice **free** and redistribution licensing verified, exact digest pinned, no paid API or auto-download requirement.
4. **VOICE-04:** Owner-enabled mic PTT starts only approved device and returns recognized transcript; disabled/muted/no permission yields no capture.
5. **VOICE-05:** Moonshine CPU streaming vs whisper.cpp/faster-whisper baseline measured on multilingual, casual, noisy and technical commands; no invented confidence.
6. **VOICE-06:** Silero VAD endpointing rejects silence and TTS/TV false positives in controlled tests; timestamps and end-of-speech correct.
7. **VOICE-07:** Pocket TTS/Kokoro/Piper real local output across cold/warm starts and CPU budgets with no GPU dependency.
8. **VOICE-08:** Qwen3 voice design gives repeatable authorized reference, and 0.6B clone profile matches chosen Sofía voice; restart and backend changes preserve identity.
9. **VOICE-09:** Prosody adapters apply only supported emotion/rate/pitch/volume controls and accurately receipt ignored ones.
10. **VOICE-10:** Synthesized chunks reach actual output sink; status NEVER claims heard/spoken solely on text/model generation.
11. **VOICE-11:** PTT interruption during active synthesis/playback terminates old audio chunks and does not restart old turn after cancellation.
12. **VOICE-12:** STOP, revocation, untrusted principal, stale worker and session/device generation deny input/output and discard late chunks.
13. **VOICE-13:** Headset unplug, mic switch, speaker mute, echo, loss of network, backpressure and malformed audio produce bounded truthful failures.
14. **VOICE-14:** No unauthorized hot mic, wake phrase, raw recording, storage, external telemetry or cross-audience audio replication, even in recovery.
15. **VOICE-15:** Sensitive spoken request cannot bypass SAFE approval, spoof owner auth or leak Core private memories from guest/Discord audiences.
16. **VOICE-16:** Normalized speech handles abbreviations, URLs, emoji, markdown/code, numbers and technical instructions without saying secrets.
17. **VOICE-17:** Avatar lip sync/face movement uses actual timed audio + verified render receipt, independent of source speech model.
18. **VOICE-18:** AG-D031 pressure test: one 12GB GPU, active Qwen LLM, CPU voice, optional Qwen3-TTS GPU preload, game foreground; record VRAM/RAM/CPU/power and accepted resource decisions.
19. **VOICE-19:** Voice model source/license/digest is visible in Aegis UI/TUI; uninstall/disable leaves existing text and Core identity intact.
20. **VOICE-20:** Owner-disabled internet / absent WAN still supports full PTT -> STT -> Core text -> TTS -> actual device playback after optional models preinstalled.
21. **VOICE-21:** Hands-free/wake word stays disabled unless specifically consented; properly distinguishes ambiguous/false wake and has a positive hardware UI/mute check.
22. **VOICE-22:** Approved Windows and Debian full signed bundle/integration tests, exact SHAs, actual performance/latency quality, fallback, licensing, user acceptance and independent signoff.

## 11. Primary research sources checked on 2026-11-09

- Official Qwen3-TTS repository / variants / voice design: https://github.com/QwenLM/Qwen3-TTS
- Qwen3 voice design model and weights license: https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign
- Qwen3 0.6B Base: https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-Base
- Kokoro Apache 2.0 model: https://huggingface.co/hexgrad/Kokoro-82M
- Pocket TTS official CPU/streaming/Rust binaries/voice cloning: https://github.com/kyutai-labs/pocket-tts
- Moonshine Voice project + model licensing: https://github.com/moonshine-ai/moonshine ; https://github.com/moonshine-ai/moonshine/blob/main/docs/license.md
- faster-whisper: https://github.com/SYSTRAN/faster-whisper
- whisper.cpp: https://github.com/ggml-org/whisper.cpp
- Vosk: https://github.com/alphacep/vosk-api
- Silero VAD: https://github.com/snakers4/silero-vad
- Piper engine (GPL-3.0) and per voice card: https://github.com/OHF-Voice/piper1-gpl ; https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/VOICES.md
- VoxCPM 2: https://github.com/OpenBMB/VoxCPM
- Fun-CosyVoice 3: https://github.com/QwenAudio/CosyVoice
- Supertonic 3 OpenRAIL-M: https://huggingface.co/Supertone/supertonic-3
- Chatterbox V3 archived and unsupported since Aug 2026: https://github.com/resemble-ai/chatterbox
- openWakeWord pretrained weight restriction: https://github.com/pozalabs/openwakeword
- RealtimeSTT orchestration reference: https://github.com/KoljaB/RealtimeSTT

**Research conclusion:** a free, locally served, CPU-first voice stack is feasible in principle but NOT validated end to end here. First prototype should test **Moonshine streaming STT + Silero VAD + Pocket TTS or Kokoro**, retaining Windows legacy fallback; separately generate an original Sofía reference using **Qwen3-TTS VoiceDesign** and measure **Qwen3-TTS Base 0.6B** against CPU-first synthesis. Do not make any of it Platform 1.0 mandatory.
