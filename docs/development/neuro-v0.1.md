# NEURO v0.1

**Status:** production-wired multi-system deterministic baseline; live workload measurement pending
**Owner:** PKG-CORE subsystem  
**Date:** 2026-10-05

## Purpose

NEURO is a small deterministic control layer inspired by useful nervous-system
motifs such as salience, competition, decay, novelty and homeostasis. It is not
an LLM and it does not attempt to reproduce the fly connectome neuron by neuron.

The first implementation exists to answer one bounded question:

> What already-observed signal deserves the most attention right now?

## Hard boundaries

NEURO is deliberately authority-free.

A neural activation:

- is not factual evidence;
- is not a memory or memory-promotion decision;
- is not an emotional fact;
- is not a preference;
- is not consent or willingness;
- is not tool or execution authority;
- is not an execution receipt;
- cannot mutate canonical state.

Matrix evidence, SAFE/capability authority, MEM provenance, INTERACT boundaries,
and execution receipts remain independently authoritative.

## Runtime shape

```text
host-observed event
      |
      v
NeuralSignal
      |
      v
SalienceNetwork
  decay + bounded reinforcement
      |
      v
ranked NeuralActivation values
      |
      +--> winner / secondary competition
      |
      v
HomeostasisController
      |
      v
NeuroStateSnapshot
      |
      v
bounded SYSTEM projection
      |
      v
Matrix-controlled cognitive request
```

There is no dedicated NEURO thread. Decay is lazy and is evaluated only when an
event arrives or a snapshot is requested. The application RUN coordinator
refreshes canonical inputs every 60 seconds when background work is active.
There are no NumPy, PyTorch, GPU or Ollama dependencies. SQLite stores only a
bounded diagnostic snapshot and recent machine-safe signal metadata; transient
activations are never restored as evidence after restart.

## Production wiring

One `NeuroRuntime` is owned by `SofiaApplication` and shared by the local
conversation service and channel conversations such as Discord. A user turn is
saved first, Matrix performs its normal deterministic turn classification, then
the resulting observed turn/domain metadata is converted into bounded attention
signals.

Host-owned deterministic interaction replies use the same observation boundary,
including stopped/boundary/compound gestures and reviewed offer clarification.

The snapshot is projected only for the matching current message. A NEURO
exception is non-fatal and the conversation proceeds without neural context.

Current production inputs:

- foreground user turn;
- Matrix domain relevance;
- ENVIRONMENT time/daypart, season, daylight, current weather and provider faults;
- authenticated read-only phone/BODY activity, battery and connectivity state;
- current evidence-derived EMOTION labels and intensity;
- local OPS CPU/GPU/RAM/storage/temperature/throttling anomalies;
- Fleet enrollment, reconciliation drift and failed workload summaries;
- eligible promoted MEM results returned by the normal principal-bound retriever;
- established HABIT confidence and recent REL contact;
- principal/audience-scoped canonical active goals, plus INTERACT session stop
  and recent gesture outcome;
- RUN background work/failures;
- settled AVATAR presentation and VOICE runtime health.

The application bridge samples subsystem APIs and canonical stores read-only.
NEURO never promotes memory, creates emotion evidence, changes goals, infers
consent, executes background work, controls presentation, speaks, or commands a
body. A typed `body` reflex input is available for a future Gaia controller, but
servo/motor reflex ownership remains outside NEURO.

Active goals contribute a bounded, short-lived signal computed without neural
relevance. NEURO can only help a separate generator notice a possible goal; it
cannot persist or activate one. This one-way projection prevents priority and
salience from recursively amplifying each other.

For Matrix `AUTO` turns, NEURO may select `fast`, `standard`, or `deep` compute
from attention/load. Explicit Matrix `standard`, `deep`, and `verify` decisions
always win. NEURO cannot downgrade a verification route or grant tool exposure.
Deterministic host replies and periodic input refreshes use no LLM.

The tray Settings window includes a live NEURO page showing primary/secondary
attention, homeostatic loads, recent signals, routing, and why the winner won.

## Privacy / injection resistance

NEURO does not retain raw user text for novelty tracking. It retains only a
bounded list of SHA-256 fingerprints of normalized recent turns.

Signal `source` and `kind` identifiers accept only bounded machine-safe
characters. This prevents arbitrary event text from becoming injected SYSTEM
instructions when a snapshot is projected to cognition.

## v0.1 computation

The salience score is deterministic:

```text
0.30 * urgency
+ 0.25 * novelty
+ 0.25 * confidence
+ 0.20 * value
```

All values are bounded to 0..1.

Nodes decay exponentially with a default 120-second half-life, expire under
their individual TTL, and are capped at 64 active nodes. Repeated stimulation
may reinforce a node but cannot exceed 1.0. Stale out-of-order observations do
not rewind newer node state.

Foreground and Matrix-domain nodes are transient per-turn inputs: the next turn
replaces them so a reinforced old topic cannot override the new Matrix decision.
Trusted external signals retain their normal TTL and may continue competing.
Decay time and source-observation time are tracked separately, so inspecting a
snapshot cannot make a later-arriving but genuinely newer observation appear
stale. Exact duplicate observations do not reinforce a node.

Homeostasis derives three non-subjective control variables:

- `cognitive_load`;
- `novelty_load`;
- `competition_pressure`.

These are machine-control values, not claims about Sofía's feelings.

## Expected overhead

The v0.1 design performs O(n) work over at most 64 active nodes on event/snapshot
updates and performs no work while idle. No performance acceptance claim is made
until Venus measurements are captured.

Initial target:

- idle CPU attributable to NEURO: effectively zero;
- active overhead per turn: below normal timing noise relative to LLM inference;
- retained in-memory state: far below 1 MB for v0.1;
- no additional model invocation.

## Next stages after production measurement

1. Capture Venus CPU, latency, route-quality and model-wake measurements.
2. Add event subscriptions where polling currently supplies bounded summaries.
3. Add a separate fast Gaia sensorimotor/reflex controller when hardware exists.
   LLM output must never become direct servo timing or reflex control.
4. Consider learned slow baselines only after explainable deterministic behavior
   demonstrates measurable benefit and rollback criteria exist.

Do not move to learned weights or spiking simulation until this deterministic
baseline has real workload measurements and a clear demonstrated benefit.
