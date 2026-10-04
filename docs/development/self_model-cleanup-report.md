# Phase 6: self_model cleanup

## What was there / what it does

Three modules provide verified core identity/foundational values and a separate current operational projection. Original definitions/imports/reference candidates follow below.

Runtime.start loads verified constitution/identity -> create_core_state -> SofiaCoreState. Runtime._create_operational_self_model wraps current operational state, continuity and workspace evidence -> CognitiveContext -> AuthoritativeSelfState and assembler. The explicit verification AB probe also creates core state.

## File decisions

| File | Decision | Evidence |
|---|---|---|
| `__init__.py` | KEEP | Exports active typed core/operational contracts. |
| `model.py` | KEEP | Runtime creates core state from verified identity/constitution; cognition projects its identity, self-concept, foundational values and relationships. All validators/factory fields serve these live values. |
| `operational.py` | KEEP | Runtime creates current operational/continuity/workspace projection for cognitive context. |

## What was wrong / what I merged / deleted / renamed or moved / fixed

No dead member, competing persistent owner or misleading module was found. No merge, deletion, rename, move or source fix was justified. Core foundational identity and transient operational existence have separate responsibilities; combining them would obscure that boundary. This checkpoint records the audited KEEP decisions rather than introducing artificial edits.

## What remains

Constitution and IdentityStore remain authoritative sources. SofiaCoreState is a typed semantic projection with verified constitution version/hash; it does not persist independent identity. OperationalState/RuntimeContinuity remain authoritative runtime evidence, and SofiaOperationalSelfModel projects them without granting authority. Relationship declarations here represent foundational self-concept; rel owns observed contact history rather than duplicating those declarations.

## Tests / checkpoint

Compile passed. Core/operational model, cognitive grounding/self-state, continuity context, composition and matrix gate: **162 passed**. Source/tests are unchanged from the preceding full-suite snapshot: **3469 passed, 8 failed, 2 skipped**; five failures require unavailable Ollama and three are existing platform assumptions.

Checkpoint: `git log -1 --format=%H -- docs/development/self_model-cleanup-report.md` identifies the containing commit.

## Original inventory


## Original file, symbol and import inventory

Reference paths below are lexical candidates in the current source/test tree; generic names may belong to other classes. Actual production chains and dynamic access are described above. Original definitions and line numbers come from `HEAD`. This static index cannot prove every possible dynamic execution path.

### `src/sofia/self_model/__init__.py`

Production/test importers: none in direct absolute imports.

Imports:

- `from sofia.self_model.model import Relationship, SelfConcept, SofiaCoreState, create_core_state`
- `from sofia.self_model.operational import SofiaOperationalSelfModel`

Definitions:


Module declarations: `__all__ = ['Relationship', 'SelfConcept', 'SofiaCoreState', 'SofiaOperationalSelfModel', 'create_core_state']`.

### `src/sofia/self_model/model.py`

Production/test importers: `src/sofia/cognition/context.py`, `src/sofia/cognition/self_state.py`, `src/sofia/runtime/runtime.py`, `src/sofia/self_model/__init__.py`, `src/sofia/verify/interaction/ab_probe.py`, `test/test_cognitive_assembler.py`, `test/test_cognitive_benchmark_contract.py`, `test/test_cognitive_context_assembler.py`, `test/test_cognitive_self_state.py`, `test/test_cognitive_self_state_assembler_contract.py`, `test/test_conversation_workspace_projection.py`, `test/test_conversational_context_projection.py`, `test/test_embodiment_semantic_contract.py`, `test/test_self_model.py`.

Imports:

- `from dataclasses import dataclass`
- `from sofia.constitution.model import Constitution`
- `from sofia.identity.model import SofiaIdentity`

Definitions:

- `SelfConcept` (line 8): `test/test_cognitive_assembler.py:114`; `test/test_cognitive_benchmark_contract.py:29`; `test/test_cognitive_self_state.py:26`; `test/test_cognitive_self_state_assembler_contract.py:40`; `test/test_self_model.py:33,177`.
  Data declarations: `nature: str`; `biological_status: str`; `identity_independence: str`; `embodiment_relationship: str`.
- `SelfConcept.__post_init__` (line 21): no external lexical candidates.
- `Relationship` (line 42): `test/test_cognitive_assembler.py:132`; `test/test_self_model.py:44`.
  Data declarations: `subject: str`; `roles: tuple[str, ...]`.
- `Relationship.__post_init__` (line 51): no external lexical candidates.
- `SofiaCoreState` (line 80): `src/sofia/cognition/context.py:53,155`; `src/sofia/cognition/self_state.py:25,32`; `src/sofia/runtime/runtime.py:222,284`; `test/test_cognitive_assembler.py:109,112,161`; `test/test_cognitive_benchmark_contract.py:24`; `test/test_cognitive_self_state.py:20,21`; `test/test_cognitive_self_state_assembler_contract.py:34,35`; `test/test_self_model.py:175`.
  Data declarations: `identity: SofiaIdentity`; `self_concept: SelfConcept`; `relationships: tuple[Relationship, ...]`; `foundational_values: tuple[str, ...]`; `constitution_version: str`; `constitution_hash: str`.
- `SofiaCoreState.__post_init__` (line 99): no external lexical candidates.
- `create_core_state` (line 160): `src/sofia/runtime/runtime.py:527`; `src/sofia/verify/interaction/ab_probe.py:88`; `test/test_cognitive_assembler.py:269,285,301,335,348,371,389,405,420`; `test/test_cognitive_context_assembler.py:596,642,698`; `test/test_cognitive_self_state.py:96,106,120,226,267,288`; `test/test_conversation_workspace_projection.py:60`; `test/test_conversational_context_projection.py:30`; `test/test_embodiment_semantic_contract.py:91`; `test/test_self_model.py:60,71,83,95,115,136,148,158`.

### `src/sofia/self_model/operational.py`

Production/test importers: `src/sofia/cognition/context.py`, `src/sofia/runtime/runtime.py`, `src/sofia/self_model/__init__.py`, `test/test_self_model_operational.py`.

Imports:

- `from dataclasses import dataclass`
- `from sofia.filesystem.changes import FilesystemChangeEvent`
- `from sofia.operational.model import OperationalState, RuntimeContinuity`

Definitions:

- `SofiaOperationalSelfModel` (line 11): `src/sofia/cognition/context.py:58,213`; `src/sofia/runtime/runtime.py:480,489`; `test/test_self_model_operational.py:66`.
  Data declarations: `operational_state: OperationalState`; `continuity: RuntimeContinuity`; `workspace_changes: FilesystemChangeEvent | None = None`.
- `SofiaOperationalSelfModel.__post_init__` (line 23): no external lexical candidates.

