# Phase 4: continuity cleanup

## What was there, what it does, and classification

Three modules combine existing runtime/filesystem evidence into immutable events.

| File | Decision | Responsibility |
| --- | --- | --- |
| `__init__.py` | KEEP | Canonical event/classifier exports. |
| `model.py` | KEEP, DELETE unused members | ContinuityEvent, the reachable event kinds, deterministic create_continuity_event. |
| `matrix.py` | KEEP | Routes restart/workspace questions to CONTINUITY evidence. |

Production trace: Runtime provides operational continuity and filesystem changes;
CognitiveContext.continuity_event invokes create_continuity_event; cognition evidence
formatting and conversation summary consume the event. The default matrix registry
calls ContinuityMatrixEvaluator. restart_observed, evidence_status, and
workspace_change_count are all read by production evidence formatting and the
conversation service. Constructors and validation hooks are implicit callers.

## What was wrong and what was deleted/fixed

ContinuityEvent.has_workspace_changes had one own-test assertion and no production
caller; production uses the authoritative workspace_change_count and filesystem
change evidence. Remove the duplicate convenience property and its assertion.
ContinuityEventKind.UNKNOWN was never produced by the classifier or consumed by
production. Its sole reference was the immutable-event test's attempted mutation;
remove the dead enum value and mutate to a reachable enum value in that same test.
Remove the matrix module's unused MatrixIntent import. Repair the earlier regression
document's mention of the retired property. No compatibility aliases remain.

## What was merged, moved, renamed, and what remains

No file merge, move, or rename: the event model and matrix routing are separate
responsibilities. Operational and filesystem subsystems remain the state owners;
continuity only projects their evidence. INITIAL_RUNTIME already represents unknown
prior-runtime evidence; no new interpretation or event classification is introduced.
All reachable event classifications and immutability tests remain intact.

## Verification

- Compile and diff checks passed.
- Folder events/context/assembler, conversation continuity, proactive awareness,
  cognition matrix, and production runtime gate: **143 passed** (16.91 s).
- Full suite: **3,571 passed, 8 known failures, 2 skipped** (125.60 s).
  The same five unavailable-Ollama and three platform failures remain; no new
  failure and no integration test disabled.
- Search confirmed no ContinuityEventKind.UNKNOWN, event.has_workspace_changes,
  or def has_workspace_changes remains in source or tests. The classifier's local
  boolean and FilesystemChangeEvent.has_changes remain live implementation details.
- Commit: `git log -1 --format=%H -- docs/development/continuity-cleanup-report.md`.


## Original file, symbol and import inventory

Reference paths below are lexical candidates in the current source/test tree; generic names may belong to other classes. Actual production chains and dynamic access are described above. Original definitions and line numbers come from `HEAD`. This static index cannot prove every possible dynamic execution path.

### `src/sofia/continuity/__init__.py`

Production/test importers: none in direct absolute imports.

Imports:

- `from sofia.continuity.model import ContinuityEvent, ContinuityEventKind, create_continuity_event`

Definitions:


Module declarations: `__all__ = ['ContinuityEvent', 'ContinuityEventKind', 'create_continuity_event']`.

### `src/sofia/continuity/matrix.py`

Production/test importers: `src/sofia/cognition/matrix/defaults.py`.

Imports:

- `import re`
- `from sofia.cognition.matrix.model import DomainContribution, MatrixDomain, MatrixIntent, MatrixRelevance`

Definitions:

- `ContinuityMatrixEvaluator` (line 19): `src/sofia/cognition/matrix/defaults.py:64`.
  Data declarations: `domain = MatrixDomain.CONTINUITY`.
- `ContinuityMatrixEvaluator.evaluate` (line 22): `src/sofia/act/delivery.py:508`; `src/sofia/act/system_notice.py:425`; `src/sofia/application/bootstrap.py:555`; `src/sofia/application/conversation_matrix.py:461`; `src/sofia/application/conversation_service.py:559`; `src/sofia/cognition/matrix/coordinator.py:65`; `test/test_act_outreach.py:36`; `test/test_authority.py:197,214`; `test/test_authorization_evaluator.py:27,48,71,91,114,119,137,142,156,174,187,193,199,228,243,266`; `test/test_avatar_presentation_routine.py:51,93,114,139,167`; `test/test_capability_composition_scope.py:107`; `test/test_cognition_matrix.py:219,238,251,269,323,349,390,404,415,455,495,509,519,529,543,602,617,636,668,687,720,758,795,828,839,858,870,959,989,1025,1036,1049,1102,1111,1121,1147,1184,1261,1277,1301,1330,1392,1406,1419,1431`; `test/test_conversation_service.py:1148,1158`; `test/test_filesystem_orchestrator.py:108`; `test/test_ops_failure_recovery_matrix.py:23,32,37,46,54,63,70,80,87,97,109,132,143,152,161,169,178,192,212`; `test/test_rel_habit_matrix.py:85,107,120`; `test/test_release_compatibility_matrix.py:82,91,100,109,118,127,138,150,159,168,181,192,212`; `test/test_semantic_domain_matrix.py:30,49,69,83,101,117,128`; `test/test_voice_matrix.py:10,12,14,16,21`; `test/test_voice_runtime_matrix.py:5,7,9,11,13,15`.

Module declarations: `_CONTINUITY = re.compile('\\b(?:restart(?:ed)?|reboot(?:ed)?|startup|shutdown|previous\\s+runtime|previous\\s+run|continuity|workspace\\s+changes?|what\\s+changed)\\b', re.IGNORECASE)`.

### `src/sofia/continuity/model.py`

Production/test importers: `src/sofia/application/conversation_service.py`, `src/sofia/cognition/context.py`, `src/sofia/cognition/context_evidence.py`, `src/sofia/continuity/__init__.py`, `src/sofia/runtime/internal_workspace.py`, `src/sofia/runtime/runtime.py`, `test/test_continuity_context.py`, `test/test_continuity_events.py`, `test/test_interaction_world_internal_noise.py`, `test/test_internal_workspace_awareness.py`, `test/test_internal_workspace_string_path_regression.py`, `test/test_proactive_continuity_awareness.py`.

Imports:

- `from dataclasses import dataclass`
- `from enum import Enum`
- `from sofia.filesystem.changes import FilesystemChangeEvent`
- `from sofia.operational.model import ContinuityEvidenceStatus, RuntimeContinuity`

Definitions:

- `ContinuityEventKind` (line 11): `src/sofia/cognition/context_evidence.py:151,158,165,171,176`; `src/sofia/runtime/internal_workspace.py:19,20,21`; `src/sofia/runtime/runtime.py:574,575,576`; `test/test_continuity_context.py:56`; `test/test_continuity_events.py:89,101,150,193,205`; `test/test_interaction_world_internal_noise.py:53,79`; `test/test_internal_workspace_awareness.py:65,69,79`; `test/test_internal_workspace_string_path_regression.py:56`; `test/test_proactive_continuity_awareness.py:142,325,390`.
  Data declarations: `INITIAL_RUNTIME = 'initial_runtime'`; `RUNTIME_RESUMED = 'runtime_resumed'`; `WORKSPACE_CHANGED = 'workspace_changed'`; `CONTINUITY_AND_WORKSPACE_CHANGED = 'continuity_and_workspace_changed'`; `CONTINUITY_STABLE = 'continuity_stable'`; `UNKNOWN = 'unknown'`.
- `ContinuityEvent` (line 30): `src/sofia/application/conversation_service.py:320`; `src/sofia/cognition/context.py:332`; `src/sofia/cognition/context_evidence.py:118`; `src/sofia/runtime/runtime.py:235,443,654`.
  Data declarations: `kind: ContinuityEventKind`; `runtime_continuity: RuntimeContinuity`; `workspace_changes: FilesystemChangeEvent | None = None`.
- `ContinuityEvent.__post_init__` (line 44): no external lexical candidates.
- `ContinuityEvent.restart_observed` (line 75): `src/sofia/application/conversation_service.py:345`; `src/sofia/cognition/assembler.py:457`; `src/sofia/cognition/context_evidence.py:133`; `test/test_continuity_events.py:90,102`; `test/test_operational_awareness_acceptance.py:170,189`; `test/test_operational_continuity.py:42,95`; `test/test_proactive_continuity_awareness.py:143,327`.
- `ContinuityEvent.workspace_change_count` (line 79): `src/sofia/application/conversation_service.py:346`; `src/sofia/cognition/context_evidence.py:136`; `test/test_continuity_events.py:91,152,194`; `test/test_interaction_world_internal_noise.py:54`; `test/test_internal_workspace_awareness.py:66,80,146`; `test/test_internal_workspace_string_path_regression.py:57,62`; `test/test_proactive_continuity_awareness.py:328,392`.
- `ContinuityEvent.has_workspace_changes` (line 86): `test/test_continuity_events.py:153`.
- `ContinuityEvent.evidence_status` (line 93): `src/sofia/application/conversation_service.py:344`; `src/sofia/cognition/assembler.py:445,540`; `src/sofia/cognition/context_evidence.py:132`; `src/sofia/operational/model.py:89,99,164`; `test/test_operational_continuity.py:30,83`.
- `create_continuity_event` (line 97): `src/sofia/cognition/context.py:344`; `src/sofia/runtime/internal_workspace.py:43`; `src/sofia/runtime/runtime.py:558`; `test/test_continuity_events.py:83,95,141,186,198`; `test/test_interaction_world_internal_noise.py:50,75`; `test/test_internal_workspace_awareness.py:52`; `test/test_internal_workspace_string_path_regression.py:50`.

