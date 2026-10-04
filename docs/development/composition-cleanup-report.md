# Phase 2: composition cleanup

## What was there / what it does

Two modules: an empty package marker and an 848-line root. All definitions were reachable through `compose`, the production application bootstrap entry, except that engine factory helpers were also invoked directly by routing and production-role tests. Composition creates canonical State Plane/configuration, stores, capability registrations, tools, engine routing and one runtime.

Production trace: CLI/desktop/Discord application construction → application bootstrap → `compose` → reviewed configuration and durable host location → service/authority/tool wiring → local/lifecycle/fleet engine factories → cognitive system → runtime. Capability gateway callbacks resolve that same runtime at execution time. No startup/model execution occurs merely because the factory is imported.

## Every original file: classification

| File | Decision | Result |
|---|---|---|
| `__init__.py` | KEEP | Empty package marker; no extra exports or compatibility aliases needed. |
| `root.py` | SPLIT | Retain canonical configuration and service wiring; move engine construction and capability authorization to dedicated owners. |

## What was wrong / split / renamed / deleted

Root mixed three responsibilities. `engines.py` now owns local provider construction, lifecycle wrapping, fleet placement and routed-role selection. The factory entry points are `create_cognitive_engine` and `create_model_lifecycle`; production and tests import them from their owner. Their private subordinate helpers stay in the same module. No obsolete forwarding shim remains.

`authorization.py` now owns operator-stop permitted read capabilities and the capability-authorizer factory. It resolves the current runtime through a provider callback and denies requests before runtime composition is complete. Filesystem ALLOW/domain/scope/operation checks and standing capability checks retain their original behavior. Four repeated storage names were removed from the frozenset literal; effective membership is identical.

Root remains 454 lines and owns the graph construction; the 209-line engine and 210-line authorization modules each serve one responsibility. No service was duplicated and no class, active capability or authority check was deleted. Removed imports moved with their actual functions. This is a split, not a general-purpose everything module.

## Dependency repairs / ownership / what remains

Updated routing and production dual-engine tests to import the named engine factories from their canonical module. Application still imports `compose` from root. Durable host location projection stays beside canonical configuration initialization; its tests remain at that boundary.

One State Plane and one reviewed configuration feed the graph. The authorizer closes over that configuration and resolves the graph's current runtime; it does not cache a second authorization state. Operator-stop policy remains a durable store query on each check. Engine construction retains lifecycle roles, pinned remote transport requirements, fallback policy and activity-store behavior.

Further cognition and capability consolidation belongs to their later folders. No live provider or remote service was contacted for this refactor. Historical reports contain prior source inventories and are not active imports.

## Folder gate

- Compile passed; whitespace check passed.
- Composition, exact-scope capability boundary, routing/fleet construction, lifecycle, reviewed settings, application and tool-completion gate: **144 passed**.
- AST comparison verified all four engine construction bodies are equivalent after relocation and factory rename.
- Full suite: **3,599 passed, 10 unchanged baseline failures, 2 skipped** (121.47 seconds). The same five live Ollama tests, three Linux/Windows assumptions and two existing response assertions fail; no new failures or skips were introduced.

## Commit

Resolve the checkpoint with `git log -1 --format=%H -- docs/development/composition-cleanup-report.md`. It is pushed to `origin/work`; final merging to `main` follows completion of all phases.

## Original file, symbol and import inventory

Reference paths below are lexical candidates in the current source/test tree; generic names may belong to other classes. Actual production chains and dynamic access are described above. Original definitions and line numbers come from `HEAD`. This static index cannot prove every possible dynamic execution path.

### `src/sofia/composition/__init__.py`

Production/test importers: `test/test_environment_machine_location.py`.

Imports:

None.

Definitions:


### `src/sofia/composition/root.py`

Production/test importers: `src/sofia/application/bootstrap.py`, `src/sofia/verify/dual_cognition.py`, `test/test_capability_composition_scope.py`, `test/test_composition.py`, `test/test_default_runtime_provider_boundary.py`, `test/test_embodiment_prompt_regression.py`, `test/test_embodiment_runtime_projection.py`, `test/test_memory_runtime_wiring.py`, `test/test_ollama_integration.py`, `test/test_runtime_action_integration.py`, `test/test_tools_completion_acceptance.py`.

Imports:

- `from dataclasses import replace`
- `from pathlib import Path`
- `from sofia.action.executor import FailClosedActionExecutor`
- `from sofia.action.system import ActionSystem`
- `from sofia.authorization.model import AuthorizationDecision, AuthorizationDomain, FilesystemAuthorizationOperation`
- `from sofia.capability.gateway import CapabilityGateway`
- `from sofia.capability.catalog import ToolCatalogCapability, create_tool_catalog_binding`
- `from sofia.capability.system import CapabilitySystem`
- `from sofia.codebase.codebase import CodebaseCapability`
- `from sofia.codebase.inspector import CodebaseInspector`
- `from sofia.cognition.activity import CognitiveModelActivityStore`
- `from sofia.cognition.assembler import CognitiveContextAssembler`
- `from sofia.cognition.conversation_assembler import ConversationalContextAssembler`
- `from sofia.cognition.llm_engine import LLMCognitiveEngine`
- `from sofia.cognition.fleet_engine import FleetCognitionPolicy, FleetPlacedCognitiveEngine`
- `from sofia.cognition.model_lifecycle import CognitiveModelRole, LifecycleManagedCognitiveEngine, ModelLifecycleManager`
- `from sofia.cognition.providers.factory import create_llm_provider`
- `from sofia.cognition.routing import CognitiveEngineRegistry, RoutingCognitiveEngine`
- `from sofia.cognition.rules import RuleEngine`
- `from sofia.cognition.system import CognitiveSystem`
- `from sofia.cognition.test_engine import TestCognitiveEngine`
- `from sofia.cognition.tools import CognitiveToolDispatcher, create_default_tool_bindings, create_system_tool_bindings`
- `from sofia.config.cognitive_models import CognitiveModelSelection`
- `from sofia.config.model import SofiaConfiguration`
- `from sofia.config.reviewed_projection import apply_reviewed_configuration`
- `from sofia.constitution.integrity import ConstitutionIntegrityVerifier`
- `from sofia.constitution.store import ConstitutionStore`
- `from sofia.embodiment.store import AvatarStore`
- `from sofia.environment.config import ConfiguredLocation`
- `from sofia.environment.factory import create_environment_service`
- `from sofia.environment.model import LocationSubject`
- `from sofia.distributed.capability import create_configured_remote_fleet_tools`
- `from sofia.distributed.inference_client import create_configured_remote_inference_client`
- `from sofia.dev.capability import DevCapabilitySet, DevToolService, create_dev_tool_bindings`
- `from sofia.filesystem.capability import FilesystemCapability`
- `from sofia.filesystem.change_capability import FilesystemChangesCapability, create_filesystem_changes_binding`
- `from sofia.filesystem.observation import FilesystemObservationStore`
- `from sofia.identity.store import IdentityStore`
- `from sofia.integrations.capabilities import create_configured_integration_tools`
- `from sofia.integrations.ollama import OllamaAdapter`
- `from sofia.memory.chatgpt_export_store import ChatGPTExportEvidenceStore`
- `from sofia.memory.provenance_store import DurableMemoryCandidateStore`
- `from sofia.memory.store import MemoryStore`
- `from sofia.knowledge.access import KnowledgeAccessStore`
- `from sofia.knowledge.capability import KnowledgeCapabilitySet, create_knowledge_tool_bindings`
- `from sofia.knowledge.lifecycle import SQLiteKnowledgeLifecycle`
- `from sofia.knowledge.persistence import SQLiteKnowledgeStore`
- `from sofia.knowledge.service import KnowledgeService`
- `from sofia.memory.system import MemorySystem`
- `from sofia.machine.capability import HardwareInspectionCapability, MachineCapabilitySet, MachineToolService, create_machine_tool_bindings`
- `from sofia.machine.discovery import create_machine_discovery`
- `from sofia.machine.location import MachineLocationRegistry`
- `from sofia.machine.location_state import StatePlaneMachineLocationRegistry`
- `from sofia.ops.capability import OpsCapabilitySet, OpsToolService, create_ops_tool_bindings`
- `from sofia.safe.capability_policy import protected_capability_extras`
- `from sofia.safe.dev_approval import DevApprovalVerifier`
- `from sofia.safe.execution_approval import ExecutionApprovalVerifier`
- `from sofia.safe.operator_stop import OperatorStopStore`
- `from sofia.operational.store import OperationalStore`
- `from sofia.personality.store import PersonalityStore`
- `from sofia.runtime.runtime import SofiaRuntime`
- `from sofia.system.capability import create_local_system_capabilities`
- `from sofia.state.sqlite_plane import SQLiteStatePlane`

Definitions:

- `_configuration_with_persistent_host_location` (line 87): `test/test_environment_machine_location.py:85,134,159,210`.
- `_create_llm_engine` (line 134): `src/sofia/composition/engines.py:143,156,191`.
- `_create_model_lifecycle` (line 160): no external lexical candidates.
- `_fleet_wrap_cognitive_engine` (line 178): `src/sofia/composition/engines.py:142,155,196`.
- `_create_cognitive_engine` (line 220): no external lexical candidates.
- `compose` (line 320): `src/sofia/application/bootstrap.py:125`; `src/sofia/verify/dual_cognition.py:216`; `test/test_capability_composition_scope.py:127,277`; `test/test_composition.py:45,53,61,77,93,109,127,209,239,270,290,305,320,343,366,391,415,441,451`; `test/test_default_runtime_provider_boundary.py:45`; `test/test_embodiment_prompt_regression.py:138`; `test/test_embodiment_runtime_projection.py:113`; `test/test_memory_runtime_wiring.py:186,266,350,391,429,474,557,611`; `test/test_ollama_integration.py:93,171,247`; `test/test_runtime_action_integration.py:62`; `test/test_tools_completion_acceptance.py:87,100,244`.
- `compose.filesystem_inspector_provider` (line 452): no external lexical candidates.
- `compose.capability_authorized` (line 538): `src/sofia/composition/authorization.py:210`.

