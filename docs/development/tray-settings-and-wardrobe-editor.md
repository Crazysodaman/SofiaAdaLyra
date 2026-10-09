# Tray settings, wardrobe editing and emotion display

The tray settings window uses the selected canonical database across child
processes, Windows startup registration and application restarts. Settings pages
have a sidebar and scrolling content. All persisted runtime preferences have
controls; the schema version is migration metadata.

## Settings and state ownership

| Page | Working controls | Persistence and consumer |
|---|---|---|
| General | Windows startup; keep tray running when chat closes | `ui_control_settings`; Windows Run registration and desktop/tray lifecycle |
| Sofía | Idle reflection; habit learning; automatic-or-ask update restart policy; identity/personality inspection | `ui_runtime_settings`; application startup, stable service host and background coordinator; protected definitions remain with their existing owners |
| Chat | Adaptive theme; canonical storage inspection | `ui_runtime_settings`; desktop theme toggle also saves directly |
| ACT | Delivery enabled by default, desktop/Discord/Home Assistant channel, mute, notification service, explicit local quiet-hours selectors/timezone, intervals and category quotas | `ui_runtime_settings`; ACT policy and operational notice destination |
| Fleet | Cognitive placement, fallback, resource limits, host lists, discovery controls, agent provisioning settings and enrolled-node inspection | Existing discovery preferences plus typed cognition/bootstrap preferences; production configuration and reviewed Fleet workflows |
| Workloads | Game mode and service names | `ui_control_settings` and `ops_activity_override`; tray and service controller |
| Models | Models, context sizes, thinking, routing, verification, four-mode resource-aware residency management, installation, idle timeout, keep-alive, temperature, seed and maximum output tokens | `ui_runtime_settings`; provider, routing and model lifecycle configuration |
| Integrations | Discord IDs/token and Home Assistant URL/token/entity selection | Nonsecret preferences in SQLite; tokens remain protected by Windows DPAPI |
| Environment | Location, timezone, coordinates, subjects, NWS station/user agent and freshness intervals | Existing environment preferences and hot reload |
| Avatar | Automatic routines; approved public daily outfit; current presentation and presets | Owner preferences plus canonical `avatar_presentation_state` |
| Wardrobe | Searchable item/outfit list; full structured item editor; outfit editor with garment chooser; submit, inspect, retry and answer review questions | `avatar_wardrobe_reviews`; validated catalog overlay and live application bundle refresh |
| Mood & Emotion | Current tone, active emotions, intensities, evidence and timestamps; automatic refresh | Existing emotional journal and scoped current-state projection |
| Memory | Inspect owner candidates and exact originals; promote, reject or revoke after explicit confirmation | Existing durable memory candidate lifecycle; conversation originals are retained |
| EVOLVE | Inspect reviewed revisions and configuration authority records | Existing reviewed revision and state-plane records; governed edits retain the existing approval workflow |
| Safety & Authority | Inspect stop state; pause/resume actions with reason and confirmation; inspect standing capabilities | Existing operator stop owner and execution checks |
| Permissions | Existing standing grants, revocation, private/adult authority and Fleet candidate workflows | Latest upstream permission engine and its confirmations retained |
| Advanced | Database integrity/table diagnostics; inspect/export saved preferences | Canonical database; exports exclude protected token values |

Environment preferences refresh on subsequent turns. Tray game mode, service
settings and model policies reload through their existing consumers. Model,
integration, reflection and habit preferences can require an application
restart. Process-level model overrides retain their existing explicit precedence.
Fleet provisioning settings select policy inputs; they do not grant permission
to enroll a host or execute a deployment.

Idle reflection and proactive outreach default to enabled. An explicit saved or
environment opt-out still wins. Desktop delivery is the default and persists a
native tray notification without requiring Home Assistant. Home Assistant
delivery remains optional and fails closed unless its URL, protected token and
notification service are complete. Discord delivery uses only the enabled,
verified and active Sparks DM binding and rechecks that binding immediately
before each send.

## Save and restart behavior

Desktop preferences, runtime preferences and the game-mode override commit in
one SQLite transaction. Invalid values and missing integration credentials are
rejected before mutation. Protected-token changes are compensated if a settings
transaction fails. Windows registry registration runs after persistence: a
registration failure reports a warning and permits retry without discarding the
saved profile. The Run-key path uses the correct registry separators.

Tray, settings and desktop launches carry `--state-path`, including the Windows
startup command. Existing settings windows accept section-navigation requests
from the tray. Closing chat can request tray exit after desktop shutdown; it
does not stop the independently managed runtime or LLM services.

Runtime schema 6 adds the delivery-channel and update-restart preferences while
retaining schema 5 values. Existing Home Assistant outreach profiles migrate to
the same channel; profiles without a transport migrate to desktop delivery.

## Wardrobe review

Creating or editing metadata submits an immutable proposal, not an approval.
Submission validates garment fields, material/environment/context/comfort
profiles, outfit layering, public coverage and private metadata against the
current catalog. All fields are editable through structured controls.

The running application's background coordinator claims pending reviews. The
garment review uses the existing `GeneratedGarmentDecisionService` request and
decision parser. Outfit review uses the same `accept`, `reject`, `ask_sparks`
decision vocabulary. Requests disable tools and treat design content as
untrusted data. Sofía can request preference input and can still reject the
design after receiving it. Invalid responses or provider failures remain
`review_failed`, with a visible reason and a retry control.

Claims are exclusive and leased; a crashed worker can be recovered. Approval
checks the original target digest to prevent a stale edit replacing a newer
decision. It also verifies the current presentation can still be restored.
Accepted editor changes are stored as an overlay over the packaged and existing
generated-owned catalog; those original sources are preserved. The application's
existing bundle installer refreshes live wardrobe, clothing actions, matrix
projection and routine planning. Restart rebuilds the same accepted catalog.
No asset-generation or current-wearing claim is implied by accepting metadata.

Empty queues skip background budget claims. Operator stop prevents reviews from
starting. Mood display reads Sparks' exact relationship scope, preserving other
principals' and audience-private emotional data.

## File review

| File | Action | Reason |
|---|---|---|
| `ui/settings_window.py` | UPDATE | Sidebar, scrolling, complete settings sections and durable save orchestration; upstream permission/discovery controls retained. |
| `ui/settings_sections.py` | ADD | Typed preference forms and functioning state/review panels for the former placeholder pages. |
| `ui/settings_service.py` | ADD | Transactional settings save, secret compensation, startup reconciliation and bounded diagnostics. |
| `ui/wardrobe_panel.py` | ADD | Item/outfit browser, structured editor, review queue and scoped mood projection. |
| `ui/control_center.py` | UPDATE | Wardrobe/mood commands and consumed navigation/exit requests; transactional desktop-settings write. |
| `ui/tray_agent.py` | UPDATE | Opens the requested section, preserves database selection and handles chat-requested tray exit. |
| `ui/windows_tray.py` | UPDATE | Native menu dispatch for Wardrobe and Mood & Emotion. |
| `ui/tray_launcher.py` | UPDATE | Passes the selected database to the detached tray process. |
| `ui/windows_startup.py` | UPDATE | Correct Run-key path and database-specific startup command. |
| `ui/desktop.py` | UPDATE | Persists theme selection and honors keep-tray preference on clean shutdown. |
| `config/user_settings.py` | UPDATE | Schema 5 preferences, typed validation and preserved schema 4 discovery migration. |
| `config/model_catalog.py` | UPDATE | Keeps the existing 768-token production default canonical while making the output budget editable. |
| `config/defaults.py` | UPDATE | Projects saved generation, Fleet cognition and bootstrap settings into production configuration. |
| `ops/activity.py` | UPDATE | Allows activity override to participate in the canonical settings transaction. |
| `avatar/wardrobe_review.py` | ADD | Durable submissions, validated overlays, leased claims, stale-edit checks and Sofía decision processing. |
| `avatar/presentation_runtime.py` | UPDATE | Loads accepted editor overlays and restores the owner's selected daily outfit. |
| `application/bootstrap.py` | UPDATE | Applies reflection/habit/routine preferences and retains explicit outreach timezone selection. |
| `application/background.py` | UPDATE | Optional readiness predicate avoids spending budget on empty queues. |
| `application/background_runtime.py` | UPDATE | Connects wardrobe reviews to live cognition and the existing avatar bundle installer. |
| `application/act_service.py` | UPDATE | Loads saved delivery policy, protected credentials and notification destination. |
| `application/fleet_runtime.py` | UPDATE | Uses the saved notification destination for operational notices. |
| `test_default_configuration.py` | UPDATE | Checks the retained production output budget alongside the default provider configuration. |
| `test_ui_settings_persistence.py` | ADD | Fresh-process persistence, production projection, transaction failure, protected secret rollback and outreach wiring. |
| `test_ui_settings_window.py` | ADD | Actual Tk save/reopen/editor interactions and emotion scope isolation. |
| `test_ui_wardrobe_runtime.py` | ADD | Accepted metadata reaches live application and survives restart without changing attire. |
| `test_avatar_wardrobe_review.py` | ADD | Acceptance, rejection, questions, invalid replies, stale edits, crash recovery and operator stop. |
| `test_application_background.py` | UPDATE | Empty readiness does not consume global background budget. |
| `test_ui_application.py` | UPDATE | Checks the current wardrobe preview and unchanged presentation rather than retired response wording. |
| `test_ui_tray_launcher.py` | UPDATE | Verifies the explicit database in the detached launch command. |
| `test_ui_tray_shutdown.py` | UPDATE | Exercises the argument-aware tray entry point. |
| `test_ui_windows_startup.py` | UPDATE | Verifies the registry path and selected database in startup registration. |

## Validation

Real Tk interaction tests run under Xvfb in the cloud environment. Native Windows
menu wiring and registry calls are covered by the existing platform-safe tests
and mocked registration tests; a live Windows notification-area smoke test is
still platform-dependent. The cloud does not have a local Ollama server.

The targeted runtime, persistence, real Tk, background and Windows-startup
checks passed: **42 passed**. Compilation and dependency checks also passed.

The full work-branch suite produced **3,443 passed, 20 failed, 2 skipped**.
A separate, untouched checkout of upstream main at `5649aa7b` produced
**3,413 passed, 21 failed, 2 skipped** under the same environment. All 20 work
failures also occur on upstream; there are no failures unique to these changes.
The additional upstream default-configuration failure is repaired by retaining
and asserting its existing 768-token output budget.

Shared failures cover conversation/matrix regressions, idle-reflection fixture
wiring, state-replication tests, and live-provider/embodiment checks. The latter
require a local Ollama server, which is absent in this cloud. These unrelated
upstream failures remain visible rather than being skipped or weakened.

The main feature checkpoint is `b5b39416`; upstream synchronization is recorded
in merge `bf6c990c`. The final settings/report follow-up is committed before
publishing the completed work branch and merging it to main.

The final pull incorporated upstream `e4659dee` (migration approval hardening
and matrix assertion updates), merged as `5d43b1be`. Its affected migration and
conversation tests produced **29 passed, 5 failed**; all five failures belong
to the already reproduced upstream conversation failures listed above. The two
updated matrix assertions now pass. Feature follow-up commit: `37b62835`.
