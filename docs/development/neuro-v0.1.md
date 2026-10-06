# NEURO v0.1

**Status:** coded foundation, verification pending  
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

There is no background NEURO thread in v0.1. Decay is lazy and is evaluated only
when an event arrives or a snapshot is requested. There are no NumPy, PyTorch,
GPU, Ollama or SQLite dependencies in the subsystem.

## Production wiring

One `NeuroRuntime` is owned by `SofiaApplication` and shared by the local
conversation service and channel conversations such as Discord. A user turn is
saved first, Matrix performs its normal deterministic turn classification, then
the resulting observed turn/domain metadata is converted into bounded attention
signals.

The snapshot is projected only for the matching current message. A NEURO
exception is non-fatal and the conversation proceeds without neural context.

Current production inputs:

- foreground user turn;
- Matrix domain relevance.

Generic `observe_signal()` is intentionally available for later trusted host
adapters. Future ENVIRONMENT, OPS, Fleet, MEM, ACT and BODY/Gaia integration
should translate their own already-observed typed state into bounded
`NeuralSignal` objects rather than allowing NEURO to read those stores itself.

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

## Next stages after v0.1 acceptance

1. Wire trusted ENVIRONMENT changes as bounded signals.
2. Wire OPS/Fleet anomalies and recovery as bounded signals.
3. Add MEM candidate activation only after normal retrieval eligibility, never
   as an eligibility bypass.
4. Add ACT/RUN goal competition without execution authority.
5. Measure whether NEURO can avoid unnecessary LLM wake-ups.
6. Later, build a separate fast BODY/Gaia sensorimotor layer. LLM output must
   never become direct servo timing or reflex control.

Do not move to learned weights or spiking simulation until this deterministic
baseline has real workload measurements and a clear demonstrated benefit.
