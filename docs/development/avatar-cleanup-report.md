# Avatar folder cleanup

Base commit: `37890e347881925acd1ea6ce8c2e0f07def18f3f`.
Scope: `src/sofia/avatar`, its affected tests, and its development documentation.
Stop after this folder; the next phase is application/runtime/composition.

## What was there and what it does

Sixteen Python modules, 5,433 lines before cleanup. AVATAR owns wardrobe metadata,
validated outfit selection, headless presentation transitions, durable presentation
snapshots, contextual outfit proposals, privacy grants and deterministic self-fact
answers. It has no working renderer or independently verified garment assets.

| Original file | Decision | Responsibility and production reachability |
| --- | --- | --- |
| `__init__.py` | KEEP | Inert package marker; no re-export or initialization side effects. |
| `authoring.py` | MOVE + DELETE | Fit anchors move to `fit.py`; standalone body snapshot and studio prototypes are removed. Catalog construction reaches the anchors, not the removed classes. |
| `clothing_action.py` | KEEP, remove dead field | Application bootstrap wires `handle` into conversation; mutations go through the presentation store. |
| `clothing_intent.py` | KEEP | Parser, typed intents and target normalization used by the clothing action service. |
| `matrix.py` | KEEP | Matrix defaults register the AVATAR evaluator; conversation routing invokes it. |
| `presentation.py` | KEEP | Sole revisioned presentation authority; runtime, routine, store and clothing service consume it. |
| `presentation_routine.py` | KEEP | Application startup and pre-response/background hooks evaluate trusted daily context. |
| `presentation_runtime.py` | KEEP | Application startup loads/bootstrap state and attaches the bundle to runtime. Includes actively invoked state migrations. |
| `presentation_store.py` | KEEP | SQLite persistence and durable-or-rollback mutations used by runtime bootstrap, clothing actions and routines. |
| `private_grant.py` | KEEP | Runtime and clothing actions resolve trusted host/session/stop evidence. |
| `self_fact_query.py` | KEEP | Runtime responds to grounded outfit/body/appearance queries before LLM inference. |
| `wardrobe.py` | KEEP | Canonical slot/layer metadata, normalization, selection validation and future renderer display gate. |
| `wardrobe_autonomy.py` | KEEP | Clothing service evaluates contextual choice; bootstrap supplies the context provider. |
| `wardrobe_catalog.py` | KEEP | One subsystem: inventory definitions, generated pieces/presets, blueprint validation, source-backed preferences and starter construction. Also documented offline manifest handoff. |
| `wardrobe_matrix.py` | KEEP | Runtime bundle derives slot/layer cells from the catalog and current item IDs. |
| `wardrobe_planner.py` | KEEP | Application routine and clothing autonomy propose context-compatible outfits without changing state. |

The catalog is large but its definitions construct one wardrobe inventory. No split
or forced merge was warranted in this batch. Parsing, policy, state authority,
durability and projection retain separate responsibilities.

## Actual usage and dependency direction

Production entry points include `sofia.__main__`, the desktop/UI entry point and
Discord application startup. They create `SofiaApplication`, which composes runtime
and wires the AVATAR bundle and services:

1. `SofiaApplication.start` → `load_or_bootstrap_presentation` →
   `build_starter_wardrobe` → generated specifications/blueprints/presets →
   `Wardrobe`, validated `fit.DEFAULT_FIT_ANCHORS` and `PresentationStore`.
2. Application contextual evaluation → `WardrobeContext.from_environment_snapshot`
   and `wardrobe_emotion_influences` → `HeadlessPresentationRoutine.evaluate`
   (or daypart fallback) → `OutfitPlanner.suggest` → authority transition →
   `PresentationStore.persist_mutation`.
3. Conversation clothing handler → `ClothingActionService.handle` → intent parser,
   item/outfit resolution, private grant and contextual autonomy → dynamic outfit
   registration/proposal/commit → durable verification → derived current matrix.
4. Runtime response → audience-safe authority projection → matrix builder →
   `AvatarSelfFactResolver.resolve`, or typed presentation grounding for cognition.
5. Conversation matrix routing → default evaluator registry →
   `AvatarMatrixEvaluator.evaluate`.
6. UI theme reads a presentation projection; it does not own current wardrobe state.

The inventory below records imports, definitions, constants, fields and source/test
reference candidates. Shared names such as `evaluate`, `save` and `resolve` require
receiver inspection; lexical matches alone do not establish a call graph.

## What was wrong, deleted, moved and fixed

- `WardrobeStudio`, `GarmentDesignRequest` and their compose/design methods were
  referenced only by their own tests. No application, CLI, runtime or documented
  executable tool wired them. Their comment about production persistence wiring
  described wiring that did not exist. Remove this dormant authoring surface.
- `BodyAuthoringContract` and its SHA pin validator were likewise test-only. The
  production catalog directly validates anchor names; it never constructs this
  snapshot contract. Remove it rather than imply the production avatar is pinned
  or checked by it. Planned art requirements remain in design documents.
- Retain and move `BodyRegion`, `AuthoringLandmark`, landmark restrictions,
  `REGION_TO_SLOTS`, `FitAnchor`, `BodyContractError` and `DEFAULT_FIT_ANCHORS` to
  `fit.py`. Landmark restrictions are used by real anchor validation.
- Remove `ClothingActionService._base_outfits`, an unused second preset map. The
  service's `_plans` is a lookup of immutable catalog plans; current/dynamic outfit
  registration remains owned by `PresentationAuthority`.
- Update the catalog import and rename the focused authoring tests to
  `test_avatar_fit.py`. Remove tests solely exercising the deleted APIs. Preserve
  production registration/persistence/rollback tests in clothing/presentation
  suites. Add anchor uniqueness and reference-only checks. The package gate has
  18 fewer collected cases after retirement, not 18 newly skipped cases.
- Correct stale headless-completion documentation: canonical state is a SQLite
  table in `sofia.db`; retired JSON is an input migration, not a live state store.
  Replace acceptance commands referring to previously removed test files.

No merge was needed. Related changes outside the folder are included when needed to repair this phase's dependency surface. No unrelated package was refactored. Package initialization
stays inert, so there were no initializer exports to repair.

## Canonical state ownership and remaining APIs

`PresentationAuthority` owns current presentation, daily fallback, revisions,
pending/finished transitions and dynamic outfit registration. `PresentationStore`
persists settled snapshots in `avatar_presentation_state` in canonical `sofia.db`.
`WardrobePrebuild` supplies immutable catalog metadata; matrices and projections
are derived views. `Embodiment` remains the canonical representational body source.
The planner and autonomy context do not create a second mutable presentation model.

Legacy JSON retirement and original bootstrap color migration remain because
startup actually executes them and supported old state must be preserved.
The legacy autonomy override hook also remains an exercised policy extension point.
Catalog `pieces`, `closet_summary` and `manifest` have no live UI caller; they remain
explicit offline inventory/handoff APIs on the same validated catalog. Likewise,
`require_public_ready`, presentation appearance/cancel APIs and renderer-receipt
planning contracts remain boundary APIs rather than falsely claimed live rendering.
These exceptions are deliberate API roles, not retention justified solely by tests.

Repository searches found no remaining source/test imports of the retired module
or uses of the removed names/map. Class/function reference review found no further
unexplained production orphan in this folder; Python hooks, local callbacks and the
explicit offline/boundary APIs above account for indirect entry points. External
consumers not present in this repository are unknown: removal intentionally breaks
imports of the retired authoring prototypes; no compatibility shim is retained.

## Validation and cloud setup

- Python 3.12 virtual environment, editable project install and pytest installed.
- `pip check`: no broken requirements.
- Compile all source and tests: passed.
- Original AVATAR non-integration package gate: 746 passed.
- Updated AVATAR non-integration package gate: 728 passed, 2,875 deselected.
- Relevant avatar/context matrices plus UI/application/dual-cognition/storage
  wiring: 50 passed, one pre-existing Linux WindowsPath test failure.
- First full suite: 3,583 passed, 18 failed, 2 skipped.
- All 18 failing nodes also fail with the original AVATAR package loaded from a
  temporary module overlay. The baseline overlay was verified to contain the
  original prototypes and original clothing service; no worktree was created.
- Supported writable `SOFIA_STATE_ROOT` resolved four provisioning failures;
  affected probes/entrypoint checks rerun: 21 passed, one obsolete CLI export test
  still failed. No test assertion was weakened.
- Final full suite with the writable state override: **3,587 passed, 14 failed,
  2 skipped** (119.57 seconds). All remaining failing nodes also failed in the
  original-AVATAR comparison.

Remaining failure categories are unavailable live Ollama integration (five cases),
Windows assumptions on Linux, stale application conversation imports/monkeypatches,
and unrelated provider/response-quality assertions. These reproduce at baseline;
the full repository gate is not green. Live Ollama, Discord and graphical desktop
behavior are unverified. This environment supports deterministic headless
development; it is not a fully validated production deployment.

Saved environment draft fields: complete `install_script`, `start_skill` and the
non-secret `SOFIA_STATE_ROOT` requirement/suggestion pointing to the ignored writable
`state/cloud-runtime` directory. Review and save these settings, then publish the
environment through its settings. Saving the draft does not apply or publish it;
fresh-task snapshot restoration has not been tested.

Checkpoint: this report is included in the avatar cleanup commit; obtain its SHA
with `git log -1 --format=%H -- docs/development/avatar-cleanup-report.md`.

## Definition and dependency inventory (before cleanup)
Each definition below was inspected statically. Line numbers refer to the base commit. References are lexical candidates in AVATAR, its direct consumers and related tests; identical method names can refer to other types. They are a search index, not proof that every candidate is a reachable call. Constructor/dataclass hooks are invoked by Python. Production paths and dormant-API decisions above supply the ownership conclusions. Dynamic external imports cannot be ruled out by this repository audit.

### src/sofia/avatar/__init__.py
Imports out: .
Module constants/state: none.
| Definition | Decision | Reference candidates |
| --- | --- | --- |

### src/sofia/avatar/authoring.py
Imports out: `from __future__ import annotations`; `from dataclasses import dataclass`; `from enum import Enum`; `import re`; `from .wardrobe import SLOTS`; `from dataclasses import dataclass`; `from .presentation import PresentationAuthority`; `from .presentation_store import PresentationStore`; `from .wardrobe import Garment, WardrobeError`; `from .wardrobe_planner import Activity, OutfitPlan, Season`; `from .wardrobe_catalog import WardrobePrebuild, all_closet_categories`; `from .wardrobe_catalog import GarmentBlueprint`.
Module constants/state: `_SHA256`, `_ID`, `REQUIRED_AUTHORING_LANDMARKS`, `REGION_TO_SLOTS`, `DEFAULT_FIT_ANCHORS`.
| Definition | Decision | Reference candidates |
| --- | --- | --- |
| `BodyContractError` (L19) | MOVE to fit.py | authoring.py:111,113,115,117,162,164,166,168,170,172,174,176,180; test_avatar_authoring.py:38,46,52,71,73,78,80,92 |
| `BodyRegion` (L23) | MOVE to fit.py | authoring.py:71,72,73,74,75,76,77,78,79,80,81,82,83,84,85,86,87,88,89,90,91,92,93,94,95,96,97,98,106,112,121,122,123,124,125,126,127,128,129,130,131,132,133,134,135,136,137,138,139,140,141,142,143,144,145,175; test_avatar_authoring.py:57,59,60,61,66,67,72,74 |
| `AuthoringLandmark` (L58) | MOVE to fit.py | authoring.py:67,116,155,167; test_avatar_authoring.py:47 |
| `FitAnchor` (L103) | MOVE to fit.py | authoring.py:121,122,123,124,125,126,127,128,129,130,131,132,133,134,135,136,137,138,139,140,141,142,143,144,145,156,169,178; test_avatar_authoring.py:72,74 |
| `FitAnchor.__post_init__` (L109) | MOVE to fit.py | Python constructor/dataclass protocol; inspect containing type references |
| `BodyAuthoringContract` (L150) | DELETE | test_avatar_authoring.py:28,39,43,47,53,79,81,85,93,98 |
| `BodyAuthoringContract.__post_init__` (L160) | DELETE | Python constructor/dataclass protocol; inspect containing type references |
| `BodyAuthoringContract.anchors_for_slot` (L178) | DELETE | test_avatar_authoring.py:81,85 |
| `GarmentDesignRequest` (L193) | DELETE | authoring.py:296,300; test_avatar_seasonal_outfits.py:97 |
| `WardrobeStudio` (L203) | DELETE | test_avatar_authoring.py:131,157,176; test_avatar_seasonal_outfits.py:58,80,95,162 |
| `WardrobeStudio.__init__` (L206) | DELETE | Python constructor/dataclass protocol; inspect containing type references |
| `WardrobeStudio.compose` (L231) | DELETE | bootstrap.py:134; test_avatar_authoring.py:138,162,177; test_avatar_seasonal_outfits.py:59,82,163 |
| `WardrobeStudio.design_piece` (L294) | DELETE | test_avatar_seasonal_outfits.py:96 |

### src/sofia/avatar/clothing_action.py
Imports out: `from __future__ import annotations`; `from collections.abc import Callable`; `from dataclasses import replace`; `import re`; `from threading import RLock`; `from sofia.safe.operator_stop import OperatorStopStore`; `from sofia.social.model import PrincipalContext`; `from .clothing_intent import ClothingActionIntent, ClothingActionKind, ClothingActionParser, _clean_target, _normalize`; `from .presentation import PrivatePresentationGrant, PresentationState`; `from .private_grant import PrivatePresentationGrantResolver`; `from .presentation_runtime import PresentationRuntimeBundle`; `from .wardrobe import WardrobeConflict, WardrobeError, normalize_slots`; `from .wardrobe_autonomy import WardrobeAutonomyContext, WardrobeAutonomyPolicy`; `from .wardrobe_planner import OutfitPlan, OutfitPlanner`.
Module constants/state: none.
| Definition | Decision | Reference candidates |
| --- | --- | --- |
| `ClothingActionService` (L43) | KEEP | bootstrap.py:216,737; test_avatar_clothing_action.py:150,178,203,226,252,287,310,334,358,384,408,424,435,466,487,537,557 |
| `ClothingActionService.__init__` (L46) | KEEP | Python constructor/dataclass protocol; inspect containing type references |
| `ClothingActionService.handle` (L109) | KEEP | bootstrap.py:327,749; test_avatar_clothing_action.py:152,180,205,230,240,256,265,292,315,339,363,389,413,426,440,473,493,499,540,567 |
| `ClothingActionService._handle_locked` (L126) | KEEP | clothing_action.py:119 |
| `ClothingActionService._hypothetical_reply` (L199) | KEEP | clothing_action.py:162 |
| `ClothingActionService._decline_private` (L214) | KEEP | clothing_action.py:167,543,558 |
| `ClothingActionService._private_grant` (L223) | KEEP | clothing_action.py:165,556 |
| `ClothingActionService._commit_nude` (L232) | KEEP | clothing_action.py:168 |
| `ClothingActionService._wear` (L267) | KEEP | clothing_action.py:174 |
| `ClothingActionService._remove` (L302) | KEEP | clothing_action.py:180 |
| `ClothingActionService._add` (L334) | KEEP | clothing_action.py:186 |
| `ClothingActionService._add_blueprint` (L368) | KEEP | clothing_action.py:295,361 |
| `ClothingActionService._swap` (L391) | KEEP | clothing_action.py:192 |
| `ClothingActionService._resolve_outfit` (L456) | KEEP | clothing_action.py:275,342 |
| `ClothingActionService._resolve_blueprint` (L497) | KEEP | clothing_action.py:286,311,352,400 |
| `ClothingActionService._commit_candidate` (L530) | KEEP | clothing_action.py:277,325,344,382,444 |

### src/sofia/avatar/clothing_intent.py
Imports out: `from __future__ import annotations`; `from dataclasses import dataclass, replace`; `from enum import Enum`; `import re`.
Module constants/state: none.
| Definition | Decision | Reference candidates |
| --- | --- | --- |
| `_normalize` (L9) | KEEP | clothing_action.py:472,476,514,515; clothing_intent.py:16; self_fact_query.py:119,347 |
| `_clean_target` (L15) | KEEP | clothing_action.py:457,503; clothing_intent.py:140,147,154,161,168 |
| `ClothingActionKind` (L22) | KEEP | clothing_action.py:164,173,179,185,191,200; clothing_intent.py:32,37,133,139,146,153,160,167 |
| `ClothingActionIntent` (L31) | KEEP | clothing_action.py:199,269,304,336,370,393,532; clothing_intent.py:99,131,133,138,145,152,159,166; wardrobe_autonomy.py:83,87,101 |
| `ClothingActionIntent.__post_init__` (L36) | KEEP | Python constructor/dataclass protocol; inspect containing type references |
| `ClothingActionParser` (L47) | KEEP | clothing_action.py:82 |
| `ClothingActionParser.parse` (L99) | KEEP | clothing_action.py:149,153 |
| `ClothingActionParser.is_followup` (L126) | KEEP | clothing_action.py:150 |
| `ClothingActionParser._parse_direct` (L131) | KEEP | clothing_intent.py:108,117,124 |

### src/sofia/avatar/matrix.py
Imports out: `import re`; `from sofia.cognition.matrix.model import DomainContribution, MatrixDomain, MatrixIntent, MatrixRelevance`.
Module constants/state: `_AVATAR`.
| Definition | Decision | Reference candidates |
| --- | --- | --- |
| `AvatarMatrixEvaluator` (L19) | KEEP | defaults.py:35 |
| `AvatarMatrixEvaluator.evaluate` (L22) | KEEP | bootstrap.py:572; test_avatar_presentation_routine.py:51,93,114,139,167 |

### src/sofia/avatar/presentation.py
Imports out: `from __future__ import annotations`; `from dataclasses import dataclass`; `from enum import Enum`; `from typing import Any`; `import re`; `from .wardrobe import Wardrobe`.
Module constants/state: `_ID`, `_HEX`.
| Definition | Decision | Reference candidates |
| --- | --- | --- |
| `PresentationError` (L28) | KEEP | presentation.py:52,58,60,67,89,119,134,136,138,140,145,148,150,153,156,201,203,205,211,222,274,276,307,309,365,433,496,501,504,509,518,520,528,554,557,563,616,619,648,651,664,667; presentation_store.py:186; test_avatar_presentation.py:266 |
| `PresentationConflict` (L32) | KEEP | presentation.py:272,399,413,422,468,601,603,605,610; test_avatar_presentation.py:200,207; test_avatar_presentation_store.py:96 |
| `PresentationDenied` (L36) | KEEP | presentation.py:99,216,229,279,283,312,316,340,392,396,448,550,624; presentation_store.py:185; test_avatar_presentation.py:117,128 |
| `AudienceScope` (L40) | KEEP | presentation.py:176,428,432,436; runtime.py:359,377,389,392; test_avatar_presentation.py:47,79,95,111,112,188; test_avatar_runtime_projection.py:138; test_avatar_seasonal_outfits.py:147,148; test_avatar_self_fact_query.py:36,427; test_ui_theme.py:72 |
| `AttireMode` (L45) | KEEP | presentation.py:125,135,146,163,178,234,320,346,376,394,412,437,441,549,614,662; presentation_routine.py:70,142; self_fact_query.py:353,425,449,521; assembler.py:55; test_avatar_clothing_action.py:449,454; test_avatar_presentation.py:48,77,80,96,186; test_avatar_presentation_store.py:66; test_avatar_self_fact_query.py:319,379,428; test_ui_theme.py:74 |
| `_id` (L50) | KEEP | presentation.py:154,209,220,270,305,420,512,559,599,608; wardrobe_planner.py:88,236,240,286,287,304,306 |
| `_text` (L56) | KEEP | presentation.py:65,110,141,326,352,380 |
| `_color` (L64) | KEEP | presentation.py:111,112 |
| `PrivatePresentationGrant` (L72) | KEEP | clothing_action.py:226,236; presentation.py:336,339,389,395,430,442; private_grant.py:48,81; runtime.py:365,384; test_avatar_presentation.py:34,43; test_avatar_presentation_routine.py:122; test_avatar_presentation_store.py:37; test_avatar_runtime_projection.py:64,65; test_avatar_seasonal_outfits.py:17 |
| `PrivatePresentationGrant.__post_init__` (L81) | KEEP | Python constructor/dataclass protocol; inspect containing type references |
| `PrivatePresentationGrant.require` (L91) | KEEP | presentation.py:341,397,447; private_grant.py:89 |
| `AppearanceState` (L103) | KEEP | presentation.py:128,137,166,181,198,204,300,337,361,364,646,652; presentation_runtime.py:35,39; test_avatar_authoring.py:117; test_avatar_clothing_action.py:47; test_avatar_presentation.py:25,141,223; test_avatar_presentation_routine.py:31; test_avatar_presentation_runtime.py:38,77,87,127; test_avatar_presentation_store.py:26; test_avatar_seasonal_outfits.py:117,158; test_avatar_self_fact_query.py:29; test_environment_behavior_matrix.py:104; test_ui_theme.py:77 |
| `AppearanceState.__post_init__` (L109) | KEEP | Python constructor/dataclass protocol; inspect containing type references |
| `PresentationState` (L123) | KEEP | clothing_action.py:240,257,635,660; presentation.py:232,247,251,390,401,613,629,659,668; presentation_routine.py:29,103,120,166,183 |
| `PresentationState.__post_init__` (L132) | KEEP | Python constructor/dataclass protocol; inspect containing type references |
| `PresentationChange` (L160) | KEEP | presentation.py:243,255,303,317,338,343,363,367,607 |
| `PresentationProjection` (L173) | KEEP | presentation.py:431,451; self_fact_query.py:327,335; assembler.py:28,29; context.py:65,241; runtime.py:355,366,400; theme.py:154,161; test_ui_theme.py:71 |
| `PresentationAuthority` (L187) | KEEP | authoring.py:210,217; presentation_routine.py:37,41; presentation_runtime.py:18,49,54,96,143,196; presentation_store.py:52,53,91,101,149,179; runtime.py:279,351,406,411; test_avatar_authoring.py:113; test_avatar_clothing_action.py:40; test_avatar_presentation.py:18,21,181,219,239,267; test_avatar_presentation_routine.py:27; test_avatar_presentation_runtime.py:34,73,123; test_avatar_presentation_store.py:22; test_avatar_runtime_projection.py:83; test_avatar_seasonal_outfits.py:113,154,193; test_avatar_self_fact_query.py:25; test_environment_behavior_matrix.py:100 |
| `PresentationAuthority.__init__` (L192) | KEEP | Python constructor/dataclass protocol; inspect containing type references |
| `PresentationAuthority.current` (L247) | KEEP | bootstrap.py:532; clothing_action.py:238,243,310,313,322,376,377,380,399,402,413,540,604,644; presentation.py:547,551,553,566; presentation_routine.py:69,70,75,86,94,106,141,142,147,162,169; presentation_runtime.py:32,62,65,67,69,71,84,85; private_grant.py:75; test_avatar_clothing_action.py:160,172,173,188,189,190,197,198,213,227,238,247,253,263,272,273,286,301,302,308,324,329,348,353,372,377,398,421,449,450,454,455,471,482,507,508,509,510,513,514,538,548; test_avatar_presentation.py:72,77,186; test_avatar_presentation_routine.py:64,65,66,82,83,96,142; test_avatar_presentation_runtime.py:26,56,57,58,64,65,109,110,111,142,153,154; test_avatar_presentation_store.py:66,164,200; test_avatar_private_grant.py:19,44; test_avatar_runtime_projection.py:84,95,119,129,172; test_avatar_seasonal_outfits.py:125,136,182,198; test_avatar_self_fact_query.py:111,113,155,162,217,219,239,241; test_ui_application.py:138,139,152,161,169,175,186,193,199,218,219; test_ui_theme.py:110,127 |
| `PresentationAuthority.last_daily` (L251) | KEEP | presentation_routine.py:89,157; presentation_runtime.py:63; test_avatar_presentation.py:64,156,187; test_avatar_presentation_routine.py:53,116,143; test_avatar_presentation_store.py:67; test_avatar_runtime_projection.py:106 |
| `PresentationAuthority.pending` (L255) | KEEP | test_avatar_clothing_action.py:575; test_avatar_presentation_store.py:178 |
| `PresentationAuthority.available_outfit_ids` (L259) | KEEP | presentation_routine.py:81; self_fact_query.py:337,338,652; runtime.py:1103,1131; test_avatar_authoring.py:147,152,171; test_avatar_clothing_action.py:559,574; test_avatar_presentation.py:245; test_avatar_seasonal_outfits.py:178,199 |
| `PresentationAuthority.register_outfit` (L262) | KEEP | authoring.py:275; clothing_action.py:637; presentation.py:542; test_avatar_presentation.py:230 |
| `PresentationAuthority.propose_outfit` (L293) | KEEP | clothing_action.py:642; presentation_routine.py:104,167; test_avatar_presentation.py:55,129,161,193,201,208; test_avatar_presentation_runtime.py:134; test_avatar_presentation_store.py:42,90,162,198; test_avatar_runtime_projection.py:93,117,170; test_avatar_seasonal_outfits.py:123,134,180 |
| `PresentationAuthority.propose_nude` (L330) | KEEP | clothing_action.py:241; test_avatar_presentation.py:66,88,104,118,170; test_avatar_presentation_routine.py:123; test_avatar_presentation_store.py:50; test_avatar_runtime_projection.py:127 |
| `PresentationAuthority.propose_appearance` (L356) | KEEP | test_avatar_presentation.py:147; test_avatar_presentation_runtime.py:84 |
| `PresentationAuthority.commit_text` (L384) | KEEP | clothing_action.py:247,650; presentation_routine.py:111,174; test_avatar_presentation.py:62,72,94,110,153,168,176,199; test_avatar_presentation_routine.py:129; test_avatar_presentation_runtime.py:95; test_avatar_presentation_store.py:49,56,169,205; test_avatar_runtime_projection.py:100,124,133,177; test_avatar_seasonal_outfits.py:142,187 |
| `PresentationAuthority.cancel` (L419) | KEEP | test_avatar_presentation_runtime.py:141 |
| `PresentationAuthority.projection` (L426) | KEEP | assembler.py:29,32,33,34,35,36,37,38,39,40,41,42,43,55; runtime.py:359,377,388,392; test_avatar_presentation.py:47,79,95,111,112,188; test_avatar_runtime_projection.py:138; test_avatar_seasonal_outfits.py:147,148; test_avatar_self_fact_query.py:36,154,156,180,182,272,277,280,291,295,316,318,376,378,424,426,452,454 |
| `PresentationAuthority.snapshot` (L466) | KEEP | bootstrap.py:376,485,525,707,860; presentation.py:495,497,498,499,502,555,587; presentation_runtime.py:91,93,99,150,158; presentation_store.py:55,106,123; wardrobe_planner.py:157,161,167,170,201,202; runtime.py:794,795,807,809,810,817,820,839,840,849,854,873,874,1174,1237; test_avatar_clothing_action.py:558,573; test_avatar_presentation.py:177,184,235,236,242,258,259,270; test_avatar_presentation_runtime.py:47,101,143,155; test_avatar_presentation_store.py:123,124,138,154,177,189,213; test_avatar_seasonal_outfits.py:191,196; test_avatar_wardrobe_environment_context.py:63,70,72,80,119,125; test_environment_behavior_matrix.py:53,78,114,118,143,155,159,176,186,215,308,312,317,324 |
| `PresentationAuthority.restore` (L488) | KEEP | presentation.py:584; presentation_runtime.py:96,143; presentation_store.py:179; test_avatar_presentation.py:181,239,267; test_avatar_seasonal_outfits.py:193 |
| `PresentationAuthority.restore_snapshot` (L571) | KEEP | presentation_store.py:129 |
| `PresentationAuthority._begin` (L598) | KEEP | presentation.py:304,342,366 |
| `PresentationAuthority._require_pending` (L607) | KEEP | presentation.py:393 |
| `PresentationAuthority._validate_clothed_state` (L613) | KEEP | presentation.py:551,552 |
| `PresentationAuthority._state_dict` (L629) | KEEP | presentation.py:472,473 |
| `PresentationAuthority._appearance_from_dict` (L646) | KEEP | presentation.py:534,673 |
| `PresentationAuthority._state_from_dict` (L659) | KEEP | presentation.py:547,548 |

### src/sofia/avatar/presentation_routine.py
Imports out: `from __future__ import annotations`; `from dataclasses import dataclass`; `from .presentation import AttireMode, PresentationAuthority, PresentationState`; `from .presentation_store import PresentationStore`; `from .wardrobe_planner import Cadence, OutfitPlanner, OutfitProposal, Preference, WardrobeContext, WornEvidence`.
Module constants/state: none.
| Definition | Decision | Reference candidates |
| --- | --- | --- |
| `PresentationRoutineResult` (L25) | KEEP | presentation_routine.py:56,71,82,90,124,140,143,158,187 |
| `HeadlessPresentationRoutine` (L33) | KEEP | bootstrap.py:215,751; test_avatar_presentation_routine.py:37 |
| `HeadlessPresentationRoutine.__init__` (L34) | KEEP | Python constructor/dataclass protocol; inspect containing type references |
| `HeadlessPresentationRoutine.evaluate_daypart_fallback` (L51) | KEEP | bootstrap.py:543; test_avatar_presentation_routine.py:58,71,76 |
| `HeadlessPresentationRoutine.evaluate` (L132) | KEEP | bootstrap.py:572; test_avatar_presentation_routine.py:51,93,114,139,167 |

### src/sofia/avatar/presentation_runtime.py
Imports out: `from __future__ import annotations`; `from dataclasses import dataclass`; `import json`; `from pathlib import Path`; `from sofia.embodiment.model import Embodiment`; `from .presentation import AppearanceState, PresentationAuthority`; `from .presentation_store import PresentationStore`; `from .wardrobe_catalog import WardrobePrebuild, build_starter_wardrobe`; `from .wardrobe_matrix import WardrobeSlotMatrix, build_wardrobe_matrix`.
Module constants/state: none.
| Definition | Decision | Reference candidates |
| --- | --- | --- |
| `PresentationRuntimeBundle` (L17) | KEEP | bootstrap.py:214; clothing_action.py:48,57; presentation_runtime.py:176,203; test_avatar_clothing_action.py:56 |
| `PresentationRuntimeBundle.matrix_for` (L22) | KEEP | bootstrap.py:735; presentation_runtime.py:32 |
| `PresentationRuntimeBundle.current_matrix` (L30) | KEEP | clothing_action.py:259,663; test_avatar_clothing_action.py:162,191,215,451; test_ui_application.py:141 |
| `_appearance_from_embodiment` (L35) | KEEP | presentation_runtime.py:200 |
| `_migrate_legacy_bootstrap_colors` (L47) | KEEP | presentation_runtime.py:188 |
| `_legacy_presentation_state_path` (L105) | KEEP | presentation_runtime.py:182 |
| `_retired_legacy_path` (L110) | KEEP | presentation_runtime.py:164 |
| `_legacy_snapshot` (L119) | KEEP | presentation_runtime.py:146 |
| `_migrate_legacy_presentation_state` (L133) | KEEP | presentation_runtime.py:180 |
| `load_or_bootstrap_presentation` (L172) | KEEP | bootstrap.py:730; test_avatar_presentation_runtime.py:22,52,105,148 |

### src/sofia/avatar/presentation_store.py
Imports out: `from __future__ import annotations`; `from collections.abc import Callable`; `from contextlib import closing`; `from datetime import datetime, timezone`; `import json`; `from pathlib import Path`; `import sqlite3`; `from .presentation import PresentationAuthority, PresentationDenied, PresentationError`; `from .wardrobe import Wardrobe`.
Module constants/state: none.
| Definition | Decision | Reference candidates |
| --- | --- | --- |
| `PresentationStoreError` (L19) | KEEP | bootstrap.py:1196; presentation_store.py:44,85,114,120,124,161,165,171,175,190,206; test_avatar_clothing_action.py:562,566; test_avatar_presentation_store.py:116,142,157,174,210 |
| `PresentationStore` (L23) | KEEP | authoring.py:211,219; presentation_routine.py:38,43; presentation_runtime.py:19,51,135,179; test_avatar_authoring.py:124; test_avatar_clothing_action.py:54; test_avatar_presentation_routine.py:35; test_avatar_presentation_runtime.py:60,146; test_avatar_presentation_store.py:62,73,97,102,127,152,187 |
| `PresentationStore.__init__` (L35) | KEEP | Python constructor/dataclass protocol; inspect containing type references |
| `PresentationStore.database_path` (L49) | KEEP | bootstrap.py:157; clothing_action.py:84; test_avatar_clothing_action.py:460 |
| `PresentationStore.save` (L52) | KEEP | bootstrap.py:1192; presentation_runtime.py:101,156,202; presentation_store.py:110,132; test_avatar_authoring.py:125; test_avatar_clothing_action.py:55; test_avatar_presentation_routine.py:36; test_avatar_presentation_runtime.py:146; test_avatar_presentation_store.py:63,73,97,153,188 |
| `PresentationStore.persist_mutation` (L89) | KEEP | authoring.py:288; clothing_action.py:253,656; presentation_routine.py:116,179; test_avatar_presentation_store.py:175,211 |
| `PresentationStore.load` (L144) | KEEP | bootstrap.py:129,408; presentation_runtime.py:149,157,187; runtime.py:600,606,607,608; test_avatar_authoring.py:148; test_avatar_clothing_action.py:60; test_avatar_presentation_runtime.py:18,60; test_avatar_presentation_store.py:64,117,143; test_avatar_self_fact_query.py:22; test_environment_behavior_matrix.py:213; test_interaction_avatar_world.py:25 |
| `PresentationStore._read_snapshot_json` (L194) | KEEP | presentation_store.py:112,212 |
| `PresentationStore.exists` (L211) | KEEP | presentation_runtime.py:113,148,186; test_avatar_presentation_runtime.py:66; test_avatar_runtime_projection.py:85; test_interaction_avatar_world.py:164; test_interaction_avatar_world_probe_cleanup.py:39 |

### src/sofia/avatar/private_grant.py
Imports out: `from __future__ import annotations`; `from pathlib import Path`; `from sofia.safe.operator_stop import OperatorStopStore`; `from sofia.social.model import AudienceKind, PrincipalContext`; `from sofia.social.principals import SPARKS_PRINCIPAL_ID`; `from .presentation import PrivatePresentationGrant`.
Module constants/state: none.
| Definition | Decision | Reference candidates |
| --- | --- | --- |
| `PrivatePresentationGrantResolver` (L13) | KEEP | clothing_action.py:83; runtime.py:194; test_avatar_private_grant.py:20,45 |
| `PrivatePresentationGrantResolver.__init__` (L16) | KEEP | Python constructor/dataclass protocol; inspect containing type references |
| `PrivatePresentationGrantResolver.last_error` (L39) | KEEP | test_avatar_private_grant.py:30,56 |
| `PrivatePresentationGrantResolver.resolve` (L43) | KEEP | bootstrap.py:157; clothing_action.py:227; runtime.py:1072,1078,1099,1116,1126,1179,1226,1350,1353,1376; test_avatar_presentation_runtime.py:13; test_avatar_private_grant.py:26,51; test_avatar_self_fact_query.py:18,41,122,159,188,226,248,274,302,325,387,439,463; test_environment_behavior_matrix.py:35; test_interaction_avatar_world.py:19 |

### src/sofia/avatar/self_fact_query.py
Imports out: `from __future__ import annotations`; `from dataclasses import dataclass`; `import re`; `from sofia.embodiment.model import Embodiment`; `from .presentation import AttireMode, PresentationProjection`; `from .wardrobe_matrix import WardrobeSlotMatrix`.
Module constants/state: none.
| Definition | Decision | Reference candidates |
| --- | --- | --- |
| `AvatarSelfFactAnswer` (L18) | KEEP | self_fact_query.py:330,355,363,373,395,399,408,415,426,440,450,477,494,512,522,529,538,546,565,581,587,602,633,641,654,661,669 |
| `AvatarSelfFactAnswer.__post_init__` (L22) | KEEP | Python constructor/dataclass protocol; inspect containing type references |
| `_normalize` (L31) | KEEP | clothing_action.py:472,476,514,515; clothing_intent.py:16; self_fact_query.py:119,347 |
| `_friendly_outfit` (L60) | KEEP | self_fact_query.py:349,653 |
| `AvatarSelfFactResolver` (L90) | KEEP | runtime.py:282; test_avatar_self_fact_query.py:41,122,159,188,226,248,274,302,325,385,436,463 |
| `AvatarSelfFactResolver.allows_private_projection` (L111) | KEEP | runtime.py:1108; test_avatar_self_fact_query.py:393,437 |
| `AvatarSelfFactResolver._is_presentation_reason_query` (L232) | KEEP | self_fact_query.py:123,351 |
| `AvatarSelfFactResolver._is_current_outfit_query` (L236) | KEEP | self_fact_query.py:121,255,520 |
| `AvatarSelfFactResolver._is_current_outfit_state_followup` (L250) | KEEP | self_fact_query.py:122,424 |
| `AvatarSelfFactResolver._is_undergarment_query` (L261) | KEEP | self_fact_query.py:124,448 |
| `AvatarSelfFactResolver._is_body_description_query` (L271) | KEEP | self_fact_query.py:592 |
| `AvatarSelfFactResolver._measurement_text` (L285) | KEEP | self_fact_query.py:595,596,597,598,599,600 |
| `AvatarSelfFactResolver._requested_undergarment_categories` (L293) | KEEP | self_fact_query.py:457 |
| `AvatarSelfFactResolver._matrix_garments` (L306) | KEEP | self_fact_query.py:458 |
| `AvatarSelfFactResolver.resolve` (L322) | KEEP | bootstrap.py:157; clothing_action.py:227; runtime.py:1072,1078,1099,1116,1126,1179,1226,1350,1353,1376; test_avatar_presentation_runtime.py:13; test_avatar_private_grant.py:26,51; test_avatar_self_fact_query.py:18,41,122,159,188,226,248,274,302,325,387,439,463; test_environment_behavior_matrix.py:35; test_interaction_avatar_world.py:19 |

### src/sofia/avatar/wardrobe.py
Imports out: `from __future__ import annotations`; `from dataclasses import dataclass`; `from enum import IntEnum`; `import re`.
Module constants/state: `_ID`, `BILATERAL_SLOT_EXPANSIONS`, `SINGLETON_SLOTS`, `LEAF_SLOTS`, `SLOTS`, `COVERED_DEFAULT`.
| Definition | Decision | Reference candidates |
| --- | --- | --- |
| `normalize_slots` (L54) | KEEP | clothing_action.py:410,426; wardrobe.py:167,175,179,182; wardrobe_matrix.py:113,133 |
| `WardrobeError` (L71) | KEEP | authoring.py:246,250,254,270,305,307; clothing_action.py:432,549,578; wardrobe.py:57,62,93,114,116,119,123,125,127,147,150,155,164,210; wardrobe_catalog.py:553,555,559,561,565,569,571,573,580,582,584,599,642,644,656,660,662,665,671,673,675,677,684,690,694,699,705,728,748,760,762; wardrobe_matrix.py:49,51,110; wardrobe_planner.py:68,74,86,107,109,111,118,125,139,141,146,158,160,162,238,247,249,255,259,265,280,282,284,289,291,293,322,336,338,340,349,353,356,367,369,371,373,375,385; test_avatar_behavior_matrix.py:113; test_avatar_wardrobe_catalog.py:61,91,98,100,102,112; test_avatar_wardrobe_environment_context.py:121; test_avatar_wardrobe_metadata.py:93,117,122,127,132; test_avatar_wardrobe_routine.py:142,144,225,230,236,241,247,254,256,258,273,317 |
| `WardrobeConflict` (L75) | KEEP | clothing_action.py:432,549,578; wardrobe.py:157,170,180,186,210; test_avatar_wardrobe_metadata.py:62,75,87,93,99,102 |
| `VisibilityDenied` (L79) | KEEP | wardrobe.py:205,211,222; test_avatar_piece_catalog.py:84; test_avatar_wardrobe_catalog.py:38; test_avatar_wardrobe_metadata.py:40,48,139,141,156; test_avatar_wardrobe_routine.py:280 |
| `Layer` (L83) | KEEP | wardrobe.py:103,115,165; wardrobe_catalog.py:38,52,67,68,69,70,71,72,73,74,75,76,77,78,79,80,81,82,83,84,89,93,446,470,865,923,927,931,939,946,957,961,967,972,980,984,990,994,1001,1016,1023,1029; wardrobe_matrix.py:22,46,50,84; test_avatar_clothing_action.py:164,168,193,216,217; test_avatar_wardrobe_catalog.py:46,47,120; test_avatar_wardrobe_matrix.py:86; test_avatar_wardrobe_metadata.py:14,25,53,54,55,109; test_avatar_wardrobe_routine.py:19,20,21,22,23,24,25,248,289,297,304 |
| `_identifier` (L91) | KEEP | wardrobe.py:112,129,160 |
| `Garment` (L98) | KEEP | authoring.py:309; wardrobe.py:145,146,158,195; wardrobe_catalog.py:539,552,874; test_avatar_wardrobe_metadata.py:16; test_avatar_wardrobe_routine.py:19,20,21,22,23,24,25,248,286,294,301 |
| `Garment.__post_init__` (L111) | KEEP | Python constructor/dataclass protocol; inspect containing type references |
| `Outfit` (L133) | KEEP | wardrobe.py:153,187,201,204; wardrobe_planner.py:312,342,394; test_avatar_wardrobe_metadata.py:148 |
| `Wardrobe` (L142) | KEEP | presentation.py:194,200,490; presentation_store.py:146; wardrobe_catalog.py:649,655,1043; wardrobe_planner.py:334,335; test_avatar_piece_catalog.py:80; test_avatar_wardrobe_metadata.py:20,45,53,61,67,74,80,98,101,107,128; test_avatar_wardrobe_routine.py:27,308 |
| `Wardrobe.__init__` (L145) | KEEP | Python constructor/dataclass protocol; inspect containing type references |
| `Wardrobe.selection` (L153) | KEEP | authoring.py:247; clothing_action.py:431,546; presentation.py:212,277,526; wardrobe.py:197,209; wardrobe_catalog.py:691; wardrobe_matrix.py:100,131,133,134,135; wardrobe_planner.py:344; test_avatar_behavior_matrix.py:143; test_avatar_lounge_graphic_tee.py:39; test_avatar_piece_catalog.py:81,83,86; test_avatar_seasonal_outfits.py:38; test_avatar_wardrobe_catalog.py:25,27,29,30,36,37,39; test_avatar_wardrobe_matrix.py:74,75,76; test_avatar_wardrobe_metadata.py:32,41,46,56,63,68,76,88,94,100,103,111,138; test_avatar_wardrobe_routine.py:53,250 |
| `Wardrobe.garments` (L195) | KEEP | presentation.py:459; wardrobe.py:146,148,151; wardrobe_matrix.py:106; test_avatar_lounge_graphic_tee.py:44,48,49; test_avatar_wardrobe_catalog.py:45,46,47,48,118,119 |
| `Wardrobe.require_public_ready` (L200) | KEEP | test_avatar_piece_catalog.py:85; test_avatar_wardrobe_catalog.py:39; test_avatar_wardrobe_metadata.py:34,41,49,140,142,157; test_avatar_wardrobe_routine.py:281 |

### src/sofia/avatar/wardrobe_autonomy.py
Imports out: `from __future__ import annotations`; `from dataclasses import dataclass`; `from sofia.cognition.matrix import ContextualInfluencePlan, InfluenceMode, InfluenceSignal, InfluenceSurface`; `from sofia.personality.influence import ContinuityInfluence`; `from .clothing_intent import ClothingActionIntent`; `from .wardrobe_planner import OutfitPlan, WardrobeContext`.
Module constants/state: none.
| Definition | Decision | Reference candidates |
| --- | --- | --- |
| `WardrobeAutonomyDecision` (L19) | KEEP | wardrobe_autonomy.py:86,93,107,198,199; test_avatar_clothing_action.py:278 |
| `WardrobeAutonomyDecision.__post_init__` (L24) | KEEP | Python constructor/dataclass protocol; inspect containing type references |
| `WardrobeAutonomyContext` (L43) | KEEP | bootstrap.py:475,509; clothing_action.py:52; wardrobe_autonomy.py:106; test_avatar_clothing_action.py:76,138 |
| `WardrobeAutonomyContext.__post_init__` (L50) | KEEP | Python constructor/dataclass protocol; inspect containing type references |
| `WardrobeAutonomyPolicy` (L71) | KEEP | clothing_action.py:50,61,80; wardrobe_autonomy.py:109; test_avatar_clothing_action.py:276 |
| `WardrobeAutonomyPolicy.decide` (L80) | KEEP | wardrobe_autonomy.py:109,110,116 |
| `WardrobeAutonomyPolicy.decide_contextual` (L98) | KEEP | clothing_action.py:594 |
| `WardrobeAutonomyPolicy._counter` (L195) | KEEP | wardrobe_autonomy.py:137,150,164,187 |

### src/sofia/avatar/wardrobe_catalog.py
Imports out: `from __future__ import annotations`; `from dataclasses import dataclass`; `from enum import Enum`; `from hashlib import sha256`; `import json`; `import re`; `from .authoring import DEFAULT_FIT_ANCHORS`; `from .wardrobe import Garment, Layer, Wardrobe, WardrobeError`; `from .wardrobe_planner import Activity, OutfitPlan, Preference, PreferenceActor, PreferenceTarget, Season, Sentiment, Weather`.
Module constants/state: `CLOSET_CATEGORIES`, `SPECIAL_PRIVATE_CATEGORIES`, `NORMAL_STYLES`, `PRIVATE_STYLES`, `_PALETTE`, `_NORMAL_STYLE_DETAILS`, `_PRIVATE_STYLE_DETAILS`, `_STYLE_DETAILS`, `_SEASON_INDEX`, `_BIKINI_DESIGNS`, `_HEX`, `_ID`, `DRAFT_STATUS`, `ALL_SEASONS`, `GRAPHIC_TEE_ID`, `GRAPHIC_OUTFIT_ID`, `GRAPHIC_REQUEST_SOURCE_ID`, `SPARKS_LIKED_OUTFIT_SOURCE_IDS`.
| Definition | Decision | Reference candidates |
| --- | --- | --- |
| `ClosetCategory` (L33) | KEEP | wardrobe_catalog.py:66,67,68,69,70,71,72,73,74,75,76,77,78,79,80,81,82,83,84,87,88,92,99,187 |
| `PieceSpec` (L47) | KEEP | wardrobe_catalog.py:192,223,248,250,425,427,438,462,896 |
| `all_closet_categories` (L99) | KEEP | authoring.py:228 |
| `_piece` (L186) | KEEP | wardrobe_catalog.py:253,257,262 |
| `generated_piece_specs` (L248) | KEEP | wardrobe_catalog.py:1039; test_avatar_piece_catalog.py:17 |
| `_shift` (L276) | KEEP | wardrobe_catalog.py:294,295,296,302,320,321,324,328,344,345,346,347 |
| `_n` (L280) | KEEP | wardrobe_catalog.py:293,294,295,296,300,320,321,322,328 |
| `_p` (L284) | KEEP | wardrobe_catalog.py:343,344,345,346,347 |
| `_seasonal_normal` (L288) | KEEP | wardrobe_catalog.py:364 |
| `_seasonal_lounge` (L315) | KEEP | wardrobe_catalog.py:365 |
| `_seasonal_private` (L340) | KEEP | wardrobe_catalog.py:366 |
| `generated_seasonal_outfits` (L360) | KEEP | wardrobe_catalog.py:1082; test_avatar_seasonal_outfits.py:21,204 |
| `generated_bikini_piece_specs` (L425) | KEEP | wardrobe_catalog.py:1040 |
| `generated_bikini_outfits` (L490) | KEEP | wardrobe_catalog.py:1083 |
| `RequestStatus` (L531) | KEEP | wardrobe_catalog.py:634,641,716,718,1086,1088,1091,1096,1101; test_avatar_lounge_graphic_tee.py:67,74; test_avatar_starter_user_preferences.py:16,33,38,64,65; test_avatar_wardrobe_catalog.py:79,83,92 |
| `GarmentBlueprint` (L538) | KEEP | authoring.py:320; wardrobe_catalog.py:650,658,755,872,873,896 |
| `GarmentBlueprint.__post_init__` (L551) | KEEP | Python constructor/dataclass protocol; inspect containing type references |
| `GarmentBlueprint.design_signature` (L602) | KEEP | wardrobe_catalog.py:663,790,823; wardrobe_matrix.py:30,80,125; test_avatar_wardrobe_matrix.py:35,63 |
| `StyleInput` (L631) | KEEP | wardrobe_catalog.py:652,674,1086,1088,1090,1095,1100; test_avatar_wardrobe_catalog.py:92 |
| `StyleInput.__post_init__` (L638) | KEEP | Python constructor/dataclass protocol; inspect containing type references |
| `WardrobePrebuild` (L648) | KEEP | authoring.py:208,215; presentation_runtime.py:20; wardrobe_catalog.py:917,1106; wardrobe_matrix.py:97 |
| `WardrobePrebuild.__post_init__` (L654) | KEEP | Python constructor/dataclass protocol; inspect containing type references |
| `WardrobePrebuild.reviewed_preferences` (L707) | KEEP | bootstrap.py:570; clothing_action.py:106; test_avatar_starter_user_preferences.py:71 |
| `WardrobePrebuild.preset` (L744) | KEEP | clothing_action.py:467,493; test_avatar_authoring.py:136,164,179; test_avatar_behavior_matrix.py:109,141; test_avatar_lounge_graphic_tee.py:22,23,32,33; test_avatar_wardrobe_catalog.py:45,57,62,118; test_avatar_wardrobe_matrix.py:81,113,135 |
| `WardrobePrebuild.pieces` (L750) | KEEP | self_fact_query.py:434,436,437,527,528,535,536; wardrobe_catalog.py:250,252,256,261,265,427,437,461,487,784,785; test_avatar_piece_catalog.py:56,60,74,94; test_avatar_seasonal_outfits.py:48,49; test_avatar_self_fact_query.py:293 |
| `WardrobePrebuild.closet_summary` (L775) | KEEP | test_avatar_piece_catalog.py:34; test_avatar_wardrobe_matrix.py:11 |
| `WardrobePrebuild.manifest` (L813) | KEEP | test_avatar_lounge_graphic_tee.py:102,105,109; test_avatar_piece_catalog.py:104,106; test_avatar_wardrobe_catalog.py:66,67,68,71,72 |
| `_bp` (L864) | KEEP | wardrobe_catalog.py:897,923,927,931,939,946,957,961,967,972,980,984,990,994,1001,1016,1023,1029 |
| `_generated_blueprint` (L896) | KEEP | wardrobe_catalog.py:1037 |
| `build_starter_wardrobe` (L917) | KEEP | presentation_runtime.py:177; test_avatar_authoring.py:100,108,175; test_avatar_behavior_matrix.py:24,107,127; test_avatar_clothing_action.py:39; test_avatar_lounge_graphic_tee.py:21,31,43,60,89,102; test_avatar_piece_catalog.py:33,55,73,92,104; test_avatar_presentation.py:19,179,217,261; test_avatar_presentation_routine.py:25; test_avatar_presentation_runtime.py:32,71,118; test_avatar_presentation_store.py:20; test_avatar_seasonal_outfits.py:31,47,57,79,95,112,152; test_avatar_self_fact_query.py:23,273,292,330; test_avatar_starter_user_preferences.py:12,29,58,70; test_avatar_wardrobe_catalog.py:15,34,44,53,62,66,76,97,107,117,124; test_avatar_wardrobe_matrix.py:10,25,39,80,112,134,158; test_environment_behavior_matrix.py:99 |

### src/sofia/avatar/wardrobe_matrix.py
Imports out: `from __future__ import annotations`; `from dataclasses import dataclass`; `from typing import TYPE_CHECKING`; `from .wardrobe import LEAF_SLOTS, Layer, WardrobeError, normalize_slots`; `from .wardrobe_catalog import WardrobePrebuild`; `from .wardrobe_catalog import WardrobePrebuild`.
Module constants/state: none.
| Definition | Decision | Reference candidates |
| --- | --- | --- |
| `WardrobeMatrixCell` (L20) | KEEP | wardrobe_matrix.py:37,47,105,115 |
| `WardrobeSlotMatrix` (L35) | KEEP | presentation_runtime.py:22,30; self_fact_query.py:307,329,343; wardrobe_matrix.py:93,130 |
| `WardrobeSlotMatrix.cell` (L42) | KEEP | self_fact_query.py:315,316,318,319; wardrobe_matrix.py:54,55,56,64,65,71,73,74,75,76,77,78,79,80,81; test_avatar_clothing_action.py:164,168,191,216,217 |
| `WardrobeSlotMatrix.as_dict` (L61) | KEEP | test_avatar_wardrobe_matrix.py:83,115,137; test_ui_application.py:143 |
| `build_wardrobe_matrix` (L90) | KEEP | presentation_runtime.py:28; test_avatar_self_fact_query.py:278,300,329; test_avatar_wardrobe_matrix.py:82,114,136 |

### src/sofia/avatar/wardrobe_planner.py
Imports out: `from __future__ import annotations`; `from dataclasses import dataclass`; `from datetime import datetime, timedelta, timezone`; `from enum import Enum, IntEnum`; `from sofia.environment.model import EnvironmentFreshness, EnvironmentSnapshot, Season`; `from sofia.personality.influence import ContinuityInfluence`; `from .wardrobe import Wardrobe, WardrobeError, Outfit`.
Module constants/state: none.
| Definition | Decision | Reference candidates |
| --- | --- | --- |
| `Activity` (L23) | KEEP | bootstrap.py:503,563; authoring.py:236; wardrobe_catalog.py:308,332,352,500,501,1051,1056,1062,1067,1077; wardrobe_planner.py:132,138,153,159,218,226,242; test_avatar_authoring.py:141,165,180; test_avatar_behavior_matrix.py:48,59,71,80,89,95,118,135; test_avatar_clothing_action.py:126; test_avatar_lounge_graphic_tee.py:94; test_avatar_presentation_routine.py:49,91,104,137; test_avatar_seasonal_outfits.py:69,85,172; test_avatar_wardrobe_environment_context.py:73,87,112,126; test_avatar_wardrobe_routine.py:33,34,35,39,66,76,82,110,119,124,153,158,164,173,179,184,189,196,204,218,219,224,231,237,312; test_environment_behavior_matrix.py:144,177,325 |
| `Weather` (L32) | KEEP | wardrobe_catalog.py:504,1058; wardrobe_planner.py:80,85,184,189,191,193,209,228,244; test_avatar_behavior_matrix.py:55,67; test_avatar_clothing_action.py:73,332,406; test_avatar_wardrobe_environment_context.py:78,81,96,97,98,99; test_avatar_wardrobe_routine.py:34,35,75,81,88,197,242 |
| `Cadence` (L39) | KEEP | presentation_routine.py:139; wardrobe_planner.py:319,321,323,325,362,366; test_avatar_wardrobe_routine.py:204,208,214 |
| `PreferenceActor` (L45) | KEEP | wardrobe_catalog.py:734; wardrobe_planner.py:271,279,421; test_avatar_wardrobe_routine.py:150,151,157,163,170,171,178,255,257,260,261 |
| `PreferenceTarget` (L50) | KEEP | wardrobe_catalog.py:724,726; wardrobe_planner.py:272,279,288,290,292,414,415,416; test_avatar_wardrobe_routine.py:150,151,157,163,170,171,178,255,257,260,261 |
| `Sentiment` (L56) | KEEP | wardrobe_catalog.py:717,719; wardrobe_planner.py:274,281; test_avatar_wardrobe_routine.py:150,151,157,163,170,171,178,255,257,260,261 |
| `_id` (L64) | KEEP | presentation.py:154,209,220,270,305,420,512,559,599,608; wardrobe_planner.py:88,236,240,286,287,304,306 |
| `_aware` (L72) | KEEP | wardrobe_planner.py:87,137,305,320 |
| `WeatherObservation` (L79) | KEEP | wardrobe_planner.py:133,140,194; test_avatar_behavior_matrix.py:54,66; test_avatar_clothing_action.py:130; test_avatar_wardrobe_environment_context.py:51; test_avatar_wardrobe_routine.py:75,81,88,197,242; test_environment_behavior_matrix.py:44,62,292; test_ui_theme.py:48 |
| `WeatherObservation.__post_init__` (L84) | KEEP | Python constructor/dataclass protocol; inspect containing type references |
| `EmotionStyleInfluence` (L92) | KEEP | wardrobe_planner.py:134,144,154,459,483; test_avatar_clothing_action.py:116; test_avatar_presentation_routine.py:106; test_avatar_wardrobe_routine.py:95,106,128,143,145 |
| `EmotionStyleInfluence.__post_init__` (L105) | KEEP | Python constructor/dataclass protocol; inspect containing type references |
| `WardrobeContext` (L129) | KEEP | bootstrap.py:501,561; presentation_routine.py:134; wardrobe_autonomy.py:48,64; wardrobe_planner.py:360,366; test_avatar_behavior_matrix.py:48,58,70,80,88,94,115,132; test_avatar_clothing_action.py:123; test_avatar_lounge_graphic_tee.py:91; test_avatar_presentation_routine.py:46,88,101,134; test_avatar_wardrobe_environment_context.py:71,85,107,124; test_avatar_wardrobe_routine.py:41,237; test_environment_behavior_matrix.py:142,175,323 |
| `WardrobeContext.__post_init__` (L136) | KEEP | Python constructor/dataclass protocol; inspect containing type references |
| `WardrobeContext.from_environment_snapshot` (L149) | KEEP | bootstrap.py:501,561; test_avatar_wardrobe_environment_context.py:71,85,107,124; test_environment_behavior_matrix.py:142,175,323 |
| `WardrobeContext.effective_weather` (L209) | KEEP | wardrobe_autonomy.py:147,148; wardrobe_planner.py:392; test_avatar_wardrobe_environment_context.py:81,90; test_avatar_wardrobe_routine.py:89,243 |
| `WardrobeContext.lounge_window` (L216) | KEEP | wardrobe_autonomy.py:159; wardrobe_planner.py:404,406,408,445,449 |
| `OutfitPlan` (L223) | KEEP | authoring.py:244,257; clothing_action.py:469; wardrobe_autonomy.py:104,105,197; wardrobe_catalog.py:288,305,315,329,340,349,360,361,490,493,651,669,744,1046,1053,1060,1065,1075; wardrobe_planner.py:334,337,342,394; test_avatar_wardrobe_routine.py:33,34,35,117,122,218,224,309 |
| `OutfitPlan.__post_init__` (L235) | KEEP | Python constructor/dataclass protocol; inspect containing type references |
| `Preference` (L269) | KEEP | presentation_routine.py:137; wardrobe_catalog.py:707,714,733; wardrobe_planner.py:363,368; test_avatar_wardrobe_routine.py:45,171,255,257 |
| `Preference.__post_init__` (L278) | KEEP | Python constructor/dataclass protocol; inspect containing type references |
| `WornEvidence` (L297) | KEEP | presentation_routine.py:138; wardrobe_planner.py:364,370; test_avatar_wardrobe_routine.py:49 |
| `WornEvidence.__post_init__` (L303) | KEEP | Python constructor/dataclass protocol; inspect containing type references |
| `OutfitProposal` (L310) | KEEP | presentation_routine.py:28; wardrobe_planner.py:365,447,454 |
| `period_key` (L319) | KEEP | wardrobe_planner.py:313,376,438; test_avatar_wardrobe_routine.py:210,214 |
| `OutfitPlanner` (L331) | KEEP | bootstrap.py:754; clothing_action.py:101; presentation_routine.py:39,45; test_avatar_behavior_matrix.py:25,111,128; test_avatar_lounge_graphic_tee.py:90; test_avatar_presentation_routine.py:40; test_avatar_wardrobe_routine.py:59,66,70,76,82,98,109,131,153,158,164,173,179,184,189,195,204,219,226,231,259,266,274,278,318; test_environment_behavior_matrix.py:147 |
| `OutfitPlanner.__init__` (L334) | KEEP | Python constructor/dataclass protocol; inspect containing type references |
| `OutfitPlanner.suggest` (L358) | KEEP | clothing_action.py:574; presentation_routine.py:151; test_avatar_behavior_matrix.py:47,57,69,79,87,93,114,128; test_avatar_lounge_graphic_tee.py:97; test_avatar_wardrobe_routine.py:59,66,70,76,82,98,109,131,153,158,164,173,179,184,189,195,204,219,231,259,266,274,278; test_environment_behavior_matrix.py:147 |
| `wardrobe_emotion_influences` (L457) | KEEP | bootstrap.py:504,559; test_avatar_behavior_matrix.py:86,119,136; test_environment_behavior_matrix.py:145 |

## Nested functions and class fields
Nested mutation callbacks belong to their containing host operation and are passed to `PresentationStore.persist_mutation`; nested planner scoring is called by `suggest`. Fields below are enum members, dataclass schema fields, or class policy constants, rather than additional state stores.

src/sofia/avatar/authoring.py

- `BodyRegion`: `HEAD`, `FACE`, `NECK`, `CHEST`, `ABDOMEN`, `BACK`, `PELVIS`, `BUTTOCKS`, `PERINEUM`, `LEFT_SHOULDER`, `RIGHT_SHOULDER`, `LEFT_UPPER_ARM`, `RIGHT_UPPER_ARM`, `LEFT_FOREARM`, `RIGHT_FOREARM`, `LEFT_WRIST`, `RIGHT_WRIST`, `LEFT_HAND`, `RIGHT_HAND`, `LEFT_THIGH`, `RIGHT_THIGH`, `LEFT_CALF`, `RIGHT_CALF`, `LEFT_ANKLE`, `RIGHT_ANKLE`, `LEFT_FOOT`, `RIGHT_FOOT`, `LEFT_FOX_EAR`, `RIGHT_FOX_EAR`, `TAIL_ROOT`, `TAIL_SHAFT`, `TAIL_TIP`
- `AuthoringLandmark`: `LEFT_NIPPLE`, `RIGHT_NIPPLE`, `VULVA`, `ANUS`, `TAIL_ROOT`
- `FitAnchor`: `name`, `region`, `slot`
- `BodyAuthoringContract`: `canonical_avatar_sha256`, `revision`, `adult_female_character`, `landmarks`, `anchors`, `normal_display_clothed`, `unclothed_authoring_only`
- `GarmentDesignRequest`: `item_id`, `name`, `category_id`, `primary_hex`, `material`, `style_tags`, `private_only`
- Nested function `WardrobeStudio.compose.mutate` (L274), DELETE with its unwired parent

src/sofia/avatar/clothing_action.py

- Nested function `ClothingActionService._commit_nude.mutate` (L240), KEEP
- Nested function `ClothingActionService._commit_candidate.mutate` (L635), KEEP

src/sofia/avatar/clothing_intent.py

- `ClothingActionKind`: `WEAR`, `ADD`, `REMOVE`, `SWAP`, `UNDRESS`
- `ClothingActionIntent`: `kind`, `target`, `hypothetical`
- `ClothingActionParser`: `_FOLLOW`, `_IF_ASKED`, `_QUESTION`, `_UNDRESS`, `_REMOVE_A`, `_REMOVE_B`, `_SWAP`, `_CHANGE_OUTFIT`, `_WEAR`, `_ADD`

src/sofia/avatar/matrix.py

- `AvatarMatrixEvaluator`: `domain`

src/sofia/avatar/presentation.py

- `AudienceScope`: `PUBLIC`, `PRIVATE`
- `AttireMode`: `CLOTHED`, `NUDE`
- `PrivatePresentationGrant`: `adult_verified`, `owner_verified`, `private_session`, `explicit_current_opt_in`, `external_stop_active`
- `AppearanceState`: `hairstyle`, `hair_color`, `tail_color`, `style_tags`
- `PresentationState`: `revision`, `attire`, `outfit_id`, `item_ids`, `appearance`, `private_only`, `reason`
- `PresentationChange`: `operation_id`, `expected_revision`, `attire`, `outfit_id`, `item_ids`, `appearance`, `private_only`, `daily`, `reason`
- `PresentationProjection`: `audience`, `source_revision`, `attire`, `outfit_id`, `item_ids`, `appearance`, `private_fallback_used`, `reason`, `item_names`
- `PresentationAuthority`: `SCHEMA`

src/sofia/avatar/presentation_routine.py

- `PresentationRoutineResult`: `changed`, `deferred_private`, `proposal`, `state`, `reason`
- Nested function `HeadlessPresentationRoutine.evaluate_daypart_fallback.mutate` (L103), KEEP
- Nested function `HeadlessPresentationRoutine.evaluate.mutate` (L166), KEEP

src/sofia/avatar/presentation_runtime.py

- `PresentationRuntimeBundle`: `authority`, `store`, `catalog`

src/sofia/avatar/presentation_store.py

- `PresentationStore`: `_KEY`, `_SCHEMA`

src/sofia/avatar/self_fact_query.py

- `AvatarSelfFactAnswer`: `recognized`, `content`
- `AvatarSelfFactResolver`: `_UNDERGARMENT_TERM_RE`, `_UNDERGARMENT_FACT_CUE_RE`, `_CURRENT_OUTFIT_STATE_FOLLOWUP_RE`, `_DAYPART_OUTFIT_REASON`, `_PRESENTATION_REASON_RE`, `_UNDERGARMENT_PRESENTATION_FORMS`, `_CURRENT_OUTFIT_FORMS`, `_PUBLIC_PRESENTATION_FORMS`, `_HAIR_COLOR_FORMS`, `_TAIL_COLOR_FORMS`, `_CURRENT_LOOK_FORMS`, `_BODY_DESCRIPTION_FORMS`, `_FORM_OR_AVATAR_FORMS`, `_TONIGHT_OUTFIT_FORMS`

src/sofia/avatar/wardrobe.py

- `Layer`: `UNDERWEAR`, `BASE`, `MID`, `OUTER`, `ACCESSORY`
- `Garment`: `item_id`, `name`, `layer`, `slots`, `coverage`, `tail_clearance`, `ear_clearance`, `asset_ref`, `private_only`
- `Outfit`: `item_ids`, `coverage`, `covered_default`, `asset_refs_present`, `private_only`

src/sofia/avatar/wardrobe_autonomy.py

- `WardrobeAutonomyDecision`: `accepted`, `reason`, `alternative_outfit_id`
- `WardrobeAutonomyContext`: `continuity`, `influence_plan`, `wardrobe_context`

src/sofia/avatar/wardrobe_catalog.py

- `ClosetCategory`: `category_id`, `label`, `noun`, `private_noun`, `layer`, `slots`, `coverage`, `fit_anchors`, `tail_clearance`, `ear_clearance`
- `PieceSpec`: `item_id`, `name`, `description`, `category`, `layer`, `slots`, `coverage`, `primary_hex`, `accent_hexes`, `material`, `construction`, `fit_anchors`, `style_tags`, `private_only`, `tail_clearance`, `ear_clearance`
- `RequestStatus`: `USER_REQUESTED`, `USER_LIKED`, `USER_DISLIKED`
- `GarmentBlueprint`: `garment`, `primary_hex`, `accent_hexes`, `material`, `construction`, `fit_anchors`, `provenance`, `category`, `style_tags`, `private_only`, `description`
- `StyleInput`: `subject_id`, `status`, `source_id`, `detail`
- `WardrobePrebuild`: `wardrobe`, `blueprints`, `presets`, `inputs`

src/sofia/avatar/wardrobe_matrix.py

- `WardrobeMatrixCell`: `slot`, `layer`, `garment_id`, `name`, `description`, `category`, `primary_hex`, `accent_hexes`, `style_tags`, `design_signature`, `private_only`
- `WardrobeSlotMatrix`: `item_ids`, `cells`, `coverage`, `covered_default`, `private_only`

src/sofia/avatar/wardrobe_planner.py

- `Activity`: `CONVERSATION`, `ENGINEERING`, `LAB`, `RELAXING`, `SLEEP`, `FORMAL`
- `Weather`: `HOT`, `COLD`, `WET`, `MILD`
- `Cadence`: `DAILY`, `WEEKLY`, `MONTHLY`
- `PreferenceActor`: `SPARKS`, `SOFIA`
- `PreferenceTarget`: `OUTFIT`, `ITEM`, `COMBINATION`
- `Sentiment`: `HATE`, `DISLIKE`, `LIKE`, `LOVE`
- `WeatherObservation`: `condition`, `observed_at`, `source_id`
- `EmotionStyleInfluence`: `emotion`, `intensity`, `style_tags`, `evidence_refs`
- `WardrobeContext`: `now`, `season`, `activity`, `weather`, `emotion_influences`
- `OutfitPlan`: `outfit_id`, `item_ids`, `activities`, `seasons`, `weather`, `lounge`, `private_only`, `style_tags`, `display_name`, `manual_only`
- `Preference`: `actor`, `target`, `ids`, `sentiment`, `source_id`, `reviewed`
- `WornEvidence`: `outfit_id`, `occurred_at`, `renderer_receipt_id`
- `OutfitProposal`: `outfit_id`, `outfit`, `period_key`, `reasons`, `requires_renderer_verification`
- Nested function `OutfitPlanner.suggest.score` (L394), KEEP
