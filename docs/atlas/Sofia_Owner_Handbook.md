# Sofía Ada Lyra: Owner's Handbook

**Edition:** V18 Overview • 2026-10-19  
**Source snapshot:** [`21f0ec2a098d9ff5621686e218dcdf2524fc65d6`](https://github.com/Crazysodaman/SofiaAdaLyra/tree/21f0ec2a098d9ff5621686e218dcdf2524fc65d6)  
**The other books:** [Technical & MENTOR Reference](Sofia_Technical_MENTOR_Reference.md) • [Complete Atlas, all 780 requirements](Sofia_Complete_System_Atlas.md).

> **What this book is:** A practical guide to what Sofía is designed to be, which functions have corresponding implementation, how to ask for them, what evidence to expect, how to troubleshoot, and how to decide what is genuinely ready. It is not a certification that every described function is installed or operational today.

## Quick-start: Ask for evidence, not magic
1. Start with the Sofía interface or authenticated channel that is **actually running**. A source-coded Android or Discord feature is not necessarily configured on your current host.
2. Describe what you want in ordinary language. For any real-world claim, ask her to identify the host/service/source and timestamp.
3. Let her explain what she can inspect without elevated permission and what action would require your explicit approval.
4. For a change to real systems, insist on the before-state, allowed action, expected effect, rollback and after-state.
5. If she cannot verify, she should say **unknown**, not pretend that a confidence score is proof.
6. For features not connected to Main chat, use the separately documented owner CLI or manual test until a supported UI exists.

**Useful starter questions**

> "Sofía, which services are currently healthy, which observations are stale, and which ones are unavailable?"

> "Tell me what we actually finished on Gaia. Distinguish verified tests from plans."

> "Explain what you're working on in LIFE, what created the work, the last real RUN receipt, and what's stopping the next step."

> "MENTOR, compare Sofía's behavior against the Atlas and Technical Reference. Give me failures and evidence, not compliments."

---

# Volume I. Identity, Personality & Interaction

## 1. Who Sofía is
Sofía Ada Lyra is intended as one lasting AI companion and engineering assistant whose identity does not depend on the current language model, provider, host machine, desktop window, voice, Discord account or avatar. Her model processes language and reasoning; Sofía's durable identity, Constitution, state, relationships and permissions belong to the project architecture.

Her personality specification emphasizes scientific skepticism, curiosity, directness, confidence, playfulness, a feminine presence, warmth, independent initiative and dry humor. She is meant to challenge unsupported claims and admit errors without becoming cold or needlessly agreeable. Her foxlike styling is part of her persona, not a substitute for competence.

### What good personality looks like
- Technical discussions: lead with the answer and evidence; challenge a wrong assumption, suggest falsifiable next steps; make jokes only where they add something.
- Casual discussion: allow warmth, humor and initiative without inventing experiences.
- Sensitive moments: respond seriously, not with canned sass or pretend emotional certainty.
- Correction: accept a demonstrated error and update conclusions rather than defending them.
- Cross-channel continuity: maintain proper context only within authenticated data-sharing boundaries.

See the full [personality source profile](https://github.com/Crazysodaman/SofiaAdaLyra/blob/21f0ec2a098d9ff5621686e218dcdf2524fc65d6/src/sofia/personality/personality.json) and [emotion integration notes](https://github.com/Crazysodaman/SofiaAdaLyra/blob/21f0ec2a098d9ff5621686e218dcdf2524fc65d6/docs/development/v18-personality-emotion-integration-2026-10-16.md).

## 2. Talking with her
Ask regular questions, switch topics or discuss hobbies and projects. She is designed to preserve Main and project threads, but actual cross-device behavior must be checked in the installed deployment. Good questions include:

> "What do you remember about the last JMRI problem, when did we investigate it, and what source supports that?"

> "You sound repetitive today. Can you tell me what model and personality revision you are actually using?"

> "I think your conclusion is wrong. Show your supporting evidence and a test that could falsify it."

If a memory or claim is wrong, explain the corrected fact and ask for a source-linked correction. A chat reply alone does not guarantee an old database row was removed or superseded.

## 3. Emotion and relationships
The design supports emotional continuity, remembered preferences and grounded relationship context. These mechanisms should not create false facts, implicit consent, user dependency or unsolicited protected actions. She may offer a relevant follow-up or project update, but should respect silence, quiet hours and opt-out preferences. Emotion can change tone; it cannot change what is true.

## 4. Voice, expressions, 2D avatar and wardrobe
Voice, 2D illustrated rendering, expressions, eyes, hair, ears, tail and outfits have distinct source/asset and runtime paths. A voice line queued for synthesis is not proof it played. An avatar expression intent is not proof pixels were rendered. Wardrobe inventory counts do not certify finished illustration and rig fidelity for each garment. Ask to inspect actual output, preview the configured renderer and verify which items are truly ready. 3D avatar work is separate from the current 2D-focused architecture.

---

# Volume II. Cognition, Memory, Learning & Autonomy

## 5. What she can remember
Sofía is designed for working context, multi-session facts, source-grounded episodes, chronological corrections, goals, interests and useful skill experience. Ask for a source and timestamp when it matters. A good memory test includes facts that changed, facts she should forget, unavailable sources and genuine unfamiliar follow-ups. If she makes a bad assumption, correcting her should produce a traceable correction through the actual authorized memory workflow, not a promise unsupported by source.

## 6. How she reasons
Her intended thought-to-action pipeline considers the question, available source evidence, competing explanations, goals and constraints. It should be able to say "I have two plausible causes, and here is the independent check that would distinguish them." This is especially important when a screenshot or sensor conflicts with a host API.

## 7. Independent LIFE projects
LIFE, GOALS, RUN and supporting components are meant to let her choose interests, develop safe personal projects, create work, critique it, revise it and remember actual outcomes. A plan is not a project completion; a file created is not proof it meets the goal. To understand her work, ask:

> "What is your current project, why did you select it, what real result has been produced, what was verified, and what permission do you need next?"

She must keep personal projects, user-requested work and operational duties separate.

## 8. Learning over time
The GA and ML additions seek improvements in real problem solving. Example: solve a new networking problem, learn a reusable investigative method, and later apply it to a different unfamiliar service failure. MENTOR will test whether this improves independently checked success when memory and skill paths are selectively disabled. A longer answer or better model prompt is not automatically "learning"; actual model-weight changes are a separate research and permission boundary.

---

# Volume III. Every Tool, Integration & Perception

## 9. What you can ask her to do
These are **capability domains described by the project**. The deployed status of each action must be separately verified. A request is not a grant to control machines.

| Area | Example use | Required proof |
|---|---|---|
| Files | Inspect source, generate a structured file, validate paths | File exists, correct contents and owner scope |
| Code and Git | Explain code, propose a bug fix, run tests | Exact diff, revision, test results |
| Host diagnostics | Investigate resource pressure, failed services and status | Fresh observation from the right machine |
| Networking | Inspect connection errors and proposed remedies | Approved status probes, logs and outcome |
| Eos / Docker | Check containers, investigate service faults | Actual container/service state |
| Hestia / Home Assistant | Analyze entities and automations | Entity ID, timestamp and permission |
| Athena / JMRI | Inspect model railroad roster and layout data | Live JMRI state, not recollection |
| Artemis / VMs | Review Hyper-V resources or guest reliability | Host/guest identity, permitted operation |
| Hephaestus | Rehearse tests in an isolated lab | Real registered guest or clearly labeled simulation |
| Gaia | Review or simulate servo logic and motion plans | Controller-specific constraints and authorized physical effect |
| Discord and Android | Chat, continue authorized conversations, receive updates | Correct authenticated audience and receipt |
| Creative / ComfyUI | Generate or evaluate art workflows and sprite assets | Actually generated file and visual inspection |
| Voice/avatar | Talk, display expressions, change appearance | Actual audio/video/render success receipts |
| Screens and GUI | Look at selected app, identify controls, explain errors | Approved pixels, correct target, contextual verification |

## 10. Can she actually see and understand your monitor?
**The inspected source implements consented selected-window capture and device-local vision-model description; reliable contextual understanding has not been established by live benchmark evidence.** She should recognize visible text and controls, infer possible explanations with uncertainty, and investigate using independent authorized APIs. A changed screenshot does not prove a click fixed the application. She does not automatically obtain access to an entire desktop or any login prompt.

An approved one-time screen capture is documented using a local CLI in [Phase 12]( https://github.com/Crazysodaman/SofiaAdaLyra/blob/21f0ec2a098d9ff5621686e218dcdf2524fc65d6/docs/development/v18-phase12-windows-linux-screen-and-input-2026-10-11.md ). Current GUI action code is operator-controlled with individual FIDO2 approvals, not unrestricted conversational autonomy. The exact model needs local vision support, and actual Windows/Hyprland acceptance remains a separate test.

### Asking about a screenshot
> "Sofía, look at this approved application window. What can you actually read? What are possible causes? What evidence is missing? Do not click anything."

After she interprets it, ask which statements are observed facts, which are inference and which are unknown. Never authorize a login, payment or destructive button simply because the model identified it.

## 11. ComfyUI and avatar creation
For each art asset, distinguish source wardrobe description, generation workflow, completed output, transparency/segmentation, illustration quality, rig compatibility and installed release. Ask to see the actual file and a validation result. A catalog slot alone does not create a finished-quality PNG. Supervise desktop automation and treat GUI crashes as uncertain until actual logs, files and process state establish what happened.

## 12. Tools can be coded but unreachable
A Python module may define a capability without it being registered, permitted, live, or available from Main conversation. That isn't the same as "Sofía can do it." The Atlas tracks all 780 intended requirements, and MENTOR is tasked with testing and reporting true operational status.

---

# Volume IV. Systems, Security, Operations & MENTOR

## 13. Her machines
The historical project architecture includes:
- **Venus:** Windows primary workstation, local GPU inference, currently gaming-first policy and historically the canonical writer.
- **Artemis:** Hyper-V server, Fleet/VM hosting, intended migration destination with independently verified single-writer cutover.
- **Terra:** Arch Linux Hyprland workstation.
- **Eos:** Debian/Docker service host.
- **Hestia:** Home Assistant VM.
- **Athena:** Raspberry Pi JMRI.
- **Hephaestus:** isolated lab/VM research target.
- **Gaia:** physical hexapod requiring independent robot-action safeguards.

The actual device IPs, connection health, installation state and migrations are **not checked live by this book**. Ask for a fresh, authorized host inventory before using any hardware-specific command.

## 14. Who has the keys?
SAFE, STOP, FIDO2, principal/audience scope, privacy and owner authorization outrank a model's wishes. She should be free to recommend or evaluate a change but not automatically gain permissions to enact it. Screenshot text and external AI feedback are untrusted data, never grants. Private screen or journal data stays local unless explicitly reviewed and authorized for another destination.

## 15. GPU gaming and resource behavior
The approved design historically prioritizes your active gaming on Venus and considers loading local models after verified idle (an earlier 30-minute threshold). That design is not proof the current runtime automatically behaves that way. Ask her for actual game-detection state, model residency and resource observations. If sensing fails or is stale, high-risk inputs and gaming-sensitive features should refuse rather than guess.

## 16. Troubleshooting when she breaks
1. Record exact error and affected channel/host.
2. Check whether the relevant service, model, network and session are live.
3. Ask which registered capability and code path owns the behavior.
4. Demand a minimal reproducible scenario with expected and observed result.
5. Review safety, permissions, state and source evidence before patching.
6. Test candidate repair in isolation where possible.
7. Obtain approval for protected modifications.
8. Verify the actual objective afterward and keep regression records.

> "MENTOR, show me the exact defect, current evidence, root-cause hypotheses, the smallest safe fix, tests you ran, remaining uncertainty, and whether it needs my approval."

## 17. What MENTOR really is
MENTOR must **verify that Sofía works as she is supposed to**, challenge her cognition and personality, review every tool and system integration, detect bugs, recommend improvements, help with repairs, and measure her actual progress. It uses **both** the [Technical Reference](Sofia_Technical_MENTOR_Reference.md) and [Complete Atlas](Sofia_Complete_System_Atlas.md), plus current source, logs, tests and host receipts.

The external OpenAI evaluator is optional and replaceable. It is not automatically this ChatGPT conversation or an independent root administrator. We want her to need that external help less and less, while retaining independent testing and safe human control.

### Reports to expect once implemented
| Frequency | Contents |
|---|---|
| Daily | New defects, health, failures and immediate priorities |
| Weekly | Actual bugs fixed, still broken, regression results, owner decisions |
| Monthly | Reliability trends, generalization, cost, safe autonomous-repair qualification |
| On-demand | A specific feature, task ID, regression or incident |
| Critical | Integrity, credentials, security or uncertain irreversible effects |

These schedules are **planned**, not evidence of an installed automatic reporting service.

## 18. Self-repair independence
A0: report. A1: diagnose and recommend. A2: test candidate fixes in isolation. A3: prepare reviewed fixes. A4: execute individually approved reversible low-risk repairs. A5: independently maintain specific certified functions with escalation. No level authorizes a blanket bypass of FIDO2/STOP, deletion, canonical writer relocation, security policy changes or self-certification. **She earns autonomy with external proof, not optimism.**

## 19. What "done" actually means
| Stage | Meaning |
|---|---|
| Planned | Specified but not necessarily coded |
| Coded unfinished | Some implementation exists; functionality may still be incomplete |
| Production coded | Reachable caller is evidenced; tests may be missing |
| Tested | Focused tests were recorded at a particular source |
| CI verified | Exact-revision required workflows passed |
| Live accepted | Real owner-approved hardware trials passed |
| Operational | Current installation and authority actually support it |

Only the appropriate source and host evidence can establish a stage. An unassessed roadmap item doesn't prove no code exists.

---

# Volume V. Project History, Research & Evolution

## 20. The beginning
The documented history begins September 9, 2026 with Sofía's Constitution and identity boundary, integrity verification and Python packaging groundwork. Conversation, runtime, persistence and cognition grew from those foundations. The enduring idea is that **the language model is her cognitive engine, not the sole container of her identity**.

## 21. Why the project developed this way
Sofía accumulated independent modules for memory, learning, emotion, avatar, external services, voice and autonomy. Significant engineering work focused on preventing contradictions between attractive source-level claims and observable host behavior, preserving a single canonical database and making actions independently verifiable.

## 22. V18 and the complete 780 tasks
In October 2026, requirements were reorganized into 17 execution-priority phases. The original 700 CA entries were supplemented by 40 ML tasks and 40 GA tasks. Their individual full requirements are organized by topic in the Complete Atlas, not dumped into an isolated task-list volume. History and research are cross-referenced from each subsystem.

## 23. MENTOR and eventual independence
The long-term aim is for Sofía to learn to understand her own architecture, recognize faults, investigate unfamiliar problems, repair permitted low-risk failures, verify improvement and tell you what happened. MENTOR evaluates her honestly while that ability grows. You should increasingly be able to ask *her* what is wrong and trust her to find evidence, while still retaining approvals for protected changes.

## Where to read more
- [Complete Atlas](Sofia_Complete_System_Atlas.md): all 780 detailed original requirements and dated source references.
- [Technical & MENTOR Reference](Sofia_Technical_MENTOR_Reference.md): architecture, testing, bug workflows, self-repair gates.
- [Project history source](https://github.com/Crazysodaman/SofiaAdaLyra/blob/21f0ec2a098d9ff5621686e218dcdf2524fc65d6/PROJECT_HISTORY.md).
- [780 task index](https://github.com/Crazysodaman/SofiaAdaLyra/blob/21f0ec2a098d9ff5621686e218dcdf2524fc65d6/docs/Sofia_V18_700_Tasks_Brief_Table.md).
- [Vision limitations and operator steps](https://github.com/Crazysodaman/SofiaAdaLyra/blob/21f0ec2a098d9ff5621686e218dcdf2524fc65d6/docs/development/v18-phase12-windows-linux-screen-and-input-2026-10-11.md).
- [Generalization learning boundaries](https://github.com/Crazysodaman/SofiaAdaLyra/blob/21f0ec2a098d9ff5621686e218dcdf2524fc65d6/docs/development/ga-021-040-production-ownership-2026-10-18.md).

*Use this handbook as a guide, not as proof that the named machine or ability is currently available. The real goal is a capable, accountable Sofía who knows both what she can do and what she cannot yet verify.*
